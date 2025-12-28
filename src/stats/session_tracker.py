"""
Session tracking utilities for PyHoldem Pro.

This module records per-hand actions and aggregates per-session statistics used by
the training/progression systems (VPIP, PFR, aggression factor, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SessionMetrics:
    """Aggregated session metrics for a single player."""

    player_name: str
    game_type: str
    limit_type: str
    bankroll_start: int
    bankroll_end: int
    small_blind: int
    big_blind: int
    buy_in: Optional[int] = None
    starting_chips: Optional[int] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: Optional[str] = None

    hands_played: int = 0
    hands_won: int = 0

    vpip_hands: int = 0
    pfr_hands: int = 0

    postflop_calls: int = 0
    postflop_raises: int = 0

    quizzes_total: int = 0
    quizzes_correct: int = 0
    pot_odds_quizzes: int = 0
    pot_odds_quizzes_correct: int = 0

    decisions_total: int = 0
    decisions_optimal: int = 0

    biggest_pot: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metrics to a JSON-friendly dictionary."""
        hands = self.hands_played or 0

        vpip = self.vpip_hands / hands if hands > 0 else 0.0
        pfr = self.pfr_hands / hands if hands > 0 else 0.0
        aggression_factor = (
            (self.postflop_raises / self.postflop_calls)
            if self.postflop_calls > 0
            else (float("inf") if self.postflop_raises > 0 else 0.0)
        )

        winrate = self.hands_won / hands if hands > 0 else 0.0

        pot_odds_accuracy = (
            self.pot_odds_quizzes_correct / self.pot_odds_quizzes
            if self.pot_odds_quizzes > 0
            else None
        )

        quiz_accuracy = (
            self.quizzes_correct / self.quizzes_total if self.quizzes_total > 0 else None
        )

        decision_accuracy = (
            self.decisions_optimal / self.decisions_total
            if self.decisions_total > 0
            else None
        )

        return {
            "player_name": self.player_name,
            "game_type": self.game_type,
            "limit_type": self.limit_type,
            "bankroll_start": int(self.bankroll_start),
            "bankroll_end": int(self.bankroll_end),
            "profit": int(self.bankroll_end) - int(self.bankroll_start),
            "small_blind": int(self.small_blind),
            "big_blind": int(self.big_blind),
            "buy_in": int(self.buy_in) if self.buy_in is not None else None,
            "starting_chips": int(self.starting_chips) if self.starting_chips is not None else None,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "hands_played": int(self.hands_played),
            "hands_won": int(self.hands_won),
            "winrate": winrate,
            "vpip": vpip,
            "pfr": pfr,
            "aggression_factor": aggression_factor,
            "biggest_pot": int(self.biggest_pot),
            "quizzes_total": int(self.quizzes_total),
            "quizzes_correct": int(self.quizzes_correct),
            "quiz_accuracy": quiz_accuracy,
            "pot_odds_quizzes": int(self.pot_odds_quizzes),
            "pot_odds_quizzes_correct": int(self.pot_odds_quizzes_correct),
            "pot_odds_accuracy": pot_odds_accuracy,
            "decisions_total": int(self.decisions_total),
            "decisions_optimal": int(self.decisions_optimal),
            "decision_accuracy": decision_accuracy,
        }


