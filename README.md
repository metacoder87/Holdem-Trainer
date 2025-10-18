# PyHoldem Pro - Terminal Texas Hold'em Poker

A comprehensive terminal-based Texas Hold'em Poker game written in Python featuring both cash games and tournaments with AI opponents and detailed statistics.

## Features

- **Multiple Game Modes**: Cash games and tournaments with limit/no-limit variants
- **AI Opponents**: Cautious, wild, balanced, and random playing styles
- **Comprehensive Statistics**: Pot odds, hand odds, and performance analytics
- **Persistent Player Data**: JSON-based player profiles and bankrolls
- **Professional Interface**: Rich terminal UI with real-time updates

## Installation

1. Clone the repository:
```bash
git clone <repository_url>
cd pyholdem_pro
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the game:
```bash
python main.py
```

## Testing

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=src --cov-report=html
```

## Game Rules

Standard Texas Hold'em rules apply:
- Each player receives 2 hole cards
- 5 community cards dealt in stages (flop, turn, river)
- Best 5-card hand wins
- Standard poker hand rankings

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License.
