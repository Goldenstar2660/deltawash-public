"""Detector for WHO Step 3 - Palm Over Opposite Dorsum with Interlaced Fingers.

Key cues from recordings (2-hand frames):
- Palm distance: ~0.27 (moderate)
- Tip to palm: ~0.336 (HIGH - fingers NOT pointing at palm center)
- Tip to MCP: ~0.31 (moderate)
- Vertical offset: ~0.056 (some offset, but not as high as step 7)

Step 3 is distinguished by:
- Fingers interlaced over dorsum, NOT pointing at palm
- High tip_to_palm distance (unlike step 5, 7)
- Moderate palm distance (unlike step 2, 4)
"""

from deltawash_pi.detectors._geometry import (
    HandPair,
    HandSide,
    clamp01,
    closeness_score,
    fingertips_to_palm_distance,
    get_hand_count,
    mean_tip_to_mcp_distance,
    ramp_score,
    select_hand_pair,
    select_single_hand,
)
from deltawash_pi.detectors.base import MetadataDetector
from deltawash_pi.interpreter.types import StepID, StepOrientation

# Thresholds from recording analysis
PALM_DIST_CENTER = 0.27
PALM_DIST_TOLERANCE = 0.12
TIP_TO_PALM_MIN = 0.25  # Key: tips NOT near palm (distinguishes from step 5, 7)


class Step3Detector(MetadataDetector):
    step_id = StepID.STEP_3

    def _score_packet(self, packet):  # type: ignore[override]
        num_hands = get_hand_count(packet)

        # Try two-hand detection first
        pair, note = select_hand_pair(packet)
        if pair is not None:
            return self._score_two_hands(pair)

        # Fall back to single-hand detection with reduced confidence
        if num_hands == 1:
            return self._score_single_hand(packet)

        return 0.0, StepOrientation.NONE, note

    def _score_two_hands(self, pair):
        """Score based on two-hand geometry.

        Step 3 is distinguished by:
        - Fingertips NOT close to palm (high tip_to_palm > 0.25)
        - Moderate palm distance
        - Lower horizontal offset (hands stacked) vs step 6 (hands side-by-side)
        """
        # KEY GATING: Tips must NOT be near palm (unlike step 5, 7)
        tip_palm_left = fingertips_to_palm_distance(pair.first, pair.second)
        tip_palm_right = fingertips_to_palm_distance(pair.second, pair.first)
        min_tip_palm = min(tip_palm_left, tip_palm_right)

        # GATE: If tips are too close to palm, this is step 5 or 7, not step 3
        if min_tip_palm < 0.20:
            return 0.0, StepOrientation.NONE, "tips_too_close_for_step3"

        # High tip_palm = good for step 3
        tips_away_score = ramp_score(min_tip_palm, min_value=0.25, max_value=0.40)

        # Palm distance - moderate (not too close like step 2/4)
        # From recordings: step3_left_over_right has palm_dist up to 0.524
        palm_score = closeness_score(
            pair.palms_distance(), ideal=PALM_DIST_CENTER, tolerance=0.20
        )

        # GATE: Palm distance must be in range (very wide to handle occlusion variability)
        if pair.palms_distance() > 0.60:
            return 0.0, StepOrientation.NONE, "palm_dist_out_of_range"
        
        # Calculate horizontal offset
        horiz_offset = abs(pair.first.palm_center[0] - pair.second.palm_center[0])
        
        # GATE: If horizontal offset is very high, this is likely step 6 (hands side-by-side)
        # Step 3 avg horiz: 0.16-0.24 (max 0.50), Step 6 avg: 0.28-0.36 (max 0.64)
        if horiz_offset > 0.50:
            return 0.0, StepOrientation.NONE, "horiz_too_high_for_step3"

        # Vertical offset: some, but not too high (step 7 has very high offset)
        # Step 3 offset: avg 0.03-0.07, max ~0.22
        vertical_score = closeness_score(pair.vertical_offset(), ideal=0.05, tolerance=0.12)

        # GATE: Not step 7 (vertical offset too high) - widened based on recordings
        if pair.vertical_offset() > 0.25:
            return 0.0, StepOrientation.NONE, "vert_offset_too_high"

        # Interlaced fingers: fingertips near the other hand's MCPs
        hook_left = mean_tip_to_mcp_distance(pair.first, pair.second)
        hook_right = mean_tip_to_mcp_distance(pair.second, pair.first)
        hook_score = closeness_score(min(hook_left, hook_right), ideal=0.30, tolerance=0.12)

        raw_confidence = (
            (0.35 * tips_away_score)
            + (0.25 * palm_score)
            + (0.25 * hook_score)
            + (0.15 * vertical_score)
        )
        confidence = clamp01(raw_confidence)

        orientation = _orientation_from_pair(pair)
        detail = None if confidence >= 0.2 else "landmark_heuristic_low"
        return confidence, orientation, detail

    def _score_single_hand(self, packet):
        """Score based on single-hand features during occlusion.

        Step 3 is NOT reliably detectable from single-hand frames.
        Return minimal confidence to avoid false positives.
        """
        hand, note = select_single_hand(packet)
        if hand is None:
            return 0.0, StepOrientation.NONE, note

        # Step 3 needs two hands to detect dorsum contact
        # Return very low confidence for single-hand
        return 0.15, StepOrientation.NONE, "single_hand_low_confidence"


def _orientation_from_pair(pair: HandPair) -> StepOrientation:
    """Determine which hand is on top based on y-position and depth."""
    # Lower y = higher in frame = on top
    y_diff = pair.first.palm_center[1] - pair.second.palm_center[1]
    depth_diff = pair.first.depth - pair.second.depth

    # Use y-position primarily (more reliable), depth as tiebreaker
    if abs(y_diff) > 0.03:
        top = pair.first if y_diff < 0 else pair.second
    elif abs(depth_diff) > 0.01:
        top = pair.first if depth_diff < 0 else pair.second
    else:
        # Very close - use y as final arbiter
        top = pair.first if y_diff <= 0 else pair.second

    if top.side is HandSide.RIGHT:
        return StepOrientation.RIGHT_OVER_LEFT
    if top.side is HandSide.LEFT:
        return StepOrientation.LEFT_OVER_RIGHT
    return StepOrientation.NONE


__all__ = ["Step3Detector"]
