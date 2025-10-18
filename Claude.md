# PyHoldem Pro - Terminal Texas Hold'em Poker

## Game Overview
**PyHoldem Pro** is a comprehensive terminal-based Texas Hold'em Poker game written in Python. The game features both cash games and tournaments with limit and no-limit variations, complete with AI opponents and detailed poker statistics.

## Core Features

### 1. Game Name
**PyHoldem Pro** - A professional-grade Python implementation of Texas Hold'em

### 2. Card System
- Standard 52-card deck
- 4 suits: Hearts (♥), Diamonds (♦), Spades (♠), Clubs (♣)
- 13 ranks: 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A
- Ace values: 1 (low) or 14 (high) depending on context
- Randomized shuffling before each hand

### 3. Game Modes

#### Cash Games
- Limit and No-Limit variants
- Blinds structure: 1/2, 2/4, 5/10, 10/20, 25/50, 50/100, ..., 500,000/1,000,000
- Minimum buy-in: 10 big blinds
- Players can leave anytime with their chips

#### Tournaments
- Limit and No-Limit variants
- Buy-ins: 50 to 50,000,000 chips
- Increasing blinds at regular intervals
- Single elimination format
- Winner takes all (or structured payouts)

### 4. Player Management
- Create new players or load existing ones
- Player data stored in JSON format
- Persistent bankrolls across sessions
- Player statistics tracking

### 5. Table Structure
- 2-9 players per table (user + 1-8 AI opponents)
- Dealer button rotation
- Small blind / Big blind positions
- Automatic blind posting

### 6. AI Opponents
- **Cautious Players**: Conservative betting, fold often
- **Wild Players**: Aggressive betting, bluff frequently  
- **Balanced Players**: Mathematical approach, optimal play
- **Random Players**: Unpredictable, simulate beginners

### 7. Game Flow
1. Pre-flop: Deal 2 cards to each player
2. Betting round 1 (starting left of big blind)
3. Flop: Burn 1 card, deal 3 community cards
4. Betting round 2
5. Turn: Burn 1 card, deal 1 community card
6. Betting round 3
7. River: Burn 1 card, deal 1 community card
8. Final betting round
9. Showdown (if multiple players remain)

### 8. Hand Rankings (High to Low)
1. Royal Flush
2. Straight Flush
3. Four of a Kind
4. Full House
5. Flush
6. Straight
7. Three of a Kind
8. Two Pair
9. One Pair
10. High Card

### 9. User Interface
- Clear terminal-based display
- Real-time game state visualization
- Player cards (face up for user, face down for others)
- Community cards
- Pot size and individual contributions
- Current betting action
- Player statistics and bankrolls

### 10. Statistics & Analytics
- **Pot Odds**: Ratio of pot size to bet required
- **Hand Odds**: Probability of improving hand
- **Outs**: Number of cards that improve hand
- **Expected Value (EV)**: Mathematical expectation
- **Position Analysis**: Strength based on seating
- **Opponent Tendencies**: AI player patterns
- **Historical Performance**: Win/loss statistics

## Technical Architecture

### 1. Core Classes
```python
class Card:
    # Represents individual playing card
    
class Deck:
    # 52-card deck with shuffle functionality
    
class Player:
    # Player data, bankroll, actions
    
class AIPlayer(Player):
    # AI decision making logic
    
class Hand:
    # Hand evaluation and comparison
    
class Pot:
    # Pot management and side pots
    
class Game:
    # Main game logic and flow control
    
class Table:
    # Table state and player management
    
class Tournament:
    # Tournament-specific logic
    
class CashGame:
    # Cash game specific logic
    
class Statistics:
    # Poker statistics calculations
    
class UI:
    # Terminal user interface
    
class DataManager:
    # JSON file operations for player data
```

### 2. File Structure
```
pyholdem_pro/
├── src/
│   ├── __init__.py
│   ├── game/
│   │   ├── __init__.py
│   │   ├── card.py
│   │   ├── deck.py
│   │   ├── hand.py
│   │   ├── player.py
│   │   ├── ai_player.py
│   │   ├── pot.py
│   │   ├── table.py
│   │   ├── game_engine.py
│   │   ├── cash_game.py
│   │   └── tournament.py
│   ├── stats/
│   │   ├── __init__.py
│   │   ├── calculator.py
│   │   └── analyzer.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── display.py
│   │   └── input_handler.py
│   ├── data/
│   │   ├── __init__.py
│   │   └── manager.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── tests/
│   ├── __init__.py
│   ├── test_card.py
│   ├── test_deck.py
│   ├── test_hand.py
│   ├── test_player.py
│   ├── test_ai_player.py
│   ├── test_pot.py
│   ├── test_table.py
│   ├── test_game_engine.py
│   ├── test_cash_game.py
│   ├── test_tournament.py
│   ├── test_statistics.py
│   ├── test_ui.py
│   └── test_data_manager.py
├── data/
│   └── players.json
├── main.py
├── requirements.txt
├── README.md
├── Claude.md
└── .gitignore
```

### 3. Dependencies
- **pytest**: Testing framework
- **colorama**: Terminal colors and formatting
- **rich**: Enhanced terminal UI
- **click**: Command-line interface
- **jsonschema**: JSON data validation

### 4. Data Persistence
- Player data stored in `data/players.json`
- JSON schema validation for data integrity
- Automatic backup system for player data

## Development Phases

### Phase 1: Core Foundation
- [ ] Basic card and deck implementation
- [ ] Hand evaluation system
- [ ] Player data management
- [ ] JSON persistence layer

### Phase 2: Game Engine
- [ ] Basic game flow implementation
- [ ] Betting rounds and pot management
- [ ] Table state management
- [ ] Basic UI framework

### Phase 3: AI Implementation
- [ ] AI player decision algorithms
- [ ] Different AI personality types
- [ ] AI betting patterns and strategies

### Phase 4: Game Modes
- [ ] Cash game implementation
- [ ] Tournament structure
- [ ] Blind level management

### Phase 5: Statistics & Analytics
- [ ] Pot odds calculations
- [ ] Hand probability analysis
- [ ] Player performance tracking
- [ ] Advanced statistics

### Phase 6: Enhanced UI
- [ ] Rich terminal interface
- [ ] Real-time updates
- [ ] Color coding and formatting
- [ ] Help system and tutorials

### Phase 7: Testing & Polish
- [ ] Comprehensive test coverage
- [ ] Performance optimization
- [ ] Bug fixes and edge cases
- [ ] Documentation completion

## Testing Strategy

### Unit Tests
- Individual class functionality
- Edge case handling
- Data validation
- Mathematical calculations

### Integration Tests
- Game flow scenarios
- AI interaction
- Data persistence
- UI components

### End-to-End Tests
- Complete game sessions
- Tournament simulations
- Player data lifecycle
- Error handling

## Performance Considerations
- Efficient hand evaluation algorithms
- Optimized AI decision making
- Minimal memory footprint
- Fast JSON operations

## Future Enhancements
- Online multiplayer support
- Advanced statistics dashboard
- Hand history replay
- Custom AI training
- Mobile terminal compatibility

## Success Metrics
- All tests passing (100% coverage goal)
- Smooth gameplay experience
- Accurate poker rules implementation
- Realistic AI behavior
- Comprehensive statistics
- Stable data persistence

This document serves as the blueprint for developing PyHoldem Pro, ensuring all requirements are met while maintaining high code quality and user experience standards.
