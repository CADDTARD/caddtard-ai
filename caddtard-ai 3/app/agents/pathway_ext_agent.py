"""Genomics Division: Pathway Intelligence Agent, via the Reactome
ContentService REST API (reactome.org, public, unauthenticated). Live search
for curated human pathways matching each mechanistic term surfaced in the
chromoblastomycosis pathway deep dive (melanin biosynthesis, cell wall
biosynthesis, etc.) and the V-ATPase program's lysosomal-acidification
mechanism - grounds the "signaling pathways" narrative in a queryable
database rather than a static literature citation."""
import httpx

from app.agents.base import agent_run, with_session
from app.config import get_settings

NAME = "pathway_intelligence"

PATHWAY_TERMS = [
    "vacuolar ATPase",
    "lysosomal acidification",
    "melanin biosynthesis",
    "fungal cell wall biosynthesis",
    "Th17 differentiation",
]


def _entry_count(group: dict) -> int:
    """Return a Reactome result group's hit count across API schema variants.

    ContentService currently returns ``entries`` as a list of result objects.
    Older/example payloads have represented it as a numeric count, so accept
    both forms and treat an absent or unexpected value as no hits.
    """
    entries = group.get("entries")
    if isinstance(entries, list):
        return len(entries)
    if isinstance(entries, (int, float)) and not isinstance(entries, bool):
        return int(entries)
    return 0


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for term in PATHWAY_TERMS:
                    entry = {"term": term}
                    try:
                        resp = client.get(
                            "https://reactome.org/ContentService/search/query",
                            params={"query": term, "cluster": "true", "species": "Homo sapiens"},
                        )
                        if resp.status_code == 200:
                            try:
                                data = resp.json()
                            except ValueError:
                                # Reactome's ContentService has occasionally returned an
                                # empty 200 body when under load; recorded as a soft
                                # failure rather than crashing the run.
                                entry["error"] = "empty or non-JSON response body from Reactome"
                                findings.append(entry)
                                continue
                            groups = data.get("results", []) or []
                            total = sum(_entry_count(group) for group in groups)
                            entry["result_group_count"] = len(groups)
                            entry["total_entries"] = total
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"searches": findings}
            result["summary"] = f"Queried Reactome for {len(findings)} mechanistic pathway terms across the portfolio."
    finally:
        db.close()
