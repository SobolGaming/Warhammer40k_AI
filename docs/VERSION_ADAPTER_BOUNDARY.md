# Version Adapter Boundary

The pre-ML adapter boundary is defined in:
- `src/warhammer40k_ai/engine/version_adapter.py`

Decision context field:
- `version_adapter_boundary`

Boundary payload:
- `adapter_family`
- `adapter_version`
- `adapter_id`
- `rules_bundle_id`
- `descriptor_bundle_id`
- `descriptor_ids`
- `descriptor_ids.army_build_descriptor_id`
- `conditioning_keys`
- `conditioning_signature`

Current defaults:
- `adapter_family = "rules_conditioned_path"`
- `adapter_version = "1"`
- `adapter_id = "adapter:default"`

Purpose:
- keep the rules-conditioned path patchable without touching invariant board encoding
- provide deterministic conditioning signatures for replay and training dataset slicing
- stabilize adapter inputs before introducing ML framework dependencies
- distinguish not just mission/deployment/terrain semantics, but also the army-construction semantics that produced the battle

Edition-invariant consumers:
- `src/warhammer40k_ai/engine/combat_timing.py` derives `CombatTimingProfile` from the active `rules_bundle_id` / version-adapter context.
- Combat timing currently centralizes charge-target binding timing, fight-phase starting-player selection, pile-in/consolidate step enablement, and disembark charge policy selection behind that profile.
- Preview-derived behavior remains provisional until PR-012, but the adapter boundary is now the stable seam the combat runtime reads when edition-level invariants differ.
