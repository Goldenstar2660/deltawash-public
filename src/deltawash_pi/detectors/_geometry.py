"""Geometry helpers for WHO step detectors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np

from deltawash_pi.interpreter.types import FramePacket

PALM_LANDMARKS = np.array([0, 5, 9, 13, 17])
FINGER_TIPS = np.array([8, 12, 16, 20])
FINGER_MCPS = np.array([5, 9, 13, 17])
FINGER_DIPS = np.array([7, 11, 15, 19])
THUMB_TIP_INDEX = 4

# Single-hand detection thresholds (from recording analysis)
# Used when 2 hands are occluded and only 1 is visible
SINGLE_HAND_THRESHOLDS = {
    "step2": {"finger_ext_max": 0.25, "finger_spread_x_max": 0.07, "tips_to_palm_max": 0.28},
    "step4": {"finger_spread_x_max": 0.04, "z_spread_min": 0.025, "avg_z_max": -0.15},
    "step5": {"tips_to_palm_max": 0.18, "finger_ext_max": 0.18},
}


class HandSide(str, Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SingleHandFeatures:
    """Features for single-hand frame analysis (when other hand is occluded)."""

    side: HandSide
    points: np.ndarray
    palm_center: np.ndarray
    finger_extension: float
    finger_spread_x: float
    finger_spread_y: float
    tips_to_palm: float
    z_spread: float
    avg_z: float

    @classmethod
    def from_landmarks(cls, raw) -> Optional["SingleHandFeatures"]:
        landmark_list = getattr(raw, "landmark", None)
        if not landmark_list:
            return None
        points = np.zeros((21, 3), dtype=np.float32)
        max_index = min(21, len(landmark_list))
        for idx in range(max_index):
            lm = landmark_list[idx]
            x = _clamp(getattr(lm, "x", 0.0))
            y = _clamp(getattr(lm, "y", 0.0))
            z = float(getattr(lm, "z", 0.0))
            points[idx] = (x, y, z)

        palm_pts = points[PALM_LANDMARKS]
        palm_center = np.mean(palm_pts, axis=0)

        tips = points[FINGER_TIPS, :2]
        mcps = points[FINGER_MCPS, :2]

        finger_extension = float(np.mean(np.linalg.norm(tips - mcps, axis=1)))
        finger_spread_x = float(np.std(tips[:, 0]))
        finger_spread_y = float(np.std(tips[:, 1]))
        tips_to_palm = float(np.mean(np.linalg.norm(tips - palm_center[:2], axis=1)))

        z_vals = points[FINGER_TIPS, 2]
        z_spread = float(np.std(z_vals))
        avg_z = float(np.mean(points[:, 2]))

        side = _infer_side(points)

        return cls(
            side=side,
            points=points,
            palm_center=palm_center,
            finger_extension=finger_extension,
            finger_spread_x=finger_spread_x,
            finger_spread_y=finger_spread_y,
            tips_to_palm=tips_to_palm,
            z_spread=z_spread,
            avg_z=avg_z,
        )


@dataclass(frozen=True)
class HandFeatures:
    """Pre-computed geometry for a single hand."""

    side: HandSide
    points: np.ndarray  # shape=(21, 3)
    palm_center: np.ndarray  # shape=(3,)
    depth: float

    @classmethod
    def from_landmarks(cls, raw) -> Optional["HandFeatures"]:
        landmark_list = getattr(raw, "landmark", None)
        if not landmark_list:
            return None
        points = np.zeros((21, 3), dtype=np.float32)
        max_index = min(21, len(landmark_list))
        for idx in range(max_index):
            lm = landmark_list[idx]
            x = _clamp(getattr(lm, "x", 0.0))
            y = _clamp(getattr(lm, "y", 0.0))
            z = float(getattr(lm, "z", 0.0))
            points[idx] = (x, y, z)
        palm_center = np.mean(points[PALM_LANDMARKS], axis=0)
        depth = float(np.mean(points[PALM_LANDMARKS, 2]))
        side = _infer_side(points)
        return cls(side=side, points=points, palm_center=palm_center, depth=depth)

    def fingertips(self) -> np.ndarray:
        return self.points[FINGER_TIPS, :2]

    def mcps(self) -> np.ndarray:
        return self.points[FINGER_MCPS, :2]

    def dips(self) -> np.ndarray:
        return self.points[FINGER_DIPS, :2]

    def thumb_tip(self) -> np.ndarray:
        return self.points[THUMB_TIP_INDEX, :2]


@dataclass(frozen=True)
class HandPair:
    first: HandFeatures
    second: HandFeatures

    def palms_distance(self) -> float:
        return _distance2d(self.first.palm_center, self.second.palm_center)

    def vertical_offset(self) -> float:
        return abs(float(self.first.palm_center[1] - self.second.palm_center[1]))

    def sorted_by_depth(self) -> List[HandFeatures]:
        return sorted((self.first, self.second), key=lambda hand: hand.depth)

    def as_tuple(self) -> Tuple[HandFeatures, HandFeatures]:
        return self.first, self.second


def select_hand_pair(packet: FramePacket) -> Tuple[Optional[HandPair], Optional[str]]:
    raw_landmarks = getattr(packet, "landmarks", None)
    if not raw_landmarks:
        return _cached_pair(packet, "missing_landmarks")
    try:
        landmarks: Sequence[object] = list(raw_landmarks)
    except TypeError:
        return None, "invalid_landmarks"
    filtered: List[HandFeatures] = []
    for landmark_set in landmarks:
        features = HandFeatures.from_landmarks(landmark_set)
        if features is not None:
            filtered.append(features)
    if len(filtered) < 2:
        return _cached_pair(packet, "requires_two_hands")
    if len(filtered) > 2:
        return None, "ambiguous_hands"
    filtered.sort(key=lambda hand: float(hand.palm_center[0]))
    pair = HandPair(filtered[0], filtered[1])
    # Cache the pair for single-hand frame fallback
    if hasattr(packet, "metadata") and isinstance(packet.metadata, dict):
        packet.metadata["_hand_pair_cache"] = pair
    return pair, None


def select_single_hand(
    packet: FramePacket,
) -> Tuple[Optional[SingleHandFeatures], Optional[str]]:
    """Extract single-hand features when only one hand is visible (occlusion case)."""
    raw_landmarks = getattr(packet, "landmarks", None)
    if not raw_landmarks:
        return None, "missing_landmarks"
    try:
        landmarks: Sequence[object] = list(raw_landmarks)
    except TypeError:
        return None, "invalid_landmarks"
    if len(landmarks) == 0:
        return None, "no_hands"
    if len(landmarks) > 1:
        return None, "multiple_hands"
    features = SingleHandFeatures.from_landmarks(landmarks[0])
    if features is None:
        return None, "invalid_hand"
    return features, None


def get_hand_count(packet: FramePacket) -> int:
    """Return the number of hands visible in the frame."""
    raw_landmarks = getattr(packet, "landmarks", None)
    if not raw_landmarks:
        return 0
    try:
        return len(list(raw_landmarks))
    except TypeError:
        return 0


def _cached_pair(packet: FramePacket, reason: str) -> Tuple[Optional[HandPair], Optional[str]]:
    cached = packet.metadata.get("_hand_pair_cache")
    if isinstance(cached, HandPair):
        return cached, "cached_pair"
    return None, reason


def mean_tip_distance(pair: HandPair) -> float:
    return _mean_distance(pair.first.fingertips(), pair.second.fingertips())


def mean_tip_to_mcp_distance(source: HandFeatures, target: HandFeatures) -> float:
    return _mean_distance(source.fingertips(), target.mcps())


def dips_to_palm_distance(source: HandFeatures, target: HandFeatures) -> float:
    return _mean_distance_to_point(source.dips(), target.palm_center[:2])


def fingertips_to_palm_distance(source: HandFeatures, target: HandFeatures) -> float:
    return _mean_distance_to_point(source.fingertips(), target.palm_center[:2])


def thumb_to_palm_distance(source: HandFeatures, target: HandFeatures) -> float:
    return _distance2d(np.array([*source.thumb_tip(), 0.0], dtype=np.float32), target.palm_center)


def support_fingers_to_point(source: HandFeatures, point: np.ndarray) -> float:
    return _mean_distance_to_point(source.fingertips(), point[:2])


def finger_alternation_score(pair: HandPair) -> float:
    combined: List[Tuple[float, int]] = []
    for idx in FINGER_TIPS:
        combined.append((float(pair.first.points[idx, 0]), 0))
        combined.append((float(pair.second.points[idx, 0]), 1))
    combined.sort(key=lambda item: item[0])
    transitions = 0
    for i in range(1, len(combined)):
        if combined[i][1] != combined[i - 1][1]:
            transitions += 1
    return transitions / (len(combined) - 1)


def closeness_score(distance: float, *, ideal: float, tolerance: float) -> float:
    if distance <= ideal:
        return 1.0
    limit = ideal + tolerance
    if distance >= limit:
        return 0.0
    span = max(limit - ideal, 1e-6)
    return 1.0 - (distance - ideal) / span


def ramp_score(value: float, *, min_value: float, max_value: float) -> float:
    if value <= min_value:
        return 0.0
    if value >= max_value:
        return 1.0
    span = max(max_value - min_value, 1e-6)
    return (value - min_value) / span


def centered_score(value: float, *, center: float, tolerance: float) -> float:
    if tolerance <= 0.0:
        return 1.0 if value == center else 0.0
    delta = abs(value - center)
    if delta >= tolerance:
        return 0.0
    return 1.0 - (delta / tolerance)


def clamp01(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _mean_distance(points_a: np.ndarray, points_b: np.ndarray) -> float:
    deltas = points_a - points_b
    distances = np.linalg.norm(deltas, axis=1)
    return float(distances.mean())


def _mean_distance_to_point(points: np.ndarray, point: np.ndarray) -> float:
    deltas = points - point[:2]
    distances = np.linalg.norm(deltas, axis=1)
    return float(distances.mean())


def _distance2d(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a[:2] - b[:2]))


def _infer_side(points: np.ndarray) -> HandSide:
    thumb_x = float(points[THUMB_TIP_INDEX, 0])
    pinky_x = float(points[FINGER_TIPS[-1], 0])
    if thumb_x < pinky_x - 1e-3:
        return HandSide.RIGHT
    if thumb_x > pinky_x + 1e-3:
        return HandSide.LEFT
    return HandSide.UNKNOWN


def _clamp(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


__all__ = [
    "HandFeatures",
    "HandPair",
    "HandSide",
    "SingleHandFeatures",
    "SINGLE_HAND_THRESHOLDS",
    "clamp01",
    "closeness_score",
    "centered_score",
    "dips_to_palm_distance",
    "finger_alternation_score",
    "fingertips_to_palm_distance",
    "get_hand_count",
    "mean_tip_distance",
    "mean_tip_to_mcp_distance",
    "ramp_score",
    "select_hand_pair",
    "select_single_hand",
    "support_fingers_to_point",
    "thumb_to_palm_distance",
]
