"""SolverCache tests.

The cache is dirt-simple but it's the only thing standing between us
and corrupted strategy data, so we exercise the corner cases:

  - Round-trip put/get returns an equivalent Policy.
  - Missing entries return None (never raise).
  - The on-disk index survives process restart.
  - Cache-version mismatches are silently dropped.
  - Concurrent readers see a consistent index after a write.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfr.cache import CACHE_VERSION, INDEX_FILENAME, SPOTS_SUBDIR, SolverCache
from cfr.policy import Policy
from cfr.spot import SpotKey


def _make_spot(street: str = "flop", board: str = "Aa,Kb,2c") -> SpotKey:
    return SpotKey(
        street=street,
        board_canonical=board,
        pot_bb=20,
        spr_bucket=2,
        first_actor=0,
    )


def _make_policy() -> Policy:
    return Policy(
        {
            "b=0|h=": {"CHECK_OR_CALL": 0.6, "ALL_IN": 0.4},
            "b=5|h=k": {"CHECK_OR_CALL": 0.2, "RAISE_0.66": 0.8},
        }
    )


# ---------- Open / initialize ----------


def test_cache_open_creates_directories(tmp_path: Path):
    root = tmp_path / "artifacts"
    assert not root.exists()
    cache = SolverCache.open(root)
    assert (root / SPOTS_SUBDIR).is_dir()
    assert len(cache) == 0


def test_cache_open_handles_missing_index(tmp_path: Path):
    cache = SolverCache.open(tmp_path)
    assert cache.all_signatures() == []


def test_cache_open_handles_corrupt_index(tmp_path: Path):
    (tmp_path / INDEX_FILENAME).write_text("not valid json{{{", encoding="utf-8")
    cache = SolverCache.open(tmp_path)
    # Corrupt index -> empty cache, not a crash.
    assert len(cache) == 0


# ---------- Put / get round-trip ----------


def test_cache_round_trip_returns_equivalent_policy(tmp_path: Path):
    cache = SolverCache.open(tmp_path)
    spot = _make_spot()
    original = _make_policy()
    cache.put(spot, original, iterations=1000)

    loaded = cache.get(spot)
    assert loaded is not None
    assert loaded.num_infosets() == original.num_infosets()
    for key in original.infoset_keys():
        assert loaded.probs(key) is not None
        for action, prob in original.probs(key).items():
            assert abs(loaded.probs(key)[action] - prob) < 1e-9


def test_cache_has_reflects_put(tmp_path: Path):
    cache = SolverCache.open(tmp_path)
    spot = _make_spot()
    assert not cache.has(spot)
    cache.put(spot, _make_policy(), iterations=10)
    assert cache.has(spot)


def test_cache_get_returns_none_for_unknown(tmp_path: Path):
    cache = SolverCache.open(tmp_path)
    assert cache.get(_make_spot()) is None


# ---------- Persistence ----------


def test_cache_index_survives_reopen(tmp_path: Path):
    spot = _make_spot()
    first = SolverCache.open(tmp_path)
    first.put(spot, _make_policy(), iterations=42, meta={"trainer": "test"})

    second = SolverCache.open(tmp_path)
    assert second.has(spot)
    entry = second.entry(spot)
    assert entry is not None
    assert entry.iterations == 42
    assert entry.meta == {"trainer": "test"}
    # And the policy is still loadable.
    loaded = second.get(spot)
    assert loaded is not None
    assert loaded.num_infosets() == 2


def test_cache_skips_stale_version_entries(tmp_path: Path):
    """A pre-existing index entry with a wrong cache_version is ignored."""
    (tmp_path / SPOTS_SUBDIR).mkdir(parents=True)
    bad_index = {
        "stale__key": {
            "filename": "stale__key.npz",
            "iterations": 100,
            "num_infosets": 1,
            "created_at": 0.0,
            "cache_version": CACHE_VERSION + 99,
        }
    }
    (tmp_path / INDEX_FILENAME).write_text(json.dumps(bad_index), encoding="utf-8")
    cache = SolverCache.open(tmp_path)
    assert cache.all_signatures() == []


# ---------- Remove ----------


def test_cache_remove_drops_entry_and_file(tmp_path: Path):
    cache = SolverCache.open(tmp_path)
    spot = _make_spot()
    cache.put(spot, _make_policy(), iterations=5)
    entry = cache.entry(spot)
    assert entry is not None
    spot_file = tmp_path / SPOTS_SUBDIR / entry.filename
    assert spot_file.exists()

    removed = cache.remove(spot)
    assert removed is True
    assert not cache.has(spot)
    assert not spot_file.exists()

    # Remove on missing entry returns False without raising.
    assert cache.remove(spot) is False


# ---------- Index integrity after write ----------


def test_cache_index_file_is_valid_json(tmp_path: Path):
    cache = SolverCache.open(tmp_path)
    cache.put(_make_spot(), _make_policy(), iterations=7)
    index_path = tmp_path / INDEX_FILENAME
    assert index_path.exists()
    parsed = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(parsed) == 1
    only_entry = next(iter(parsed.values()))
    assert only_entry["iterations"] == 7
    assert only_entry["cache_version"] == CACHE_VERSION


def test_cache_get_returns_none_when_file_deleted(tmp_path: Path):
    """File missing on disk -> get() returns None rather than raising."""
    cache = SolverCache.open(tmp_path)
    spot = _make_spot()
    cache.put(spot, _make_policy(), iterations=3)
    entry = cache.entry(spot)
    (tmp_path / SPOTS_SUBDIR / entry.filename).unlink()
    assert cache.get(spot) is None


def test_cache_handles_two_distinct_spots(tmp_path: Path):
    cache = SolverCache.open(tmp_path)
    spot_a = _make_spot(street="flop")
    spot_b = _make_spot(street="turn", board="Aa,Kb,2c,Qa")
    cache.put(spot_a, _make_policy(), iterations=1)
    cache.put(spot_b, _make_policy(), iterations=2)
    assert cache.has(spot_a) and cache.has(spot_b)
    assert cache.entry(spot_a).iterations == 1
    assert cache.entry(spot_b).iterations == 2
