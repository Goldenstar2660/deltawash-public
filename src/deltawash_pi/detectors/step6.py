"""Detector for WHO Step 6 - Rotational Rubbing of Thumb Clasped in Opposite Palm.

Key cues from recordings:
- left_thumb: Palm distance ~0.393, thumb-to-palm ~0.229, tips-to-palm ~0.320
- right_thumb: Palm distance ~0.364, thumb-to-palm ~0.252, tips-to-palm ~0.385
- Single-hand visibility: 58-68% of frames

Orientation detection:
- The hand whose thumb is being rubbed determines orientation
- LEFT hand thumb being rubbed = LEFT_THUMB
- RIGHT hand thumb being rubbed = RIGHT_THUMB
"""

from deltawash_pi.detectors._geometry import (
    HandSide,
    clamp01,
    closeness_score,
    get_hand_count,
    ramp_score,
    select_hand_pair,
    select_single_hand,
    support_fingers_to_point,
    thumb_to_palm_distance,
)
from deltawash_pi.detectors.base import MetadataDetector
from deltawash_pi.interpreter.types import StepID, StepOrientation

# Thresholds from recording analysis
PALM_DIST_CENTER = 0.38  # From recordings: 0.364-0.393
PALM_DIST_TOLERANCE = 0.20
THUMB_TO_PALM_IDEAL = 0.24  # From recordings: 0.229-0.252


class Step6Detector(MetadataDetector):
    step_id = StepID.STEP_6

    def _score_packet(self, packet):  # type: ignore[override]
        num_hands = get_hand_count(packet)

        # Try two-hand detection first
        pair, note = select_hand_pair(packet)
        if pair is not None:
            return self._score_two_hands(pair)

        # Fall back to single-hand detection
        if num_hands == 1:
            return self._score_single_hand(packet)

        return 0.0, StepOrientation.NONE, note

    def _score_two_hands(self, pair):
        """Score based on two-hand geometry.

        Step 6 is distinctive:
        - HIGHEST palm distance (~0.39) - hands widely separated
        - Thumb of one hand is near the other palm (~0.24)
        - HIGH horizontal offset (hands side-by-side) - avg 0.28-0.36
        - Moderate vertical offset (not as high as step 7)
        """
        palm_dist = pair.palms_distance()

        # GATE: Palm distance must be moderate-high (relaxed based on recordings)
        # step6_right_thumb has palm_dist as low as 0.006
        if palm_dist < 0.10:  # Very close hands probably occlusion artifacts
            return 0.0, StepOrientation.NONE, "palm_too_close_for_step6"

        # Calculate horizontal offset (hands side-by-side)
        horiz_offset = abs(pair.first.palm_center[0] - pair.second.palm_center[0])
        
        # GATE: Horizontal offset should be present (distinguishes from step 3)
        # Relaxed based on recordings - step6_right_thumb has 44% of frames < 0.20
        if horiz_offset < 0.10:
            return 0.0, StepOrientation.NONE, "horiz_too_low_for_step6"

        # GATE: Vertical offset must not be too high (that's step 7)
        if pair.vertical_offset() > 0.20:
            return 0.0, StepOrientation.NONE, "vert_too_high_for_step6"

        # Find which thumb is closer to the other hand's palm
        dist_first = thumb_to_palm_distance(pair.first, pair.second)
        dist_second = thumb_to_palm_distance(pair.second, pair.first)
        if dist_first <= dist_second:
            active, support, thumb_distance = pair.first, pair.second, dist_first
        else:
            active, support, thumb_distance = pair.second, pair.first, dist_second

        # Thumb close to opposite palm center
        thumb_score = closeness_score(
            thumb_distance, ideal=THUMB_TO_PALM_IDEAL, tolerance=0.14
        )

        # Support hand's fingers wrapping around the thumb
        wrap = support_fingers_to_point(support, active.thumb_tip())
        wrap_score = closeness_score(wrap, ideal=0.22, tolerance=0.15)

        # Wide palm separation
        palm_score = closeness_score(
            palm_dist, ideal=PALM_DIST_CENTER, tolerance=PALM_DIST_TOLERANCE
        )

        confidence = clamp01(
            (0.45 * thumb_score)
            + (0.30 * wrap_score)
            + (0.25 * palm_score)
        )
        orientation = _thumb_orientation(active.side)
        detail = None if confidence >= 0.2 else "landmark_heuristic_low"
        return confidence, orientation, detail

    def _score_single_hand(self, packet):
        """Score based on single-hand features during occlusion.

        Step 6 requires seeing thumb interaction - hard to detect from single hand.
        Return minimal confidence.
        """
        hand, note = select_single_hand(packet)
        if hand is None:
            return 0.0, StepOrientation.NONE, note

        # Step 6 needs two hands to detect thumb clasping
        return 0.10, StepOrientation.NONE, "single_hand_low_confidence"


def _thumb_orientation(side: HandSide) -> StepOrientation:
    if side is HandSide.LEFT:
        return StepOrientation.LEFT_THUMB
    if side is HandSide.RIGHT:
        return StepOrientation.RIGHT_THUMB
    return StepOrientation.NONE


__all__ = ["Step6Detector"]
