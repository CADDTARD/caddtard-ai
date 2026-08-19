"""Disease Intelligence Division: WHO Global Health Observatory Burden Agent.
Queries the WHO GHO OData API (ghoapi.azureedge.net, public, unauthenticated)
for indicators whose name matches each portfolio disease term, live - this is
the same GHO dataset WHO's own NTD dashboards are built on, not a cached
snapshot. Where WHO has not defined a named indicator for a disease (true of
most of the ultra-neglected NTDs in this portfolio), the agent reports that
explicitly rather than guessing a burden number."""
import httpx

from app.agents.base import agent_run, with_session
from app.agents.portfolio import ALL_DISEASE_TERMS
from app.config import get_settings

NAME = "who_burden"


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for term in ALL_DISEASE_TERMS:
                    entry = {"term": term}
                    # GHO OData doesn't support free-text search of disease
                    # names directly against indicator codes, so this
                    # searches IndicatorName via $filter=contains(...).
                    key_word = term.split()[0]
                    try:
                        resp = client.get(
                            "https://ghoapi.azureedge.net/api/Indicator",
                            params={"$filter": f"contains(IndicatorName,'{key_word}')"},
                        )
                        if resp.status_code == 200:
                            values = resp.json().get("value", [])
                            entry["matching_indicators"] = len(values)
                            entry["indicator_names"] = [v.get("IndicatorName") for v in values[:3]]
                            entry["who_gho_has_named_indicator"] = len(values) > 0
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"searches": findings}
            named = sum(1 for f in findings if f.get("who_gho_has_named_indicator"))
            result["summary"] = f"Checked WHO GHO for {len(findings)} portfolio disease terms; {named} have a named WHO indicator (the rest lack formal WHO burden tracking, which is itself the diligence finding)."
    finally:
        db.close()
