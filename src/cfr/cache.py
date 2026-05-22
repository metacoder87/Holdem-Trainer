"""Disk-backed cache of trained subgame policies.

The cache is keyed by :class:`cfr.spot.SpotKey` and stores the
``Policy`` for each spot as an ``.npz`` file plus a small JSON index
that records metadata (iteration count, infoset count, timestamp).

Why both files:

  - The ``.npz`` files are the heavy artifacts we want to keep
    immutable and shippable (e.g. as GitHub Release Assets).
  - The ``index.json`` is the index — fast to mmap-on-startup and
    cheap to update when new spots are precomputed.

The split also lets a deploy ship just the npz files it needs, and
regenerate the index from the directory contents if the index file is
ever lost.

Read path::

    cache = SolverCache.open(Path("backend/cfr_artifacts"))
    if cache.has(spot):
        policy = cache.get(spot)         # cached Policy
    else:
        policy = train_on_demand(spot)   # caller's job
        cache.put(spot, policy, iterations=5000)

The cache is **read-mostly** at runtime; the only writer is the
precompute script. Concurrent readers are safe; concurrent writers
should not run (cache is single-process during precompute).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from cfr.io import load as load_policy, save as save_policy
from cfr.policy import Policy
from cfr.spot import SpotKey


# Layout constants. Bump CACHE_VERSION on backward-incompatible changes
# to the .npz format; the cache reader will then skip stale entries.
CACHE_VERSION = 1
INDEX_FILENAME = "index.json"
SPOTS_SUBDIR = "spots"


@dataclass(frozen=True)
class CacheEntry:
    """One row in the cache index."""

    signature: str
    filename: str  # relative to spots/ directory
    iterations: int
    num_infosets: int
    created_at: float  # unix timestamp
    cache_version: int = CACHE_VERSION
    meta: Optional[Dict] = None


class SolverCache:
    """Disk-backed cache of trained subgame policies.

    Construct via :meth:`open` to load (or initialize) a cache at a
    specific root directory. The root directory contains ``index.json``
    + a ``spots/`` subdirectory of ``.npz`` files.
    """

    __slots__ = ("_root", "_index")

    def __init__(self, root: Path, index: Dict[str, CacheEntry]) -> None:
        self._root = Path(root)
        self._index = index

    # ---------- Construction ----------

    @classmethod
    def open(cls, root: Path | str) -> "SolverCache":
        """Open (and lazily create) a cache at ``root``."""
        root_path = Path(root)
        root_path.mkdir(parents=True, exist_ok=True)
        (root_path / SPOTS_SUBDIR).mkdir(exist_ok=True)

        index_path = root_path / INDEX_FILENAME
        if index_path.exists():
            try:
                raw = json.loads(index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                raw = {}
        else:
            raw = {}

        index: Dict[str, CacheEntry] = {}
        for sig, payload in raw.items():
            if not isinstance(payload, dict):
                continue
            try:
                version = int(payload.get("cache_version", CACHE_VERSION))
                if version != CACHE_VERSION:
                    # Skip stale entries; they'll get re-trained.
                    continue
                index[sig] = CacheEntry(
                    signature=sig,
                    filename=str(payload["filename"]),
                    iterations=int(payload.get("iterations", 0)),
                    num_infosets=int(payload.get("num_infosets", 0)),
                    created_at=float(payload.get("created_at", 0.0)),
                    cache_version=version,
                    meta=payload.get("meta"),
                )
            except (KeyError, ValueError, TypeError):
                continue

        return cls(root_path, index)

    # ---------- Query ----------

    @property
    def root(self) -> Path:
        return self._root

    def has(self, spot: SpotKey) -> bool:
        return spot.signature() in self._index

    def get(self, spot: SpotKey) -> Optional[Policy]:
        """Load and return the cached Policy for ``spot``, or None if absent.

        Returns None (not raises) on missing entry, missing file, or
        corrupt file — the caller is expected to fall back to a
        heuristic in any of those cases.
        """
        entry = self._index.get(spot.signature())
        if entry is None:
            return None
        path = self._root / SPOTS_SUBDIR / entry.filename
        if not path.exists():
            return None
        try:
            return load_policy(path)
        except (OSError, ValueError, KeyError):
            return None

    def entry(self, spot: SpotKey) -> Optional[CacheEntry]:
        """Return cache metadata for ``spot`` without loading the policy."""
        return self._index.get(spot.signature())

    def all_signatures(self) -> List[str]:
        return list(self._index.keys())

    def __len__(self) -> int:
        return len(self._index)

    def __iter__(self) -> Iterator[CacheEntry]:
        return iter(self._index.values())

    # ---------- Write ----------

    def put(
        self,
        spot: SpotKey,
        policy: Policy,
        *,
        iterations: int,
        meta: Optional[Dict] = None,
    ) -> CacheEntry:
        """Persist ``policy`` for ``spot`` and update the index."""
        signature = spot.signature()
        filename = f"{signature}.npz"
        path = self._root / SPOTS_SUBDIR / filename
        save_policy(policy, path)

        entry = CacheEntry(
            signature=signature,
            filename=filename,
            iterations=int(iterations),
            num_infosets=policy.num_infosets(),
            created_at=time.time(),
            cache_version=CACHE_VERSION,
            meta=dict(meta) if meta else None,
        )
        self._index[signature] = entry
        self._flush_index()
        return entry

    def remove(self, spot: SpotKey) -> bool:
        """Drop a cached spot. Returns True if anything was removed."""
        sig = spot.signature()
        entry = self._index.pop(sig, None)
        if entry is None:
            return False
        path = self._root / SPOTS_SUBDIR / entry.filename
        try:
            if path.exists():
                path.unlink()
        except OSError:
            # Best-effort: leave the file behind if the OS refuses.
            pass
        self._flush_index()
        return True

    # ---------- Internal ----------

    def _flush_index(self) -> None:
        """Atomically rewrite the index file."""
        serializable: Dict[str, Dict] = {}
        for sig, entry in self._index.items():
            serializable[sig] = {
                "filename": entry.filename,
                "iterations": entry.iterations,
                "num_infosets": entry.num_infosets,
                "created_at": entry.created_at,
                "cache_version": entry.cache_version,
            }
            if entry.meta is not None:
                serializable[sig]["meta"] = entry.meta

        target = self._root / INDEX_FILENAME
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        tmp.replace(target)
