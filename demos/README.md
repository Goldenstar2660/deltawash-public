# Demo Assets

Curated demo assets ensure deterministic validation of WHO Steps 2-7 without requiring a live sink each time features are tested.

## Expectations
- Provide at least 30 recorded sessions that cover every WHO step orientation variant (Step 3 left/right, Step 6 thumbs, Step 7 fingertips).
- Include ambiguous sessions (multiple people, reflective sinks, camera reconnects) to validate uncertainty handling.
- Annotate each session with per-step start/end timestamps plus optional MediaPipe landmark sequences.
- Store assets in `.npz` or similar compressed formats under `demos/` and reference them via `demos/manifest.json`.

## Usage
1. Update `demos/manifest.json` with each asset's file path, total frames, FPS, and annotation metadata.
2. Run `python -m deltawash_pi.cli.demo --asset <path>` to replay assets deterministically.
3. Extend smoke tests to cross-check generated session logs and console grid output against the annotations documented here.

### Sample Inference Mode
Use sample inference to exercise the full capture pipeline while swapping only the ML detector output.

```
python -m deltawash_pi.cli.capture --demo-asset sample-sequence --sample-inference
```

This uses the demo annotations to synthesize deterministic ML-like predictions (including dropouts/mislabels) while keeping session gating, interpreter timing, logging, and LED integration unchanged.

Add `--demo-realtime` to pace the replay and watch status updates as they evolve.

### Labeled Subset Overview
| Asset ID | Coverage Highlights | Notes |
|----------|--------------------|-------|
| sample-sequence | Steps 2-3 canonical order | Baseline ROI tuning clip; use for regression smoke tests. |
| thumb-variants | Step 6 (left/right) + Step 7 (left fingertips) | Demonstrates orientation metadata published by detectors. |
| multi-step-canonical | Steps 2-7 in a single take | Use for end-to-end demo timing validation and analytics accuracy checks. |

Each manifest annotation entry captures `step_id`, `orientation`, `start_ms`, and `end_ms`. This keeps replay deterministic and enables CLI smoke tests to assert timing expectations without parsing video again.

### Extending the Labeled Set
- Keep ROI coordinates in the manifest aligned with the profile used during capture so FramePacket metadata reflects the original framing.
- Add `notes` keys per asset when ambiguity scenarios (multiple people, glare) need to be surfaced to downstream analytics.
- Preserve at least one asset per orientation variant as new recordings are added; regression tests rely on that coverage parity.

## Privacy & Retention
- Only include recordings captured with explicit operator consent; do not ship identity-revealing footage outside the controlled dataset.
- Strip raw audio and any HUD overlays tied to unrelated experiments.
- Update this README as new fixtures are produced so downstream teams know what coverage exists.
