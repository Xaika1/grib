import atexit
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="grib-test-"))
atexit.register(shutil.rmtree, _TMP, True)
os.environ.update(
    GRIB_SECRET_KEY="test-secret-test-secret-test-secret-42",
    GRIB_SCHEDULER="0",
    GRIB_SQLITE_DIR=str(_TMP / "sources"),
    GRIB_ADMIN_LOGIN="admin",
    GRIB_ADMIN_PASSWORD="admin",
    GRIB_MIN_COLLECTOR_INTERVAL="1",
)
os.environ.setdefault("GRIB_DATABASE_URL", f"sqlite:///{_TMP / 'grib.db'}")
(_TMP / "sources").mkdir()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _make_shop(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE orders (id INTEGER PRIMARY KEY, created_at TIMESTAMP, amount NUMERIC, status TEXT, region TEXT);
        CREATE TABLE queue_state (name TEXT PRIMARY KEY, size INTEGER);
        """
    )
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    rows = []
    for i in range(48):
        t = now - timedelta(minutes=30 * i)
        rows.append((t.strftime("%Y-%m-%d %H:%M:%S"), 100 + i, "paid" if i % 3 else "new", "Москва" if i % 2 else "Казань"))
    conn.executemany("INSERT INTO orders (created_at, amount, status, region) VALUES (?, ?, ?, ?)", rows)
    conn.executemany("INSERT INTO queue_state VALUES (?, ?)", [("orders", 5), ("emails", 50)])
    conn.commit()
    conn.close()


_make_shop(_TMP / "sources" / "shop.db")


@pytest.fixture(scope="session")
def shop_path() -> Path:
    return _TMP / "sources" / "shop.db"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def admin(client) -> dict:
    r = client.post("/api/auth/login", json={"login": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    return auth(r.json()["token"])
