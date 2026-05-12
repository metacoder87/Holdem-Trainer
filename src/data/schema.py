PLAYER_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "bankroll": {"type": "number", "minimum": 0},
        "created_at": {"type": "string"},
        "last_played": {"type": "string"},
        "games_played": {"type": "integer", "minimum": 0},
        "games_won": {"type": "integer", "minimum": 0},
        "total_winnings": {"type": "number"},
        "hands_played": {"type": "integer", "minimum": 0},
        "hands_won": {"type": "integer", "minimum": 0},
        "biggest_pot": {"type": "number", "minimum": 0},
    },
    "required": ["name", "bankroll", "created_at"],
    "additionalProperties": True,
}
