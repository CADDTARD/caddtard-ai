"""Therapeutics Division: Small Molecule Agent, via the public ChEMBL REST API.
Looks up known bioactive compounds annotated against each top-3 target where a
ChEMBL target mapping exists (V-ATPase subunit small-molecule pharmacology is
sparse - bafilomycin/concanamycin-class inhibitors are the best-known chemical
matter for the complex as a whole, not gene-specific)."""
import httpx

from app.agents.base import agent_run, with_session

NAME = "small_molecule"

# ChEMBL molecule search terms relevant to V-ATPase pharmacology; this is a
# pathway-level agent (the complex, not a single top-3 gene) since that is
# where the actual chemical matter in ChEMBL is annotated.
SEARCH_TERMS = ["bafilomycin", "concanamycin", "vacuolar ATPase"]


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    from app.config import get_settings

    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for term in SEARCH_TERMS:
                    entry = {"term": term}
                    try:
                        resp = client.get(
                            "https://www.ebi.ac.uk/chembl/api/data/molecule/search",
                            params={"q": term, "format": "json"},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            mols = data.get("molecules", [])
                            entry["hit_count"] = len(mols)
                            entry["first_chembl_id"] = mols[0].get("molecule_chembl_id") if mols else None
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"searches": findings}
            result["summary"] = f"Queried ChEMBL for {len(findings)} V-ATPase-relevant chemical matter terms."
    finally:
        db.close()