class SessionTracker:
    """
    Records per-hand actions and aggregates per-session metrics for one player.

    The tracker is intentionally conservative in what it records so that it can
    be used both for gameplay analytics and as input to the adaptive training
    pipeline.
    """

    def __init__(self, player_name: str):
        self.player_name = player_name
        self._metrics: Optional[SessionMetrics] = None
        self._hand_number = 0
        self._hand_vpip = False
        self._hand_pfr = False
        self._hand_decision_number = 0
        self.hand_history: List[Dict[str, Any]] = []

    @property
    def active(self) -> bool:
        return self._metrics is not None

    @property
    def metrics(self) -> Optional[SessionMetrics]:
        return self._metrics

    def start_session(
        self,
        *,
        game_type: str,
        limit_type: str,
        bankroll_start: int,
        small_blind: int,
        big_blind: int,
        buy_in: Optional[int] = None,
        starting_chips: Optional[int] = None,
    ) -> None:
        self._metrics = SessionMetrics(
            player_name=self.player_name,
            game_type=game_type,
            limit_type=limit_type,
            bankroll_start=int(bankroll_start),
            bankroll_end=int(bankroll_start),
            small_blind=int(small_blind),
            big_blind=int(big_blind),
            buy_in=int(buy_in) if buy_in is not None else None,
            starting_chips=int(starting_chips) if starting_chips is not None else None,
        )
        self._hand_number = 0
        self.hand_history = []

    def start_hand(
        self,
        *,
        hero_hole_cards: Optional[List[str]] = None,
        hand_meta: Optional[Dict[str, Any]] = None,
    ) -> int:
        if self._metrics is None:
            raise RuntimeError("Session has not been started")

        self._hand_number += 1
        self._hand_vpip = False
        self._hand_pfr = False
        self._hand_decision_number = 0

        record: Dict[str, Any] = {
            "hand_number": self._hand_number,
            "started_at": datetime.now().isoformat(),
            "hero_hole_cards": hero_hole_cards or [],
            "meta": dict(hand_meta) if isinstance(hand_meta, dict) else {},
            "board": [],
            "board_by_street": {},
            "actions": [],
            "decision_points": [],
            "winners": [],
            "pot_total": 0,
        }
        self.hand_history.append(record)
        return self._hand_number

    def set_board(self, board_cards: List[str]) -> None:
        if not self.hand_history:
            return

        cards = list(board_cards)
        self.hand_history[-1]["board"] = cards

        board_by_street = self.hand_history[-1].setdefault("board_by_street", {})
        if not isinstance(board_by_street, dict):
            board_by_street = {}
            self.hand_history[-1]["board_by_street"] = board_by_street

        if len(cards) == 3:
            board_by_street["flop"] = cards
        elif len(cards) == 4:
            board_by_street["turn"] = cards
        elif len(cards) == 5:
            board_by_street["river"] = cards

    def record_action(
        self,
        *,
        player_name: str,
        action: str,
        amount: int,
        pot_before: int,
        betting_round: str,
        did_raise: bool = False,
    ) -> None:
        if self._metrics is None or not self.hand_history:
            return

        pot_before_int = int(pot_before)
        amount_int = int(amount)
        self.hand_history[-1]["actions"].append(
            {
                "player": player_name,
                "action": action,
                "amount": amount_int,
                "pot_before": pot_before_int,
                "pot_after": pot_before_int + amount_int,
                "betting_round": betting_round,
                "did_raise": bool(did_raise),
            }
        )

        if player_name != self.player_name:
            return

        # VPIP / PFR are preflop-only.
        if betting_round == "preflop":
            if amount > 0 and action in {"call", "raise", "all_in"}:
                if not self._hand_vpip:
                    self._metrics.vpip_hands += 1
                    self._hand_vpip = True
            if did_raise and action in {"raise", "all_in"}:
                if not self._hand_pfr:
                    self._metrics.pfr_hands += 1
                    self._hand_pfr = True
            return

        # Postflop aggression: (raises)/(calls). (We count "bet" as a raise in the engine.)
        if action == "call" and amount > 0:
            self._metrics.postflop_calls += 1
        elif action in {"raise", "all_in"} and amount > 0:
            if did_raise:
                self._metrics.postflop_raises += 1

    def record_decision(self, decision: Dict[str, Any]) -> None:
        """Record a graded decision point for the current hand."""
        if not self.hand_history or not isinstance(decision, dict):
            return

        self._hand_decision_number += 1
        payload = dict(decision)
        payload.setdefault("decision_number", self._hand_decision_number)
        self.hand_history[-1].setdefault("decision_points", []).append(payload)

        if self._metrics is None:
            return

        self._metrics.decisions_total += 1
        if payload.get("quality") == "optimal":
            self._metrics.decisions_optimal += 1

    def end_hand(self, *, winners: List[str], pot_total: int) -> None:
        if self._metrics is None or not self.hand_history:
            return

        self._metrics.hands_played += 1
        if self.player_name in winners:
            self._metrics.hands_won += 1

        self._metrics.biggest_pot = max(self._metrics.biggest_pot, int(pot_total))

        self.hand_history[-1]["winners"] = list(winners)
        self.hand_history[-1]["pot_total"] = int(pot_total)
        self.hand_history[-1]["ended_at"] = datetime.now().isoformat()

    def record_quiz_result(self, *, quiz_type: str, correct: bool) -> None:
        if self._metrics is None:
            return

        self._metrics.quizzes_total += 1
        if correct:
            self._metrics.quizzes_correct += 1

        if quiz_type == "pot_odds":
            self._metrics.pot_odds_quizzes += 1
            if correct:
                self._metrics.pot_odds_quizzes_correct += 1

    def finalize(self, *, bankroll_end: int) -> Dict[str, Any]:
        if self._metrics is None:
            raise RuntimeError("Session has not been started")

        self._metrics.bankroll_end = int(bankroll_end)
        self._metrics.ended_at = datetime.now().isoformat()
        return self._metrics.to_dict()
