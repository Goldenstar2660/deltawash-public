"""Shared dataclasses and enums used across detectors, interpreter, and logging."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from deltawash_pi.config.loader import ROI


class StepID(str, Enum):
    STEP_2 = "STEP_2"
    STEP_3 = "STEP_3"
    STEP_4 = "STEP_4"
    STEP_5 = "STEP_5"
    STEP_6 = "STEP_6"
    STEP_7 = "STEP_7"


class StepOrientation(str, Enum):
    NONE = "NONE"
    RIGHT_OVER_LEFT = "RIGHT_OVER_LEFT"
    LEFT_OVER_RIGHT = "LEFT_OVER_RIGHT"
    LEFT_THUMB = "LEFT_THUMB"
    RIGHT_THUMB = "RIGHT_THUMB"
    LEFT_FINGERTIPS = "LEFT_FINGERTIPS"
    RIGHT_FINGERTIPS = "RIGHT_FINGERTIPS"


class StepState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    UNCERTAIN = "UNCERTAIN"


class UncertaintyReason(str, Enum):
    AMBIGUOUS_HANDS = "AMBIGUOUS_HANDS"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    CAMERA_DROPPED = "CAMERA_DROPPED"
    ROI_EXIT = "ROI_EXIT"


class LedSignalState(str, Enum):
    CURRENT = "CURRENT"
    COMPLETED = "COMPLETED"
    IDLE = "IDLE"


class StepSignalSource(str, Enum):
    MODEL = "MODEL"
    HEURISTIC = "HEURISTIC"
    DEMO = "DEMO"


@dataclass(frozen=True)
class MotionMetrics:
    mean_velocity: float
    relative_motion: float


@dataclass(frozen=True)
class FramePacket:
    frame_id: int
    timestamp_ms: int
    roi: ROI
    config_version: str
    motion: MotionMetrics
    landmarks: Any
    image: Any | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepSignal:
    step_id: StepID
    orientation: StepOrientation
    confidence: float
    is_confident: bool
    timestamp_ms: int
    source: StepSignalSource
    notes: Optional[str] = None


@dataclass
class StepStatus:
    step_id: StepID
    orientation: StepOrientation = StepOrientation.NONE
    state: StepState = StepState.NOT_STARTED
    accumulated_ms: int = 0
    completed_ts: Optional[int] = None
    uncertainty_count: int = 0


@dataclass(frozen=True)
class UncertaintyEvent:
    timestamp_ms: int
    reason: UncertaintyReason
    details: Optional[str] = None


@dataclass
class SessionRecord:
    session_id: str
    config_version: str
    roi_rect: ROI
    demo_mode: bool
    start_ts: int
    end_ts: Optional[int]
    step_statuses: List[StepStatus] = field(default_factory=list)
    uncertainty_events: List[UncertaintyEvent] = field(default_factory=list)
    total_rubbing_ms: int = 0
    notes: Optional[str] = None


@dataclass(frozen=True)
class LedSignal:
    step_id: StepID
    state: LedSignalState
    timestamp_ms: int
    delivered: bool = True
    error: Optional[str] = None


__all__ = [
    "FramePacket",
    "LedSignal",
    "LedSignalState",
    "MotionMetrics",
    "ROI",
    "SessionRecord",
    "StepID",
    "StepOrientation",
    "StepSignalSource",
    "StepSignal",
    "StepState",
    "StepStatus",
    "UncertaintyEvent",
    "UncertaintyReason",
]
