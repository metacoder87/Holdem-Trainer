from __future__ import annotations

import json
import math
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from data.models import Base, GameSession, HandRecord, PlayerRecord
from data.schema import PLAYER_SCHEMA
from jsonschema import ValidationError, validate


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


class PostgresStore:
    def __init__(self, db_url: str) -> None:
        if not db_url:
            raise ValueError("Database URL is required")

        self.engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        # Base.metadata.create_all(self.engine) # Managed by Alembic now

    @contextmanager
    def _session_scope(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --- Player Methods ---

    def _row_to_record(self, row: PlayerRecord) -> Dict[str, Any]:
        record = dict(row.data or {})
        record["name"] = row.name
        record["bankroll"] = int(row.bankroll)
        if row.created_at:
            record.setdefault("created_at", row.created_at.isoformat())
        if row.last_played:
            record["last_played"] = row.last_played.isoformat()
        if row.skill_level is not None:
            record["skill_level"] = row.skill_level
        return record

    def create_player(self, name: str, initial_bankroll: int) -> Dict[str, Any]:
        name = name.strip()
        now = _now()
        record = {
            "name": name,
            "bankroll": int(initial_bankroll),
            "created_at": now.isoformat(),
            "last_played": now.isoformat(),
            "games_played": 0,
            "games_won": 0,
            "total_winnings": 0.0,
            "hands_played": 0,
            "hands_won": 0,
            "biggest_pot": 0.0,
        }

        with self._session_scope() as session:
            row = PlayerRecord(
                name=name,
                bankroll=int(initial_bankroll),
                created_at=now,
                last_played=now,
                skill_level=None,
                data=record,
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError as exc:
                raise ValueError(f"Player '{name}' already exists") from exc

        return record

    def get_player(self, name: str) -> Optional[Dict[str, Any]]:
        with self._session_scope() as session:
            row = session.get(PlayerRecord, name.strip())
            return self._row_to_record(row) if row else None
            
    def save_player(self, player) -> None:
        # Compatibility wrapper for existing code that passes a Player object
        stats = {}
        for attr in ("hands_played", "hands_won", "total_winnings"):
            if hasattr(player, attr):
                stats[attr] = getattr(player, attr)
        
        with self._session_scope() as session:
             row = session.get(PlayerRecord, player.name)
             if row:
                 record = dict(row.data or {})
                 record["bankroll"] = player.bankroll
                 for k, v in stats.items():
                     record[k] = v
                 
                 row.bankroll = int(player.bankroll)
                 row.last_played = _now()
                 row.data = record

    def list_players(self, sort_by: str = "name", reverse: bool = False) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
            stmt = select(PlayerRecord)
            rows = session.execute(stmt).scalars().all()
            players = [self._row_to_record(r) for r in rows]
        
        # In-memory sort for simplicity as data blob fields might not be indexable easily without JSON operators
        def sort_key(p):
            return p.get(sort_by) or 0
        
        players.sort(key=sort_key, reverse=reverse)
        return players

    # --- Session Methods (NEW) ---

    def create_session(self, session_data: Dict[str, Any]) -> None:
        with self._session_scope() as session:
            # Ensure player exists or link it? 
            # session_data has 'player_name', 'id' (uuid), 'game_type' etc.
            
            # Verify player exists
            player_name = session_data.get("player_name")
            if player_name and not session.get(PlayerRecord, player_name):
                # If guest/temp, maybe don't persist link? Or create dummy?
                # For now, require valid player if provided.
                pass

            row = GameSession(
                id=session_data["id"],
                player_name=player_name,
                game_type=session_data.get("game_type", "cash"),
                limit_type=session_data.get("limit_type", "no_limit"),
                created_at=_now(),
                buy_in=int(session_data.get("config", {}).get("buy_in", 0) or 0),
                hands_played=0,
                config=session_data.get("config", {}),
                data=_json_safe(dict(session_data)),
            )
            session.add(row)

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        with self._session_scope() as session:
            row = session.get(GameSession, session_id)
            if row:
                data = dict(row.data or {})
                data.update(_json_safe(updates))
                row.data = data
                if "hands_played" in updates:
                     row.hands_played = updates["hands_played"]
                if "ended_at" in updates:
                    row.ended_at = _parse_datetime(updates["ended_at"])
                if "bankroll_end" in updates:
                    row.cash_out = _safe_int(updates["bankroll_end"])
                elif "cash_out" in updates:
                    row.cash_out = _safe_int(updates["cash_out"])

    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._session_scope() as session:
            row = session.get(GameSession, session_id)
            if not row:
                return None
            data = dict(row.data or {})
            data.update(
                {
                    "id": row.id,
                    "player_name": row.player_name,
                    "game_type": row.game_type,
                    "limit_type": row.limit_type,
                    "created_at": row.created_at.isoformat() if row.created_at else data.get("created_at"),
                    "ended_at": row.ended_at.isoformat() if row.ended_at else data.get("ended_at"),
                    "hands_played": row.hands_played,
                    "buy_in": row.buy_in,
                    "cash_out": row.cash_out,
                }
            )
            return data

    def get_sessions(self, player_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
            stmt = select(GameSession).where(GameSession.player_name == player_name).order_by(GameSession.created_at.desc()).limit(limit)
            rows = session.execute(stmt).scalars().all()
            results = []
            for r in rows:
                data = dict(r.data or {})
                data.update({
                    "id": r.id,
                    "player_name": r.player_name,
                    "game_type": r.game_type,
                    "limit_type": r.limit_type,
                    "created_at": r.created_at.isoformat() if r.created_at else data.get("created_at"),
                    "ended_at": r.ended_at.isoformat() if r.ended_at else data.get("ended_at"),
                    "hands_played": r.hands_played,
                    "buy_in": r.buy_in,
                    "cash_out": r.cash_out,
                    "net_result": (r.cash_out - r.buy_in) if r.cash_out is not None else data.get("net_result", 0),
                })
                results.append(data)
            return results

    def get_filtered_hands(
        self,
        player_name: str,
        winner: Optional[str] = None,
        min_pot: Optional[int] = None,
        limit: int = 50,
        session_id: Optional[str] = None,
        game_type: Optional[str] = None,
        street: Optional[str] = None,
        decision_quality: Optional[str] = None,
        weakness: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
             stmt = select(HandRecord).where(HandRecord.player_name == player_name)
             
             if winner:
                 if winner == "hero":
                     stmt = stmt.where(HandRecord.winner == player_name)
                 else:
                     stmt = stmt.where(HandRecord.winner == winner)
             
             if min_pot:
                 stmt = stmt.where(HandRecord.pot_size >= min_pot)

             if session_id:
                 stmt = stmt.where(HandRecord.session_id == session_id)
             
             stmt = stmt.order_by(HandRecord.saved_at.desc()).limit(max(limit * 5, limit))
             rows = session.execute(stmt).scalars().all()
             records = []
             for row in rows:
                 hand = dict(row.data or {})
                 meta = hand.get("meta") if isinstance(hand.get("meta"), dict) else {}
                 if game_type and str(meta.get("game_type") or hand.get("game_type") or "").lower() != str(game_type).lower():
                     continue
                 if street:
                     actions = hand.get("actions") or []
                     decisions = hand.get("decision_points") or []
                     has_street = any(isinstance(action, dict) and action.get("betting_round") == street for action in actions)
                     has_street = has_street or any(
                         isinstance(decision, dict) and decision.get("betting_round") == street for decision in decisions
                     )
                     if not has_street:
                         continue
                 if decision_quality:
                     decisions = hand.get("decision_points") or []
                     if not any(
                         isinstance(decision, dict)
                         and str(decision.get("quality") or "").lower() == str(decision_quality).lower()
                         for decision in decisions
                     ):
                         continue
                 if weakness:
                     if str(weakness).lower() not in json.dumps(hand.get("decision_points") or [], ensure_ascii=False).lower():
                         continue
                 records.append(hand)
                 if len(records) >= limit:
                     break
             return records

    # --- Hand History Methods ---

    def append_hand_history(self, player_name: str, hand_record: Dict[str, Any]) -> str:
        winners = hand_record.get("winners")
        if isinstance(winners, list) and winners:
            winner = str(winners[0])
        else:
            winner = hand_record.get("winner")

        pot = _safe_int(hand_record.get("pot_total", hand_record.get("pot_size", 0)))
        hero_cards = hand_record.get("hero_hole_cards")
        if hero_cards is None:
            for player in hand_record.get("players", []):
                if isinstance(player, dict) and player.get("name") == player_name:
                    hero_cards = player.get("hole_cards")
                    break

        board = hand_record.get("board", hand_record.get("board_cards"))
        meta = hand_record.get("meta") or {}
        session_id = hand_record.get("session_id") or meta.get("session_id")

        with self._session_scope() as session:
            row = HandRecord(
                player_name=player_name,
                session_id=session_id,
                hand_number=hand_record.get("hand_number", 0),
                saved_at=_now(),
                hole_cards=hero_cards,
                board_cards=board,
                winner=winner,
                pot_size=pot,
                data=hand_record
            )
            session.add(row)
        
        return "db://hands"

    def load_hand_history(self, player_name: str, limit: int = 200, reverse: bool = True) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
            stmt = select(HandRecord).where(HandRecord.player_name == player_name)
            if reverse:
                stmt = stmt.order_by(HandRecord.saved_at.desc())
            else:
                stmt = stmt.order_by(HandRecord.saved_at.asc())
            
            stmt = stmt.limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [dict(r.data) for r in rows]

    # --- Passthrough for existing methods ---
    def update_player_bankroll(self, name: str, amount: int):
        with self._session_scope() as session:
            row = session.get(PlayerRecord, name)
            if row:
                row.bankroll = amount
                record = dict(row.data or {})
                record["bankroll"] = amount
                record["last_played"] = _now().isoformat()
                row.data = record
                row.last_played = _now()

    def update_player_stats(self, name: str, stats: Dict[str, Any]):
         with self._session_scope() as session:
             row = session.get(PlayerRecord, name)
             if row:
                record = dict(row.data or {})
                record.update(_json_safe(stats))
                row.data = record
                if "bankroll" in stats:
                    row.bankroll = _safe_int(stats["bankroll"])
                if "skill_level" in stats:
                    row.skill_level = stats["skill_level"]
                row.last_played = _now()

    def player_exists(self, name: str) -> bool:
         with self._session_scope() as session:
             return session.get(PlayerRecord, name) is not None

    def get_data_summary(self) -> Dict[str, Any]:
        with self._session_scope() as session:
            count = session.scalar(select(func.count()).select_from(PlayerRecord))
            total_bankroll = session.scalar(select(func.coalesce(func.sum(PlayerRecord.bankroll), 0)))
            total_sessions = session.scalar(select(func.count()).select_from(GameSession))
            return {
                "total_players": int(count or 0),
                "total_bankroll": int(total_bankroll or 0),
                "total_games_played": int(total_sessions or 0),
                "file_exists": True,
            }

    def cleanup_inactive_players(self, days_inactive: int = 365):
        pass

    def export_data(self, export_file: str, format: str = "json"):
        pass

    def delete_player(self, name: str):
        with self._session_scope() as session:
            row = session.get(PlayerRecord, name)
            if row:
                session.delete(row)
