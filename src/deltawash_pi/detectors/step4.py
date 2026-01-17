"""Detector for WHO Step 4 - Palm-to-Palm with Interlaced Fingers.

Key cues from recordings:
- Palm distance: ~0.067 (std 0.032) - hands very close
- Fingertip distance: ~0.137 - tips interweaved
- Single-hand visibility: 93.4% of frames (heavy occlusion due to tight interlacing)

Single-hand pattern (when occluded):
- Finger spread X: ~0.025 (very tight fingers)
- Z spread: ~0.041 (varying depth from interlacing)
- Avg Z: ~-0.23 (deep hand posture)
"""

from deltawash_pi.detectors._geometry import (
    SINGLE_HAND_THRESHOLDS,
    clamp01,
    closeness_score,
    finger_alternation_score,
    get_hand_count,
    mean_tip_to_mcp_distance,
    ramp_score,
    select_hand_pair,
    select_single_hand,
)
from deltawash_pi.detectors.base import MetadataDetector
from deltawash_pi.interpreter.types import StepID, StepOrientation

# Thresholds from recording analysis
PALM_DIST_IDEAL = 0.07  # From recordings: mean 0.067
PALM_DIST_TOLERANCE = 0.06


class Step4Detector(MetadataDetector):
    step_id = StepID.STEP_4

    def _score_packet(self, packet):  # type: ignore[override]
        num_hands = get_hand_count(packet)

        # Try two-hand detection first
        pair, note = select_hand_pair(packet)
        if pair is not None:
            return self._score_two_hands(pair)

        # Fall back to single-hand detection (very common for step 4)
        if num_hands == 1:
            return self._score_single_hand(packet)

        return 0.0, StepOrientation.NONE, note

    def _score_two_hands(self, pair):
        """Score based on two-hand geometry.

        Step 4 distinctive features:
        - LOWEST palm distance (~0.067) - very tight grip
        - Interlaced fingers
        - Fingers hooked together
        """
        palm_dist = pair.palms_distance()

        # GATE: Palm distance must be very low (step 4 has lowest)
        if palm_dist > 0.12:  # Too far for step 4
            return 0.0, StepOrientation.NONE, "palm_too_far_for_step4"

        # Very close palms - tighter than step 2
        palm_overlap = closeness_score(
            palm_dist, ideal=PALM_DIST_IDEAL, tolerance=PALM_DIST_TOLERANCE
        )

        # High interlacing score (fingers woven together)
        interlace = ramp_score(
            finger_alternation_score(pair), min_value=0.40, max_value=0.80
        )

        # Fingertips near opposite MCPs (hooked)
        hooked_left = mean_tip_to_mcp_distance(pair.first, pair.second)
        hooked_right = mean_tip_to_mcp_distance(pair.second, pair.first)
        hook_score = closeness_score(min(hooked_left, hooked_right), ideal=0.14, tolerance=0.10)

        confidence = clamp01(
            (0.40 * interlace) + (0.35 * palm_overlap) + (0.25 * hook_score)
        )
        detail = None if confidence >= 0.2 else "landmark_heuristic_low"
        return confidence, StepOrientation.NONE, detail

    def _score_single_hand(self, packet):
        """Score based on single-hand features during occlusion.

        Step 4 has distinctive single-hand pattern:
        - Very low finger spread (~0.025)
        - High z spread (~0.04) from interlacing
        - Deep z depth (~-0.23)
        """
        hand, note = select_single_hand(packet)
        if hand is None:
            return 0.0, StepOrientation.NONE, note

        # GATE: Must have very tight fingers (distinctive for step 4)
        if hand.finger_spread_x > 0.04:  # Too spread for step 4
            return 0.0, StepOrientation.NONE, "spread_too_high_for_step4"

        # Step 4 distinctive: very tight fingers
        spread_score = closeness_score(hand.finger_spread_x, ideal=0.025, tolerance=0.02)
        z_spread_score = ramp_score(hand.z_spread, min_value=0.025, max_value=0.06)
        depth_score = ramp_score(-hand.avg_z, min_value=0.15, max_value=0.28)

        # Single-hand heavily penalized (max 0.35)
        raw_confidence = (0.40 * spread_score) + (0.35 * z_spread_score) + (0.25 * depth_score)
        confidence = clamp01(raw_confidence * 0.35)

        detail = "single_hand_occlusion" if confidence >= 0.2 else "landmark_heuristic_low"
        return confidence, StepOrientation.NONE, detail


__all__ = ["Step4Detector"]
