import asyncio
import time

import pytest

from app.api import chaos
from app.core import config


@pytest.fixture
def marker(tmp_path, monkeypatch):
    path = tmp_path / "down-until"
    monkeypatch.setenv("CHAOS_MARKER", str(path))
    return path


@pytest.fixture
def no_exit(monkeypatch):
    calls = []
    monkeypatch.setattr(chaos, "_exit_process", lambda: calls.append("exit"))
    return calls


def test_crash_disabled_by_default(client, marker, no_exit):
    r = client.post("/admin/crash", params={"down_seconds": 5})
    assert r.status_code == 403
    assert not marker.exists()


def test_crash_writes_marker_and_exits(client, marker, no_exit, monkeypatch):
    monkeypatch.setattr(chaos, "settings", config.Settings(enable_chaos=True))
    r = client.post("/admin/crash", params={"down_seconds": 7})
    assert r.status_code == 200 and r.json()["crashing"] is True
    assert float(marker.read_text()) == pytest.approx(time.time() + 7, abs=2)
    time.sleep(0.4)
    assert no_exit == ["exit"]


def test_crash_refused_through_proxy_and_validated(client, marker, no_exit, monkeypatch):
    monkeypatch.setattr(chaos, "settings", config.Settings(enable_chaos=True))
    assert client.post("/admin/crash", headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 403
    assert client.post("/admin/crash", params={"down_seconds": 999}).status_code == 422
    assert not marker.exists() and no_exit == []


def test_crash_not_under_public_api_prefix(client):
    assert client.post("/api/admin/crash").status_code in (404, 405)


def test_wait_if_crashed(marker):
    assert asyncio.run(chaos.wait_if_crashed()) == 0.0              # no marker
    marker.write_text(f"{time.time() - 5}")
    assert asyncio.run(chaos.wait_if_crashed()) == 0.0              # downtime already over
    assert not marker.exists()
    marker.write_text(f"{time.time() + 0.3}")
    t0 = time.time()
    waited = asyncio.run(chaos.wait_if_crashed())
    assert 0.1 < waited <= 0.3 and time.time() - t0 >= 0.1 and not marker.exists()
    marker.write_text("garbage")
    assert asyncio.run(chaos.wait_if_crashed()) == 0.0
