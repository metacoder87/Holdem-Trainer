"""
AI Player module for PyHoldem Pro.
Implements different AI playing styles and decision-making logic.
"""
import random
from enum import Enum
from functools import lru_cache
from typing import Tuple, Dict, List, Optional
from game.player import Player, PlayerAction
from game.card import Card, Rank
from game.hand import Hand


@lru_cache(maxsize=4096)
def _cached_villain_bucket(
    hole_repr: Tuple[str, str],
    board_repr: Tuple[str, ...],
    num_buckets: int,
    bucketing: str,
    potential_weight: float,
) -> Optional[int]:
    """LRU-cached bucket call keyed by str(card) tuples.

    ``bucketing`` is part of the cache key so the same (hole, board)
    can have legitimately different bucket IDs under "plain" vs
    "potential" weighting.
    """
    try:
        # Late imports: keep ai_player free of cfr dependency on import.
        from cfr.abstractions.hand_bucketing import (
            hand_bucket,
            potential_aware_bucket,
        )

        hole = [_parse_card_repr(c) for c in hole_repr]
        board = [_parse_card_repr(c) for c in board_repr]
        if bucketing == "potential":
            return potential_aware_bucket(
                hole,
                board,
                num_buckets=num_buckets,
                weight=potential_weight,
                rng=random.Random(0x60A1),
            )
        return hand_bucket(
            hole,
            board,
            num_buckets=num_buckets,
            rng=random.Random(0x60A1),
        )
    except Exception:
        return None


def _parse_card_repr(card_str: str) -> Card:
    """Inverse of str(Card). Used only by the cached bucket helper."""
    from game.card import Suit  # local import to avoid cyclic concerns

    cleaned = card_str.strip()
    suit_glyphs = {"♥": "h", "♦": "d", "♣": "c", "♠": "s"}
    for glyph, letter in suit_glyphs.items():
        cleaned = cleaned.replace(glyph, letter)
    suit_letter = cleaned[-1].lower()
    rank_part = cleaned[:-1].upper()
    rank_map = {
        "2": Rank.TWO, "3": Rank.THREE, "4": Rank.FOUR, "5": Rank.FIVE,
        "6": Rank.SIX, "7": Rank.SEVEN, "8": Rank.EIGHT, "9": Rank.NINE,
        "10": Rank.TEN, "T": Rank.TEN,
        "J": Rank.JACK, "Q": Rank.QUEEN, "K": Rank.KING, "A": Rank.ACE,
    }
    suit_map = {"h": Suit.HEARTS, "d": Suit.DIAMONDS, "c": Suit.CLUBS, "s": Suit.SPADES}
    return Card(suit_map[suit_letter], rank_map[rank_part])


def _round_to_nearest_5(amount):
    return int(round(amount / 5)) * 5


class AIStyle(Enum):
    """Enumeration for AI playing styles."""
    CAUTIOUS = "cautious"
    WILD = "wild"
    BALANCED = "balanced"
    RANDOM = "random"
    GTO = "gto"  # Samples actions from a precomputed CFR+ policy.


