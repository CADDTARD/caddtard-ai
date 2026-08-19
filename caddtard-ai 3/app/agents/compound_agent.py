"""Therapeutics Division: Compound Properties Agent, via the PubChem PUG REST
API (pubchem.ncbi.nlm.nih.gov, public, unauthenticated, NIH-operated). Live
molecular formula/weight/canonical SMILES for each repurposing candidate -
the ground-truth chemistry record a medicinal chemist would actually pull
before starting analog work, not a copied value."""
import httpx

from app.agents.base import agent_run, with_session
from app.agents.portfolio import COMPOUND_TERMS
from app.config import get_settings

NAME = "compound_properties"


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for term in COMPOUND_TERMS:
                    entry = {"compound": term}
                    try:
                        resp = client.get(
                            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{term}/property/"
                            "MolecularFormula,MolecularWeight,CanonicalSMILES/JSON"
                        )
                        if resp.status_code == 200:
                            props = resp.json().get("PropertyTable", {}).get("Properties", [])
                            if props:
                                p = props[0]
                                entry["cid"] = p.get("CID")
                                entry["molecular_formula"] = p.get("MolecularFormula")
                                entry["molecular_weight"] = p.get("MolecularWeight")
                                entry["canonical_smiles"] = p.get("CanonicalSMILES")
                        elif resp.status_code == 404:
                            entry["found"] = False
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"searches": findings}
            result["summary"] = f"Pulled live PubChem chemistry records for {len(findings)} portfolio compounds."
    finally:
        db.close()
