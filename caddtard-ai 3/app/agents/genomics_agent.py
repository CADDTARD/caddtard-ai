"""Genomic variant curation agent - cross-checks every top-3 gene's UniProt
accession live against rest.uniprot.org, server-side (no browser CORS
dependency, unlike the original prototype)."""
import httpx
from sqlalchemy import select

from app.agents.base import agent_run, with_session
from app.config import get_settings
from app.models import Gene

NAME = "genomics"


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            genes = db.scalars(select(Gene).where(Gene.in_top3.is_(True))).all()
            findings = []
            mismatches = 0
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for gene in genes:
                    acc = gene.uniprot_accession
                    entry = {"gene": gene.symbol, "accession": acc}
                    try:
                        resp = client.get(
                            f"https://rest.uniprot.org/uniprotkb/{acc}.json",
                            params={"fields": "gene_names"},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            names = data.get("genes", [])
                            live_name = names[0]["geneName"]["value"] if names else None
                            entry["live_gene_name"] = live_name
                            entry["match"] = live_name == gene.symbol
                            if not entry["match"]:
                                mismatches += 1
                        else:
                            entry["http_status"] = resp.status_code
                            entry["match"] = None
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                        entry["match"] = None
                    findings.append(entry)

            result["detail"] = {"genes_checked": len(genes), "mismatches": mismatches, "findings": findings}
            result["summary"] = f"Checked {len(genes)} accessions, {mismatches} mismatch(es)."
    finally:
        db.close()
