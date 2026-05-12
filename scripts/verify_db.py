import os
import sys
import uuid
from datetime import datetime

# Setup path
sys.path.append(os.path.join(os.getcwd(), "src"))
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Force DB usage
os.environ["PYHOLDEM_USE_DB"] = "true"
# Use the port we configured (5435)
os.environ["PYHOLDEM_DB_URL"] = "postgresql://postgres:postgres@localhost:5435/holdem_trainer"

from data.manager import DataManager

def verify():
    print("Initializing DataManager with DB...")
    manager = DataManager()
    
    # 1. Create Player
    player_name = f"TestPlayer_{uuid.uuid4().hex[:8]}"
    print(f"Creating player: {player_name}")
    try:
        manager.create_player(player_name, 10000)
    except ValueError as e:
        print(f"Player creation error (expected if exists): {e}")

    # 2. Create Session
    session_id = uuid.uuid4().hex
    print(f"Creating session: {session_id}")
    manager.create_session({
        "id": session_id,
        "player_name": player_name,
        "game_type": "cash",
        "limit_type": "no_limit",
        "config": {"buy_in": 1000}
    })

    # 3. Verify Session Exists
    sessions = manager.get_sessions(player_name)
    print(f"Sessions found: {len(sessions)}")
    assert len(sessions) > 0, "No sessions found!"
    assert sessions[0]["id"] == session_id, "Session ID mismatch"

    # 4. Save Hand
    print("Saving hand history...")
    hand_record = {
        "session_id": session_id,
        "hand_number": 1,
        "players": [{"name": player_name, "hole_cards": ["Ah", "As"], "is_human": True}],
        "board_cards": ["Kd", "Qd", "Jd", "10d", "9d"],
        "winner": player_name,
        "pot_size": 200,
        "actions": []
    }
    manager.append_hand_history(player_name, hand_record)

    # 5. Verify Hand Filter
    print("Verifying hand filter...")
    hands = manager.get_filtered_hands(player_name, winner=player_name)
    print(f"Hands found: {len(hands)}")
    assert len(hands) > 0, "No hands found!"
    assert hands[0]["pot_size"] == 200, "Pot size mismatch"

    print("\nSUCCESS! Database integration verified.")

if __name__ == "__main__":
    verify()
