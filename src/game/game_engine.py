"""
Game Engine module for PyHoldem Pro.
Orchestrates the main game flow, betting rounds, and hand completion.
"""
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any
import random

from game.deck import Deck
from game.player import Player, PlayerAction
from game.ai_player import AIPlayer, AIStyle, create_ai_player
from game.table import Table, TableType
from game.pot import Pot
from game.hand import Hand
from game.card import Card
from stats.session_tracker import SessionTracker


class GameState(Enum):
    """Enum representing the current state of the game."""
    WAITING = "waiting"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    HAND_COMPLETE = "hand_complete"


class BettingRound(Enum):
    """Enum representing the current betting round."""
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class GameEngine:
    """
    Main game engine that orchestrates poker game flow.
    Handles game setup, betting rounds, card dealing, and hand completion.
    """

    LIMIT_MAX_BETS_PER_ROUND = 4

    def __init__(self, human_player: Player, data_manager, display, input_handler):
        """
        Initialize the game engine.
        
        Args:
            human_player: The human player
            data_manager: Manager for data persistence
            display: UI display handler
            input_handler: User input handler
        """
        self.human_player = human_player
        self.data_manager = data_manager
        self.display = display
        self.input_handler = input_handler
        
        # Game state
        self.game_state = GameState.WAITING
        self.current_betting_round: Optional[BettingRound] = None
        
        # Game components
        self.table: Optional[Table] = None
        self.pot: Optional[Pot] = None
        self.deck: Optional[Deck] = None
        
        # Game settings
        self.small_blind = 0
        self.big_blind = 0
        self.ante = 0
        self.limit_type = "no_limit"
        self.tournament_mode = False
        self.blind_level = 1
        self._tournament_hands_per_level = 20
        self._tournament_blind_increase_factor = 1.5
        self._tournament_ante_start_level = 3
        self._tournament_ante_bb_fraction = 0.1
        self._tournament_elimination_order: List[str] = []
        self._tournament_buy_in: Optional[int] = None
        self._tournament_starting_chips: Optional[int] = None
        self._tournament_total_players: Optional[int] = None
        self._tournament_prize_pool: Optional[int] = None
        self._tournament_cash_bankroll_after_buy_in: Optional[int] = None

        # Training / analytics
        self.training_enabled = False
        self.in_game_quizzes_enabled = False
        self.hud_enabled = False
        self.post_hand_feedback_enabled = False
        self._trainer = None
        self._hud = None
        self._hand_analyzer = None
        self.session_tracker = SessionTracker(self.human_player.name)
        
        # Community cards
        self.community_cards: List[Card] = []
        
        # Statistics
        self.hands_played = 0

        # Betting round state (used for correct raise rules)
        self._min_raise_increment = 0
        self._raises_in_round = 0
        self._raise_closed_players = set()
        self._game_analyzer = None
        self._decision_analyzer = None

    def _is_fixed_limit(self) -> bool:
        return str(self.limit_type).lower() in {"limit", "fixed_limit", "fixed-limit"}

    def _get_limit_bet_size(self, betting_round: BettingRound) -> int:
        base = int(self.big_blind)
        if betting_round in {BettingRound.TURN, BettingRound.RIVER}:
            return base * 2
        return base

    def _reset_betting_round_state(self, betting_round: BettingRound, *, starting_highest_bet: int) -> None:
        self._raise_closed_players = set()

        if self._is_fixed_limit():
            self._min_raise_increment = self._get_limit_bet_size(betting_round)
            # In fixed-limit preflop the big blind counts as the first bet.
            if betting_round == BettingRound.PREFLOP and starting_highest_bet > 0:
                self._raises_in_round = 1
            else:
                self._raises_in_round = 0
            return

        # No-limit: minimum raise starts at the big blind and becomes the last full raise size.
        self._min_raise_increment = int(self.big_blind)
        self._raises_in_round = 0

    def _is_raise_allowed_for_player(self, player: Player) -> bool:
        if player in self._raise_closed_players:
            return False
        if self._is_fixed_limit() and self._raises_in_round >= self.LIMIT_MAX_BETS_PER_ROUND:
            return False
        return True
        
    def start_game(self, game_config: Dict[str, Any]) -> None:
        """
        Start a new game with the given configuration.
        
        Args:
            game_config: Dictionary containing game settings
        """
        game_type = game_config.get('type', 'cash')
        self.limit_type = game_config.get("limit", "no_limit")
        self.training_enabled = bool(game_config.get("training", False))
        self.in_game_quizzes_enabled = bool(
            game_config.get("in_game_quizzes", self.training_enabled)
        )
        self.hud_enabled = bool(game_config.get("hud", self.training_enabled))
        self.post_hand_feedback_enabled = bool(
            game_config.get("post_hand_feedback", self.training_enabled)
        )

        if self.training_enabled:
            # Lazy import to keep core gameplay independent from training.
            from training.trainer import PokerTrainer

            self._trainer = PokerTrainer()
            self._trainer.enable_training()

            if self.hud_enabled:
                try:
                    from training.hud import TrainerHUD

                    self._hud = TrainerHUD()
                    self._hud.enable()
                    hud_mode = game_config.get("hud_mode", "basic")
                    if isinstance(hud_mode, str):
                        self._hud.set_display_mode(hud_mode)
                except Exception:
                    self._hud = None
            else:
                self._hud = None

            if self.post_hand_feedback_enabled:
                try:
                    from training.analyzer import HandAnalyzer

                    self._hand_analyzer = HandAnalyzer()
                except Exception:
                    self._hand_analyzer = None
            else:
                self._hand_analyzer = None
        else:
            self._trainer = None
            self._hud = None
            self._hand_analyzer = None
        
        if game_type == 'cash':
            self._start_cash_game(game_config)
        elif game_type == 'tournament':
            self._start_tournament(game_config)
        elif game_type == "training":
            # Training sessions are orchestrated by main.py (menu-driven).
            return
            
    def _start_cash_game(self, config: Dict[str, Any]) -> None:
        """Start a cash game."""
        small_blind = config.get('small_blind', 10)
        big_blind = config.get('big_blind', 20)
        max_players = config.get('max_players', 9)  # Allow up to 9 players total
        
        # Get number of opponents from input handler
        num_opponents = int(self.input_handler.get_number_input(
            f"How many opponents (1-{max_players-1})? ",
            1, max_players - 1,
            integer_only=True
        ))
        
        self._setup_cash_game_table(num_opponents, small_blind, big_blind)
        self.tournament_mode = False

        self.session_tracker.start_session(
            game_type="cash",
            limit_type=self.limit_type,
            bankroll_start=int(self.human_player.bankroll),
            small_blind=int(self.small_blind),
            big_blind=int(self.big_blind),
        )
        
        # Start the game loop (unless in test mode)
        if not getattr(self, '_test_mode', False):
            self.run_game_loop()
        
    def _start_tournament(self, config: Dict[str, Any]) -> None:
        """Start a tournament."""
        buy_in = int(config.get('buy_in', 1000))
        starting_chips = config.get('starting_chips')
        if starting_chips is None:
            starting_chips = buy_in * 10
        starting_chips = int(starting_chips)

        # Tournament structure configuration (no prompting here; main.py can supply values)
        self._tournament_hands_per_level = int(
            config.get("hands_per_level", config.get("blind_increase_interval_hands", self._tournament_hands_per_level))
        )
        self._tournament_blind_increase_factor = float(
            config.get("blind_increase_factor", self._tournament_blind_increase_factor)
        )
        self._tournament_ante_start_level = int(
            config.get("ante_start_level", self._tournament_ante_start_level)
        )
        self._tournament_ante_bb_fraction = float(
            config.get("ante_bb_fraction", self._tournament_ante_bb_fraction)
        )
        starting_small_blind = int(config.get("tournament_small_blind", 25))
        starting_big_blind = int(config.get("tournament_big_blind", 50))
        self._tournament_elimination_order = []

        if buy_in <= 0:
            raise ValueError("Tournament buy-in must be positive")
        if starting_chips <= 0:
            raise ValueError("Tournament starting chips must be positive")
        
        # Get number of opponents
        num_opponents = int(self.input_handler.get_number_input(
            "How many opponents (1-8)? ",
            1, 8,
            integer_only=True
        ))

        cash_bankroll_before = int(self.human_player.bankroll)
        if cash_bankroll_before < buy_in:
            print(
                f"\n❌ Insufficient bankroll for tournament buy-in (${buy_in:.0f}). "
                f"Your bankroll: ${cash_bankroll_before:.0f}"
            )
            return

        self._tournament_buy_in = buy_in
        self._tournament_starting_chips = starting_chips
        self._tournament_total_players = num_opponents + 1
        self._tournament_prize_pool = buy_in * self._tournament_total_players
        self._tournament_cash_bankroll_after_buy_in = cash_bankroll_before - buy_in

        try:
            self._setup_tournament_table(
                num_opponents,
                starting_chips,
                small_blind=starting_small_blind,
                big_blind=starting_big_blind,
            )
        except Exception:
            self._tournament_buy_in = None
            self._tournament_starting_chips = None
            self._tournament_total_players = None
            self._tournament_prize_pool = None
            self._tournament_cash_bankroll_after_buy_in = None
            self.human_player.bankroll = cash_bankroll_before
            raise

        self.tournament_mode = True
        self._update_tournament_ante()

        self.session_tracker.start_session(
            game_type="tournament",
            limit_type=self.limit_type,
            bankroll_start=int(cash_bankroll_before),
            small_blind=int(self.small_blind),
            big_blind=int(self.big_blind),
            buy_in=int(buy_in),
            starting_chips=int(starting_chips),
        )
        
        # Start the game loop (unless in test mode)
        if not getattr(self, '_test_mode', False):
            self.run_game_loop()
        
    def _setup_cash_game_table(self, num_opponents: int, small_blind: int, big_blind: int) -> None:
        """
        Set up a table for cash game.
        
        Args:
            num_opponents: The number of AI opponents
            small_blind: Small blind amount
            big_blind: Big blind amount
        """
        self.small_blind = small_blind
        self.big_blind = big_blind
        
        # Create table
        self.table = Table(table_type=TableType.CASH_GAME, max_players=num_opponents + 1)
        
        # Add human player
        self.table.add_player(self.human_player)
        
        # Add AI opponents
        ai_styles = [AIStyle.CAUTIOUS, AIStyle.WILD, AIStyle.BALANCED, AIStyle.RANDOM]
        for i in range(num_opponents):
            ai_style = ai_styles[i % len(ai_styles)]
            ai_player = create_ai_player(f"AI_{i+1}", self.human_player.bankroll, ai_style)
            self.table.add_player(ai_player)
            
        # Create pot
        self.pot = Pot()
        
        # Create deck
        self.deck = Deck()
        
    def _setup_tournament_table(
        self,
        num_opponents: int,
        starting_chips: int,
        *,
        small_blind: int = 25,
        big_blind: int = 50,
    ) -> None:
        """
        Set up a table for tournament.
        
        Args:
            num_opponents: The number of AI opponents
            starting_chips: Tournament starting stack
        """
        # Set initial blinds
        self.small_blind = int(small_blind)
        self.big_blind = int(big_blind)
        self.blind_level = 1
        self.ante = 0
        
        # Create table
        self.table = Table(table_type=TableType.TOURNAMENT, max_players=num_opponents + 1)

        # Set human player chips
        self.human_player.bankroll = starting_chips
        
        # Add human player
        self.table.add_player(self.human_player)
        
        # Add AI opponents
        ai_styles = [AIStyle.CAUTIOUS, AIStyle.WILD, AIStyle.BALANCED, AIStyle.RANDOM]
        for i in range(num_opponents):
            ai_style = ai_styles[i % len(ai_styles)]
            ai_player = create_ai_player(f"AI_{i+1}", starting_chips, ai_style)
            self.table.add_player(ai_player)
            
        # Create pot
        self.pot = Pot()
        
        # Create deck
        self.deck = Deck()
        
    def _deal_hole_cards(self) -> None:
        """Deal hole cards to all players."""
        self.deck.shuffle()
        
        print("\n" + "="*70)
        print("🎲 DEALING HOLE CARDS...")
        
        for player in self.table.get_players_in_order():
            cards = self.deck.deal_cards(2)
            player.deal_hole_cards(cards)
            if player == self.human_player:
                print(f"   Your cards: {cards[0]} {cards[1]}")
        print("="*70)
            
    def _post_blinds(self) -> None:
        """Post small and big blinds."""
        sb_player = self.table.get_small_blind_player()
        bb_player = self.table.get_big_blind_player()

        ante = int(getattr(self, "ante", 0) or 0) if self.tournament_mode else 0

        print("\n💰 POSTING BLINDS:")
        if self.tournament_mode:
            level_line = f"   Level {self.blind_level}: {int(self.small_blind)}/{int(self.big_blind)}"
            if ante > 0:
                level_line += f" (Ante ${ante})"
            print(level_line)

        if ante > 0:
            print("   Collecting antes...")
            for player in self.table.get_players_in_order():
                if player.bankroll <= 0:
                    continue
                pot_before = self.pot.total if self.pot else 0
                paid = player.pay_ante(ante)
                if paid <= 0:
                    continue
                self.pot.add_bet(player, paid)
                if player != self.human_player:
                    print(f"   {player.name} posts ante: ${paid:.0f}")
                self.session_tracker.record_action(
                    player_name=player.name,
                    action="ante",
                    amount=int(paid),
                    pot_before=int(pot_before),
                    betting_round="preflop",
                    did_raise=False,
                )
        
        # Small blind
        if sb_player.bankroll > 0:
            sb_amount = min(self.small_blind, sb_player.bankroll)
            if sb_amount > 0:
                pot_before = self.pot.total if self.pot else 0
                if sb_player.bankroll <= self.small_blind:
                    sb_player.go_all_in()
                    print(f"   {sb_player.name} goes all-in for the small blind: ${sb_amount:.0f}")
                else:
                    sb_player.place_bet(self.small_blind)
                    print(f"   {sb_player.name} posts small blind: ${self.small_blind:.0f}")
                self.pot.add_bet(sb_player, sb_amount)
                self.session_tracker.record_action(
                    player_name=sb_player.name,
                    action="small_blind",
                    amount=int(sb_amount),
                    pot_before=int(pot_before),
                    betting_round="preflop",
                    did_raise=False,
                )

        # Big blind
        if bb_player.bankroll > 0:
            bb_amount = min(self.big_blind, bb_player.bankroll)
            if bb_amount > 0:
                pot_before = self.pot.total if self.pot else 0
                if bb_player.bankroll <= self.big_blind:
                    bb_player.go_all_in()
                    print(f"   {bb_player.name} goes all-in for the big blind: ${bb_amount:.0f}")
                else:
                    bb_player.place_bet(self.big_blind)
                    print(f"   {bb_player.name} posts big blind: ${self.big_blind:.0f}")
                self.pot.add_bet(bb_player, bb_amount)
                self.session_tracker.record_action(
                    player_name=bb_player.name,
                    action="big_blind",
                    amount=int(bb_amount),
                    pot_before=int(pot_before),
                    betting_round="preflop",
                    did_raise=False,
                )
        
    def _run_betting_round(self, betting_round: BettingRound) -> None:
        """
        Run a complete betting round.

        Args:
            betting_round: The current betting round
        """
        self.current_betting_round = betting_round

        active_players = [p for p in self.table.get_players_in_order() if not p.folded]
        if len(active_players) < 2:
            return

        highest_bet = max(p.current_bet for p in active_players)
        self._reset_betting_round_state(betting_round, starting_highest_bet=int(highest_bet))

        # Determine starting position (by seat index, 0-8) and map into the
        # compacted players list to handle empty seats (e.g. after eliminations).
        if betting_round == BettingRound.PREFLOP:
            bb_pos = self.table.get_player_position(self.table.get_big_blind_player())
            start_seat = (bb_pos + 1) % 9 if bb_pos is not None else 0
        else:
            dealer_pos = self.table.get_player_position(self.table.get_dealer_player())
            start_seat = (dealer_pos + 1) % 9 if dealer_pos is not None else 0

        players_in_round = self.table.get_players_in_order()
        num_players = len(players_in_round)
        player_index = next((i for i, p in enumerate(players_in_round) if p.position >= start_seat), 0)

        players_acted = {p: False for p in players_in_round}

        action_count = 0
        while action_count < num_players * 2:  # Safety break
            player = players_in_round[player_index]

            if player.folded or player.all_in:
                player_index = (player_index + 1) % num_players
                action_count += 1
                continue

            # Check if round is over
            if self._is_betting_round_complete(players_in_round, players_acted, highest_bet):
                break

            # Get player action
            action, amount = self._get_player_action(player, self.game_state, highest_bet)
            players_acted[player] = True

            # Fixed-limit games cannot legally bet more than the street bet size.
            # Treat "all-in" as an aggressive action (bet/raise) that will be clamped.
            if action == PlayerAction.ALL_IN and self._is_fixed_limit():
                action = PlayerAction.RAISE

            # Process action
            if action == PlayerAction.FOLD:
                pot_before = self.pot.total if self.pot else 0
                player.fold()
                if player != self.human_player:
                    print(f"   {player.name} folds.")
                self.session_tracker.record_action(
                    player_name=player.name,
                    action="fold",
                    amount=0,
                    pot_before=int(pot_before),
                    betting_round=betting_round.value,
                    did_raise=False,
                )
            elif action == PlayerAction.CHECK:
                pot_before = self.pot.total if self.pot else 0
                if player != self.human_player:
                    print(f"   {player.name} checks.")
                self.session_tracker.record_action(
                    player_name=player.name,
                    action="check",
                    amount=0,
                    pot_before=int(pot_before),
                    betting_round=betting_round.value,
                    did_raise=False,
                )
            elif action == PlayerAction.CALL:
                pot_before = self.pot.total if self.pot else 0
                called_amount = player.call(highest_bet)
                self.pot.add_bet(player, called_amount)
                if player != self.human_player:
                    print(f"   {player.name} calls ${called_amount:.0f}.")
                self.session_tracker.record_action(
                    player_name=player.name,
                    action="call",
                    amount=int(called_amount),
                    pot_before=int(pot_before),
                    betting_round=betting_round.value,
                    did_raise=False,
                )
            elif action == PlayerAction.RAISE:
                pot_before = self.pot.total if self.pot else 0
                previous_highest_bet = int(highest_bet)
                previous_min_raise = int(self._min_raise_increment)

                raise_allowed = self._is_raise_allowed_for_player(player)
                raise_to = int(amount)

                if not raise_allowed:
                    action = PlayerAction.CALL

                if action == PlayerAction.RAISE and self._is_fixed_limit():
                    bet_size = int(self._get_limit_bet_size(betting_round))
                    raise_to = bet_size if previous_highest_bet == 0 else previous_highest_bet + bet_size

                max_raise_to = int(player.current_bet + player.bankroll)
                if raise_to > max_raise_to:
                    raise_to = max_raise_to

                min_raise_to = previous_highest_bet + previous_min_raise

                if action == PlayerAction.RAISE:
                    if raise_to <= previous_highest_bet:
                        if getattr(player, "is_ai", False):
                            print(
                                f"   {player.name} attempts an invalid raise to ${raise_to:.0f}. Treating as a call."
                            )
                        action = PlayerAction.CALL
                    elif raise_to < min_raise_to and raise_to < max_raise_to:
                        # Non-all-in raises must meet the min-raise requirement.
                        if getattr(player, "is_ai", False):
                            print(
                                f"   {player.name} attempts an undersized raise to ${raise_to:.0f}. Treating as a call."
                            )
                        action = PlayerAction.CALL

                if action == PlayerAction.CALL:
                    called_amount = player.call(highest_bet)
                    self.pot.add_bet(player, called_amount)
                    if player != self.human_player:
                        print(f"   {player.name} calls ${called_amount:.0f}.")
                    self.session_tracker.record_action(
                        player_name=player.name,
                        action="call",
                        amount=int(called_amount),
                        pot_before=int(pot_before),
                        betting_round=betting_round.value,
                        did_raise=False,
                    )
                else:
                    raised_amount = player.raise_bet(raise_to)
                    self.pot.add_bet(player, raised_amount)

                    new_highest_bet = int(player.current_bet)
                    highest_bet = new_highest_bet

                    raise_size = new_highest_bet - previous_highest_bet
                    full_raise = raise_size >= previous_min_raise

                    if player != self.human_player:
                        verb = "bets" if previous_highest_bet == 0 else "raises to"
                        print(f"   {player.name} {verb} ${new_highest_bet:.0f}.")

                    self.session_tracker.record_action(
                        player_name=player.name,
                        action="raise",
                        amount=int(raised_amount),
                        pot_before=int(pot_before),
                        betting_round=betting_round.value,
                        did_raise=True,
                    )

                    if full_raise:
                        # Full raise reopens action and sets the next minimum raise size.
                        self._min_raise_increment = int(raise_size)
                        self._raise_closed_players = set()
                        if self._is_fixed_limit():
                            self._raises_in_round += 1

                        for p in players_in_round:
                            if not p.all_in:
                                players_acted[p] = False
                        players_acted[player] = True  # Player who raised has acted
                    else:
                        # Non-full raise (typically all-in) does NOT reopen betting
                        # for players who have already acted.
                        for p, acted in players_acted.items():
                            if acted and p is not player:
                                self._raise_closed_players.add(p)
            elif action == PlayerAction.ALL_IN:
                previous_highest_bet = int(highest_bet)
                previous_min_raise = int(self._min_raise_increment)
                max_total_bet = int(player.current_bet + player.bankroll)
                raise_allowed = self._is_raise_allowed_for_player(player)

                # If raising is closed for this player, an all-in that would exceed the
                # current bet is treated as a call instead.
                if max_total_bet > previous_highest_bet and not raise_allowed:
                    pot_before = self.pot.total if self.pot else 0
                    called_amount = player.call(highest_bet)
                    self.pot.add_bet(player, called_amount)
                    if player != self.human_player:
                        print(f"   {player.name} calls ${called_amount:.0f}.")
                    self.session_tracker.record_action(
                        player_name=player.name,
                        action="call",
                        amount=int(called_amount),
                        pot_before=int(pot_before),
                        betting_round=betting_round.value,
                        did_raise=False,
                    )
                else:
                    pot_before = self.pot.total if self.pot else 0
                    all_in_amount = player.go_all_in()
                    self.pot.add_bet(player, all_in_amount)

                    new_total_bet = int(player.current_bet)
                    did_raise = new_total_bet > previous_highest_bet
                    if did_raise:
                        highest_bet = new_total_bet

                        raise_size = new_total_bet - previous_highest_bet
                        full_raise = raise_size >= previous_min_raise

                        if full_raise:
                            self._min_raise_increment = int(raise_size)
                            self._raise_closed_players = set()

                            for p in players_in_round:
                                if not p.all_in:
                                    players_acted[p] = False
                            players_acted[player] = True  # Player who raised has acted
                        else:
                            for p, acted in players_acted.items():
                                if acted and p is not player:
                                    self._raise_closed_players.add(p)

                    if player != self.human_player:
                        print(f"   {player.name} goes all-in with ${all_in_amount:.0f}.")
                    self.session_tracker.record_action(
                        player_name=player.name,
                        action="all_in",
                        amount=int(all_in_amount),
                        pot_before=int(pot_before),
                        betting_round=betting_round.value,
                        did_raise=bool(did_raise),
                    )

            player_index = (player_index + 1) % num_players
            action_count += 1

    def _is_betting_round_complete(self, players: List[Player], players_acted: Dict[Player, bool], highest_bet: float) -> bool:
        """
        Check if the betting round is complete.

        Returns:
            True if betting round is complete, False otherwise
        """
        active_players = [p for p in players if not p.folded]

        if len(active_players) <= 1:
            return True

        # All remaining players must have acted and have the same bet amount
        for player in active_players:
            if not players_acted[player] and not player.all_in:
                return False
            if player.current_bet != highest_bet and not player.all_in:
                return False

        return True
        
    def _get_player_action(self, player: Player, game_state: GameState, highest_bet: float) -> Tuple[PlayerAction, int]:
        """
        Get action from player (human or AI).
        
        Args:
            player: The player to act
            game_state: Current game state
            highest_bet: The highest bet amount in the current round
            
        Returns:
            Tuple of (action, amount)
        """
        if player == self.human_player:
            return self._get_human_player_action(self._get_action_context(player))
        else:
            # AI player - build game state dict
            betting_round = (
                self.current_betting_round.value
                if self.current_betting_round is not None
                else self.game_state.value
            )
            min_raise = int(self._min_raise_increment) if int(self._min_raise_increment) > 0 else int(self.big_blind)
            limit_bet_size = (
                int(self._get_limit_bet_size(self.current_betting_round))
                if self._is_fixed_limit() and self.current_betting_round is not None
                else None
            )
            game_state_info = {
                'community_cards': self.community_cards,
                'pot_size': self.pot.total if self.pot else 0,
                'pot': self.pot.total if self.pot else 0,  # backwards compatibility
                'current_bet': highest_bet,
                'call_amount': max(0, highest_bet - player.current_bet),
                'min_raise': min_raise,
                'small_blind': self.small_blind,
                'big_blind': self.big_blind,
                'betting_round': betting_round,
                'player': player,
                'players_in_hand': len([p for p in self.table.get_players_in_order() if not p.folded]),
                'limit_type': self.limit_type,
                'limit_bet_size': limit_bet_size,
                'raise_allowed': self._is_raise_allowed_for_player(player),
            }
            return player.make_decision(game_state_info)
            
    def _get_action_context(self, player: Optional[Player] = None) -> Dict[str, Any]:
        """Get context for player action decision."""
        if not self.table:
            return {
                "current_bet": 0,
                "min_raise": int(self.big_blind),
                "can_check": True,
                "pot_total": 0,
                "raise_allowed": True,
                "limit_bet_size": None,
            }

        acting_player = player or self.human_player
        highest_bet = max(p.current_bet for p in self.table.get_players_in_order())
        can_check = acting_player.current_bet == highest_bet

        min_raise = int(self._min_raise_increment) if int(self._min_raise_increment) > 0 else int(self.big_blind)
        limit_bet_size = None
        if self._is_fixed_limit() and self.current_betting_round is not None:
            limit_bet_size = int(self._get_limit_bet_size(self.current_betting_round))

        return {
            "current_bet": int(highest_bet),
            "min_raise": int(min_raise),
            "can_check": bool(can_check),
            "pot_total": int(self.pot.total if self.pot else 0),
            "raise_allowed": bool(self._is_raise_allowed_for_player(acting_player)),
            "limit_bet_size": limit_bet_size,
        }
        
    def _get_human_player_action(self, context: Dict[str, Any]) -> Tuple[PlayerAction, int]:
        """
        Get action from human player.
        
        Args:
            context: Action context with current bet, etc.
            
        Returns:
            Tuple of (action, amount)
        """
        current_bet = int(context.get("current_bet", 0) or 0)
        can_check = bool(context.get("can_check", True))
        pot_total = int(context.get("pot_total", 0) or 0)
        call_amount = max(0, current_bet - self.human_player.current_bet)

        if (
            self.training_enabled
            and self.in_game_quizzes_enabled
            and self._trainer is not None
            and call_amount > 0
            and pot_total > 0
            and self._trainer.should_trigger_quiz()
        ):
            self._run_pot_odds_quiz(pot_total=pot_total, bet_to_call=call_amount)

        # Display game state
        print("\n" + "="*70)
        print(f"POT: ${pot_total:.0f}  |  Current Bet: ${current_bet:.0f}")
        print(f"Your Stack: ${self.human_player.bankroll:.0f}  |  Your Bet: ${self.human_player.current_bet:.0f}")
        if self.human_player.hole_cards:
            print(f"\nYour Cards: {self.human_player.hole_cards[0]} {self.human_player.hole_cards[1]}")
        if self.community_cards:
            print(f"Board: {' '.join(str(card) for card in self.community_cards)}")
        print("="*70)

        if self.training_enabled and self.hud_enabled and self._hud is not None:
            try:
                opponent_stats = self._get_opponent_stats_for_hud()
                if opponent_stats:
                    print("\n📌 HUD - Opponent Profiles:")
                    for opponent, stats in opponent_stats.items():
                        print(f"  {self._hud.format_opponent_display(opponent, stats)}")

                if pot_total > 0:
                    print(f"  {self._hud.generate_pot_odds_display(float(pot_total), float(call_amount))}")

                players_in_hand = 0
                if self.table is not None:
                    try:
                        players_in_hand = len(
                            [p for p in self.table.get_players_in_order() if not getattr(p, "folded", False)]
                        )
                    except Exception:
                        players_in_hand = 0

                if self.human_player.hole_cards and (self.community_cards or call_amount > 0):
                    features = self._compute_equity_and_outs(
                        hole_cards=list(self.human_player.hole_cards),
                        community_cards=list(self.community_cards),
                        players_in_hand=int(players_in_hand or 0) or 2,
                    )
                    equity_estimate = float(features.get("equity_estimate", 0.0) or 0.0)
                    if call_amount > 0 and pot_total > 0 and equity_estimate > 0:
                        required_equity = float(call_amount) / float(pot_total + call_amount)
                        print(f"  {self._hud.generate_equity_display(equity_estimate, required_equity)}")

                    outs_info = features.get("outs") if isinstance(features.get("outs"), dict) else {}
                    if outs_info:
                        cards_to_come = int(features.get("cards_to_come", 0) or 0)
                        label = "by river" if cards_to_come == 2 else ("on river" if cards_to_come == 1 else "")
                        parts = []
                        for draw_type, data in outs_info.items():
                            if not isinstance(data, dict):
                                continue
                            outs = int(data.get("outs", 0) or 0)
                            approx_pct = float(data.get("rule_of_2_4_pct", 0.0) or 0.0)
                            if outs > 0:
                                parts.append(f"{draw_type} {outs} (~{approx_pct:.0f}%)")
                        if parts:
                            suffix = f" {label}" if label else ""
                            print(f"  Outs{suffix}: " + ", ".join(parts))
            except Exception:
                pass

        # Dynamically build options
        options = []
        raise_allowed = bool(context.get("raise_allowed", True))
        if can_check:
            options.append(('Check', PlayerAction.CHECK))
        else:
            options.append((f'Call ${call_amount:.0f}', PlayerAction.CALL))

        if raise_allowed:
            if self._is_fixed_limit():
                bet_size = int(context.get("limit_bet_size") or context["min_raise"])
                raise_to = bet_size if can_check else int(current_bet) + bet_size
                if self.human_player.can_raise(raise_to):
                    label = f"Bet ${bet_size:.0f}" if can_check else f"Raise to ${raise_to:.0f}"
                    options.append((label, PlayerAction.RAISE))
            else:
                min_raise_amount = current_bet + context['min_raise']
                if self.human_player.can_raise(min_raise_amount):
                    options.append((f'Raise (min ${min_raise_amount:.0f})', PlayerAction.RAISE))
        options.append(('Fold', PlayerAction.FOLD))
        if self.human_player.bankroll > 0:
            allow_all_in = True
            if self._is_fixed_limit():
                bet_size = int(context.get("limit_bet_size") or context["min_raise"])
                legal_raise_to = bet_size if int(current_bet) == 0 else int(current_bet) + bet_size
                amount_needed_for_raise = max(0, legal_raise_to - int(self.human_player.current_bet))

                if raise_allowed:
                    allow_all_in = int(self.human_player.bankroll) <= amount_needed_for_raise
                else:
                    # If raising is closed/capped, only allow all-in as a short call.
                    allow_all_in = call_amount > 0 and int(self.human_player.bankroll) <= int(call_amount)
            else:
                # No-limit: if raising is closed, all-in is only legal as a short call.
                if not raise_allowed:
                    allow_all_in = call_amount > 0 and int(self.human_player.bankroll) <= int(call_amount)

            if allow_all_in:
                options.append(('All-In', PlayerAction.ALL_IN))

        # Get user choice
        option_strs = [opt[0] for opt in options]
        print("\n🎯 It's your turn to act:")
        choice_idx = self.input_handler.get_menu_choice(option_strs, "What would you like to do") - 1
        
        action = options[choice_idx][1]

        chosen_amount = 0
        result_action = PlayerAction.FOLD
        result_amount = 0

        # Process action
        if action == PlayerAction.CHECK:
            print("✅ You check.")
            chosen_amount = 0
            result_action = PlayerAction.CHECK
            result_amount = 0
        elif action == PlayerAction.FOLD:
            print("❌ You fold.")
            chosen_amount = 0
            result_action = PlayerAction.FOLD
            result_amount = 0
        elif action == PlayerAction.CALL:
            call_amount = current_bet - self.human_player.current_bet
            print(f"✅ You call ${call_amount:.0f}")
            chosen_amount = int(call_amount)
            result_action = PlayerAction.CALL
            result_amount = int(current_bet)
        elif action == PlayerAction.RAISE:
            if self._is_fixed_limit():
                bet_size = int(context.get("limit_bet_size") or context.get("min_raise") or self.big_blind)
                raise_to = bet_size if can_check else int(current_bet) + bet_size
                if can_check:
                    print(f"✅ You bet ${bet_size:.0f}.")
                else:
                    print(f"✅ You raise to ${raise_to:.0f}.")
                chosen_amount = int(raise_to)
                result_action = PlayerAction.RAISE
                result_amount = int(raise_to)
            else:
                min_raise = int(current_bet) + int(context.get("min_raise") or self.big_blind)
                max_raise = int(self.human_player.bankroll + self.human_player.current_bet)

                raise_amount = min_raise
                while True:
                    print(f"\n💰 Raise amount (minimum ${min_raise:.0f}, maximum ${max_raise:.0f})")
                    raise_amount = int(
                        self.input_handler.get_number_input(
                            f"Enter raise amount (must be a multiple of 5): ",
                            min_raise,
                            max_raise,
                            integer_only=True,
                        )
                    )
                    if raise_amount % 5 == 0:
                        break
                    print("Invalid raise amount. Please enter a multiple of 5.")

                print(f"✅ You raise to ${raise_amount:.0f}")
                chosen_amount = int(raise_amount)
                result_action = PlayerAction.RAISE
                result_amount = int(raise_amount)
        elif action == PlayerAction.ALL_IN:
            all_in_amount = int(self.human_player.bankroll)
            print(f"✅ You go all-in with ${all_in_amount:.0f}!")
            chosen_amount = int(all_in_amount)
            result_action = PlayerAction.ALL_IN
            result_amount = int(all_in_amount)

        self._record_human_decision_point(
            context=context,
            chosen_action=result_action,
            chosen_amount=int(chosen_amount),
        )

        return result_action, result_amount

    def _run_pot_odds_quiz(self, *, pot_total: float, bet_to_call: float) -> None:
        if self._trainer is None:
            return

        try:
            from training.trainer import QuizType
        except Exception:
            return

        quiz = self._trainer.generate_quiz(
            QuizType.POT_ODDS,
            pot_size=float(pot_total),
            bet_to_call=float(bet_to_call),
        )

        print("\n" + "-" * 70)
        print(quiz.get("question", "Training quiz"))
        user_answer = self.input_handler.get_number_input(
            "Your answer (%): ",
            min_value=0,
            max_value=100,
            integer_only=True,
        )

        result = self._trainer.evaluate_answer(
            float(quiz.get("correct_answer", 0)),
            float(user_answer) / 100.0,
            tolerance=0.05,
        )
        correct = bool(result.get("correct", False))
        self.session_tracker.record_quiz_result(quiz_type="pot_odds", correct=correct)

        print(result.get("feedback", ""))
        print(quiz.get("explanation", ""))
        print("-" * 70)

    def _get_game_analyzer(self):
        if self._game_analyzer is not None:
            return self._game_analyzer

        try:
            from stats.analyzer import GameAnalyzer

            self._game_analyzer = GameAnalyzer()
        except Exception:
            self._game_analyzer = None
        return self._game_analyzer

    def _get_decision_analyzer(self):
        if self._decision_analyzer is not None:
            return self._decision_analyzer

        try:
            from training.analyzer import HandAnalyzer

            self._decision_analyzer = HandAnalyzer()
        except Exception:
            self._decision_analyzer = None
        return self._decision_analyzer

    def _compute_equity_and_outs(
        self,
        *,
        hole_cards: List[Card],
        community_cards: List[Card],
        players_in_hand: int,
    ) -> Dict[str, Any]:
        """Compute quick equity + outs features for training (best-effort)."""
        if len(hole_cards) != 2:
            return {
                "hand_strength": 0.0,
                "hand_potential": 0.0,
                "equity_estimate": 0.0,
                "cards_to_come": 0,
                "outs": {},
            }

        try:
            from stats.calculator import HandOddsCalculator

            hand_strength = float(HandOddsCalculator.calculate_hand_strength(hole_cards, community_cards))
            hand_potential = float(HandOddsCalculator.calculate_hand_potential(hole_cards, community_cards))
            opponents = max(0, int(players_in_hand or 0) - 1)
            opponent_factor = 1.0 / (1.0 + opponents * 0.2) if opponents > 0 else 1.0
            equity_estimate = min(1.0, (hand_strength + hand_potential * 0.4) * opponent_factor)

            cards_to_come = 0
            if len(community_cards) == 3:
                cards_to_come = 2
            elif len(community_cards) == 4:
                cards_to_come = 1

            outs_payload: Dict[str, Any] = {}
            if cards_to_come:
                unseen = max(1, 52 - 2 - len(community_cards))

                def exact_prob(outs: int) -> float:
                    outs_int = max(0, int(outs))
                    if outs_int <= 0:
                        return 0.0
                    if cards_to_come == 1:
                        return min(1.0, outs_int / unseen)
                    miss1 = (unseen - outs_int) / unseen
                    miss2 = (unseen - 1 - outs_int) / max(1, unseen - 1)
                    return max(0.0, min(1.0, 1.0 - (miss1 * miss2)))

                for draw_type in ("flush", "straight", "pair"):
                    outs = int(HandOddsCalculator.calculate_outs(hole_cards, community_cards, draw_type))
                    if outs <= 0:
                        continue
                    outs_payload[draw_type] = {
                        "outs": outs,
                        "cards_to_come": int(cards_to_come),
                        "rule_of_2_4_pct": float(
                            HandOddsCalculator.rule_of_four_and_two(outs, cards_to_come)
                        ),
                        "exact_pct": float(exact_prob(outs) * 100.0),
                    }

            return {
                "hand_strength": hand_strength,
                "hand_potential": hand_potential,
                "equity_estimate": equity_estimate,
                "cards_to_come": int(cards_to_come),
                "outs": outs_payload,
            }
        except Exception:
            return {
                "hand_strength": 0.0,
                "hand_potential": 0.0,
                "equity_estimate": 0.0,
                "cards_to_come": 0,
                "outs": {},
            }

    def _record_human_decision_point(
        self,
        *,
        context: Dict[str, Any],
        chosen_action: PlayerAction,
        chosen_amount: int,
    ) -> None:
        """Capture a snapshot of a human decision and store a grade in the hand history."""
        if not getattr(self.session_tracker, "hand_history", None):
            return

        betting_round = (
            self.current_betting_round.value
            if self.current_betting_round is not None
            else getattr(self.game_state, "value", "unknown")
        )

        current_bet = int(context.get("current_bet", 0) or 0)
        pot_total = int(context.get("pot_total", 0) or 0)
        can_check = bool(context.get("can_check", False))
        raise_allowed = bool(context.get("raise_allowed", True))
        call_amount = max(0, current_bet - int(getattr(self.human_player, "current_bet", 0) or 0))

        hole_cards = list(getattr(self.human_player, "hole_cards", []) or [])
        community_cards = list(getattr(self, "community_cards", []) or [])

        decision: Dict[str, Any] = {
            "betting_round": betting_round,
            "pot_total": int(pot_total),
            "current_bet": int(current_bet),
            "to_call": int(call_amount),
            "can_check": bool(can_check),
            "raise_allowed": bool(raise_allowed),
            "min_raise_increment": int(context.get("min_raise", 0) or 0),
            "limit_bet_size": context.get("limit_bet_size"),
            "hero_stack": int(getattr(self.human_player, "bankroll", 0) or 0),
            "hero_current_bet": int(getattr(self.human_player, "current_bet", 0) or 0),
            "hero_position": int(getattr(self.human_player, "position", 0) or 0),
            "hero_hole_cards": [str(c) for c in hole_cards],
            "board": [str(c) for c in community_cards],
            "chosen_action": str(getattr(chosen_action, "value", chosen_action)),
            "chosen_amount": int(chosen_amount),
        }

        players_in_hand = 0
        if self.table is not None:
            try:
                players_in_hand = len(
                    [p for p in self.table.get_players_in_order() if not getattr(p, "folded", False)]
                )
            except Exception:
                players_in_hand = 0
        decision["players_in_hand"] = int(players_in_hand or 0)

        # Identify the opponent who set the current bet (best-effort).
        aggressor_name = None
        try:
            hand = self.session_tracker.hand_history[-1]
            actions = list(hand.get("actions") or [])
            for entry in reversed(actions):
                if entry.get("betting_round") != betting_round:
                    continue
                if entry.get("did_raise"):
                    name = entry.get("player")
                    if name and name != self.human_player.name:
                        aggressor_name = str(name)
                        break
        except Exception:
            aggressor_name = None

        if aggressor_name is None and betting_round == "preflop" and self.table is not None:
            try:
                aggressor_name = self.table.get_big_blind_player().name
            except Exception:
                aggressor_name = None

        opponent_type = "unknown"
        if aggressor_name:
            try:
                stats = self._get_table_player_stats()
                opponent_type = str(stats.get(aggressor_name, {}).get("type", "unknown"))
            except Exception:
                opponent_type = "unknown"

        decision["opponent"] = {"name": aggressor_name, "type": opponent_type}

        features = self._compute_equity_and_outs(
            hole_cards=hole_cards,
            community_cards=community_cards,
            players_in_hand=int(players_in_hand or 0) or 2,
        )
        equity_estimate = float(features.get("equity_estimate", 0.0) or 0.0)
        hand_strength = float(features.get("hand_strength", 0.0) or 0.0)
        hand_potential = float(features.get("hand_potential", 0.0) or 0.0)

        decision["equity"] = equity_estimate
        decision["hand_strength"] = hand_strength
        decision["hand_potential"] = hand_potential
        decision["outs"] = features.get("outs", {}) if isinstance(features.get("outs"), dict) else {}

        # Grade decision (preflop uses GameAnalyzer; postflop uses pot odds + equity).
        recommended_action = None
        quality = "ungraded"
        analysis: Dict[str, Any] = {}

        chosen = str(getattr(chosen_action, "value", chosen_action))
        if chosen == "all_in":
            chosen_for_grade = "raise" if betting_round == "preflop" else "call"
        elif chosen == "raise":
            chosen_for_grade = "raise" if betting_round == "preflop" else ("call" if call_amount > 0 else "raise")
        else:
            chosen_for_grade = chosen

        if betting_round == "preflop":
            analyzer = self._get_game_analyzer()
            if analyzer is not None and len(hole_cards) == 2:
                try:
                    action_data = {
                        "position": int(getattr(self.human_player, "position", 0) or 0),
                        "hole_cards": hole_cards,
                        "action": chosen_for_grade,
                        "amount": int(chosen_amount),
                        "pot_size_before": int(pot_total),
                        "players_in_hand": int(players_in_hand or 0) or 2,
                    }
                    analysis = analyzer.analyze_preflop_action(action_data) or {}
                    recommended_action = analysis.get("recommended_action")
                    quality = analysis.get("action_quality", "ungraded")
                except Exception:
                    analysis = {}
        else:
            if call_amount > 0 and pot_total > 0 and equity_estimate > 0:
                try:
                    from stats.calculator import PotOddsCalculator

                    required_equity = float(PotOddsCalculator.calculate_pot_odds(float(pot_total), float(call_amount)))
                except Exception:
                    required_equity = 0.0

                margin = float(equity_estimate) - float(required_equity)
                if abs(margin) < 0.02:
                    recommended_action = "mixed"
                    quality = "acceptable"
                else:
                    recommended_action = "call" if margin > 0 else "fold"
                    if recommended_action == "call" and chosen in {"call", "raise", "all_in"}:
                        quality = "optimal" if chosen == "call" else "acceptable"
                    elif recommended_action == "fold" and chosen == "fold":
                        quality = "optimal"
                    else:
                        quality = "suboptimal"

                decision["required_equity"] = required_equity

                hand_analyzer = self._hand_analyzer or self._get_decision_analyzer()
                if hand_analyzer is not None:
                    try:
                        analysis = hand_analyzer.analyze_decision(
                            action=chosen_action,
                            pot_size=float(pot_total),
                            bet_to_call=float(call_amount),
                            hand_equity=float(equity_estimate),
                            opponent_type=opponent_type,
                        )
                    except Exception:
                        analysis = {}
            else:
                # No bet to call: heuristic grading for check vs bet/raise.
                if equity_estimate >= 0.75:
                    recommended_action = "raise"
                elif equity_estimate <= 0.30 and hand_potential < 0.2:
                    recommended_action = "check"
                else:
                    recommended_action = "mixed"

                if recommended_action == "mixed":
                    quality = "acceptable"
                elif recommended_action == "raise" and chosen in {"raise", "all_in"}:
                    quality = "optimal"
                elif recommended_action == "check" and chosen == "check":
                    quality = "optimal"
                else:
                    quality = "suboptimal"

                analysis = {
                    "grade_method": "heuristic",
                    "recommended_action": recommended_action,
                }

        decision["recommended_action"] = recommended_action
        decision["quality"] = quality
        decision["analysis"] = analysis

        try:
            self.session_tracker.record_decision(decision)
        except Exception:
            return

    def _classify_opponent_type(self, *, vpip: float, pfr: float, af: float) -> str:
        """Classify an opponent using simple VPIP/PFR/AF heuristics."""
        if af != af:  # NaN guard
            af = 0.0

        if vpip < 0.22:
            if pfr >= 0.12 or af >= 2.0:
                return "tight-aggressive"
            return "tight-passive"

        if vpip > 0.33:
            if pfr >= 0.18 or af >= 2.5:
                return "loose-aggressive"
            return "loose-passive"

        return "balanced"

    def _get_table_player_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Compute lightweight per-player stats from the in-memory hand history.

        Used for HUD + post-hand feedback. This is intentionally approximate.
        """
        history = list(getattr(self.session_tracker, "hand_history", []) or [])
        if not history:
            return {}

        aggregates: Dict[str, Dict[str, Any]] = {}

        for hand in history:
            actions = hand.get("actions") or []
            players_seen = set()
            vpip_players = set()
            pfr_players = set()

            for entry in actions:
                name = entry.get("player")
                if not name:
                    continue

                players_seen.add(name)
                if name not in aggregates:
                    aggregates[name] = {
                        "hands": 0,
                        "vpip_hands": 0,
                        "pfr_hands": 0,
                        "postflop_calls": 0,
                        "postflop_raises": 0,
                    }

                street = entry.get("betting_round")
                action = entry.get("action")
                amount = int(entry.get("amount") or 0)
                did_raise = bool(entry.get("did_raise", False))

                if street == "preflop":
                    if action in {"call", "raise", "all_in"} and amount > 0:
                        vpip_players.add(name)
                    if did_raise and action in {"raise", "all_in"}:
                        pfr_players.add(name)
                else:
                    if action == "call" and amount > 0:
                        aggregates[name]["postflop_calls"] += 1
                    elif action in {"raise", "all_in"} and amount > 0 and did_raise:
                        aggregates[name]["postflop_raises"] += 1

            for name in players_seen:
                aggregates[name]["hands"] += 1
            for name in vpip_players:
                aggregates[name]["vpip_hands"] += 1
            for name in pfr_players:
                aggregates[name]["pfr_hands"] += 1

        results: Dict[str, Dict[str, Any]] = {}
        for name, data in aggregates.items():
            hands = int(data.get("hands", 0))
            if hands <= 0:
                continue
            vpip = float(data.get("vpip_hands", 0)) / hands
            pfr = float(data.get("pfr_hands", 0)) / hands
            calls = int(data.get("postflop_calls", 0))
            raises = int(data.get("postflop_raises", 0))
            af = (raises / calls) if calls > 0 else (float("inf") if raises > 0 else 0.0)

            results[name] = {
                "hands": hands,
                "vpip": vpip,
                "pfr": pfr,
                "af": af,
                "type": self._classify_opponent_type(vpip=vpip, pfr=pfr, af=af),
            }

        return results

    def _get_opponent_stats_for_hud(self) -> Dict[str, Dict[str, Any]]:
        stats = self._get_table_player_stats()
        hero_name = self.human_player.name
        return {name: data for name, data in stats.items() if name != hero_name}

    def _show_post_hand_feedback(self, *, winners: List[Player], pot_total: int) -> None:
        """Display post-hand training feedback (if training modules are available)."""
        if self._hand_analyzer is None:
            return
        if not getattr(self.session_tracker, "hand_history", None):
            return

        hero_name = self.human_player.name
        hero_won = any(w.name == hero_name for w in winners)
        winner_name = hero_name if hero_won else (winners[0].name if winners else "Unknown")

        user_strength = 0.0
        try:
            from stats.calculator import HandOddsCalculator

            if self.human_player.hole_cards:
                user_strength = float(
                    HandOddsCalculator.calculate_hand_strength(
                        self.human_player.hole_cards, self.community_cards
                    )
                )
        except Exception:
            user_strength = 0.0

        try:
            hand_record = self.session_tracker.hand_history[-1]
            opponent_stats = self._get_opponent_stats_for_hud()

            hand_data = {
                "hero_name": hero_name,
                "winner": winner_name,
                "winners": [w.name for w in winners],
                "final_pot": int(pot_total),
                "board": list(hand_record.get("board", []) or []),
                "actions": list(hand_record.get("actions", []) or []),
                "user_hand_strength": user_strength,
                "opponent_stats": opponent_stats,
            }

            feedback = self._hand_analyzer.generate_post_hand_feedback(hand_data)
        except Exception:
            return

        summary = feedback.get("summary")
        learning_points = feedback.get("learning_points") or []
        rating = feedback.get("overall_rating") or {}

        print("\n" + "-" * 70)
        print("🎓 POST-HAND FEEDBACK")
        if summary:
            print(summary)
        grade = rating.get("grade")
        comment = rating.get("comment")
        if grade or comment:
            print(f"Overall: {grade or ''} {('- ' + comment) if comment else ''}".strip())
        if learning_points:
            print("\nKey learning points:")
            for point in learning_points[:3]:
                print(f"  {point}")
        print("-" * 70)
                
    def _deal_flop(self) -> None:
        """Deal the flop (3 community cards)."""
        # Burn one card
        self.deck.deal_card()
        
        # Deal 3 cards
        self.community_cards = self.deck.deal_cards(3)
        
        # Display the flop
        print("\n" + "="*70)
        print("🎴 DEALING THE FLOP:")
        print(f"   {' '.join(str(card) for card in self.community_cards[:3])}")
        print("="*70)
        
    def _deal_turn(self) -> None:
        """Deal the turn (4th community card)."""
        # Burn one card
        self.deck.deal_card()
        
        # Deal 1 card
        self.community_cards.append(self.deck.deal_card())
        
        # Display the turn
        print("\n" + "="*70)
        print("🎴 DEALING THE TURN:")
        print(f"   Board: {' '.join(str(card) for card in self.community_cards)}")
        print("="*70)
        
    def _deal_river(self) -> None:
        """Deal the river (5th community card)."""
        # Burn one card
        self.deck.deal_card()
        
        # Deal 1 card
        self.community_cards.append(self.deck.deal_card())
        
        # Display the river
        print("\n" + "="*70)
        print("🎴 DEALING THE RIVER:")
        print(f"   Board: {' '.join(str(card) for card in self.community_cards)}")
        print("="*70)
        
    def _determine_winners(self) -> List[Player]:
        """
        Determine the winner(s) of the hand.
        
        Returns:
            List of winning players
        """
        active_players = [p for p in self.table.get_players_in_order() if not p.folded]
        
        if len(active_players) == 1:
            # Only one player remains
            return active_players
            
        # Evaluate hands at showdown
        best_hand = None
        winners = []
        
        for player in active_players:
            # Combine hole cards with community cards
            all_cards = player.hole_cards + self.community_cards
            
            # Find best 5-card hand from 7 cards
            player_hand = Hand.best_hand_from_cards(all_cards)
            
            if best_hand is None or player_hand > best_hand:
                best_hand = player_hand
                winners = [player]
            elif player_hand == best_hand:
                winners.append(player)
                
        return winners
        
    def _distribute_pot(self, winners: List[Player]) -> None:
        """
        Distribute pot to winners.
        
        Args:
            winners: List of winning players
        """
        if not winners or not self.pot:
            return

        # If everyone else folded, the last player wins the entire pot (side pots irrelevant).
        if len(winners) == 1:
            winners[0].add_winnings(self.pot.total)
            self.pot.reset()
            return

        # Create side pots (no-ops if not needed) and distribute based on best hands.
        self.pot.create_side_pots()

        player_best_hands: Dict[Player, Hand] = {}
        if self.table:
            for player in self.table.get_players_in_hand():
                if not player.hole_cards:
                    continue
                all_cards = player.hole_cards + self.community_cards
                if len(all_cards) < 5:
                    continue
                try:
                    player_best_hands[player] = Hand.best_hand_from_cards(all_cards)
                except Exception:
                    continue

        if player_best_hands:
            winnings = self.pot.distribute_to_winners(player_best_hands)
            for player, amount in winnings.items():
                player.add_winnings(amount)
            return

        # Fallback (primarily for tests/mocks without real cards): split equally.
        pot_amount = self.pot.total
        amount_per_winner = pot_amount // len(winners)
        remainder = pot_amount % len(winners)

        for i, winner in enumerate(winners):
            win_amount = amount_per_winner + (1 if i < remainder else 0)
            winner.add_winnings(win_amount)

        self.pot.reset()
            
    def play_hand(self) -> None:
        """Play a complete hand from start to finish."""
        # Initialize hand
        self.community_cards = []
        self.deck = Deck()
        if self.pot:
            self.pot.reset()
        else:
            self.pot = Pot()
        
        # Reset players for new hand
        for player in self.table.get_players_in_order():
            player.reset_for_new_hand()
            player.hands_played += 1
            
        # Pre-flop
        self.game_state = GameState.PREFLOP
        self._deal_hole_cards()
        if self.session_tracker.active:
            hand_meta: Dict[str, Any] = {}
            try:
                hand_meta = self._build_hand_meta()
            except Exception:
                hand_meta = {}
            self.session_tracker.start_hand(
                hero_hole_cards=[str(c) for c in (self.human_player.hole_cards or [])],
                hand_meta=hand_meta,
            )
        self._post_blinds()
        self._run_betting_round(BettingRound.PREFLOP)
        
        # Check if hand is over (everyone folded except one)
        active_players = [p for p in self.table.get_players_in_order() if not p.folded]
        if len(active_players) == 1:
            self._complete_hand()
            return
            
        # Flop
        self.game_state = GameState.FLOP
        self._deal_flop()
        self.session_tracker.set_board([str(c) for c in self.community_cards])
        for p in self.table.get_players_in_order():
            p.reset_for_new_round()
        self._run_betting_round(BettingRound.FLOP)
        
        active_players = [p for p in self.table.get_players_in_order() if not p.folded]
        if len(active_players) == 1:
            self._complete_hand()
            return
            
        # Turn
        self.game_state = GameState.TURN
        self._deal_turn()
        self.session_tracker.set_board([str(c) for c in self.community_cards])
        for p in self.table.get_players_in_order():
            p.reset_for_new_round()
        self._run_betting_round(BettingRound.TURN)
        
        active_players = [p for p in self.table.get_players_in_order() if not p.folded]
        if len(active_players) == 1:
            self._complete_hand()
            return
            
        # River
        self.game_state = GameState.RIVER
        self._deal_river()
        self.session_tracker.set_board([str(c) for c in self.community_cards])
        for p in self.table.get_players_in_order():
            p.reset_for_new_round()
        self._run_betting_round(BettingRound.RIVER)
        
        # Showdown
        self.game_state = GameState.SHOWDOWN
        self._complete_hand()
        
    def _complete_hand(self) -> None:
        """Complete the hand, determine winners, and distribute pot."""
        # Determine winners (if there are any active players with cards)
        try:
            winners = self._determine_winners()
            pot_total = int(self.pot.total) if self.pot else 0
            for winner in winners:
                winner.hands_won += 1
            
            # Display results
            print("\n" + "="*70)
            print("🏆 HAND COMPLETE!")
            
            # Show final board if there are community cards
            if self.community_cards:
                print(f"   Final Board: {' '.join(str(card) for card in self.community_cards)}")
            
            # Show winner(s)
            if len(winners) == 1:
                print(f"   Winner: {winners[0].name}")
                print(f"   Pot: ${self.pot.total:.0f}")
            else:
                print(f"   Split pot between: {', '.join(w.name for w in winners)}")
                print(f"   Pot: ${self.pot.total:.0f} (${self.pot.total//len(winners):.0f} each)")
            
            # Show winning hand if it was a showdown
            active_players = [p for p in self.table.get_players_in_order() if not p.folded]
            if len(active_players) > 1 and self.community_cards:
                for winner in winners:
                    if winner.hole_cards:
                        print(f"   {winner.name}'s hand: {winner.hole_cards[0]} {winner.hole_cards[1]}")
            
            print("="*70)
            
            self._distribute_pot(winners)
            self.session_tracker.end_hand(
                winners=[w.name for w in winners],
                pot_total=pot_total,
            )
            self._persist_last_hand_history(winners=winners, pot_total=pot_total)

            if self.training_enabled and self.post_hand_feedback_enabled:
                self._show_post_hand_feedback(winners=winners, pot_total=pot_total)

            if not getattr(self, "_test_mode", False):
                print("\nPress Enter to continue...")
                input()
        except (ValueError, AttributeError):
            # Handle case where hand wasn't properly set up (e.g., in tests)
            pass
        
        self.hands_played += 1
        self.game_state = GameState.HAND_COMPLETE
        
        # Rotate dealer button if table exists
        if self.table:
            self.table.rotate_dealer_button()
        
        # Handle tournament-specific logic
        if self.tournament_mode:
            self._check_blind_increase()
            self._handle_eliminations()

    def _build_hand_meta(self) -> Dict[str, Any]:
        """Build metadata captured at the start of a hand for replay/training."""
        if not self.table:
            return {}

        ante = int(getattr(self, "ante", 0) or 0) if self.tournament_mode else 0

        players: List[Dict[str, Any]] = []
        for p in self.table.get_players_in_order():
            players.append(
                {
                    "name": p.name,
                    "position": int(getattr(p, "position", 0)),
                    "stack_start": int(getattr(p, "bankroll", 0)),
                    "is_hero": p is self.human_player,
                    "is_ai": bool(getattr(p, "is_ai", False)),
                }
            )

        try:
            dealer = self.table.get_dealer_player()
            sb_player = self.table.get_small_blind_player()
            bb_player = self.table.get_big_blind_player()
        except Exception:
            dealer = None
            sb_player = None
            bb_player = None

        return {
            "game_type": "tournament" if self.tournament_mode else "cash",
            "tournament_mode": bool(self.tournament_mode),
            "limit_type": str(self.limit_type),
            "small_blind": int(self.small_blind),
            "big_blind": int(self.big_blind),
            "ante": int(ante),
            "blind_level": int(getattr(self, "blind_level", 1) or 1),
            "dealer": dealer.name if dealer else None,
            "small_blind_player": sb_player.name if sb_player else None,
            "big_blind_player": bb_player.name if bb_player else None,
            "hero_name": self.human_player.name,
            "hero_position": int(getattr(self.human_player, "position", 0)),
            "players": players,
        }

    def _persist_last_hand_history(self, *, winners: List[Player], pot_total: int) -> None:
        """Persist the last completed hand to the per-player JSONL history (best-effort)."""
        if not self.data_manager:
            return

        history = getattr(self.session_tracker, "hand_history", None)
        if not history:
            return

        last_hand = history[-1]
        if not isinstance(last_hand, dict):
            return

        meta = last_hand.get("meta")
        if isinstance(meta, dict):
            meta.setdefault("hero_stack_end", int(getattr(self.human_player, "bankroll", 0)))
            meta.setdefault("hero_won", any(w.name == self.human_player.name for w in winners))
            meta.setdefault("pot_total", int(pot_total))

        try:
            append_fn = getattr(self.data_manager, "append_hand_history", None)
            if callable(append_fn):
                append_fn(self.human_player.name, last_hand)
        except Exception:
            return

    def _update_tournament_ante(self) -> None:
        """Update tournament ante based on blind level and configuration."""
        if not self.tournament_mode:
            self.ante = 0
            return

        if int(self.blind_level) < int(self._tournament_ante_start_level):
            self.ante = 0
            return

        fraction = float(self._tournament_ante_bb_fraction)
        if fraction <= 0:
            self.ante = 0
            return

        raw = float(self.big_blind) * fraction
        rounded = int(round(raw / 5.0)) * 5
        self.ante = max(0, min(int(self.big_blind), int(rounded)))
            
    def _check_blind_increase(self) -> None:
        """Check if blinds should increase in tournament."""
        hands_per_level = max(1, int(self._tournament_hands_per_level))
        factor = float(self._tournament_blind_increase_factor)
        if factor <= 1.0:
            factor = 1.5

        if self.hands_played > 0 and self.hands_played % hands_per_level == 0:
            self.blind_level += 1
            self.small_blind = int(round((float(self.small_blind) * factor) / 5.0)) * 5
            self.big_blind = int(round((float(self.big_blind) * factor) / 5.0)) * 5
            self._update_tournament_ante()
            
    def _handle_eliminations(self) -> None:
        """Handle player eliminations in tournament."""
        players_to_remove = []
        
        for player in self.table.get_players_in_order():
            if player.bankroll == 0:
                players_to_remove.append(player)
                
        for player in players_to_remove:
            if player.name not in self._tournament_elimination_order:
                self._tournament_elimination_order.append(player.name)
            self.table.remove_player(player)

    def _get_tournament_finish_position(self, player_name: str) -> Optional[int]:
        total_players = int(self._tournament_total_players or 0)
        if total_players <= 0:
            return None

        if player_name in self._tournament_elimination_order:
            eliminated_index = self._tournament_elimination_order.index(player_name)
            return total_players - eliminated_index

        if self.table:
            remaining = [p.name for p in self.table.get_players_in_tournament()]
            if len(remaining) == 1 and remaining[0] == player_name:
                return 1

        return None

    def _get_tournament_payout_table(self, total_players: int, prize_pool: int) -> Dict[int, int]:
        """
        Return a simple single-table payout structure (cash amounts) for small fields.

        Note: This is intentionally conservative and defaults to common SNG-style
        payouts for 2-9 players.
        """
        total_players = int(total_players)
        prize_pool = int(prize_pool)
        if total_players <= 1 or prize_pool <= 0:
            return {}

        if total_players == 2:
            return {1: prize_pool}

        if total_players == 3:
            first = int(prize_pool * 0.70)
            second = prize_pool - first
            return {1: first, 2: second}

        # 4+ players: pay top 3 (50/30/20).
        first = int(prize_pool * 0.50)
        second = int(prize_pool * 0.30)
        third = prize_pool - first - second
        return {1: first, 2: second, 3: third}

    def _finalize_tournament(self, result: str) -> None:
        """
        Finalize tournament bookkeeping and persist bankroll.

        Tournament play uses `Player.bankroll` as a chip stack. This restores the
        player's cash bankroll after the tournament and saves it.
        """
        cash_bankroll = self._tournament_cash_bankroll_after_buy_in
        if cash_bankroll is None:
            self.tournament_mode = False
            return

        total_players = int(self._tournament_total_players or 0)
        prize_pool = int(self._tournament_prize_pool or 0)
        place = 1 if result == "won" else self._get_tournament_finish_position(self.human_player.name)

        payout = 0
        if result != "forfeit" and total_players > 0 and prize_pool > 0 and place is not None:
            payout_table = self._get_tournament_payout_table(total_players, prize_pool)
            payout = int(payout_table.get(int(place), 0))

        cash_bankroll += int(payout)

        self.human_player.bankroll = int(cash_bankroll)

        self._finalize_and_persist_session(
            result=result,
            extra={
                "tournament_place": int(place) if place is not None else None,
                "tournament_payout": int(payout),
                "tournament_prize_pool": int(prize_pool),
                "tournament_total_players": int(total_players) if total_players > 0 else None,
                "tournament_eliminations": list(self._tournament_elimination_order),
            },
        )

        if self.data_manager:
            self.data_manager.save_player(self.human_player)

        self.tournament_mode = False
        self._tournament_buy_in = None
        self._tournament_starting_chips = None
        self._tournament_total_players = None
        self._tournament_prize_pool = None
        self._tournament_cash_bankroll_after_buy_in = None

    def _finalize_and_persist_session(
        self, *, result: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        if not self.session_tracker.active:
            return

        try:
            session_data = self.session_tracker.finalize(
                bankroll_end=int(self.human_player.bankroll)
            )
        except RuntimeError:
            return

        session_data["result"] = result
        if extra:
            for key, value in extra.items():
                session_data[key] = value

        if not self.data_manager:
            return

        existing_player = None
        try:
            existing_player = self.data_manager.get_player(self.human_player.name)
        except Exception:
            existing_player = None

        sessions: List[Dict[str, Any]] = []
        if isinstance(existing_player, dict):
            existing_sessions = existing_player.get("sessions")
            if isinstance(existing_sessions, list):
                sessions = list(existing_sessions)
        sessions.append(session_data)

        total_hands = sum(int(s.get("hands_played", 0)) for s in sessions)
        metrics_for_progress = {
            "total_hands": total_hands,
            "vpip": float(session_data.get("vpip", 0.0) or 0.0),
            "pfr": float(session_data.get("pfr", 0.0) or 0.0),
            "aggression_factor": float(session_data.get("aggression_factor", 0.0) or 0.0),
        }
        if session_data.get("pot_odds_accuracy") is not None:
            metrics_for_progress["pot_odds_accuracy"] = float(session_data["pot_odds_accuracy"])

        try:
            from training.progression_analyzer import ProgressionAnalyzer
        except Exception:
            ProgressionAnalyzer = None  # type: ignore

        training_updates: Dict[str, Any] = {
            "sessions": sessions,
            "last_session": session_data,
            "biggest_pot": max(
                int(existing_player.get("biggest_pot", 0)) if isinstance(existing_player, dict) else 0,
                int(session_data.get("biggest_pot", 0) or 0),
            ),
        }
        recent_hands: List[Dict[str, Any]] = []
        if isinstance(existing_player, dict):
            existing_recent = existing_player.get("recent_hands")
            if isinstance(existing_recent, list):
                recent_hands = list(existing_recent)

        if getattr(self.session_tracker, "hand_history", None):
            recent_hands.extend(list(self.session_tracker.hand_history))

        if len(recent_hands) > 50:
            recent_hands = recent_hands[-50:]

        if recent_hands:
            training_updates["recent_hands"] = recent_hands

        if ProgressionAnalyzer is not None:
            analyzer = ProgressionAnalyzer()
            skill_level = analyzer.determine_skill_level(metrics_for_progress)
            weaknesses = analyzer.identify_weaknesses(metrics_for_progress)
            topics = analyzer.suggest_study_topics(weaknesses)

            training_updates.update(
                {
                    "skill_level": skill_level.name.lower(),
                    "weaknesses": [w.value for w in weaknesses],
                    "recommended_topics": topics,
                }
            )

        try:
            self.data_manager.update_player_stats(self.human_player.name, training_updates)
        except Exception:
            return
            
    def run_game_loop(self) -> None:
        """Run the main game loop."""
        if self.tournament_mode:
            result: Optional[str] = None
            try:
                while True:
                    active_players = self.table.get_players_in_tournament()

                    if self.human_player not in active_players:
                        print("\n❌ You have been eliminated from the tournament.")
                        result = "lost"
                        break

                    if len(active_players) <= 1:
                        print("\n🏆 TOURNAMENT COMPLETE!")
                        if self.human_player in active_players:
                            print("   Congratulations! You won the tournament!")
                            result = "won"
                        else:
                            print("   Better luck next time!")
                            result = "lost"
                        break

                    self.play_hand()

            except KeyboardInterrupt:
                result = "forfeit"
                raise
            except Exception:
                result = "forfeit"
                raise
            finally:
                if result is not None:
                    self._finalize_tournament(result)
            return

        result: Optional[str] = None
        try:
            while True:
                # Cash game - check if human wants to continue
                if self.human_player.bankroll == 0:
                    print("\n❌ You're out of chips! Game over.")
                    result = "busted"
                    break

                # Play a hand
                self.play_hand()

                # Save player data
                if self.data_manager:
                    self.data_manager.save_player(self.human_player)

                # Ask if player wants to continue
                print(f"\n💰 Your stack: ${self.human_player.bankroll:.0f}")
                continue_playing = self.input_handler.get_yes_no_input("Continue playing")
                if not continue_playing:
                    print("\nThanks for playing!")
                    result = "quit"
                    break
        finally:
            if result is not None:
                self._finalize_and_persist_session(result=result)
                if self.data_manager:
                    self.data_manager.save_player(self.human_player)
                
    def get_game_state(self) -> Dict[str, Any]:
        """
        Get current game state for display/saving.
        
        Returns:
            Dictionary containing game state information
        """
        return {
            'game_state': self.game_state.value,
            'community_cards': [str(card) for card in self.community_cards],
            'pot_size': self.pot.total if self.pot else 0,
            'players': [
                {
                    'name': player.name,
                    'bankroll': player.bankroll,
                    'current_bet': player.current_bet,
                    'folded': player.folded,
                    'all_in': player.all_in
                }
                for player in self.table.get_players_in_order()
            ] if self.table else [],
            'blinds': {
                'small_blind': self.small_blind,
                'big_blind': self.big_blind,
                'blind_level': self.blind_level if self.tournament_mode else None
            }
        }
