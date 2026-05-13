# Rules Descriptor Compiler

The engine compiles portability descriptors at decision time via:
- `src/warhammer40k_ai/engine/descriptor_compiler.py`

Focused compiler modules:
- `src/warhammer40k_ai/engine/descriptor_bundle.py`
- `src/warhammer40k_ai/engine/descriptor_mission.py`
- `src/warhammer40k_ai/engine/descriptor_objectives.py`
- `src/warhammer40k_ai/engine/descriptor_terrain.py`
- `src/warhammer40k_ai/engine/descriptor_deployment.py`
- `src/warhammer40k_ai/engine/descriptor_army_build.py`
- `src/warhammer40k_ai/engine/descriptor_tools.py`

Compiler output families:
- `MissionDescriptor`
- `ObjectiveDescriptor`
- `TerrainDescriptor`
- `DeploymentDescriptor`
- `ArmyBuildDescriptor`
- `ToolDescriptor`

Bundle contract:
- deterministic `descriptor_bundle_id`
- deterministic family IDs in `descriptor_ids`:
  - `mission_descriptor_id`
  - `objective_descriptor_ids`
  - `terrain_descriptor_ids`
  - `deployment_descriptor_id`
  - `army_build_descriptor_id`
  - `tool_descriptor_ids`

Runtime integration:
- `Game.request_decision(...)` injects `descriptor_ids` and `descriptor_bundle_id` into decision context.
- `DecisionRecordStore` falls back to compiled descriptors if request context omits descriptor IDs.
- Version-adapter conditioning includes `army_build_descriptor_id` alongside the existing descriptor families.

Objective descriptor notes:
- `ObjectiveDescriptor` now preserves site geometry independently from control/scoring bindings.
- Descriptor payloads carry explicit objective-site geometry, explicit control-region semantics, and score-source bindings.
- Terrain-footprint and keyed-feature objective sites therefore compile deterministically without pretending every objective is just a circular marker.

Tool descriptor sources:
- active enhancement descriptors on units (`enhancement_descriptors.py`)
- active stratagem descriptors on player stratagem managers (`stratagem_descriptors.py`)

Army-build descriptor source:
- per-player roster build state attached to runtime armies (`army_blueprint`, `army_blueprint_hash`, validated muster metadata, runtime detachment summary, enhancement assignments, upgrade assignments, attachment bindings, and force disposition state)

Army-build upgrade assignment notes:
- `ArmyBuildDescriptor` includes `upgrade_assignments` from `ArmyBlueprint`.
- Upgrade assignment records are hash-participating descriptor payload, so changes
  to target kind, target ids, selected weapon profile, cardinality, points-cost
  mode, or enhancement-budget counting behavior change the `army_build_descriptor_id`.
- This keeps 11e-style upgrade semantics visible to deterministic mustering and
  AI artifact selection without treating preview faction rules as live release data.

Design goal:
- learned policy inputs stay patchable by recompiling descriptors under the active rules bundle instead of hard-coding mission/objective/terrain semantics in model weights.

Build-side companion compiler:
- `src/warhammer40k_ai/engine/descriptor_build_capability.py`

`BuildCapabilityDescriptor` is compiled from `ArmyBlueprint` plus an explicit
`rules_bundle_id`. It is intentionally kept outside the runtime
`compile_descriptor_bundle(...)` contract because it summarizes authored roster
capabilities rather than per-game mission or terrain state.
