"""Integration tests for Track 5 poker endpoints."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


# ---------- /api/poker/preflop-charts ----------


def test_preflop_charts_returns_all_named_charts(client):
    response = client.get("/api/poker/preflop-charts")
    assert response.status_code == 200
    payload = response.json()
    assert "charts" in payload
    assert "raw" in payload
    for name in ("UTG_OPEN", "MP_OPEN", "CO_OPEN", "BTN_OPEN", "BB_DEFEND"):
        assert name in payload["charts"]
        # Each chart maps class-string -> weight in [0, 1].
        for cls, weight in payload["charts"][name].items():
            assert isinstance(cls, str)
            assert 0.0 < weight <= 1.0


def test_utg_open_includes_aa(client):
    payload = client.get("/api/poker/preflop-charts").json()
    assert payload["charts"]["UTG_OPEN"].get("AA") == 1.0


# ---------- /api/poker/range-equity ----------


def test_range_equity_aces_vs_kings(client):
    response = client.post(
        "/api/poker/range-equity",
        json={
            "players": [
                {"hand": ["Ah", "As"]},
                {"hand": ["Kh", "Ks"]},
            ],
            "trials": 600,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    equities = payload["equities"]
    assert len(equities) == 2
    # AA vs KK ~ 82/18.
    assert equities[0] > 0.7
    assert equities[1] < 0.3
    assert abs(sum(equities) - 1.0) < 0.05


def test_range_equity_with_preflop_chart(client):
    response = client.post(
        "/api/poker/range-equity",
        json={
            "players": [
                {"preflop_chart": "TIGHT_3BET"},
                {"preflop_chart": "BTN_OPEN"},
            ],
            "trials": 300,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    # Tight 3-bet should crush a wide BTN open preflop.
    assert payload["equities"][0] > 0.55
    assert payload["players"][0]["label"] == "Chart: TIGHT_3BET"


def test_range_equity_with_board(client):
    response = client.post(
        "/api/poker/range-equity",
        json={
            "players": [
                {"hand": ["Ah", "As"]},
                {"range": "QQ, JJ"},
            ],
            "board": ["Qs", "Jh", "2d"],
            "trials": 200,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    # Villain flopped a set (QQ or JJ) -> ahead of AA.
    assert payload["equities"][1] > payload["equities"][0]


def test_range_equity_three_way(client):
    response = client.post(
        "/api/poker/range-equity",
        json={
            "players": [
                {"hand": ["Ah", "As"]},
                {"hand": ["Kh", "Ks"]},
                {"hand": ["Qh", "Qs"]},
            ],
            "trials": 1500,
        },
    )
    assert response.status_code == 200
    eq = response.json()["equities"]
    assert len(eq) == 3
    # AA dominates preflop 3-way (~65% equity); KK is second (~20%).
    # With 1500 trials the standard error is small enough to pin the
    # ordering reliably without requiring a seeded RNG in the API.
    assert eq[0] > 0.50
    assert eq[0] > eq[1]
    assert eq[0] > eq[2]
    assert abs(sum(eq) - 1.0) < 0.05


def test_range_equity_validates_player_count(client):
    response = client.post(
        "/api/poker/range-equity",
        json={"players": [{"hand": ["Ah", "As"]}]},
    )
    assert response.status_code == 422


def test_range_equity_validates_board_length(client):
    response = client.post(
        "/api/poker/range-equity",
        json={
            "players": [{"hand": ["Ah", "As"]}, {"hand": ["Kh", "Ks"]}],
            "board": ["Ah", "Kd"],  # 2-card board is invalid
        },
    )
    assert response.status_code == 400


def test_range_equity_validates_unknown_card(client):
    response = client.post(
        "/api/poker/range-equity",
        json={
            "players": [
                {"hand": ["Zh", "As"]},
                {"hand": ["Kh", "Ks"]},
            ],
        },
    )
    assert response.status_code == 400
    assert "rank" in response.json()["detail"].lower()


def test_range_equity_rejects_unknown_preflop_chart(client):
    response = client.post(
        "/api/poker/range-equity",
        json={
            "players": [
                {"preflop_chart": "FAKE_NAME"},
                {"hand": ["Kh", "Ks"]},
            ],
        },
    )
    assert response.status_code == 400


def test_range_equity_rejects_player_with_no_spec(client):
    response = client.post(
        "/api/poker/range-equity",
        json={
            "players": [
                {},
                {"hand": ["Kh", "Ks"]},
            ],
        },
    )
    assert response.status_code == 400
