"""Regression tests for the cross-player data leak bug.

Before the fix, ``analytics_service.load_player_record`` and
``summary_service._load_player_record`` would *silently* fall back to
the most recently played player when the explicitly-requested player
didn't exist. The Analytics page would render Player A's metrics
under Player B's name, and the Summary endpoint would do the same.

The fix keeps the implicit "no name given" fallback (still useful for
the default dashboard view) but disables the fallback when the caller
provided a player name. Each test below codifies one user-visible
symptom of the fix.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "backend"
SRC_PATH = ROOT / "src"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from app.main import app  # noqa: E402
from app.services import analytics_service, summary_service  # noqa: E402
from app.services import game_service  # noqa: E402
from data.manager import DataManager  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()
    return TestClient(app)


def _seed_one_player(data_path: Path) -> None:
    """Drop one player into the store so list_players() is non-empty."""
    manager = DataManager(data_file=str(data_path))
    manager.create_player("Alice", 5000)
    manager.save_players()


def test_summary_returns_defaults_when_player_missing(client, tmp_path):
    """Asking summary for a non-existent player must not leak another player's data."""
    _seed_one_player(tmp_path / "players.json")
    response = client.get("/api/summary?player=Nobody")
    assert response.status_code == 200
    body = response.json()
    # Before the fix this returned Alice's metrics under the "Nobody"
    # query. After the fix the default empty summary is returned.
    assert body["player"]["name"] == "Guest"
    assert body["player"]["skill_level"] == "rookie"


def test_analytics_report_returns_defaults_when_player_missing(client, tmp_path):
    """Same fix on the analytics path: don't leak Alice's stats to a Nobody query."""
    _seed_one_player(tmp_path / "players.json")
    response = client.get("/api/summary/report?player=Nobody")
    assert response.status_code == 200
    body = response.json()
    assert body["playing_style"]["player_type"] == "Unknown"
    assert body["strategy_score"] == 0
    assert body["recommendations"] == ["Play tracked hands to generate analytics."]


def test_analytics_chart_returns_empty_when_player_missing(client, tmp_path):
    """No silent data spillover into per-player charts."""
    _seed_one_player(tmp_path / "players.json")
    response = client.get("/api/charts/vpip?player=Nobody")
    assert response.status_code == 200
    assert response.json() == []


def test_analytics_career_returns_empty_when_player_missing(client, tmp_path):
    """Career career_metrics should be None for a non-existent player."""
    _seed_one_player(tmp_path / "players.json")
    response = client.get("/api/analytics/career?player=Nobody")
    assert response.status_code == 200
    body = response.json()
    assert body["session_count"] == 0
    assert body["career_metrics"] is None


def test_summary_without_player_still_falls_back_to_most_recent(client, tmp_path):
    """The *implicit* "no player name" fallback is preserved; only the
    explicit-name path stops silently fingerprint-substituting players.
    """
    _seed_one_player(tmp_path / "players.json")
    # No player query param.
    response = client.get("/api/summary")
    assert response.status_code == 200
    body = response.json()
    # Falls back to Alice (the only player in the DB).
    assert body["player"]["name"] == "Alice"


def test_load_player_record_unit_returns_none_for_unknown_name(tmp_path, monkeypatch):
    """Unit-level check on the two helpers that share the fix."""
    data_file = tmp_path / "players.json"
    _seed_one_player(data_file)
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(data_file))

    assert analytics_service.load_player_record("Nobody") is None
    assert summary_service._load_player_record("Nobody") is None

    # And the implicit-name path still finds the seeded record.
    assert analytics_service.load_player_record(None) is not None
    assert summary_service._load_player_record(None) is not None