class AIPlayer(Player):
    """Base class for AI players."""
    
    def __init__(self, name: str, bankroll: int, ai_style: AIStyle):
        """
        Initialize an AI player.
        
        Args:
            name: Player name
            bankroll: Starting bankroll
            ai_style: The AI's playing style
        """
        super().__init__(name, int(bankroll))
        self.ai_style = ai_style
        self.is_ai = True
    
    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """
        Make a decision based on game state.
        
        Args:
            game_state: Current game information
            
        Returns:
            Tuple of (action, amount)
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("AI subclasses must implement make_decision")
    
    def __str__(self) -> str:
        """Return string representation including AI style."""
        base_str = super().__str__()
        return f"{base_str} [AI: {self.ai_style.name}]"


class CautiousAI(AIPlayer):
    """Cautious/tight AI player implementation."""
    
    def __init__(self, name: str, bankroll: int):
        """Initialize a cautious AI player."""
        super().__init__(name, bankroll, AIStyle.CAUTIOUS)
        self.fold_threshold = 0.35  # Fold 35% of the time with marginal hands
        self.raise_threshold = 0.85  # Only raise with top 15% of hands
    
    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """
        Make a cautious decision based on game state.
        
        Cautious players:
        - Fold often with weak hands
        - Rarely bluff
        - Only raise with strong hands
        - Consider position heavily
        """
        pot_size = game_state.get('pot_size', 0)
        current_bet = game_state.get('current_bet', 0)
        min_raise = game_state.get('min_raise', 0)
        players_in_hand = game_state.get('players_in_hand', 2)
        community_cards = game_state.get('community_cards', [])
        betting_round = game_state.get('betting_round', 'preflop')
        
        # Evaluate hand strength
        hand_strength = self._evaluate_hand_strength(community_cards)
        
        # Position adjustment (late position is stronger)
        position_bonus = 0.05 * (self.position / 9)  # 0-5% bonus for position
        adjusted_strength = hand_strength + position_bonus

        # All-in with very strong hand
        if adjusted_strength > 0.95 and self.bankroll > 0:
            return PlayerAction.ALL_IN, self.bankroll
        
        # Cautious preflop play
        if betting_round == 'preflop':
            if adjusted_strength < 0.4:
                return PlayerAction.FOLD, 0
            elif adjusted_strength < 0.7:
                if current_bet <= self.bankroll * 0.05:  # Call small bets
                    return PlayerAction.CALL, current_bet
                else:
                    return PlayerAction.FOLD, 0
            else:
                # Strong hand
                if random.random() < 0.3:  # Occasionally raise with strong hands
                    raise_amount = min(current_bet + min_raise, self.bankroll * 0.1)
                    raise_amount = _round_to_nearest_5(raise_amount)
                    if raise_amount > current_bet:
                        return PlayerAction.RAISE, raise_amount
                return PlayerAction.CALL, current_bet
        
        # Post-flop play
        else:
            # Check if we can check
            if current_bet == 0:
                if adjusted_strength > 0.6:
                    # Sometimes bet with good hands
                    if random.random() < 0.4:
                        bet_amount = min(pot_size * 0.3, self.bankroll * 0.05)
                        if bet_amount == 0 and pot_size == 0:
                            bet_amount = game_state.get('big_blind', 10)
                        
                        bet_amount = _round_to_nearest_5(bet_amount)
                        if bet_amount > 0:
                            return PlayerAction.RAISE, bet_amount
                return PlayerAction.CHECK, 0
            
            # Facing a bet
            pot_odds = current_bet / (pot_size + current_bet) if (pot_size + current_bet) > 0 else 0
            
            if adjusted_strength < pot_odds:
                return PlayerAction.FOLD, 0
            elif adjusted_strength > 0.8:
                # Very strong hand, consider raising
                if random.random() < 0.25:
                    raise_amount = min(current_bet + min_raise, self.bankroll * 0.1)
                    raise_amount = _round_to_nearest_5(raise_amount)
                    if raise_amount > current_bet:
                        return PlayerAction.RAISE, raise_amount
            
            return PlayerAction.CALL, current_bet
    
    def _evaluate_hand_strength(self, community_cards: List[Card]) -> float:
        """
        Evaluate hand strength (0-1 scale).
        
        Args:
            community_cards: Community cards on the table
            
        Returns:
            Strength value between 0 and 1
        """
        if not self.hole_cards:
            return 0.5
        
        # Preflop hand strength based on hole cards
        if not community_cards:
            return self._evaluate_preflop_strength()
        
        # Post-flop: evaluate actual hand
        all_cards = self.hole_cards + community_cards
        if len(all_cards) >= 5:
            hand = Hand.best_hand_from_cards(all_cards)
            # Map hand rank to strength (simplified)
            rank_strength = {
                1: 0.1,   # High card
                2: 0.3,   # Pair
                3: 0.45,  # Two pair
                4: 0.6,   # Three of a kind
                5: 0.7,   # Straight
                6: 0.75,  # Flush
                7: 0.85,  # Full house
                8: 0.95,  # Four of a kind
                9: 0.98,  # Straight flush
                10: 1.0   # Royal flush
            }
            return rank_strength.get(hand.rank.value, 0.5)
        
        return 0.5
    
    def _evaluate_preflop_strength(self) -> float:
        """Evaluate preflop hand strength based on hole cards."""
        if len(self.hole_cards) != 2:
            return 0.5
        
        card1, card2 = self.hole_cards
        
        # Pocket pairs
        if card1.rank == card2.rank:
            # Higher pairs are stronger
            return 0.6 + (card1.rank.value / 14) * 0.3
        
        # Suited cards
        suited = card1.suit == card2.suit
        suited_bonus = 0.05 if suited else 0
        
        # High cards
        high_card_value = max(card1.rank.value, card2.rank.value) / 14
        low_card_value = min(card1.rank.value, card2.rank.value) / 14
        
        # Connected cards (for straight potential)
        gap = abs(card1.rank.value - card2.rank.value)
        connected_bonus = 0.05 if gap == 1 else 0.03 if gap == 2 else 0
        
        # Calculate overall strength
        strength = (high_card_value * 0.6 + low_card_value * 0.2 + 
                   suited_bonus + connected_bonus)
        
        return min(strength, 1.0)


class WildAI(AIPlayer):
    """Wild/aggressive AI player implementation."""
    
    def __init__(self, name: str, bankroll: int):
        """Initialize a wild AI player."""
        super().__init__(name, bankroll, AIStyle.WILD)
        self.bluff_frequency = 0.25  # Bluff 25% of the time
        self.aggression_factor = 2.0  # Bet/raise twice as often as call
    
    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """
        Make an aggressive decision based on game state.
        
        Wild players:
        - Bluff frequently
        - Raise aggressively
        - Rarely fold with any potential
        - Try to intimidate opponents
        """
        pot_size = game_state.get('pot_size', 0)
        current_bet = game_state.get('current_bet', 0)
        min_raise = game_state.get('min_raise', 0)
        players_in_hand = game_state.get('players_in_hand', 2)
        
        # Wild players are less concerned with hand strength
        aggression_roll = random.random()

        # Chance to go all-in
        if aggression_roll < 0.05 and self.bankroll > 0: # 5% chance to just shove it all in
            return PlayerAction.ALL_IN, self.bankroll
        
        # Check if we can be aggressive
        if current_bet == 0:
            # No bet to face - bet/raise aggressively
            if aggression_roll < 0.6:  # 60% of the time, bet
                bet_amount = min(pot_size * random.uniform(0.5, 1.2), self.bankroll * 0.2)
                if bet_amount == 0 and pot_size == 0:
                    bet_amount = game_state.get('big_blind', 10)
                
                bet_amount = _round_to_nearest_5(bet_amount)
                if bet_amount > 0:
                    return PlayerAction.RAISE, bet_amount
            return PlayerAction.CHECK, 0
        
        # Facing a bet
        if aggression_roll < 0.3:  # 30% raise/re-raise
            raise_amount = min(current_bet * random.uniform(2, 3), self.bankroll * 0.3)
            raise_amount = _round_to_nearest_5(raise_amount)
            if raise_amount > current_bet + min_raise:
                return PlayerAction.RAISE, raise_amount
        
        if aggression_roll < 0.7:  # 40% call (total 70%)
            return PlayerAction.CALL, current_bet
        
        # Only fold 30% of the time with terrible hands
        if self._has_any_potential():
            return PlayerAction.CALL, current_bet
        
        return PlayerAction.FOLD, 0
    
    def _has_any_potential(self) -> bool:
        """Check if hand has any potential (wild players see potential everywhere)."""
        if not self.hole_cards:
            return False
        
        # Wild players think any face card or pair has potential
        for card in self.hole_cards:
            if card.rank.value >= 11:  # J, Q, K, A
                return True
        
        # Or if cards are suited/connected
        if len(self.hole_cards) == 2:
            if self.hole_cards[0].suit == self.hole_cards[1].suit:
                return True
            if abs(self.hole_cards[0].rank.value - self.hole_cards[1].rank.value) <= 3:
                return True
        
        return random.random() < 0.4  # 40% chance to play anyway


class BalancedAI(AIPlayer):
    """Balanced/mathematical AI player implementation."""
    
    def __init__(self, name: str, bankroll: int):
        """Initialize a balanced AI player."""
        super().__init__(name, bankroll, AIStyle.BALANCED)
        self.pot_odds_threshold = 0.0
        self.equity_calculator = None  # Would implement equity calculation
    
    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """
        Make a balanced decision based on game state and mathematics.
        
        Balanced players:
        - Use pot odds and equity calculations
        - Mix aggression with caution
        - Adapt to opponents
        - Play position well
        """
        pot_size = game_state.get('pot_size', 0)
        current_bet = game_state.get('current_bet', 0)
        min_raise = game_state.get('min_raise', 0)
        call_amount = game_state.get('call_amount', current_bet)
        
        # Calculate pot odds
        pot_odds = self.calculate_pot_odds(game_state)
        
        # Estimate hand equity (simplified)
        hand_equity = self._estimate_equity(game_state)
        
        # Position factor
        position_factor = self.position / 9

        # Consider all-in with very high equity
        if hand_equity > 0.9 and pot_odds < 0.5 and self.bankroll > 0:
            return PlayerAction.ALL_IN, self.bankroll
        
        # Decision based on pot odds vs equity
        if current_bet == 0:
            # Can check or bet
            if hand_equity > 0.6:
                # Good hand, value bet
                bet_size = pot_size * (0.5 + hand_equity * 0.5)
                if bet_size == 0 and pot_size == 0:
                    bet_size = game_state.get('big_blind', 10)
                
                bet_size = _round_to_nearest_5(min(bet_size, self.bankroll * 0.15))
                if bet_size > 0:
                    return PlayerAction.RAISE, bet_size
            elif hand_equity > 0.4 and position_factor > 0.6:
                # Decent hand in position, sometimes bet
                if random.random() < 0.3:
                    bet_size = pot_size * 0.3
                    if bet_size == 0 and pot_size == 0:
                        bet_size = game_state.get('big_blind', 10)
                    
                    bet_size = _round_to_nearest_5(min(bet_size, self.bankroll * 0.1))
                    if bet_size > 0:
                        return PlayerAction.RAISE, bet_size
            return PlayerAction.CHECK, 0
        
        # Facing a bet - compare pot odds to equity
        if hand_equity > pot_odds + 0.1:
            # Strong equity advantage, consider raising
            if random.random() < hand_equity * 0.5:
                raise_amount = current_bet + min_raise * (1 + hand_equity)
                raise_amount = _round_to_nearest_5(min(raise_amount, self.bankroll * 0.2))
                if raise_amount > current_bet:
                    return PlayerAction.RAISE, raise_amount
            return PlayerAction.CALL, current_bet
        elif hand_equity > pot_odds - 0.05:
            # Close decision, usually call
            return PlayerAction.CALL, current_bet
        else:
            # Poor pot odds
            return PlayerAction.FOLD, 0
    
    def calculate_pot_odds(self, game_state: Dict) -> float:
        """Calculate pot odds for current decision."""
        pot_size = game_state.get('pot_size', 0)
        call_amount = game_state.get('call_amount', game_state.get('current_bet', 0))
        
        if call_amount == 0:
            return 0.0
        
        return call_amount / (pot_size + call_amount)
    
    def _estimate_equity(self, game_state: Dict) -> float:
        """Estimate hand equity via proper multiway Monte Carlo.

        Track 5: replaces the legacy ``base_strength ** (n - 1)``
        heuristic which ignored card removal entirely. We now call
        the Monte Carlo equity calculator in ``poker.range_equity``
        which respects card removal and supports variable opponent
        counts.

        The Monte Carlo path is wrapped in a try/except so test
        environments with mocked cards don't crash; on any failure
        we fall back to the legacy heuristic.
        """
        community_cards = game_state.get('community_cards', []) or []
        players_in_hand = max(2, int(game_state.get('players_in_hand', 2) or 2))

        if not self.hole_cards or len(self.hole_cards) != 2:
            return 0.5

        try:
            from poker.range_equity import equity_for_hand_vs_uniform

            n_opponents = max(1, players_in_hand - 1)
            # Cap opponent count to keep the MC fast on multi-way
            # tables; equity vs 6+ uniform random opponents is
            # essentially flat anyway.
            n_opponents = min(n_opponents, 5)
            # Trial count tuned for postflop quality without
            # blowing the AI think-time budget.
            trials = 300 if community_cards else 500
            equity = equity_for_hand_vs_uniform(
                self.hole_cards,
                board=community_cards,
                n_opponents=n_opponents,
                trials=trials,
            )
            return max(0.0, min(1.0, float(equity)))
        except Exception:
            # Fallback to the legacy heuristic on any error (mocked
            # Card objects in tests, etc.).
            base_strength = self._evaluate_hand_strength(community_cards)
            return base_strength ** (players_in_hand - 1)
    
    def _evaluate_hand_strength(self, community_cards: List[Card]) -> float:
        """Evaluate hand strength for equity calculation."""
        if not community_cards:
            # Preflop - use starting hand strength
            return self._preflop_hand_strength()
        
        # Post-flop - evaluate made hand
        all_cards = self.hole_cards + community_cards
        if len(all_cards) >= 5:
            hand = Hand.best_hand_from_cards(all_cards)
            # Convert hand rank to equity estimate - better mapping
            rank_to_strength = {
                1: 0.15,  # High card
                2: 0.40,  # Pair
                3: 0.55,  # Two pair
                4: 0.70,  # Three of a kind
                5: 0.75,  # Straight
                6: 0.80,  # Flush
                7: 0.88,  # Full house
                8: 0.95,  # Four of a kind
                9: 0.98,  # Straight flush
                10: 1.0   # Royal flush
            }
            return rank_to_strength.get(hand.rank.value, 0.5)
        
        return 0.5
    
    def _preflop_hand_strength(self) -> float:
        """Calculate preflop hand strength."""
        if len(self.hole_cards) != 2:
            return 0.5
        
        card1, card2 = self.hole_cards
        
        # Pocket pairs
        if card1.rank == card2.rank:
            return 0.5 + card1.rank.value * 0.03
        
        # High cards
        high_value = max(card1.rank.value, card2.rank.value)
        low_value = min(card1.rank.value, card2.rank.value)
        
        # Suited bonus
        suited = 0.1 if card1.suit == card2.suit else 0
        
        # Connected bonus
        gap = abs(card1.rank.value - card2.rank.value)
        connected = 0.05 if gap <= 2 else 0
        
        return (high_value * 0.04 + low_value * 0.02 + suited + connected)


class RandomAI(AIPlayer):
    """Random/unpredictable AI player implementation."""
    
    def __init__(self, name: str, bankroll: int):
        """Initialize a random AI player."""
        super().__init__(name, bankroll, AIStyle.RANDOM)
        self.randomness_factor = 0.8  # 80% random decisions
    
    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """
        Make a random decision with minimal logic.
        
        Random players:
        - Make unpredictable decisions
        - Simulate beginners who don't know strategy
        - Sometimes make brilliant plays by accident
        - Sometimes make terrible plays
        """
        current_bet = game_state.get('current_bet', 0)
        pot_size = game_state.get('pot_size', 0)
        min_raise = game_state.get('min_raise', 0)
        
        # Random decision
        decision_roll = random.random()

        # Chance to go all-in
        if decision_roll < 0.02 and self.bankroll > 0: # 2% chance to just shove it all in
            return PlayerAction.ALL_IN, self.bankroll
        
        if current_bet == 0:
            # Can check or bet
            if decision_roll < 0.6:
                return PlayerAction.CHECK, 0
            else:
                # Random bet size
                bet_size = random.uniform(0.1, 0.5) * pot_size if pot_size > 0 else 10
                bet_size = _round_to_nearest_5(min(bet_size, self.bankroll * 0.2))
                return PlayerAction.RAISE, bet_size
        else:
            # Facing a bet
            if decision_roll < 0.25:
                return PlayerAction.FOLD, 0
            elif decision_roll < 0.6:
                return PlayerAction.CALL, current_bet
            else:
                # Random raise
                raise_multiplier = random.uniform(1.5, 3)
                raise_amount = current_bet * raise_multiplier
                raise_amount = _round_to_nearest_5(min(raise_amount, self.bankroll * 0.3))
                if raise_amount > current_bet + min_raise:
                    return PlayerAction.RAISE, raise_amount
                return PlayerAction.CALL, current_bet


class GTOAIPlayer(BalancedAI):
    """Solver-driven AI villain.

    On each decision the player tries to look up a cached CFR+ policy
    for the current spot and sample an action from it. Two failure
    modes fall back to the BalancedAI parent decision logic:

      1. The spot has no cached policy (uncovered board / pot / SPR).
      2. The cached policy has no entry for the player's hand bucket.

    ``epsilon`` adds exploration noise on top of the GTO mixed
    strategy: with probability ``epsilon`` the player samples
    uniformly across legal actions instead of from the policy. This
    is useful for training (so the human sees more variety) and
    matches the standard epsilon-greedy off-equilibrium pattern.

    Construction is lazy with respect to the cfr package - the
    imports happen at first decision so games without CFR available
    still spin up a player (they just always hit the fallback path).
    """

    def __init__(
        self,
        name: str,
        bankroll: int,
        *,
        epsilon: float = 0.05,
        cache_root: Optional[str] = None,
    ) -> None:
        super().__init__(name, bankroll)
        self.ai_style = AIStyle.GTO
        self.epsilon = max(0.0, min(1.0, float(epsilon)))
        # cache_root is None -> use advisor's default (backend/cfr_artifacts).
        self._cache_root = cache_root
        self._cache = None  # type: ignore[var-annotated]
        # Track how many decisions resolved from cache vs fallback.
        self.gto_hits = 0
        self.gto_misses = 0

    # ---------- Lazy cache + cfr-package wiring ----------

    def _get_cache(self):
        """Open the cache on first use; return None if unavailable."""
        if self._cache is not None:
            return self._cache
        try:
            from cfr.cache import SolverCache  # local import; optional dep
            from pathlib import Path

            if self._cache_root is None:
                # Mirror the default in gto_advisor: <repo>/backend/cfr_artifacts.
                # We compute it relative to this file rather than rely on
                # the advisor's importability.
                default_root = (
                    Path(__file__).resolve().parents[2]
                    / "backend"
                    / "cfr_artifacts"
                )
                self._cache = SolverCache.open(default_root)
            else:
                self._cache = SolverCache.open(self._cache_root)
        except Exception:
            self._cache = None
        return self._cache

    # ---------- Decision path ----------

    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """Try cached GTO sampling first; fall back to BalancedAI on miss."""
        action = self._try_gto_decision(game_state)
        if action is not None:
            self.gto_hits += 1
            return action
        self.gto_misses += 1
        return super().make_decision(game_state)

    def _try_gto_decision(
        self, game_state: Dict
    ) -> Optional[Tuple[PlayerAction, float]]:
        """Return a sampled (action, amount) from cache, or None on miss."""
        cache = self._get_cache()
        if cache is None:
            return None
        try:
            from cfr.spot import SpotKey
        except Exception:
            return None

        # Build a SpotKey from villain's perspective. We construct a
        # decision-shaped dict because SpotKey.from_decision already
        # implements the right field-to-bucket mapping.
        pot_total = int(game_state.get("pot_size") or 0)
        current_bet = int(game_state.get("current_bet") or 0)
        call_amount = int(
            game_state.get("call_amount", current_bet - int(self.current_bet or 0))
        )
        can_check = call_amount <= 0
        community = list(game_state.get("community_cards") or [])
        big_blind = int(game_state.get("big_blind") or 1)

        villain_decision = {
            "betting_round": game_state.get("betting_round"),
            "pot_total": pot_total,
            "hero_stack": int(self.bankroll),
            "hero_position": int(self.position or 0),
            "to_call": max(0, call_amount),
            "can_check": bool(can_check),
            "board": [str(c) for c in community],
            "hero_hole_cards": [str(c) for c in (self.hole_cards or [])],
        }
        spot = SpotKey.from_decision(villain_decision, big_blind=big_blind)
        if spot is None or not cache.has(spot):
            return None
        policy = cache.get(spot)
        if policy is None:
            return None

        # Bucket count + method are meta-stored on the cache entry.
        entry = cache.entry(spot)
        meta = entry.meta if (entry and entry.meta) else {}
        try:
            from cfr.abstractions.hand_bucketing import (
                DEFAULT_BUCKETS,
                DEFAULT_POTENTIAL_WEIGHT,
            )

            num_buckets = int(meta.get("num_buckets") or DEFAULT_BUCKETS)
            default_weight = DEFAULT_POTENTIAL_WEIGHT
        except Exception:
            num_buckets = 10
            default_weight = 0.5

        bucketing = str(meta.get("bucketing") or "plain").lower()
        if bucketing not in {"plain", "potential"}:
            bucketing = "plain"
        try:
            potential_weight = float(
                meta.get("potential_weight") or default_weight
            )
        except (TypeError, ValueError):
            potential_weight = default_weight

        # Compute the villain's hand bucket via the module-level
        # LRU cache so repeated decisions on the same flop don't
        # re-run Monte Carlo equity.
        hole_repr = tuple(str(c) for c in (self.hole_cards or []))
        if len(hole_repr) != 2:
            return None
        board_repr = tuple(str(c) for c in community)
        bucket = _cached_villain_bucket(
            hole_repr,
            board_repr,
            num_buckets,
            bucketing,
            potential_weight,
        )
        if bucket is None:
            return None

        # Infer history (mirrors gto_advisor._infer_history).
        if call_amount > 0:
            history = "r"
        elif can_check and int(self.position or 0) == 0:
            history = ""
        elif can_check:
            history = "k"
        else:
            return None

        probs = policy.probs(f"b={bucket}|h={history}")
        if not probs:
            return None

        # Epsilon-greedy: sometimes ignore policy and explore uniformly
        # over legal actions for variety.
        if random.random() < self.epsilon:
            return None  # falls back to BalancedAI -> natural variety

        # Sample a fine-grained action from the policy distribution.
        actions, weights = zip(*probs.items())
        try:
            chosen = random.choices(actions, weights=weights)[0]
        except (ValueError, IndexError):
            return None

        return self._cfr_action_to_engine(
            chosen,
            pot_total=pot_total,
            current_bet=current_bet,
            call_amount=call_amount,
            big_blind=big_blind,
        )

    # ---------- CFR -> engine action mapping ----------

    def _cfr_action_to_engine(
        self,
        cfr_action: str,
        *,
        pot_total: int,
        current_bet: int,
        call_amount: int,
        big_blind: int,
    ) -> Optional[Tuple[PlayerAction, float]]:
        """Translate a CFR action name back to an engine (PlayerAction, amount)."""
        if cfr_action == "FOLD":
            # Don't fold for free if we can check.
            if call_amount <= 0:
                return PlayerAction.CHECK, 0
            return PlayerAction.FOLD, 0

        if cfr_action == "CHECK_OR_CALL":
            if call_amount <= 0:
                return PlayerAction.CHECK, 0
            return PlayerAction.CALL, current_bet

        if cfr_action == "ALL_IN":
            return PlayerAction.ALL_IN, self.bankroll

        if cfr_action.startswith("RAISE_"):
            # Action name is "RAISE_<fraction>" (e.g. RAISE_0.66).
            try:
                frac = float(cfr_action.split("_", 1)[1])
            except (IndexError, ValueError):
                frac = 0.66  # safe default
            raise_amount = max(
                current_bet + max(big_blind, 1),
                int(round(frac * (pot_total + call_amount))),
            )
            raise_amount = min(raise_amount, self.bankroll)
            raise_amount = _round_to_nearest_5(raise_amount)
            if raise_amount <= current_bet:
                # Can't actually raise — fall back to call/check.
                return (
                    (PlayerAction.CHECK, 0)
                    if call_amount <= 0
                    else (PlayerAction.CALL, current_bet)
                )
            return PlayerAction.RAISE, raise_amount

        # Unknown action -> fall back.
        return None


def create_ai_player(name: str, bankroll: int, style: AIStyle) -> AIPlayer:
    """
    Factory function to create AI players.

    Args:
        name: Player name
        bankroll: Starting bankroll
        style: AI playing style

    Returns:
        AI player instance
    """
    if style == AIStyle.CAUTIOUS:
        return CautiousAI(name, bankroll)
    elif style == AIStyle.WILD:
        return WildAI(name, bankroll)
    elif style == AIStyle.BALANCED:
        return BalancedAI(name, bankroll)
    elif style == AIStyle.RANDOM:
        return RandomAI(name, bankroll)
    elif style == AIStyle.GTO:
        return GTOAIPlayer(name, bankroll)
    else:
        raise ValueError(f"Unknown AI style: {style}")


def create_ai_players_for_table(count: int, bankroll: int) -> List[AIPlayer]:
    """
    Create multiple AI players with mixed styles.
    
    Args:
        count: Number of AI players to create
        bankroll: Starting bankroll for each player
        
    Returns:
        List of AI players
    """
    ai_players = []
    styles = list(AIStyle)
    
    for i in range(count):
        # Mix of styles with some randomness
        if i < len(styles):
            style = styles[i]
        else:
            style = random.choice(styles)
        
        name = f"AI_{style.value.capitalize()}_{i+1}"
        ai_player = create_ai_player(name, bankroll, style)
        ai_players.append(ai_player)
    
    # Shuffle to randomize seating
    random.shuffle(ai_players)
    
    return ai_players
