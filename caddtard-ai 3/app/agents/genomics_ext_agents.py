"""Genomics Division agents beyond the original Variant Agent (genomics_agent.py):
Gene Agent + Transcript Agent (Ensembl REST) and Population Genetics Agent (gnomAD
GraphQL). Same agent_run/with_session pattern as every other agent."""
import httpx
from sqlalchemy import select

from app.agents.base import agent_run, with_session
from app.config import get_settings
from app.models import Gene

ENSEMBL_NAME = "gene_transcript"
GNOMAD_NAME = "population_genetics"


def run_gene_transcript(run_id: int | None = None, trigger: str = "scheduled") -> None:
    """Gene Agent + Transcript Agent: live gene/transcript metadata from the
    Ensembl REST API for each top-3 gene. Resolves the Ensembl gene ID by
    symbol at call time (rather than hardcoding IDs) so it can't drift out of
    date and doesn't depend on a possibly-mis-recalled accession."""
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, ENSEMBL_NAME, run_id, trigger) as result:
            genes = db.scalars(select(Gene).where(Gene.in_top3.is_(True))).all()
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for gene in genes:
                    entry = {"gene": gene.symbol}
                    try:
                        xref_resp = client.get(
                            f"https://rest.ensembl.org/xrefs/symbol/homo_sapiens/{gene.symbol}",
                            params={"content-type": "application/json"},
                        )
                        ensembl_id = None
                        if xref_resp.status_code == 200:
                            for hit in xref_resp.json():
                                if hit.get("type") == "gene":
                                    ensembl_id = hit.get("id")
                                    break
                        entry["ensembl_id"] = ensembl_id
                        if ensembl_id:
                            resp = client.get(
                                f"https://rest.ensembl.org/lookup/id/{ensembl_id}",
                                params={"expand": 1, "content-type": "application/json"},
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                entry["biotype"] = data.get("biotype")
                                entry["transcript_count"] = len(data.get("Transcript", []))
                            else:
                                entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"genes": findings}
            result["summary"] = f"Fetched Ensembl gene/transcript metadata for {len(findings)} genes."
    finally:
        db.close()


def run_population_genetics(run_id: int | None = None, trigger: str = "scheduled") -> None:
    """Population Genetics Agent: gnomAD constraint metrics (missense/pLI) per
    top-3 gene via the public gnomAD GraphQL API."""
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, GNOMAD_NAME, run_id, trigger) as result:
            genes = db.scalars(select(Gene).where(Gene.in_top3.is_(True))).all()
            query = """
            query GeneConstraint($symbol: String!) {
              gene(gene_symbol: $symbol, reference_genome: GRCh38) {
                gnomad_constraint { pli oe_lof oe_mis }
              }
            }
            """
            findings = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for gene in genes:
                    entry = {"gene": gene.symbol}
                    try:
                        resp = client.post(
                            "https://gnomad.broadinstitute.org/api",
                            json={"query": query, "variables": {"symbol": gene.symbol}},
                        )
                        if resp.status_code == 200:
                            payload = resp.json()
                            constraint = (((payload.get("data") or {}).get("gene") or {}) or {}).get("gnomad_constraint")
                            entry["constraint"] = constraint
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    findings.append(entry)
            result["detail"] = {"genes": findings}
            result["summary"] = f"Fetched gnomAD constraint metrics for {len(findings)} genes."
    finally:
        db.close()
