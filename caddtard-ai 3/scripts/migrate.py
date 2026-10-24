"""Upgrade a new database or safely adopt an exact pre-Alembic v3 schema."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.database import Base, engine
from app import models, models_ops  # noqa: F401 - register every table


def run(*args: str) -> None:
    subprocess.run(["alembic", *args], check=True)


def main() -> None:
    tables = set(inspect(engine).get_table_names())
    if tables and "alembic_version" not in tables:
        # A database created by CADDTARD AI <=3.0 has tables but no migration
        # marker. Adopt it only when Alembic proves it exactly matches the
        # current ORM metadata; otherwise fail instead of hiding drift.
        with engine.connect() as connection:
            drift = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        if drift:
            raise RuntimeError(f"Refusing to stamp a legacy database with schema drift: {drift[:5]}")
        run("stamp", "head")
    run("upgrade", "head")


if __name__ == "__main__":
    main()
