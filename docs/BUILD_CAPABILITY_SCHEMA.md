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
- optional explicit `BuildCapabilityExtensionGroup` ids for additive preview
  feature groups
- either a snapshot-scoped `WahaHelper` or a rules-bundle payload carrying one of:
  `wahapedia_data_dir`, `waha_data_dir`, or `rules_data_dir`

The profile payload is intended to remain portable across heuristic and learned
evaluators. Feature names therefore stay generic instead of embedding edition-
preview wording or faction-specific assumptions.

Rules-snapshot selection notes:
- `rules_bundle_id` is provenance and deterministic identity, but replay-safe
  compilation also needs a concrete rules snapshot for datasheet resolution.
- The compiler therefore rejects ambient default-data resolution when no
  snapshot-scoped helper or bundle-scoped data directory is provided.
- Supported bundle-side selectors are `wahapedia_data_dir`, `waha_data_dir`, and
  `rules_data_dir`.
- `BUILD_CAPABILITY_SCHEMA_V1` remains the default portable schema.
- Preview combat bundles may opt into `BUILD_CAPABILITY_SCHEMA_V2` explicitly
  when matchup or mustering evaluators need the additional combat-facing fields.
  That is a scoped compatibility choice, not an in-place widening of v1.
- Preview extension groups are also explicit. They add deterministic feature
  names to an existing schema such as `build_capability_v2` without creating a
  new schema id for each preview article. When active, profile and descriptor
  payloads include `extension_group_ids` plus the extension group's provenance;
  when inactive, v1/v2 payloads stay in their existing shape.

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
- `build_capability_v2` adds preview-combat descriptors without changing the v1
  field contract or default descriptor compilation path.
- `capability_extension:11e_faction_focus_may2026` is an explicit v2 extension
  group for deterministic faction-focus preview features. It is not a learned
  model compatibility claim and is omitted unless requested by the caller.

## Example Preview Combat Capability Schema

```json
{
  "capability_schema_id": "capability_schema:build_capability_v2",
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
    },
    {
      "name": "charge_option_flexibility",
      "kind": "score",
      "description": "How much the roster can exploit flexible charge routing and target-binding choices once delivery has succeeded."
    },
    {
      "name": "ingress_charge_conversion",
      "kind": "score",
      "description": "How efficiently reserve-entry threat converts into near-term charge pressure under the active ingress exclusion geometry."
    },
    {
      "name": "fight_order_resilience",
      "kind": "score",
      "description": "How well the roster preserves value when melee fight-order priority or interrupt timing changes across the active rules bundle."
    },
    {
      "name": "overrun_chain_potential",
      "kind": "score",
      "description": "How much the roster can continue extracting melee value after an initial engagement collapses and a follow-on pile-in becomes available."
    },
    {
      "name": "consolidate_objective_swing",
      "kind": "score",
      "description": "How strongly end-of-fight consolidates can convert into objective steals, denial swings, or late activation pressure."
    },
    {
      "name": "engagement_footprint_pressure",
      "kind": "score",
      "description": "How strongly the roster can exploit enlarged engagement footprints or broad melee threat bubbles to pin space."
    },
    {
      "name": "transport_pop_punish_index",
      "kind": "score",
      "description": "How well the roster can capitalize on transport-destruction fight states and newly exposed passengers."
    }
  ]
}
```

## Example Capability Extension Group

```json
{
  "extension_group_id": "capability_extension:11e_faction_focus_may2026",
  "feature_definitions": [
    {
      "name": "detection_marker_coverage",
      "kind": "score",
      "description": "How broadly the roster can project value from generic detection-marker style visibility range changes."
    },
    {
      "name": "anti_hidden_projection",
      "kind": "score",
      "description": "How well the roster can combine reach, marker support, and ranged pressure to contest Hidden-style targets."
    },
    {
      "name": "hidden_persistence_value",
      "kind": "score",
      "description": "How much value the roster can preserve from Hidden-style protection while still contributing to board state."
    },
    {
      "name": "keyword_mutation_density",
      "kind": "score",
      "description": "How much the roster's deterministic evaluation depends on runtime keyword mutation, upgrade payloads, or detachment-authored keyword changes."
    },
    {
      "name": "cleave_horde_clearance",
      "kind": "score",
      "description": "How naturally melee pressure and model volume convert into horde-clearance value under a generic Cleave-like attack-dice modifier."
    },
    {
      "name": "heavy_stationary_fire_quality",
      "kind": "score",
      "description": "How much the roster benefits from remaining unengaged, not being set up this turn, and limiting model movement before shooting."
    },
    {
      "name": "mobile_terrain_traversal_value",
      "kind": "score",
      "description": "How much mission and movement value the roster can extract from generic Mobile-style terrain traversal."
    },
    {
      "name": "reactive_move_density",
      "kind": "score",
      "description": "How much roster value is exposed to reusable reactive-move decision points."
    },
    {
      "name": "heroic_intervention_density",
      "kind": "score",
      "description": "How strongly the roster can exploit modal Heroic Intervention or countercharge decision surfaces."
    },
    {
      "name": "must_fight_next_leverage",
      "kind": "score",
      "description": "How much the roster can gain from scheduler-visible must-fight-next constraints."
    },
    {
      "name": "action_after_advance_fallback_flex",
      "kind": "score",
      "description": "How much mission-action value remains available when units advance, fall back, or otherwise need movement-flex exceptions."
    },
    {
      "name": "reserve_reposition_flex",
      "kind": "score",
      "description": "How much the roster can exploit reserve-entry, reserve-exit, and reposition decision surfaces."
    },
    {
      "name": "upgrade_cardinality_complexity",
      "kind": "score",
      "description": "How much the roster's build-side semantics depend on multi-target, unit/model, or weapon-profile upgrade assignment shape."
    },
    {
      "name": "battle_shock_persistence_leverage",
      "kind": "score",
      "description": "How much the roster can exploit persistent tactical-status state instead of assuming automatic Command phase cleanup."
    }
  ],
  "source_provenance": [
    {
      "label": "May 2026 faction-focus preview mechanics catalog",
      "mechanics_observed": [
        "detection_markers",
        "hidden_preserving_shooting",
        "cleave",
        "updated_heavy",
        "mobile",
        "reactive_movement",
        "heroic_intervention_modes",
        "must_fight_next",
        "upgrade_cardinality",
        "battle_shock_persistence"
      ],
      "preview_only": true,
      "source_id": "preview_sources:11e_faction_focus_may2026",
      "url": "docs/preview_sources/11e_faction_focus_may2026.json"
    }
  ],
  "activation": "explicit"
}
```

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
