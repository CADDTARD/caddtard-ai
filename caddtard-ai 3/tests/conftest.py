"""
Test environment must be configured BEFORE `app.main` (and therefore
`app.config`/`app.database`) is imported anywhere, since Settings is cached
with @lru_cache. conftest.py is collected first by pytest, so setting env
vars here at module scope is the one place guaranteed to run early enough.
"""
import os
import tempfile

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["AGENTS_ENABLED"] = "false"  # tests should not spin up the real scheduler

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
