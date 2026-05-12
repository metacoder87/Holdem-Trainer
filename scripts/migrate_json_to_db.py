import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Tuple

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data.postgres_store import PostgresStore


def _load_players(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict) and "players" in data and isinstance(data["players"], dict):
        return data["players"]
    if isinstance(data, dict):
        return data
    return {}


def _load_hand_histories(hand_dir: Path) -> Iterable[Tuple[str, dict]]:
    if not hand_dir.exists():
        return []
    for path in sorted(hand_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                meta = record.get("meta") or {}
                player_name = meta.get("hero_name") or record.get("hero_name") or record.get("player_name")
                if not player_name:
                    continue
                yield player_name, record


def _create_stub_player(store: PostgresStore, name: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    store.import_players_data(
        {
            name: {
                "name": name,
                "bankroll": 0,
                "created_at": now,
                "last_played": now,
                "games_played": 0,
                "games_won": 0,
                "total_winnings": 0.0,
                "hands_played": 0,
                "hands_won": 0,
                "biggest_pot": 0.0,
            }
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate JSON persistence to PostgreSQL.")
    parser.add_argument("--db-url", required=True, help="PostgreSQL connection URL.")
    parser.add_argument("--players-file", default="data/players.json", help="Path to players.json.")
    parser.add_argument(
        "--hand-history-dir", default="data/hand_histories", help="Path to JSONL hand history directory."
    )
    parser.add_argument(
        "--skip-hand-histories", action="store_true", help="Skip importing JSONL hand histories."
    )
    parser.add_argument(
        "--create-missing-players",
        action="store_true",
        help="Create stub players when importing hand histories.",
    )

    args = parser.parse_args()

    store = PostgresStore(args.db_url)
    players_path = Path(args.players_file)
    hand_dir = Path(args.hand_history_dir)

    players = _load_players(players_path)
    if players:
        imported = store.import_players_data(players)
        print(f"Imported {imported} players from {players_path}.")
    else:
        print(f"No players loaded from {players_path}.")

    if args.skip_hand_histories:
        return

    imported_hands = 0
    for player_name, record in _load_hand_histories(hand_dir):
        try:
            store.append_hand_history(player_name, record)
            imported_hands += 1
        except ValueError:
            if args.create_missing_players:
                _create_stub_player(store, player_name)
                store.append_hand_history(player_name, record)
                imported_hands += 1

    print(f"Imported {imported_hands} hand histories from {hand_dir}.")


if __name__ == "__main__":
    main()
