"""Adaptive training engine: Bandit + SM-2 SRS + Elo difficulty.

Track 4. Replaces the in-memory ``Trainer.topic_history`` window with
three persistent learning subsystems:

  1. **Thompson-sampling multi-armed bandit** over weakness topics.
     Each topic is an arm with a Beta(alpha, beta) posterior. To pick
     the next drill topic we sample one value per arm and pull the
     arm with the highest draw. Beta-Binomial conjugacy means the
     update after each drill is closed-form: ``alpha += correct``,
     ``beta += 1 - correct``. This is the standard bandit for
     binary-outcome arms and is provably no-regret.

  2. **SM-2 spaced repetition** over memorized atoms (preflop charts,
     pot-odds ratios). Each card carries (ease_factor, interval_days,
     repetitions). After a graded review the SM-2 formula advances
     interval based on quality and ease; the ease drops when the
     card was hard.

  3. **Glicko-flavored Elo** over scenarios. Both the user and each
     scenario template have a rating. After a drill we update both
     ratings using the standard Elo formula with K-factor tuned for
     fast convergence on tens-of-attempts samples.

All state lives in the player record's ``training_progress.adaptive``
block, persisted via the existing ``DataManager._update_progress``
flow. There is no separate database table; the JSON record grows by
a few KB per player at most.

All math is pure stdlib (math + random). No scipy/numpy.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ---------- Constants ----------

# Default Beta(alpha, beta) prior for a fresh bandit arm. Beta(2, 2)
# starts symmetric around 0.5 but is informative enough that one
# observation doesn't swing the posterior to extremes.
DEFAULT_BETA_ALPHA = 2.0
DEFAULT_BETA_BETA = 2.0

# SM-2 default ease factor (every card starts here). The algorithm
# floors ease at 1.3.
DEFAULT_EASE_FACTOR = 2.5
MIN_EASE_FACTOR = 1.3

# Default Elo settings. K=32 is the classic FIDE K-factor; chosen
# because typical poker training samples are small (tens to low
# hundreds), so we want meaningful movement per attempt.
DEFAULT_ELO_RATING = 1500.0
DEFAULT_K_FACTOR = 32.0

# Topics we expose as bandit arms. Each maps to one of the
# WeaknessType values used by ``training_service``.
DEFAULT_TOPICS = (
    "pot_odds",
    "preflop_ranges",
    "value_betting",
    "bluff_catching",
    "bet_sizing",
    "position_play",
)


# ---------- Dataclasses ----------


@dataclass
class BanditArm:
    """Beta-Binomial posterior for one bandit arm.

    ``alpha`` and ``beta`` are the conjugate-prior parameters. The
    expected accuracy under the posterior is ``alpha / (alpha + beta)``;
    ``pulls`` is the integer count of how many times this arm has
    been queried so the UI can render "X attempts so far".
    """

    topic: str
    alpha: float = DEFAULT_BETA_ALPHA
    beta: float = DEFAULT_BETA_BETA
    pulls: int = 0

    def expected_accuracy(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    def credible_interval(self, *, z: float = 1.96) -> Tuple[float, float]:
        """Normal approximation to the 95% CI of the Beta posterior."""
        mean = self.expected_accuracy()
        a, b = self.alpha, self.beta
        var = (a * b) / (((a + b) ** 2) * (a + b + 1))
        std = math.sqrt(max(0.0, var))
        return max(0.0, mean - z * std), min(1.0, mean + z * std)

    def to_dict(self) -> Dict[str, Any]:
        lo, hi = self.credible_interval()
        return {
            "topic": self.topic,
            "alpha": self.alpha,
            "beta": self.beta,
            "pulls": self.pulls,
            "expected_accuracy": self.expected_accuracy(),
            "ci_lower": lo,
            "ci_upper": hi,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BanditArm":
        return cls(
            topic=str(data.get("topic", "unknown")),
            alpha=float(data.get("alpha", DEFAULT_BETA_ALPHA)),
            beta=float(data.get("beta", DEFAULT_BETA_BETA)),
            pulls=int(data.get("pulls", 0)),
        )


@dataclass
class SrsCard:
    """SM-2 review state for one memorized atom.

    Fields follow the classic SM-2 algorithm:
      - ``ease_factor``: how easy this card is (>= 1.3).
      - ``interval_days``: days until the next review.
      - ``repetitions``: consecutive successful reviews.
      - ``due_at``: ISO timestamp for next review.
      - ``last_quality``: quality rating from the most recent review
        (0=blackout to 5=perfect).
    """

    card_id: str
    ease_factor: float = DEFAULT_EASE_FACTOR
    interval_days: float = 0.0
    repetitions: int = 0
    due_at: str = ""
    last_quality: int = 0

    def is_due(self, *, now_ts: Optional[float] = None) -> bool:
        if not self.due_at:
            return True
        try:
            due = datetime.fromisoformat(self.due_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        ref_ts = now_ts if now_ts is not None else time.time()
        return due.timestamp() <= ref_ts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "ease_factor": self.ease_factor,
            "interval_days": self.interval_days,
            "repetitions": self.repetitions,
            "due_at": self.due_at,
            "last_quality": self.last_quality,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SrsCard":
        return cls(
            card_id=str(data.get("card_id", "?")),
            ease_factor=float(data.get("ease_factor", DEFAULT_EASE_FACTOR)),
            interval_days=float(data.get("interval_days", 0.0)),
            repetitions=int(data.get("repetitions", 0)),
            due_at=str(data.get("due_at", "")),
            last_quality=int(data.get("last_quality", 0)),
        )


@dataclass
class EloPlayer:
    """Player-side Elo rating + attempt counter."""

    rating: float = DEFAULT_ELO_RATING
    attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"rating": self.rating, "attempts": self.attempts}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EloPlayer":
        return cls(
            rating=float(data.get("rating", DEFAULT_ELO_RATING)),
            attempts=int(data.get("attempts", 0)),
        )


# ---------- Thompson-sampling bandit ----------


def _beta_sample(alpha: float, beta: float, rng: random.Random) -> float:
    """Sample x ~ Beta(alpha, beta) without scipy.

    Uses the standard ratio-of-gammas approach. Python's
    ``random.gammavariate`` is reliable for alpha, beta >= 0.5 (we
    enforce alpha >= 1 via the priors so this is safe).
    """
    x = rng.gammavariate(max(0.1, alpha), 1.0)
    y = rng.gammavariate(max(0.1, beta), 1.0)
    if x + y <= 0:
        return 0.5
    return x / (x + y)


def thompson_select(
    arms: Sequence[BanditArm],
    *,
    rng: Optional[random.Random] = None,
) -> BanditArm:
    """Pick one arm by Thompson sampling.

    Sample a value from each arm's Beta posterior, then return the
    arm with the **lowest** sampled value. That looks backwards but
    is intentional: arms represent topic *competence*, so the
    least-competent topic is the one we want to drill next. The
    inversion matches the standard 'pull arm with worst current
    estimate' bandit for learning environments.
    """
    if not arms:
        raise ValueError("arms must be non-empty")
    rng = rng or random.Random()
    sampled = [(_beta_sample(a.alpha, a.beta, rng), a) for a in arms]
    sampled.sort(key=lambda pair: pair[0])
    return sampled[0][1]


def bandit_update(arm: BanditArm, *, correct: bool) -> BanditArm:
    """Conjugate Beta-Binomial update for one observation."""
    arm.alpha += 1.0 if correct else 0.0
    arm.beta += 0.0 if correct else 1.0
    arm.pulls += 1
    return arm


# ---------- SM-2 spaced repetition ----------


def sm2_update(card: SrsCard, *, quality: int, now_ts: Optional[float] = None) -> SrsCard:
    """Apply one SM-2 update with a 0-5 quality rating.

    Quality semantics (SM-2):
      - 5: perfect response
      - 4: correct with hesitation
      - 3: correct with serious difficulty
      - 2: incorrect, easy to recall when shown
      - 1: incorrect, hard to recall
      - 0: complete blackout

    Quality < 3 resets repetitions to 0 and re-queues the card for
    same-day review. Quality >= 3 advances by the ease-factor-scaled
    interval.
    """
    quality = max(0, min(5, int(quality)))

    if quality < 3:
        card.repetitions = 0
        card.interval_days = 0.0
    else:
        if card.repetitions == 0:
            card.interval_days = 1.0
        elif card.repetitions == 1:
            card.interval_days = 6.0
        else:
            card.interval_days = card.interval_days * card.ease_factor
        card.repetitions += 1

    # Standard SM-2 ease update:
    # EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
    delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    card.ease_factor = max(MIN_EASE_FACTOR, card.ease_factor + delta)
    card.last_quality = quality

    ref_ts = now_ts if now_ts is not None else time.time()
    next_due_ts = ref_ts + card.interval_days * 86400.0
    card.due_at = datetime.fromtimestamp(next_due_ts, tz=timezone.utc).isoformat()
    return card


def cards_due_for_review(
    cards: Sequence[SrsCard], *, now_ts: Optional[float] = None
) -> List[SrsCard]:
    return [c for c in cards if c.is_due(now_ts=now_ts)]


# ---------- Elo difficulty ----------


def elo_expected(rating_a: float, rating_b: float) -> float:
    """Standard Elo expected-score formula."""
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))


def elo_update(
    player_rating: float,
    scenario_rating: float,
    *,
    player_won: bool,
    k_factor: float = DEFAULT_K_FACTOR,
) -> Tuple[float, float]:
    """Return updated (player_rating, scenario_rating) after one match.

    ``player_won`` is True when the drill was answered correctly. Both
    ratings shift by symmetric amounts: the player's rating goes up
    when they solve a hard scenario, the scenario's rating goes up
    when it stumps the player.
    """
    expected_player = elo_expected(player_rating, scenario_rating)
    score = 1.0 if player_won else 0.0
    delta = k_factor * (score - expected_player)
    return player_rating + delta, scenario_rating - delta


def select_scenario_near(
    scenarios: Sequence[Dict[str, Any]],
    *,
    player_rating: float,
    window: float = 200.0,
    rng: Optional[random.Random] = None,
) -> Optional[Dict[str, Any]]:
    """Pick a scenario whose Elo rating is near the player's.

    Filters to scenarios within ``window`` rating points of the
    player. Returns the closest match by default; with multiple
    equally-close matches, samples one randomly to add variety.
    """
    if not scenarios:
        return None
    rng = rng or random.Random()
    eligible = [
        s for s in scenarios
        if abs(float(s.get("elo_rating", DEFAULT_ELO_RATING)) - player_rating) <= window
    ]
    if not eligible:
        eligible = list(scenarios)
    # Closest by absolute rating distance.
    eligible.sort(
        key=lambda s: abs(float(s.get("elo_rating", DEFAULT_ELO_RATING)) - player_rating)
    )
    # If multiple share the tightest distance, pick one uniformly.
    best = eligible[0]
    best_dist = abs(float(best.get("elo_rating", DEFAULT_ELO_RATING)) - player_rating)
    tied = [
        s for s in eligible
        if abs(float(s.get("elo_rating", DEFAULT_ELO_RATING)) - player_rating) == best_dist
    ]
    return rng.choice(tied)


# ---------- Persistent state container ----------


@dataclass
class AdaptiveState:
    """Per-player adaptive engine state.

    Roundtrips to/from a JSON-friendly dict so the existing
    DataManager._update_progress(player, callback) flow can store
    it without any schema change.
    """

    bandit: Dict[str, BanditArm]
    cards: Dict[str, SrsCard]
    player_elo: EloPlayer
    scenario_elos: Dict[str, float]

    @classmethod
    def fresh(cls, topics: Sequence[str] = DEFAULT_TOPICS) -> "AdaptiveState":
        return cls(
            bandit={t: BanditArm(topic=t) for t in topics},
            cards={},
            player_elo=EloPlayer(),
            scenario_elos={},
        )

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "AdaptiveState":
        if not data:
            return cls.fresh()
        bandit_raw = data.get("bandit") or {}
        if isinstance(bandit_raw, dict):
            bandit = {
                k: BanditArm.from_dict({**(v if isinstance(v, dict) else {}), "topic": k})
                for k, v in bandit_raw.items()
            }
        else:
            bandit = {}
        if not bandit:
            bandit = {t: BanditArm(topic=t) for t in DEFAULT_TOPICS}

        cards_raw = data.get("cards") or {}
        cards = {
            k: SrsCard.from_dict({**(v if isinstance(v, dict) else {}), "card_id": k})
            for k, v in (cards_raw.items() if isinstance(cards_raw, dict) else [])
        }

        elo_player = EloPlayer.from_dict(data.get("player_elo") or {})
        scenario_elos_raw = data.get("scenario_elos") or {}
        scenario_elos = {
            k: float(v) for k, v in scenario_elos_raw.items() if isinstance(v, (int, float))
        }

        return cls(
            bandit=bandit,
            cards=cards,
            player_elo=elo_player,
            scenario_elos=scenario_elos,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bandit": {k: v.to_dict() for k, v in self.bandit.items()},
            "cards": {k: v.to_dict() for k, v in self.cards.items()},
            "player_elo": self.player_elo.to_dict(),
            "scenario_elos": dict(self.scenario_elos),
        }

    # ---- Bandit ----

    def pick_topic(self, *, rng: Optional[random.Random] = None) -> str:
        if not self.bandit:
            return DEFAULT_TOPICS[0]
        arm = thompson_select(list(self.bandit.values()), rng=rng)
        return arm.topic

    def record_topic_result(self, topic: str, *, correct: bool) -> None:
        if topic not in self.bandit:
            self.bandit[topic] = BanditArm(topic=topic)
        bandit_update(self.bandit[topic], correct=correct)

    # ---- SRS ----

    def ensure_card(self, card_id: str) -> SrsCard:
        card = self.cards.get(card_id)
        if card is None:
            card = SrsCard(card_id=card_id)
            self.cards[card_id] = card
        return card

    def review_card(
        self, card_id: str, *, quality: int, now_ts: Optional[float] = None
    ) -> SrsCard:
        card = self.ensure_card(card_id)
        sm2_update(card, quality=quality, now_ts=now_ts)
        return card

    def due_cards(self, *, now_ts: Optional[float] = None) -> List[SrsCard]:
        return cards_due_for_review(list(self.cards.values()), now_ts=now_ts)

    # ---- Elo ----

    def player_rating(self) -> float:
        return self.player_elo.rating

    def scenario_rating(self, scenario_id: str) -> float:
        return self.scenario_elos.get(scenario_id, DEFAULT_ELO_RATING)

    def record_scenario_outcome(
        self, scenario_id: str, *, player_won: bool, k_factor: float = DEFAULT_K_FACTOR
    ) -> None:
        scenario_rating = self.scenario_rating(scenario_id)
        new_player, new_scenario = elo_update(
            self.player_elo.rating,
            scenario_rating,
            player_won=player_won,
            k_factor=k_factor,
        )
        self.player_elo.rating = new_player
        self.player_elo.attempts += 1
        self.scenario_elos[scenario_id] = new_scenario


# ---------- DataManager integration ----------


_ADAPTIVE_KEY = "adaptive"


def load_state(record: Optional[Dict[str, Any]]) -> AdaptiveState:
    """Pull AdaptiveState out of a player record (or initialize fresh)."""
    if not isinstance(record, dict):
        return AdaptiveState.fresh()
    progress = record.get("training_progress") or {}
    if not isinstance(progress, dict):
        return AdaptiveState.fresh()
    return AdaptiveState.from_dict(progress.get(_ADAPTIVE_KEY))


def save_state(progress: Dict[str, Any], state: AdaptiveState) -> None:
    """Write AdaptiveState back into a mutable training_progress dict."""
    if not isinstance(progress, dict):
        return
    progress[_ADAPTIVE_KEY] = state.to_dict()


# ---------- Public summary shape ----------


def progression_summary(state: AdaptiveState) -> Dict[str, Any]:
    """Return a serializable summary for the frontend dashboard.

    Includes:
      - Per-topic Beta posterior + 95% CI (so the UI can render
        "topic X: 62% [49-74%] from 18 attempts").
      - Number of SRS cards due now and total card count.
      - Player Elo rating + attempt count.
    """
    arms = sorted(
        state.bandit.values(),
        key=lambda a: a.expected_accuracy(),
    )
    due = state.due_cards()
    return {
        "bandit": [a.to_dict() for a in arms],
        "next_topic": arms[0].topic if arms else None,
        "srs": {
            "total_cards": len(state.cards),
            "due_count": len(due),
            "due_card_ids": [c.card_id for c in due][:25],
        },
        "elo": {
            "player_rating": round(state.player_elo.rating, 1),
            "attempts": state.player_elo.attempts,
            "tracked_scenarios": len(state.scenario_elos),
        },
    }
