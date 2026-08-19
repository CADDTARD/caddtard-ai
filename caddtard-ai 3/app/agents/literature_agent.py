"""Literature surveillance agent - live PubMed hit counts per top-3 gene via
NCBI E-utilities."""
import httpx
from sqlalchemy import select

from app.agents.base import agent_run, with_session
from app.config import get_settings
from app.models import Gene

NAME = "literature"


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            genes = db.scalars(select(Gene).where(Gene.in_top3.is_(True))).all()
            counts = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for gene in genes:
                    entry = {"gene": gene.symbol}
                    try:
                        resp = client.get(
                            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                            params={
                                "db": "pubmed",
                                "retmode": "json",
                                "term": f'{gene.symbol} AND (V-ATPase OR "vacuolar ATPase")',
                            },
                        )
                        if resp.status_code == 200:
                            entry["pubmed_hits"] = int(resp.json()["esearchresult"]["count"])
                        else:
                            entry["http_status"] = resp.status_code
                    except (httpx.HTTPError, KeyError, ValueError) as exc:
                        entry["error"] = str(exc)
                    counts.append(entry)

            result["detail"] = {"counts": counts}
            total = sum(c.get("pubmed_hits", 0) for c in counts)
            result["summary"] = f"{total} total PubMed hits across {len(counts)} top-3 genes."
    finally:
        db.close()
