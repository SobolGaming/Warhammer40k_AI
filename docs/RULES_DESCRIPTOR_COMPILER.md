# Rules Descriptor Compiler

The engine compiles portability descriptors at decision time via:
- `src/warhammer40k_ai/engine/descriptor_compiler.py`

Compiler output families:
- `MissionDescriptor`
- `ObjectiveDescriptor`
- `TerrainDescriptor`
- `DeploymentDescriptor`
- `ToolDescriptor`

Bundle contract:
- deterministic `descriptor_bundle_id`
- deterministic family IDs in `descriptor_ids`:
  - `mission_descriptor_id`
  - `objective_descriptor_ids`
  - `terrain_descriptor_ids`
  - `deployment_descriptor_id`
  - `tool_descriptor_ids`

Runtime integration:
- `Game.request_decision(...)` injects `descriptor_ids` and `descriptor_bundle_id` into decision context.
- `DecisionRecordStore` falls back to compiled descriptors if request context omits descriptor IDs.

Tool descriptor sources:
- active enhancement descriptors on units (`enhancement_descriptors.py`)
- active stratagem descriptors on player stratagem managers (`stratagem_descriptors.py`)

Design goal:
- learned policy inputs stay patchable by recompiling descriptors under the active rules bundle instead of hard-coding mission/objective/terrain semantics in model weights.
