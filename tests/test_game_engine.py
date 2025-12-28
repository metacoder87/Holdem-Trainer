"""
Test suite for GameEngine class.
Tests main game logic, flow control, and rule enforcement.
"""
import pytest
from unittest.mock import Mock, patch
from game.game_engine import GameEngine, GameState, BettingRound
from game.player import Player, PlayerAction
from game.ai_player import AIPlayer, AIStyle
from game.table import Table, TableType
from game.card import Card, Suit, Rank
from game.pot import Pot


class TestGameState:
    """Test cases for GameState enum."""
    
    def test_game_state_values(self):
        """Test game state enum values."""
        assert GameState.WAITING.value == "waiting"
        assert GameState.PREFLOP.value == "preflop"
        assert GameState.FLOP.value == "flop"
        assert GameState.TURN.value == "turn"
        assert GameState.RIVER.value == "river"
        assert GameState.SHOWDOWN.value == "showdown"
        assert GameState.HAND_COMPLETE.value == "hand_complete"


class TestBettingRound:
    """Test cases for BettingRound enum."""
    
    def test_betting_round_values(self):
        """Test betting round enum values."""
        assert BettingRound.PREFLOP.value == "preflop"
        assert BettingRound.FLOP.value == "flop"
        assert BettingRound.TURN.value == "turn"
        assert BettingRound.RIVER.value == "river"


