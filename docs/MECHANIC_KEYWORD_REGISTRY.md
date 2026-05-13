# Mechanic And Keyword Registry

PR-014E adds a preview-gated runtime registry for reusable weapon, movement, and future codex mechanics.

The registry lives in `src/warhammer40k_ai/rules/mechanic_registry.py`. It defines `MechanicDefinition` / `KeywordDefinition` records with:

- `keyword_id`
- `display_name`
- `scope`
- `timing_window`
- `parameter_schema`
- `enabled_by_profile`
- `source_provenance`

The initial definitions are infrastructure-only for 11th-edition preparation. They do not make faction-focus previews live faction rules.

## Profiles

Definitions are matched by normalized profile id:

- `current`
- `11e_preview`
- `11e_release`

Preview mechanics are enabled only for `11e_preview` and `11e_release`. Current 10th-edition gameplay does not activate the new preview runtime.

## Weapon Runtime

`src/warhammer40k_ai/engine/weapon_keyword_runtime.py` collects preview-enabled weapon keyword instances and exposes attack-dice modifier hooks.

The first active hook is generic `CLEAVE X`.

During Select Targets, attack declarations are annotated with:

- keyword runtime profile id
- selected target ids for the attacking unit / weapon profile
- whether all attacks from that weapon selected exactly one target
- target model count at Select Targets
- parsed keyword instances and source provenance

That metadata is then copied into `AttackSequence.context`, which makes the Select Targets state snapshot/replay-visible. Later casualties or target-state changes do not alter the number of CLEAVE dice.

`CLEAVE X` applies at gather-attack-dice time only when:

- the weapon keyword runtime profile enables `CLEAVE`
- the weapon profile has a parsed `CLEAVE X` keyword
- exactly one target was selected for all attacks from that unit / weapon profile

The modifier is:

```text
X * floor(target_model_count_at_select_targets / 5)
```

Multi-target weapon selections receive no CLEAVE dice.

The registry also contains inert/generic hooks for `ASSAULT`, updated `HEAVY`, `LANCE`, `HAZARDOUS`, `RAPID_FIRE`, `SUSTAINED_HITS`, and `LETHAL_HITS`. Existing live behavior for those keywords remains in the current engine paths until a later PR migrates them behind the registry.

## Updated Heavy Preview Criteria

`evaluate_updated_heavy_criteria(...)` evaluates the preview Heavy eligibility shape from normalized unit-turn provenance:

- unit is unengaged
- unit was not set up this turn
- no model moved more than 3 inches this turn

PR-014H will provide the centralized `UnitTurnProvenance` object. PR-014E only adds the evaluator so the criteria are not hard-coded into attack resolution.

## Movement Runtime

`src/warhammer40k_ai/engine/movement_keyword_runtime.py` represents preview movement keywords without changing default movement or terrain behavior.

`MOBILE` is collected as a preview movement keyword with an inert terrain traversal hook. It is visible to future movement validation and AI feature work, but it does not alter current pathing legality.
