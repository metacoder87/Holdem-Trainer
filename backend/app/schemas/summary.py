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


class FocusQueueItem(BaseModel):
    id: Optional[str] = None  # focus_area id when one applies
    label: str


class SummaryResponse(BaseModel):
    player: PlayerSummary
    live_metrics: List[Metric]
    training_tracks: List[TrainingTrack]
    # Kept as a list of plain labels for backward compatibility.
    focus_queue: List[str]
    # Rich form: each item carries an optional focus_area id the Drill page
    # can deep-link to.
    focus_queue_items: List[FocusQueueItem] = []
    timeline: List[TimelineEntry]
