"""Development Division: Funding Opportunities Agent, via the NIH RePORTER
public API (api.reporter.nih.gov). Live count and top recent award per
portfolio disease term - directly answers "who is NIH currently funding to
work on this" without a manual grants.gov search. No API key required."""
import httpx

from app.agents.base import agent_run, with_session
from app.agents.portfolio import ALL_DISEASE_TERMS
from app.config import get_settings

NAME = "funding_opportunities"


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
                        resp = client.post(
                            "https://api.reporter.nih.gov/v2/projects/search",
                            json={
                                "criteria": {"advanced_text_search": {"search_field": "all", "search_text": term}},
                                "include_fields": ["ProjectTitle", "FiscalYear", "AwardAmount", "OrgName"],
                                "offset": 0,
                                "limit": 3,
                                "sort_field": "fiscal_year",
                                "sort_order": "desc",
                            },
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            results = data.get("results", [])
                            entry["total_matching"] = data.get("meta", {}).get("total")
                            entry["most_recent_award"] = (
                                {
                                    "title": results[0].get("project_title"),
                                    "fiscal_year": results[0].get("fiscal_year"),
                                    "amount_usd": results[0].get("award_amount"),
                                    "org": results[0].get("org_name"),
                                }
                                if results
                                else None
                            )
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"searches": findings}
            result["summary"] = f"Queried NIH RePORTER for active/recent US federal funding across {len(findings)} portfolio disease terms."
    finally:
        db.close()
