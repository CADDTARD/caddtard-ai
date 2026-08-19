"""Development Division: Patent Landscape Agent, via the PatentsView Search
API (search.patentsview.org). Unlike every other agent in this file, real use
of this API requires a free API key (PatentsView moved to key-gated access in
2024) - the same "does not invent data" discipline used for the CRO/vendor
layer applies here: rather than fabricate patent hits, this agent reports its
own "not configured" status honestly when PATENTSVIEW_API_KEY is unset, and
runs the real live query the moment a key is supplied via .env."""
import httpx

from app.agents.base import agent_run, with_session
from app.agents.portfolio import COMPOUND_TERMS
from app.config import get_settings

NAME = "patent_landscape"


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            if not settings.patentsview_api_key:
                result["detail"] = {
                    "configured": False,
                    "note": (
                        "PATENTSVIEW_API_KEY is not set. Free key: https://search.patentsview.org/api-request. "
                        "This agent is written and wired into the scheduler, but will not fabricate patent "
                        "results without a real key - it reports this status instead."
                    ),
                }
                result["summary"] = "PatentsView API key not configured - reporting real status, not fabricated data."
                return

            findings = []
            headers = {"X-Api-Key": settings.patentsview_api_key}
            with httpx.Client(timeout=settings.agent_http_timeout, headers=headers) as client:
                for term in COMPOUND_TERMS:
                    entry = {"compound": term}
                    try:
                        resp = client.post(
                            "https://search.patentsview.org/api/v1/patent/",
                            json={
                                "q": {"_text_any": {"patent_title": term}},
                                "f": ["patent_id", "patent_title", "patent_date"],
                                "o": {"size": 3},
                            },
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            entry["total_hits"] = data.get("total_hits")
                            patents = data.get("patents", [])
                            entry["most_recent"] = patents[0] if patents else None
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"configured": True, "searches": findings}
            result["summary"] = f"Queried PatentsView for {len(findings)} portfolio compounds."
    finally:
        db.close()
