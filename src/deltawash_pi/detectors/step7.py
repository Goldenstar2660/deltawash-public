"""Detector for WHO Step 7 - Rotational Rubbing of Fingertips in Opposite Palm.

Key cues from recordings:
- left_fingertips: Palm dist ~0.324, vertical offset ~0.242, tips-to-palm ~0.116
- right_fingertips: Palm dist ~0.251, vertical offset ~0.180, tips-to-palm ~0.142
- Single-hand visibility: 21-64% of frames (varies by orientation)

Orientation detection:
- The hand whose fingertips are pressing into the other palm determines orientation
- LEFT hand fingertips pressing = LEFT_FINGERTIPS
- RIGHT hand fingertips pressing = RIGHT_FINGERTIPS

Distinctive feature: High vertical offset (~0.18-0.24) as fingertips press down into palm.
"""

from deltawash_pi.detectors._geometry import (
    HandSide,
    clamp01,
    closeness_score,
    fingertips_to_palm_distance,
    get_hand_count,
    ramp_score,
    select_hand_pair,
    select_single_hand,
)
from deltawash_pi.detectors.base import MetadataDetector
from deltawash_pi.interpreter.types import StepID, StepOrientation

# Thresholds from recording analysis
PALM_DIST_CENTER = 0.29  # From recordings: 0.251-0.324
PALM_DIST_TOLERANCE = 0.12
TIPS_TO_PALM_IDEAL = 0.13  # From recordings: 0.116-0.142
VERTICAL_OFFSET_MIN = 0.12  # Distinctive high vertical offset


class Step7Detector(MetadataDetector):
    step_id = StepID.STEP_7

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

        Step 7 is MOST distinctive with:
        - HIGHEST vertical offset (~0.22) - fingertips pressing down
        - LOWEST tip_to_palm (~0.124) - fingertips in palm center
        - These two together are unique to step 7
        """
        vert_offset = pair.vertical_offset()

        # GATE: Must have high vertical offset (this is THE distinctive feature)
        if vert_offset < 0.12:  # Too low for step 7
            return 0.0, StepOrientation.NONE, "vert_offset_too_low_for_step7"

        # Find which hand's fingertips are closest to the other palm
        cluster_first = fingertips_to_palm_distance(pair.first, pair.second)
        cluster_second = fingertips_to_palm_distance(pair.second, pair.first)
        if cluster_first <= cluster_second:
            active, receiver, cluster = pair.first, pair.second, cluster_first
        else:
            active, receiver, cluster = pair.second, pair.first, cluster_second

        # GATE: Tips must be close to palm
        if cluster > 0.20:
            return 0.0, StepOrientation.NONE, "tips_too_far_for_step7"

        # Fingertips very close to palm center
        cluster_score = closeness_score(
            cluster, ideal=TIPS_TO_PALM_IDEAL, tolerance=0.08
        )

        # High vertical offset
        vertical_score = ramp_score(
            vert_offset, min_value=VERTICAL_OFFSET_MIN, max_value=0.30
        )

        # Moderate palm separation
        palm_score = closeness_score(
            pair.palms_distance(), ideal=PALM_DIST_CENTER, tolerance=PALM_DIST_TOLERANCE
        )

        confidence = clamp01(
            (0.45 * cluster_score)
            + (0.35 * vertical_score)
            + (0.20 * palm_score)
        )
        orientation = _fingertip_orientation(active.side)
        detail = None if confidence >= 0.2 else "landmark_heuristic_low"
        return confidence, orientation, detail

    def _score_single_hand(self, packet):
        """Score based on single-hand features during occlusion.

        Step 7 requires seeing fingertips pressing into palm - hard from single hand.
        Return minimal confidence.
        """
        hand, note = select_single_hand(packet)
        if hand is None:
            return 0.0, StepOrientation.NONE, note

        # Step 7 needs two hands to detect fingertip-palm interaction
        return 0.10, StepOrientation.NONE, "single_hand_low_confidence"


def _fingertip_orientation(side: HandSide) -> StepOrientation:
    if side is HandSide.LEFT:
        return StepOrientation.LEFT_FINGERTIPS
    if side is HandSide.RIGHT:
        return StepOrientation.RIGHT_FINGERTIPS
    return StepOrientation.NONE


__all__ = ["Step7Detector"]
