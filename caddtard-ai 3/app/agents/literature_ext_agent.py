"""Evidence & Infrastructure Division: Europe PMC Literature Agent.
Complements the existing PubMed/NCBI E-utilities literature agent with Europe
PMC's REST API (EBI), which additionally indexes preprints (bioRxiv/medRxiv),
grants links, and full-text-available flags that PubMed's own API does not
surface directly - relevant for catching very recent NTD preprints before
they're indexed in MEDLINE. Public, unauthenticated, real-time."""
import httpx

from app.agents.base import agent_run, with_session
from app.agents.portfolio import ALL_DISEASE_TERMS
from app.config import get_settings

NAME = "europepmc_literature"


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for term in ALL_DISEASE_TERMS:
                    entry = {"term": term}
                    try:
                        resp = client.get(
                            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                            params={"query": term, "format": "json", "pageSize": 5, "sort": "P_PDATE_D desc"},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            result_list = (data.get("resultList") or {}).get("result", [])
                            entry["hit_count"] = (data.get("hitCount"))
                            entry["most_recent"] = (
                                {
                                    "title": result_list[0].get("title"),
                                    "pubYear": result_list[0].get("pubYear"),
                                    "source": result_list[0].get("source"),
                                    "id": result_list[0].get("id"),
                                }
                                if result_list
                                else None
                            )
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"searches": findings}
            result["summary"] = f"Queried Europe PMC for {len(findings)} portfolio disease terms."
    finally:
        db.close()