class TestGameEngine:
    """Test cases for GameEngine class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.human_player = Player("Human", 10000)
        self.mock_data_manager = Mock()
        self.mock_display = Mock()
        self.mock_input_handler = Mock()
        
        self.game_engine = GameEngine(
            self.human_player,
            self.mock_data_manager,
            self.mock_display,
            self.mock_input_handler
        )
        
        # Set test mode to prevent game loop from running
        self.game_engine._test_mode = True
        
    def test_game_engine_creation(self):
        """Test creating a game engine."""
        assert self.game_engine.human_player == self.human_player
        assert self.game_engine.data_manager == self.mock_data_manager
        assert self.game_engine.display == self.mock_display
        assert self.game_engine.input_handler == self.mock_input_handler
        assert self.game_engine.game_state == GameState.WAITING
        assert self.game_engine.current_betting_round is None
        assert self.game_engine.table is None
        assert self.game_engine.pot is None
        
    def test_start_cash_game(self):
        """Test starting a cash game."""
        game_config = {
            'type': 'cash',
            'limit': 'no_limit',
            'small_blind': 10,
            'big_blind': 20,
            'max_players': 6
        }
        
        # Mock user inputs
        self.mock_input_handler.get_number_input.side_effect = [4, 3]  # 4 opponents, seat 3
        
        self.game_engine.start_game(game_config)
        
        assert self.game_engine.table is not None
        assert self.game_engine.pot is not None
        assert self.game_engine.small_blind == 10
        assert self.game_engine.big_blind == 20
        
    def test_start_tournament(self):
        """Test starting a tournament."""
        game_config = {
            'type': 'tournament',
            'limit': 'no_limit',
            'buy_in': 1000,
            'starting_chips': 5000
        }
        
        # Mock user inputs
        self.mock_input_handler.get_number_input.side_effect = [6, 1]  # 6 opponents, seat 1
        
        self.game_engine.start_game(game_config)
        
        assert self.game_engine.table is not None
        assert self.game_engine.tournament_mode is True
        assert self.human_player.bankroll == 5000
        assert self.game_engine._tournament_buy_in == 1000
        assert self.game_engine._tournament_starting_chips == 5000
        assert self.game_engine._tournament_total_players == 7
        assert self.game_engine._tournament_prize_pool == 7000
        assert self.game_engine._tournament_cash_bankroll_after_buy_in == 9000

    def test_tournament_requires_affordable_buy_in(self):
        """Test tournament start fails when bankroll is too small for buy-in."""
        self.human_player.bankroll = 500
        game_config = {
            'type': 'tournament',
            'limit': 'no_limit',
            'buy_in': 1000,
            'starting_chips': 5000
        }

        self.mock_input_handler.get_number_input.side_effect = [1]
        self.game_engine.start_game(game_config)

        assert self.game_engine.tournament_mode is False
        assert self.game_engine.table is None
        assert self.human_player.bankroll == 500

    def test_tournament_finalizes_win_and_saves_once(self):
        """Test tournament finalization restores bankroll and saves on win."""
        game_config = {
            'type': 'tournament',
            'limit': 'no_limit',
            'buy_in': 1000,
            'starting_chips': 5000
        }

        self.mock_input_handler.get_number_input.side_effect = [1]
        self.game_engine.start_game(game_config)

        def fake_play_hand():
            for player in self.game_engine.table.get_players_in_order():
                if player != self.human_player:
                    player.bankroll = 0

        with patch.object(self.game_engine, 'play_hand', side_effect=fake_play_hand) as mock_play_hand:
            self.game_engine.run_game_loop()

        assert mock_play_hand.call_count == 1
        assert self.human_player.bankroll == 11000  # 10000 - 1000 + (1000 * 2)
        self.mock_data_manager.save_player.assert_called_once_with(self.human_player)
        assert self.game_engine.tournament_mode is False

    def test_tournament_finalizes_loss_and_saves_once(self):
        """Test tournament finalization restores bankroll and saves on loss."""
        game_config = {
            'type': 'tournament',
            'limit': 'no_limit',
            'buy_in': 1000,
            'starting_chips': 5000
        }

        self.mock_input_handler.get_number_input.side_effect = [1]
        self.game_engine.start_game(game_config)

        self.human_player.bankroll = 0
        with patch.object(self.game_engine, 'play_hand') as mock_play_hand:
            self.game_engine.run_game_loop()

        mock_play_hand.assert_not_called()
        assert self.human_player.bankroll == 9000  # 10000 - 1000
        self.mock_data_manager.save_player.assert_called_once_with(self.human_player)
        assert self.game_engine.tournament_mode is False
        
    def test_deal_hole_cards(self):
        """Test dealing hole cards to players."""
        # Set up table with players
        self.game_engine._setup_cash_game_table(4, 10, 20)
        
        self.game_engine._deal_hole_cards()
        
        # All players should have 2 cards
        for player in self.game_engine.table.get_players_in_order():
            assert len(player.hole_cards) == 2
            
        # Deck should have 52 - (players * 2) cards remaining
        expected_remaining = 52 - (self.game_engine.table.num_players * 2)
        assert self.game_engine.deck.cards_remaining == expected_remaining
        
    def test_post_blinds(self):
        """Test posting small and big blinds."""
        # Set up table
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        self.game_engine._post_blinds()
        
        sb_player = self.game_engine.table.get_small_blind_player()
        bb_player = self.game_engine.table.get_big_blind_player()
        
        assert sb_player.current_bet == 10
        assert bb_player.current_bet == 20
        assert self.game_engine.pot.total == 30
        
    def test_betting_round_preflop(self):
        """Test preflop betting round."""
        # Set up game
        self.game_engine._setup_cash_game_table(2, 10, 20)
        self.game_engine._deal_hole_cards()
        self.game_engine._post_blinds()

        # Mock player decisions
        def mock_get_player_action(player, game_state, highest_bet):
            if player == self.human_player:
                return PlayerAction.CALL, 20
            elif player == self.game_engine.table.get_small_blind_player():
                return PlayerAction.FOLD, 0
            else: # Big blind
                return PlayerAction.CHECK, 0

        with patch.object(self.game_engine, '_get_player_action', side_effect=mock_get_player_action):
            self.game_engine._run_betting_round(BettingRound.PREFLOP)

        # Human should have called, others folded
        assert self.human_player.current_bet == 20

        # Check folded status
        for p in self.game_engine.table.get_players_in_order():
            print(f'Player: {p.name}, Folded: {p.folded}')
        active_players = self.game_engine.table.get_active_players()
        assert len(active_players) == 2  # Human + big blind

    def test_all_in_call_does_not_reset_betting_round(self):
        """Test that all-in for less than a call doesn't force extra action."""
        self.game_engine._setup_cash_game_table(2, 10, 20)
        self.game_engine._post_blinds()

        sb_player = self.game_engine.table.get_small_blind_player()
        sb_player.bankroll = 50  # short-stack all-in (below a full call)

        action_log = []

        def mock_get_player_action(player, game_state, highest_bet):
            action_log.append(player)
            if player == self.human_player:
                return PlayerAction.RAISE, 100
            if player == sb_player:
                return PlayerAction.ALL_IN, 0
            return PlayerAction.CALL, 100

        with patch.object(self.game_engine, '_get_player_action', side_effect=mock_get_player_action):
            self.game_engine._run_betting_round(BettingRound.PREFLOP)

        assert action_log.count(self.human_player) == 1

    def test_min_raise_enforced_after_raise(self):
        """Test that subsequent raises must meet the last-raise size (no-limit)."""
        self.game_engine._setup_cash_game_table(2, 10, 20)
        self.game_engine._post_blinds()

        players = self.game_engine.table.get_players_in_order()
        human = self.human_player
        ai_1 = next(p for p in players if p != human)
        ai_2 = next(p for p in players if p not in {human, ai_1})

        def mock_get_player_action(player, game_state, highest_bet):
            if player == human and highest_bet == 20:
                return PlayerAction.RAISE, 100  # full raise (size 80)
            if player == ai_1 and highest_bet == 100:
                return PlayerAction.RAISE, 150  # undersized vs min raise to 180
            return PlayerAction.CALL, int(highest_bet)

        with patch.object(self.game_engine, "_get_player_action", side_effect=mock_get_player_action):
            self.game_engine._run_betting_round(BettingRound.PREFLOP)

        # AI_1's undersized raise should be treated as a call to 100.
        assert ai_1.current_bet == 100
        assert max(p.current_bet for p in players) == 100

    def test_non_full_all_in_does_not_reopen_betting(self):
        """Test that a non-full all-in raise closes action for prior actors."""
        self.game_engine._setup_cash_game_table(2, 10, 20)
        self.game_engine._post_blinds()

        players = self.game_engine.table.get_players_in_order()
        human = self.human_player
        ai_1 = next(p for p in players if p != human)
        ai_2 = next(p for p in players if p not in {human, ai_1})

        # Make ai_2 short enough to all-in raise to 150 total (raise size 50 < 80).
        ai_2.bankroll = 130

        action_log = []

        def mock_get_player_action(player, game_state, highest_bet):
            action_log.append((player, int(highest_bet)))
            if player == human and highest_bet == 20:
                return PlayerAction.RAISE, 100  # full raise (size 80)
            if player == ai_2 and highest_bet == 100:
                return PlayerAction.ALL_IN, 0  # non-full raise to 150
            if player == human and highest_bet == 150:
                # Attempt to re-raise after the non-full all-in (should be forced to call)
                return PlayerAction.RAISE, 300
            return PlayerAction.CALL, int(highest_bet)

        with patch.object(self.game_engine, "_get_player_action", side_effect=mock_get_player_action):
            self.game_engine._run_betting_round(BettingRound.PREFLOP)

        assert action_log.count((human, 20)) == 1
        assert any(entry[0] == human and entry[1] == 150 for entry in action_log)
        assert human.current_bet == 150

    def test_fixed_limit_enforces_bet_sizing_and_raise_cap(self):
        """Test fixed-limit betting uses fixed increments and caps raises."""
        self.game_engine.limit_type = "limit"
        self.game_engine._setup_cash_game_table(2, 10, 20)
        self.game_engine._post_blinds()

        players = self.game_engine.table.get_players_in_order()
        human = self.human_player
        ai_1 = next(p for p in players if p != human)
        ai_2 = next(p for p in players if p not in {human, ai_1})

        # Script: raise/raise/raise (3 raises after the big blind), then another
        # raise attempt which should be capped and treated as a call.
        def mock_get_player_action(player, game_state, highest_bet):
            hb = int(highest_bet)
            if player == human and hb == 20:
                return PlayerAction.RAISE, 999
            if player == ai_1 and hb == 40:
                return PlayerAction.RAISE, 999
            if player == ai_2 and hb == 60:
                return PlayerAction.RAISE, 999
            if player == human and hb == 80:
                return PlayerAction.RAISE, 999  # should be capped -> call
            return PlayerAction.CALL, hb

        with patch.object(self.game_engine, "_get_player_action", side_effect=mock_get_player_action):
            self.game_engine._run_betting_round(BettingRound.PREFLOP)

        # Fixed-limit raises should be in 20-chip increments (BB size).
        assert ai_2.current_bet == 80
        assert max(p.current_bet for p in players) == 80
        # The capped raise attempt should not increase the bet to 100.
        assert human.current_bet == 80
        
    def test_deal_flop(self):
        """Test dealing the flop."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        self.game_engine.community_cards = []
        
        self.game_engine._deal_flop()
        
        assert len(self.game_engine.community_cards) == 3
        # Should have burned 1 card and dealt 3
        assert self.game_engine.deck.cards_remaining == 52 - 1 - 3
        
    def test_deal_turn(self):
        """Test dealing the turn."""
        self.game_engine._setup_cash_game_table(3, 10, 20)
        self.game_engine.community_cards = [Mock(), Mock(), Mock()]  # Simulate flop
        
        self.game_engine._deal_turn()
        
        assert len(self.game_engine.community_cards) == 4
        
    def test_deal_river(self):
        """Test dealing the river."""
        self.game_engine._setup_cash_game_table(3, 10, 20)
        self.game_engine.community_cards = [Mock(), Mock(), Mock(), Mock()]  # Simulate flop+turn
        
        self.game_engine._deal_river()
        
        assert len(self.game_engine.community_cards) == 5
        
    def test_determine_winner_single_player(self):
        """Test determining winner when only one player remains."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        # All players except human fold
        players = self.game_engine.table.get_players_in_order()
        for player in players:
            if player != self.human_player:
                player.fold()
                
        winners = self.game_engine._determine_winners()
        
        assert len(winners) == 1
        assert winners[0] == self.human_player
        
    def test_determine_winner_showdown(self):
        """Test determining winner at showdown."""
        # Set up game
        self.game_engine._setup_cash_game_table(2, 10, 20)  # Heads up
        
        # Community cards: K♠ 9♠ 2♥ 7♣ 4♦
        self.game_engine.community_cards = [
            Card(Suit.SPADES, Rank.KING),
            Card(Suit.SPADES, Rank.NINE),
            Card(Suit.HEARTS, Rank.TWO),
            Card(Suit.CLUBS, Rank.SEVEN),
            Card(Suit.DIAMONDS, Rank.FOUR)
        ]
        
        # Give human pocket aces (strong hand: pair of aces)
        self.human_player.deal_hole_cards([
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.ACE)
        ])
        
        # Give opponent weaker pair (kings with worse kicker)
        opponent = None
        for player in self.game_engine.table.get_players_in_order():
            if player != self.human_player:
                opponent = player
                break
                
        opponent.deal_hole_cards([
            Card(Suit.CLUBS, Rank.KING),
            Card(Suit.DIAMONDS, Rank.THREE)
        ])
        
        winners = self.game_engine._determine_winners()
        
        # Human should win with aces over kings
        assert len(winners) == 1
        assert winners[0] == self.human_player
        
    def test_distribute_pot_single_winner(self):
        """Test distributing pot to single winner."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        self.game_engine.pot.add_bet(self.human_player, 100)
        
        # Human wins
        winners = [self.human_player]
        original_bankroll = self.human_player.bankroll
        
        self.game_engine._distribute_pot(winners)
        
        assert self.human_player.bankroll == original_bankroll + 100
        assert self.game_engine.pot.total == 0
        
    def test_distribute_pot_split(self):
        """Test distributing split pot."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        # Two winners
        players = self.game_engine.table.get_players_in_order()
        winner1 = players[0]
        winner2 = players[1]
        
        self.game_engine.pot.add_bet(winner1, 50)
        self.game_engine.pot.add_bet(winner2, 50)
        
        original_bankroll1 = winner1.bankroll
        original_bankroll2 = winner2.bankroll
        
        self.game_engine._distribute_pot([winner1, winner2])
        
        # Each should get half
        assert winner1.bankroll == original_bankroll1 + 50
        assert winner2.bankroll == original_bankroll2 + 50
        
    def test_player_action_fold(self):
        """Test player fold action."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        # Mock input for fold
        self.mock_input_handler.get_menu_choice.return_value = 3  # Fold option
        
        action, amount = self.game_engine._get_human_player_action({
            'current_bet': 20,
            'min_raise': 20,
            'can_check': False
        })
        
        assert action == PlayerAction.FOLD
        assert amount == 0
        
    def test_player_action_call(self):
        """Test player call action."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        # Mock input for call
        self.mock_input_handler.get_menu_choice.return_value = 1  # Call option
        with patch.object(self.human_player, 'current_bet', 0):
            action, amount = self.game_engine._get_human_player_action({
                'current_bet': 20,
                'min_raise': 20,
                'can_check': False
            })
        
        assert action == PlayerAction.CALL
        assert amount == 20
        
    def test_player_action_raise(self):
        """Test player raise action."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        # Mock input for raise
        self.mock_input_handler.get_menu_choice.return_value = 2  # Raise option
        self.mock_input_handler.get_number_input.return_value = 60  # Raise to 60
        
        action, amount = self.game_engine._get_human_player_action({
            'current_bet': 20,
            'min_raise': 20,
            'can_check': False
        })
        
        assert action == PlayerAction.RAISE
        assert amount == 60
        
    def test_player_action_check(self):
        """Test player check action."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        # Mock input for check
        self.mock_input_handler.get_menu_choice.return_value = 1  # Check option (when available)
        
        action, amount = self.game_engine._get_human_player_action({
            'current_bet': 0,
            'min_raise': 20,
            'can_check': True
        })
        
        assert action == PlayerAction.CHECK
        assert amount == 0
        
    def test_player_all_in(self):
        """Test player all-in action."""
        # Set up game with short stack
        short_stack_player = Player("ShortStack", 50)
        self.game_engine.human_player = short_stack_player
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        # Short stack player is already added as human_player during setup
        # Just test the all-in functionality
        amount = short_stack_player.go_all_in()
        
        assert short_stack_player.all_in
        assert short_stack_player.bankroll == 0
        assert amount == 50
        
    def test_game_state_transitions(self):
        """Test game state transitions through hand."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        # Initial state
        assert self.game_engine.game_state == GameState.WAITING
        
        # Start hand
        self.game_engine.game_state = GameState.PREFLOP
        assert self.game_engine.game_state == GameState.PREFLOP
        
        # Progress through states
        self.game_engine.game_state = GameState.FLOP
        assert self.game_engine.game_state == GameState.FLOP
        
        self.game_engine.game_state = GameState.TURN
        assert self.game_engine.game_state == GameState.TURN
        
        self.game_engine.game_state = GameState.RIVER
        assert self.game_engine.game_state == GameState.RIVER
        
        self.game_engine.game_state = GameState.SHOWDOWN
        assert self.game_engine.game_state == GameState.SHOWDOWN
        
    def test_betting_round_completion(self):
        """Test betting round completion conditions."""
        # Set up game
        self.game_engine._setup_cash_game_table(4, 10, 20)
        
        # All players call
        players = self.game_engine.table.get_players_in_order()
        for player in players:
            player.place_bet(20)
        
        players_acted = {p: True for p in players}
        assert self.game_engine._is_betting_round_complete(players, players_acted, 20)
        
        # One player raises
        players[0].add_to_bet(30)  # Raise to 50 total
        
        players_acted = {p: True for p in players}
        players_acted[players[0]] = False
        assert not self.game_engine._is_betting_round_complete(players, players_acted, 50)
        
        # Others call the raise
        for player in players[1:]:
            player.add_to_bet(30)
            
        players_acted = {p: True for p in players}
        assert self.game_engine._is_betting_round_complete(players, players_acted, 50)
        
    def test_side_pot_creation(self):
        """Test side pot creation with all-in players."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        players = self.game_engine.table.get_players_in_order()
        
        # One player goes all-in for less
        short_stack = players[0]
        short_stack.bankroll = 100  # Set short stack
        short_stack.go_all_in()
        self.game_engine.pot.add_bet(short_stack, 100)
        
        # Others bet more
        for player in players[1:]:
            player.place_bet(200)
            self.game_engine.pot.add_bet(player, 200)
            
        self.game_engine.pot.create_side_pots()
        
        # Should create side pot
        assert len(self.game_engine.pot.side_pots) >= 1
        
    def test_tournament_blind_increases(self):
        """Test tournament blind level increases."""
        # Set up tournament
        self.game_engine.tournament_mode = True
        self.game_engine.blind_level = 1
        self.game_engine.small_blind = 25
        self.game_engine.big_blind = 50
        self.game_engine.hands_played = 0
        
        # Simulate hands played
        self.game_engine.hands_played = 20  # Trigger blind increase
        
        self.game_engine._check_blind_increase()
        
        # Blinds should have increased
        assert self.game_engine.small_blind > 25
        assert self.game_engine.big_blind > 50
        assert self.game_engine.blind_level > 1
        
    def test_tournament_elimination(self):
        """Test player elimination in tournament."""
        # Set up tournament
        self.game_engine._setup_tournament_table(4, 10000)
        self.game_engine.tournament_mode = True
        
        # Get total seated players before elimination
        all_players_before = len(self.game_engine.table.get_players_in_order())
        
        players = self.game_engine.table.get_players_in_order()
        eliminated_player = players[0]
        
        # Eliminate player (bankroll = 0)
        eliminated_player.bankroll = 0
        
        # Call handle_eliminations to remove the player from table
        self.game_engine._handle_eliminations()
        
        # Check that player was removed from table
        all_players_after = len(self.game_engine.table.get_players_in_order())
        
        # One less player should be seated at the table
        assert all_players_after == all_players_before - 1
        assert eliminated_player not in self.game_engine.table.get_players_in_order()
        
    def test_game_statistics_tracking(self):
        """Test game statistics tracking."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        
        # Simulate hand completion
        self.game_engine.hands_played = 0
        self.game_engine._complete_hand()
        
        assert self.game_engine.hands_played == 1
        
        # Player statistics should be updated
        # (This would be implemented in the actual game engine)
        
    def test_game_state_serialization(self):
        """Test game state serialization for saving/loading."""
        # Set up game
        self.game_engine._setup_cash_game_table(3, 10, 20)
        self.game_engine._deal_hole_cards()
        self.game_engine.community_cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.KING),
            Card(Suit.CLUBS, Rank.QUEEN)
        ]
        
        game_state = self.game_engine.get_game_state()
        
        assert 'game_state' in game_state
        assert 'community_cards' in game_state
        assert 'pot_size' in game_state
        assert 'players' in game_state
        assert 'blinds' in game_state
