"""Detector for WHO Step 5 - Backs of Fingers to Opposing Palm with Fingers Interlocked.

Key cues from recordings:
- Palm distance: ~0.279 (std 0.061) - moderate separation
- Fingertip distance: ~0.125 (std 0.065) - tips close
- Tips to palm (min): ~0.177 - fingertips near opposing palm
- Single-hand visibility: 68.7% of frames

Single-hand pattern (when occluded):
- Tips to palm: ~0.140 (very low - curled fingers)
- Finger extension: ~0.141 (fingers curled back)
"""

from deltawash_pi.detectors._geometry import (
    SINGLE_HAND_THRESHOLDS,
    clamp01,
    closeness_score,
    dips_to_palm_distance,
    get_hand_count,
    select_hand_pair,
    select_single_hand,
)
from deltawash_pi.detectors.base import MetadataDetector
from deltawash_pi.interpreter.types import StepID, StepOrientation

# Thresholds from recording analysis
PALM_DIST_CENTER = 0.28  # From recordings: mean 0.279
PALM_DIST_TOLERANCE = 0.12
TIPS_TO_PALM_IDEAL = 0.18  # From recordings: min ~0.177


class Step5Detector(MetadataDetector):
    step_id = StepID.STEP_5

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

        Step 5 distinctive features:
        - Moderate palm distance (~0.28)
        - Low tips/dips to palm (~0.177) - knuckles touching palm
        - Moderate vertical offset (~0.10)
        - Unlike step 7: lower vertical offset
        """
        palm_dist = pair.palms_distance()
        vert_offset = pair.vertical_offset()

        # GATE: Palm distance in moderate range
        if palm_dist < 0.15:  # Too close (step 2 or 4)
            return 0.0, StepOrientation.NONE, "palm_too_close_for_step5"
        if palm_dist > 0.40:  # Too far (step 6)
            return 0.0, StepOrientation.NONE, "palm_too_far_for_step5"

        # GATE: Vertical offset moderate (not as high as step 7)
        if vert_offset > 0.18:  # Step 7 has ~0.22
            return 0.0, StepOrientation.NONE, "vert_too_high_for_step5"

        # Finger DIPs (back of fingers) near opposing palm
        wrap_left = dips_to_palm_distance(pair.first, pair.second)
        wrap_right = dips_to_palm_distance(pair.second, pair.first)
        dorsal_wrap = closeness_score(
            min(wrap_left, wrap_right), ideal=TIPS_TO_PALM_IDEAL, tolerance=0.12
        )

        # Moderate palm separation
        separation = closeness_score(
            palm_dist, ideal=PALM_DIST_CENTER, tolerance=PALM_DIST_TOLERANCE
        )

        # Vertical offset present (hands stacked)
        vert_score = closeness_score(vert_offset, ideal=0.10, tolerance=0.06)

        confidence = clamp01(
            (0.50 * dorsal_wrap) + (0.30 * separation) + (0.20 * vert_score)
        )
        detail = None if confidence >= 0.2 else "landmark_heuristic_low"
        return confidence, StepOrientation.NONE, detail

    def _score_single_hand(self, packet):
        """Score based on single-hand features during occlusion.

        Step 5 has a distinctive single-hand pattern: very curled fingers
        with very low tips_to_palm (~0.14) and low extension (~0.14).
        """
        hand, note = select_single_hand(packet)
        if hand is None:
            return 0.0, StepOrientation.NONE, note

        # GATE: Must have very curled fingers (distinctive for step 5)
        if hand.tips_to_palm > 0.18:  # Too extended for step 5
            return 0.0, StepOrientation.NONE, "tips_not_curled_for_step5"
        if hand.finger_extension > 0.20:  # Too extended
            return 0.0, StepOrientation.NONE, "fingers_not_curled_for_step5"

        # Step 5 distinctive: very curled fingers
        tips_score = closeness_score(hand.tips_to_palm, ideal=0.14, tolerance=0.06)
        ext_score = closeness_score(hand.finger_extension, ideal=0.14, tolerance=0.06)

        # Single-hand heavily penalized (max 0.35)
        raw_confidence = (0.55 * tips_score) + (0.45 * ext_score)
        confidence = clamp01(raw_confidence * 0.35)

        detail = "single_hand_occlusion" if confidence >= 0.2 else "landmark_heuristic_low"
        return confidence, StepOrientation.NONE, detail


__all__ = ["Step5Detector"]
