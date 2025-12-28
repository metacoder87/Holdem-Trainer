"""
Hand history replay utilities for PyHoldem Pro.

Consumes the per-hand dictionaries recorded by SessionTracker and stored in
DataManager's per-player JSONL hand history.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


class HandReplayer:
    """Terminal hand-history replayer (street-by-street)."""

    def __init__(self, *, hero_name: str):
        self.hero_name = str(hero_name or "").strip() or "Hero"

    def replay(
        self,
        hand: Dict[str, Any],
        *,
        input_handler: Optional[Any] = None,
        mode: str = "street",
    ) -> None:
        if not isinstance(hand, dict):
            print("Invalid hand record.")
            return

        mode = str(mode or "street").lower()
        if mode not in {"street", "print"}:
            mode = "street"

        self._print_header(hand)

        if mode == "print":
            self._print_entire_hand(hand)
            return

        self._replay_by_street(hand, input_handler=input_handler)

    def _print_header(self, hand: Dict[str, Any]) -> None:
        meta = hand.get("meta") if isinstance(hand.get("meta"), dict) else {}

        hand_no = hand.get("hand_number", "?")
        started_at = hand.get("started_at") or meta.get("started_at")
        game_type = meta.get("game_type", "?")
        limit_type = meta.get("limit_type", "?")
        sb = meta.get("small_blind", "?")
        bb = meta.get("big_blind", "?")
        ante = meta.get("ante", 0) or 0
        blind_level = meta.get("blind_level")

        print("\n" + "-" * 70)
        title = f"Hand {hand_no}"
        if started_at:
            title += f"  ({started_at})"
        print(title)

        blinds = f"{sb}/{bb}"
        if ante:
            blinds += f" (Ante {ante})"
        if blind_level:
            blinds += f"  |  Level {blind_level}"

        print(f"{game_type} / {limit_type}  |  Blinds: {blinds}")

        hero_cards = hand.get("hero_hole_cards") or meta.get("hero_hole_cards") or []
        if isinstance(hero_cards, Sequence) and hero_cards:
            print(f"{self.hero_name} hole cards: {' '.join(str(c) for c in hero_cards)}")

        players = meta.get("players")
        if isinstance(players, list) and players:
            stacks = []
            for p in players:
                if not isinstance(p, dict):
                    continue
                name = p.get("name", "?")
                stack = p.get("stack_start")
                if stack is None:
                    continue
                marker = "*" if name == self.hero_name or p.get("is_hero") else ""
                stacks.append(f"{name}{marker}:{int(stack)}")
            if stacks:
                print("Stacks: " + "  ".join(stacks))

        print("-" * 70)

    def _print_entire_hand(self, hand: Dict[str, Any]) -> None:
        self._print_actions(hand, input_handler=None)
        self._print_decisions(hand)
        self._print_result(hand)

    def _replay_by_street(self, hand: Dict[str, Any], *, input_handler: Optional[Any]) -> None:
        streets = ("preflop", "flop", "turn", "river")
        actions = hand.get("actions") or []
        if not isinstance(actions, list):
            actions = []

        grouped: Dict[str, List[Dict[str, Any]]] = {street: [] for street in streets}
        for entry in actions:
            if not isinstance(entry, dict):
                continue
            street = entry.get("betting_round")
            if street in grouped:
                grouped[street].append(entry)

        board_by_street = hand.get("board_by_street") if isinstance(hand.get("board_by_street"), dict) else {}
        final_board = hand.get("board") if isinstance(hand.get("board"), list) else []

        for street in streets:
            board_snapshot = self._board_for_street(
                street, board_by_street=board_by_street, final_board=final_board
            )
            if board_snapshot:
                print(f"\nBoard ({street}): {' '.join(board_snapshot)}")

            if grouped.get(street):
                print(f"\nActions ({street}):")
                self._print_actions_for_street(hand, grouped[street], street)

            if input_handler is not None:
                try:
                    input_handler.wait_for_enter("Press Enter to continue...")
                except Exception:
                    input("Press Enter to continue...")
            else:
                input("Press Enter to continue...")

        self._print_decisions(hand)
        self._print_result(hand)

    def _board_for_street(
        self,
        street: str,
        *,
        board_by_street: Dict[str, Any],
        final_board: List[Any],
    ) -> List[str]:
        if street == "preflop":
            return []

        snapshot = board_by_street.get(street)
        if isinstance(snapshot, list) and snapshot:
            return [str(c) for c in snapshot]

        # Fallback for older records.
        if not final_board:
            return []
        if street == "flop" and len(final_board) >= 3:
            return [str(c) for c in final_board[:3]]
        if street == "turn" and len(final_board) >= 4:
            return [str(c) for c in final_board[:4]]
        if street == "river" and len(final_board) >= 5:
            return [str(c) for c in final_board[:5]]
        return [str(c) for c in final_board]

    def _print_actions_for_street(
        self,
        hand: Dict[str, Any],
        actions: List[Dict[str, Any]],
        street: str,
    ) -> None:
        decisions = hand.get("decision_points") or []
        if not isinstance(decisions, list):
            decisions = []

        decision_index = 0
        for entry in actions:
            line = self._format_action(entry)
            print("  " + line)

            if (
                entry.get("player") == self.hero_name
                and entry.get("action") in {"fold", "check", "call", "raise", "all_in"}
            ):
                decision = self._next_matching_decision(decisions, start_index=decision_index, street=street)
                if decision is not None:
                    decision_index = decision.get("_next_index", decision_index)
                    self._print_decision_inline(decision)

    def _format_action(self, action: Dict[str, Any]) -> str:
        player = action.get("player", "?")
        name = action.get("action", "?")
        amount = int(action.get("amount", 0) or 0)
        pot_before = int(action.get("pot_before", 0) or 0)
        pot_after = action.get("pot_after")
        if pot_after is None:
            pot_after = pot_before + amount
        pot_after = int(pot_after or 0)

        if amount > 0:
            return f"{player} {name} {amount}  (pot {pot_before} → {pot_after})"
        return f"{player} {name}  (pot {pot_before} → {pot_after})"

    def _next_matching_decision(
        self,
        decisions: List[Any],
        *,
        start_index: int,
        street: str,
    ) -> Optional[Dict[str, Any]]:
        idx = int(start_index)
        while idx < len(decisions):
            candidate = decisions[idx]
            idx += 1
            if not isinstance(candidate, dict):
                continue
            if candidate.get("betting_round") != street:
                continue
            candidate = dict(candidate)
            candidate["_next_index"] = idx
            return candidate
        return None

    def _print_decision_inline(self, decision: Dict[str, Any]) -> None:
        quality = decision.get("quality", "ungraded")
        rec = decision.get("recommended_action")
        chosen = decision.get("chosen_action")
        to_call = decision.get("to_call")
        pot_total = decision.get("pot_total")
        equity = decision.get("equity")
        req = decision.get("required_equity")

        parts = [f"Decision: {chosen} (grade: {quality})"]
        if rec:
            parts.append(f"rec: {rec}")
        if pot_total is not None and to_call is not None and int(to_call) > 0:
            parts.append(f"pot: {int(pot_total)} call: {int(to_call)}")
        if equity is not None and req is not None:
            parts.append(f"eq: {float(equity)*100:.1f}% req: {float(req)*100:.1f}%")

        print("    -> " + " | ".join(parts))

    def _print_actions(self, hand: Dict[str, Any], *, input_handler: Optional[Any]) -> None:
        actions = hand.get("actions") or []
        if not isinstance(actions, list) or not actions:
            print("No actions recorded.")
            return

        print("\nActions:")
        for entry in actions:
            if not isinstance(entry, dict):
                continue
            print("  " + self._format_action(entry))

    def _print_decisions(self, hand: Dict[str, Any]) -> None:
        decisions = hand.get("decision_points") or []
        if not isinstance(decisions, list) or not decisions:
            return

        print("\nDecision points:")
        for d in decisions:
            if not isinstance(d, dict):
                continue
            number = d.get("decision_number", "?")
            street = d.get("betting_round", "?")
            chosen = d.get("chosen_action", "?")
            quality = d.get("quality", "ungraded")
            rec = d.get("recommended_action")
            rec_str = f" (rec: {rec})" if rec else ""
            print(f"  {number}. {street}: {chosen} [{quality}]{rec_str}")

    def _print_result(self, hand: Dict[str, Any]) -> None:
        winners = hand.get("winners") or []
        pot_total = hand.get("pot_total", 0)
        if isinstance(winners, list) and winners:
            print("\nResult:")
            print(f"  Winners: {', '.join(str(w) for w in winners)}")
            print(f"  Pot: {int(pot_total or 0)}")

