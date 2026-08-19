"""Disease Biology Division: Disease Agent + Phenotype Agent, via the Monarch
Initiative's public API (cross-species disease/phenotype knowledge graph)."""
import httpx
from sqlalchemy import select

from app.agents.base import agent_run, with_session
from app.config import get_settings
from app.models import Gene

NAME = "disease_phenotype"


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            genes = db.scalars(select(Gene).where(Gene.in_top3.is_(True))).all()
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for gene in genes:
                    entry = {"gene": gene.symbol}
                    try:
                        resp = client.get(
                            "https://api-v3.monarchinitiative.org/v3/api/search",
                            params={"q": gene.symbol, "category": "biolink:Gene", "limit": 1},
                        )
                        if resp.status_code == 200:
                            items = resp.json().get("items", [])
                            entry["monarch_hit"] = items[0].get("name") if items else None
                            entry["monarch_id"] = items[0].get("id") if items else None
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"genes": findings}
            result["summary"] = f"Queried Monarch Initiative disease/phenotype graph for {len(findings)} genes."
    finally:
        db.close()
