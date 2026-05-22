"""Track 5 poker math: ranges, fast hand evaluation, range-vs-range equity.

Separated from ``src.game`` (engine/gameplay) and ``src.stats``
(analytics) so the math layer can be imported independently from
notebooks, scripts, and the API services without dragging the full
engine in.

Public API::

    from poker import Range, fast_evaluate, range_vs_range_equity
"""

from poker.range import Combo, Range, parse_range_string  # noqa: F401
from poker.fast_eval import fast_evaluate, rank_class  # noqa: F401
from poker.range_equity import (  # noqa: F401
    multiway_range_equity,
    range_vs_range_equity,
)

__all__ = [
    "Combo",
    "Range",
    "parse_range_string",
    "fast_evaluate",
    "rank_class",
    "range_vs_range_equity",
    "multiway_range_equity",
]
