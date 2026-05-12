from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

try:
    from sqlalchemy.dialects.postgresql import JSONB as JsonType
except Exception:
    from sqlalchemy import JSON as JsonType  # type: ignore

from sqlalchemy import DateTime, ForeignKey, Integer, String, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PlayerRecord(Base):
    __tablename__ = "players"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    bankroll: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_played: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    skill_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    data: Mapped[Dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)

    # Relationships
    sessions: Mapped[list["GameSession"]] = relationship(back_populates="player")
    hands: Mapped[list["HandRecord"]] = relationship(back_populates="player")


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    player_name: Mapped[str] = mapped_column(ForeignKey("players.name", ondelete="CASCADE"), index=True)
    game_type: Mapped[str] = mapped_column(String(32), nullable=False)
    limit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Validation/Stats
    buy_in: Mapped[int] = mapped_column(Integer, default=0)
    cash_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hands_played: Mapped[int] = mapped_column(Integer, default=0)
    
    # Store full config just in case
    config: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict)

    player: Mapped["PlayerRecord"] = relationship(back_populates="sessions")
    hands: Mapped[list["HandRecord"]] = relationship(back_populates="session")


class HandRecord(Base):
    __tablename__ = "hands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("game_sessions.id", ondelete="SET NULL"), index=True)
    player_name: Mapped[str] = mapped_column(ForeignKey("players.name", ondelete="CASCADE"), index=True)
    
    hand_number: Mapped[int] = mapped_column(Integer, default=0)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Searchable fields (The "Wow" factor)
    hole_cards: Mapped[Optional[list[str]]] = mapped_column(JsonType) # ["Ah", "Ks"]
    board_cards: Mapped[Optional[list[str]]] = mapped_column(JsonType) 
    winner: Mapped[Optional[str]] = mapped_column(String(64))
    winning_hand_rank: Mapped[Optional[str]] = mapped_column(String(32)) # "Flush", "High Card"
    pot_size: Mapped[int] = mapped_column(Integer, default=0)
    
    # Full hand history blob
    data: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict)

    player: Mapped["PlayerRecord"] = relationship(back_populates="hands")
    session: Mapped["GameSession"] = relationship(back_populates="hands")
