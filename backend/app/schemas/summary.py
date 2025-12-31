from typing import List, Optional

from pydantic import BaseModel


class Metric(BaseModel):
    label: str
    value: str
    delta: str
    tone: str


class TrainingTrack(BaseModel):
    title: str
    summary: str
    cadence: str
    intensity: str
    progress: int


class TimelineEntry(BaseModel):
    time: str
    label: str
    detail: str


class PlayerSummary(BaseModel):
    name: str
    skill_level: Optional[str] = None
    last_played: Optional[str] = None


class SummaryResponse(BaseModel):
    player: PlayerSummary
    live_metrics: List[Metric]
    training_tracks: List[TrainingTrack]
    focus_queue: List[str]
    timeline: List[TimelineEntry]
