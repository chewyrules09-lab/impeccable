from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# Flat (non-src) layout: guarantee the project root is importable regardless
# of how pytest/uv resolve the editable install, since `run_session.py` is a
# standalone script, not a package listed in pyproject's wheel targets.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from persistence.db import get_connection  # noqa: E402


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = get_connection(":memory:")
    yield connection
    connection.close()
