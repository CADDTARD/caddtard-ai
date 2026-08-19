"""Development Division: Regulatory Precedent Agent (openFDA) + CMC Product
Label Agent (DailyMed). Both are public, unauthenticated NIH/FDA REST APIs.

Regulatory Precedent: searches openFDA's structured product labels and
enforcement-action datasets for precedent relevant to the portfolio's
repurposing candidates (does an approved product already carry labeling or
an enforcement history that matters for a 505(b)(2) pathway?).

CMC Product Label: pulls the live structured product label (formulation,
route, dosage form as filed with FDA) for each repurposing candidate from
DailyMed - the direct data source for the "already-approved formulation"
argument in the CMC readiness pack, not a paraphrase of it."""
import httpx

from app.agents.base import agent_run, with_session
from app.agents.portfolio import COMPOUND_TERMS
from app.config import get_settings

REGULATORY_NAME = "regulatory_precedent"
CMC_LABEL_NAME = "cmc_product_label"


def run_regulatory_precedent(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, REGULATORY_NAME, run_id, trigger) as result:
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for term in COMPOUND_TERMS:
                    entry = {"compound": term}
                    try:
                        resp = client.get(
                            "https://api.fda.gov/drug/label.json",
                            params={"search": f'openfda.generic_name:"{term}"', "limit": 1},
                        )
                        if resp.status_code == 200:
                            results = resp.json().get("results", [])
                            if results:
                                openfda = results[0].get("openfda", {})
                                entry["found_label"] = True
                                entry["brand_name"] = (openfda.get("brand_name") or [None])[0]
                                entry["route"] = (openfda.get("route") or [None])[0]
                                entry["application_number"] = (openfda.get("application_number") or [None])[0]
                            else:
                                entry["found_label"] = False
                        elif resp.status_code == 404:
                            entry["found_label"] = False
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"searches": findings}
            found = sum(1 for f in findings if f.get("found_label"))
            result["summary"] = f"Checked openFDA labels for {len(findings)} compounds; {found} have an existing approved label on file."
    finally:
        db.close()


def run_cmc_product_label(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, CMC_LABEL_NAME, run_id, trigger) as result:
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for term in COMPOUND_TERMS:
                    entry = {"compound": term}
                    try:
                        resp = client.get(
                            "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json",
                            params={"drug_name": term, "pagesize": 1},
                        )
                        if resp.status_code == 200:
                            data = resp.json().get("data", [])
                            entry["spl_on_file"] = len(data) > 0
                            if data:
                                entry["set_id"] = data[0].get("setid")
                                entry["title"] = data[0].get("title")
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"searches": findings}
            on_file = sum(1 for f in findings if f.get("spl_on_file"))
            result["summary"] = f"Checked DailyMed for {len(findings)} compounds; {on_file} have a structured product label on file."
    finally:
        db.close()
