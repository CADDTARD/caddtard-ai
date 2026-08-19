"""Structural biology agent - live resolution metadata for the human V-ATPase
cryo-EM structures via the RCSB PDB Data API."""
import httpx

from app.agents.base import agent_run, with_session
from app.config import get_settings

NAME = "structural"

PDB_IDS = ["6WM2", "6WM3", "6WM4"]


def run(run_id: int | None = None, trigger: str = "scheduled") -> None:
    settings = get_settings()
    db = with_session()
    try:
        with agent_run(db, NAME, run_id, trigger) as result:
            structures = []
            with httpx.Client(timeout=settings.agent_http_timeout) as client:
                for pdb_id in PDB_IDS:
                    entry = {"pdb_id": pdb_id}
                    try:
                        resp = client.get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}")
                        if resp.status_code == 200:
                            info = resp.json().get("rcsb_entry_info", {})
                            res = info.get("resolution_combined")
                            entry["resolution_angstrom"] = res[0] if res else None
                        else:
                            entry["http_status"] = resp.status_code
                    except httpx.HTTPError as exc:
                        entry["error"] = str(exc)
                    structures.append(entry)

            result["detail"] = {"structures": structures}
            result["summary"] = f"Fetched metadata for {len(structures)} PDB entries."
    finally:
        db.close()
