"""Serialize and load Policy objects.

We use ``.npz`` (NumPy compressed archive) because it round-trips
both the infoset keys (as a string array) and per-infoset action
distributions (as a flat float array + offsets) without any Python
pickle hazards. .npz is what gets shipped as a GitHub Release Asset.

File layout::

    keys: numpy.ndarray of str, length N
    actions: numpy.ndarray of str, length M (concatenation of per-key action lists)
    offsets: numpy.ndarray of int64, length N+1 (slice into actions/probs)
    probs: numpy.ndarray of float64, length M
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Union

import numpy as np

from cfr.policy import Policy


def save(policy: Policy, path: Union[str, Path]) -> None:
    """Write ``policy`` to ``path`` as a compressed .npz archive."""
    table = policy.as_dict()
    keys: List[str] = list(table.keys())
    actions: List[str] = []
    probs: List[float] = []
    offsets: List[int] = [0]
    for key in keys:
        action_probs = table[key]
        for action_name, p in action_probs.items():
            actions.append(action_name)
            probs.append(float(p))
        offsets.append(len(actions))

    np.savez_compressed(
        str(path),
        keys=np.array(keys, dtype=object),
        actions=np.array(actions, dtype=object),
        offsets=np.array(offsets, dtype=np.int64),
        probs=np.array(probs, dtype=np.float64),
    )


def load(path: Union[str, Path]) -> Policy:
    """Load a previously-saved policy."""
    data = np.load(str(path), allow_pickle=True)
    keys = data["keys"]
    actions = data["actions"]
    offsets = data["offsets"]
    probs = data["probs"]

    table: Dict[str, Dict[str, float]] = {}
    for i, key in enumerate(keys):
        start, end = int(offsets[i]), int(offsets[i + 1])
        slice_actions = actions[start:end]
        slice_probs = probs[start:end]
        table[str(key)] = {
            str(a): float(p) for a, p in zip(slice_actions, slice_probs)
        }
    return Policy(table)
