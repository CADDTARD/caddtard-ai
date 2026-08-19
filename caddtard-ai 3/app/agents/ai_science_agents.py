"""AI Science Division: Structure Prediction Agent, via the public AlphaFold DB
API. Complements the v1 Structural Biology agent (experimental cryo-EM
structures from RCSB) with predicted per-chain models for each top-3 gene's
protein product."""
import httpx
from sqlalchemy import select

from app.agents.base import agent_run, with_session
from app.config import get_settings
from app.models import Gene

NAME = "structure_prediction"


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            genes = db.scalars(select(Gene).where(Gene.in_top3.is_(True))).all()
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for gene in genes:
                    entry = {"gene": gene.symbol, "uniprot": gene.uniprot_accession}
                    try:
                        resp = client.get(f"https://alphafold.ebi.ac.uk/api/prediction/{gene.uniprot_accession}")
                        if resp.status_code == 200:
                            data = resp.json()
                            if data:
                                entry["model_created"] = data[0].get("modelCreatedDate")
                                entry["confidence_version"] = data[0].get("latestVersion")
                                entry["pdb_url"] = data[0].get("pdbUrl")
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"genes": findings}
            result["summary"] = f"Fetched AlphaFold predicted structures for {len(findings)} genes."
    finally:
        db.close()
