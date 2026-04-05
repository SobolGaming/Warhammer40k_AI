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
