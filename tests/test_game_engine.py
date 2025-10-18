"""
Test suite for GameEngine class.
Tests main game logic, flow control, and rule enforcement.
"""
import pytest
from unittest.mock import Mock, patch
from src.game.game_engine import GameEngine, GameState, BettingRound
from src.game.player import Player, PlayerAction
from src.game.ai_player import AIPlayer, AIStyle
from src.game.table import Table, TableType
from src.game.card import Card, Suit, Rank
from src.game.pot import Pot


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
        self.game_engine._setup_cash_game_table(3, 10, 20)
        self.game_engine._deal_hole_cards()
        self.game_engine._post_blinds()
        
        # Mock player decisions
        def mock_get_player_action(player, game_state):
            if player == self.human_player:
                return PlayerAction.CALL, 20
            else:
                return PlayerAction.FOLD, 0
                
        with patch.object(self.game_engine, '_get_player_action', side_effect=mock_get_player_action):
            self.game_engine._run_betting_round(BettingRound.PREFLOP)
            
        # Human should have called, others folded
        assert self.human_player.current_bet == 20
        
        # Check folded status
        active_players = self.game_engine.table.get_active_players()
        assert len(active_players) == 2  # Human + big blind
        
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
        self.game_engine.community_cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.KING),
            Card(Suit.CLUBS, Rank.QUEEN),
            Card(Suit.SPADES, Rank.JACK),
            Card(Suit.HEARTS, Rank.TEN)
        ]
        
        # Give human a royal flush
        self.human_player.deal_hole_cards([
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.HEARTS, Rank.QUEEN)
        ])
        
        # Give opponent a weaker hand
        opponent = None
        for player in self.game_engine.table.get_players_in_order():
            if player != self.human_player:
                opponent = player
                break
                
        opponent.deal_hole_cards([
            Card(Suit.CLUBS, Rank.TWO),
            Card(Suit.SPADES, Rank.THREE)
        ])
        
        winners = self.game_engine._determine_winners()
        
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
        self.mock_input_handler.get_menu_choice.return_value = 1  # Fold option
        
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
        self.mock_input_handler.get_menu_choice.return_value = 2  # Call option
        
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
        self.mock_input_handler.get_menu_choice.return_value = 3  # Raise option
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
        
        # Replace one AI with our short stack player
        players = list(self.game_engine.table.get_players_in_order())
        self.game_engine.table.remove_player(players[-1])
        self.game_engine.table.add_player(short_stack_player)
        
        # All-in with entire stack
        action, amount = short_stack_player.go_all_in()
        
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
            
        assert self.game_engine._is_betting_round_complete()
        
        # One player raises
        players[0].add_to_bet(30)  # Raise to 50 total
        
        assert not self.game_engine._is_betting_round_complete()
        
        # Others call the raise
        for player in players[1:]:
            player.add_to_bet(30)
            
        assert self.game_engine._is_betting_round_complete()
        
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
        self.game_engine._setup_tournament_table(3, 1000)
        self.game_engine.tournament_mode = True
        
        players = self.game_engine.table.get_players_in_order()
        eliminated_player = players[0]
        
        # Eliminate player (bankroll = 0)
        eliminated_player.bankroll = 0
        
        active_players_before = len(self.game_engine.table.get_active_players())
        self.game_engine._handle_eliminations()
        active_players_after = len(self.game_engine.table.get_active_players())
        
        assert active_players_after == active_players_before - 1
        
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
