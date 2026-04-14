# Build Capability Schema

`BuildCapabilityProfile` is the deterministic, JSON-safe summary layer that
describes what a roster can do in gameplay terms without coupling callers to
datasheet internals or learned-model features.

Compiler modules:
- `src/warhammer40k_ai/roster/build_capability.py`
- `src/warhammer40k_ai/roster/build_capability_schema.py`
- `src/warhammer40k_ai/engine/descriptor_build_capability.py`

Stable ID fields:
- `capability_schema_id`: the versioned schema contract for aggregate counts,
  pressure metrics, and capability scores
- `build_capability_profile_id`: deterministic hash-derived id for the compiled
  profile payload under the active schema and `rules_bundle_id`

Compilation inputs:
- `ArmyBlueprint`
- `rules_bundle_id`
- optional explicit `BuildCapabilitySchema`

The profile payload is intended to remain portable across heuristic and learned
evaluators. Feature names therefore stay generic instead of embedding edition-
preview wording or faction-specific assumptions.

## Example Build Capability Schema

```json
{
  "capability_schema_id": "capability_schema:build_capability_v1",
  "aggregate_count_names": [
    "unit_count",
    "detachment_count",
    "enhancement_count",
    "attachment_binding_count",
    "leader_binding_count",
    "support_binding_count",
    "battleline_unit_count",
    "character_unit_count",
    "vehicle_or_monster_unit_count",
    "towering_unit_count",
    "titanic_unit_count",
    "deep_strike_unit_count",
    "infiltrator_unit_count",
    "scout_unit_count",
    "attachment_capable_unit_count"
  ],
  "pressure_metric_names": [
    "melee_pressure",
    "ranged_pressure",
    "short_range_pressure",
    "long_range_firepower",
    "indirect_firepower",
    "anti_tank_pressure",
    "action_capacity_total",
    "melee_share"
  ],
  "feature_definitions": [
    {
      "name": "terrain_occlusion_reliance",
      "kind": "score",
      "description": "How strongly the roster benefits from safe staging and obscuring lanes to deliver short-range or melee threats."
    },
    {
      "name": "elevated_fire_affinity",
      "kind": "score",
      "description": "How naturally the roster converts long-range, indirect, or towering shooting presence into table control."
    },
    {
      "name": "deployment_reveal_pressure",
      "kind": "score",
      "description": "How much the roster can pressure deployment and reserve declarations via forward deploy, scouting, or reserve-entry threats."
    },
    {
      "name": "charge_delivery_reliance",
      "kind": "score",
      "description": "How much the roster's payoff depends on delivering melee threats through charges, pregame moves, or reserve positioning."
    },
    {
      "name": "objective_spread_tolerance",
      "kind": "score",
      "description": "How well the roster can spread across multiple objectives without collapsing its scoring plan."
    },
    {
      "name": "attachment_dependency_risk",
      "kind": "score",
      "description": "How much the roster depends on leader/support pairings or bound enhancement packages to function at intended efficiency."
    },
    {
      "name": "controller_complexity_index",
      "kind": "score",
      "description": "A generic control burden estimate derived from unit count, detachments, pregame options, and attachment/enhancement state."
    },
    {
      "name": "mission_action_flex_capacity",
      "kind": "score",
      "description": "How much spare mission-action bandwidth the roster has through cheap, mobile, or self-sufficient pieces."
    },
    {
      "name": "detachment_diversity_index",
      "kind": "score",
      "description": "How much the roster spreads its authored identity across multiple detachments instead of a single detachment plan."
    },
    {
      "name": "towering_exposure_index",
      "kind": "score",
      "description": "How exposed the roster is to visibility and footprint constraints from towering or otherwise giant anchors."
    }
  ]
}
```

## Field Notes

Interpretation guidance:
- Aggregate counts are explicit authored or inferred roster-shape counts.
- Pressure metrics are raw-ish semantic totals preserved for downstream scoring.
- Capability scores are normalized `0.0-1.0` summary features intended for
  comparison, filtering, or explanation layers.
- Changing `rules_bundle_id` or `capability_schema_id` changes the compiled
  `build_capability_profile_id` deterministically.

## Example Capability Explanation

Example explanation for a mixed-detachment Space Marines roster:

> This roster wants to stage behind terrain, then project a controlled mid-board
> fight through Captain-led Bladeguard while Intercessors keep objective work
> online. It is not a towering fire base, so elevated-fire affinity stays low,
> but it does carry moderate attachment risk because its strongest authored plan
> depends on a leader-bodyguard package and an assigned enhancement. The second
> detachment increases authored flexibility, which shows up as a meaningful
> detachment-diversity score instead of forcing the roster into a single-plan
> label.
