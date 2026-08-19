"""Gene ontology agent - live term definitions via EBI QuickGO."""
import httpx

from app.agents.base import agent_run, with_session
from app.config import get_settings

NAME = "ontology"

GO_TERMS = ["GO:0033176", "GO:0016471", "GO:0070070", "GO:0007035"]


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            terms = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for go_id in GO_TERMS:
                    entry = {"go_id": go_id}
                    try:
                        resp = client.get(f"https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{go_id}")
                        if resp.status_code == 200:
                            results = resp.json().get("results", [])
                            if results:
                                entry["name"] = results[0].get("name")
                                entry["definition"] = (results[0].get("definition") or {}).get("text")
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    terms.append(entry)

            result["detail"] = {"terms": terms}
            result["summary"] = f"Fetched definitions for {len(terms)} GO terms."
    finally:
        db.close()
