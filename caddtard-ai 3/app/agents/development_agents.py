"""Development Division: Clinical Agent (ClinicalTrials.gov) + Competitive
Intelligence Agent (Open Targets Platform GraphQL) - both public, real APIs."""
import httpx
from sqlalchemy import select

from app.agents.base import agent_run, with_session
from app.config import get_settings
from app.models import Gene

CLINICAL_NAME = "clinical_trials"
COMPETITIVE_NAME = "competitive_intelligence"
GITHUB_NAME = "github_watch"


def run_clinical(run_id: int | None = None, trigger: str = "scheduled") -> None:
    """Clinical Agent: live count of registered trials mentioning each top-3
    disease area, via the ClinicalTrials.gov v2 API."""
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, CLINICAL_NAME, run_id, trigger) as result:
            terms = ["distal renal tubular acidosis", "developmental epileptic encephalopathy ATP6V0C", "osteopetrosis TCIRG1"]
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for term in terms:
                    entry = {"term": term}
                    try:
                        resp = client.get(
                            "https://clinicaltrials.gov/api/v2/studies",
                            params={"query.term": term, "pageSize": 5, "countTotal": "true"},
                        )
                        if resp.status_code == 200:
                            entry["total_count"] = resp.json().get("totalCount")
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"searches": findings}
            result["summary"] = f"Queried ClinicalTrials.gov for {len(findings)} disease-area terms."
    finally:
        db.close()


def run_competitive_intelligence(run_id: int | None = None, trigger: str = "scheduled") -> None:
    """Competitive Intelligence Agent: target-disease association evidence and
    tractability from the Open Targets Platform GraphQL API, per top-3 gene."""
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, COMPETITIVE_NAME, run_id, trigger) as result:
            genes = db.scalars(select(Gene).where(Gene.in_top3.is_(True))).all()
            query = """
            query TargetInfo($symbol: String!) {
              search(queryString: $symbol, entityNames: ["target"]) {
                hits { id name entity }
              }
            }
            """
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for gene in genes:
                    entry = {"gene": gene.symbol}
                    try:
                        resp = client.post(
                            "https://api.platform.opentargets.org/api/v4/graphql",
                            json={"query": query, "variables": {"symbol": gene.symbol}},
                        )
                        if resp.status_code == 200:
                            hits = (((resp.json().get("data") or {}).get("search") or {}).get("hits")) or []
                            entry["opentargets_id"] = hits[0]["id"] if hits else None
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"genes": findings}
            result["summary"] = f"Queried Open Targets Platform for {len(findings)} genes."
    finally:
        db.close()


def run_github_watch(run_id: int | None = None, trigger: str = "scheduled") -> None:
    """Competitive Intelligence / Data Fabric support: watches public GitHub
    for repositories relevant to V-ATPase research tooling, via the
    unauthenticated GitHub Search API."""
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, GITHUB_NAME, run_id, trigger) as result:
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout, headers={"Accept": "application/vnd.github+json"}) as client:
                for query in ["ATP6V vacuolar ATPase", "V-ATPase inhibitor"]:
                    entry = {"query": query}
                    try:
                        resp = client.get(
                            "https://api.github.com/search/repositories",
                            params={"q": query, "sort": "updated", "per_page": 5},
                        )
                        if resp.status_code == 200:
                            items = resp.json().get("items", [])
                            entry["repo_count"] = resp.json().get("total_count")
                            entry["top_repo"] = items[0]["full_name"] if items else None
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"searches": findings}
            result["summary"] = f"Searched GitHub for {len(findings)} query terms."
    finally:
        db.close()
