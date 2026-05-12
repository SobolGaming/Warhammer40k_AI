# Semantic Diff Classifier

Classifier module:
- `src/warhammer40k_ai/engine/semantic_diff.py`

Purpose:
- classify bundle deltas by semantic surface
- select a bounded training scope before running expensive retraining

Semantic surfaces:
- `LEGALITY_SURFACE`
- `GEOMETRY_MOVEMENT_VISIBILITY_SURFACE`
- `SCORING_SURFACE`
- `RESOURCE_ECONOMY_TOOL_SURFACE`
- `COMBAT_SURFACE`
- `DEPLOYMENT_RESERVE_SURFACE`
- `ENTITY_TAXONOMY_SURFACE`

Training scope output includes:
- `scope_id`
- `adapter_first`
- `relabel_required`
- `broad_retrain_required`
- `descriptor_families_to_recompile`
- `fine_tune_targets`
- `freeze_targets`
- `notes`

CLI:

```bash
uv run python scripts/classify_semantic_diff.py \
  --source-core-rules-id core_10e \
  --source-rules-commentary-id commentary_2025q4 \
  --source-mission-pack-id mission_2025 \
  --source-terrain-pack-id terrain_wtc_2025 \
  --source-dataslate-id dataslate_2025q4 \
  --source-points-id points_2025q4 \
  --source-faction-pack-id faction_2025q4 \
  --source-detachment-pack-id detachment_2025q4 \
  --target-core-rules-id core_11e \
  --target-rules-commentary-id commentary_2026q1 \
  --target-mission-pack-id mission_2026 \
  --target-terrain-pack-id terrain_wtc_2026 \
  --target-dataslate-id dataslate_2026q1 \
  --target-points-id points_2026q1 \
  --target-faction-pack-id faction_2026q1 \
  --target-detachment-pack-id detachment_2026q1
```

Policy intent:
- points-only changes should avoid broad in-game retraining
- mission/terrain changes should prioritize descriptor recompilation plus replay relabeling
- edition changes should use adapter-first transfer before broad retraining
