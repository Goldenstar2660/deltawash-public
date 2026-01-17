"""Detector for WHO Step 2 - Palm-to-Palm Rubbing.

Key cues from recordings:
- Palm distance: ~0.146 (std 0.122) - hands close together
- Fingertip distance: ~0.120 (std 0.087) - tips aligned
- Vertical offset: ~0.036 - hands horizontally aligned
- Single-hand visibility: 82% of frames (hands occlude each other during rubbing)

Single-hand pattern (when occluded):
- Finger extension: ~0.217 (fingers moderately extended)
- Finger spread X: ~0.053 (fingers together, not spread)
- Tips to palm: ~0.249
"""

from deltawash_pi.detectors._geometry import (
    SINGLE_HAND_THRESHOLDS,
    clamp01,
    closeness_score,
    finger_alternation_score,
    get_hand_count,
    mean_tip_distance,
    ramp_score,
    select_hand_pair,
    select_single_hand,
)
from deltawash_pi.detectors.base import MetadataDetector
from deltawash_pi.interpreter.types import StepID, StepOrientation

# Thresholds from recording analysis
PALM_DIST_IDEAL = 0.15  # From recordings: mean 0.146
PALM_DIST_TOLERANCE = 0.15  # Allow up to ~0.30
TIP_DIST_IDEAL = 0.12  # From recordings: mean 0.120
TIP_DIST_TOLERANCE = 0.12  # Allow up to ~0.24


class Step2Detector(MetadataDetector):
    step_id = StepID.STEP_2

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

        Step 2 distinctive features:
        - Low palm distance (~0.15) - hands close
        - Low tip distance (~0.12) - fingers aligned
        - Low vertical offset (~0.036) - hands horizontally aligned
        - Non-interlaced fingers
        """
        palm_dist = pair.palms_distance()

        # GATE: Palm distance must be in the low-moderate range
        # Step 2: ~0.15, Step 4: ~0.07, Step 3/5/6/7: > 0.25
        if palm_dist < 0.06:  # Too close = step 4
            return 0.0, StepOrientation.NONE, "palm_too_close_for_step2"
        if palm_dist > 0.22:  # Too far = step 3, 5, 6, or 7
            return 0.0, StepOrientation.NONE, "palm_too_far_for_step2"

        # GATE: Vertical offset must be low (step 7 has high offset)
        if pair.vertical_offset() > 0.10:
            return 0.0, StepOrientation.NONE, "vert_offset_too_high"

        # Palm-to-palm close alignment
        palm_overlap = closeness_score(
            palm_dist, ideal=PALM_DIST_IDEAL, tolerance=PALM_DIST_TOLERANCE
        )
        # Fingertips aligned (not interlaced)
        tip_alignment = closeness_score(
            mean_tip_distance(pair), ideal=TIP_DIST_IDEAL, tolerance=TIP_DIST_TOLERANCE
        )
        # Low vertical offset (hands horizontally aligned)
        vert_score = closeness_score(pair.vertical_offset(), ideal=0.0, tolerance=0.06)
        # Non-interlaced fingers (step 2 has fingers aligned, not woven)
        alternation = finger_alternation_score(pair)
        non_interlaced = clamp01(1.0 - ramp_score(alternation, min_value=0.25, max_value=0.70))

        raw_confidence = (
            (0.30 * palm_overlap)
            + (0.30 * tip_alignment)
            + (0.20 * vert_score)
            + (0.20 * non_interlaced)
        )
        confidence = clamp01(raw_confidence)
        detail = None if confidence >= 0.2 else "landmark_heuristic_low"
        return confidence, StepOrientation.NONE, detail

    def _score_single_hand(self, packet):
        """Score based on single-hand features during occlusion.

        Step 2 single-hand pattern:
        - Moderate finger spread (~0.05) - higher than step 4 (~0.025)
        - Moderate finger extension (~0.22) - similar to step 4
        """
        hand, note = select_single_hand(packet)
        if hand is None:
            return 0.0, StepOrientation.NONE, note

        # GATE: Finger spread must be moderate (not too low like step 4)
        if hand.finger_spread_x < 0.03:  # Too tight = likely step 4
            return 0.0, StepOrientation.NONE, "spread_too_low_for_step2"

        thresholds = SINGLE_HAND_THRESHOLDS.get("step2", {})

        # Fingers together (low-moderate spread) but not too tight
        spread_score = closeness_score(
            hand.finger_spread_x,
            ideal=0.05,
            tolerance=0.03,  # 0.02 - 0.08 range
        )
        # Moderate extension
        ext_score = closeness_score(
            hand.finger_extension,
            ideal=0.22,
            tolerance=0.08,
        )
        tips_score = closeness_score(
            hand.tips_to_palm,
            ideal=0.25,
            tolerance=0.06,
        )

        # Single-hand scores heavily penalized (max 0.35) to avoid false positives
        # Step 2 is best detected with two visible palms
        raw_confidence = (0.40 * spread_score) + (0.35 * ext_score) + (0.25 * tips_score)
        confidence = clamp01(raw_confidence * 0.35)

        detail = "single_hand_occlusion" if confidence >= 0.2 else "landmark_heuristic_low"
        return confidence, StepOrientation.NONE, detail


__all__ = ["Step2Detector"]
