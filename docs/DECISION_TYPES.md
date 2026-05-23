# Decision Types Catalog

Status: Complete; keep in sync with `src/warhammer40k_ai/engine/decision_kinds.py`.

This catalog enumerates every decision kind currently defined in the engine.

Each gameplay-facing decision should be emitted as a `DecisionRequest` with deterministic
`options[]`, `candidates[]`, and `mask[]`, then resolved through the same
`RESOLVE_DECISION` command seam regardless of whether the controller is a local UI, a
network UI, a headless policy, or a future AI policy.

Reachability audit:
- Reviewed against `src/warhammer40k_ai/engine/decision_kinds.py` on May 13, 2026.
- All 124 decision kinds in that module have live `src/warhammer40k_ai/` references.
- The catalog below therefore covers the full current decision-kind surface, including
  faction-, datasheet-, detachment-, and weapon-specific windows that only appear under
  the right rules conditions.

For UI mapping, see `docs/NETWORK_SAVELOAD_DESIGN.md`.

## Resolution Invariant

- The trigger for a decision belongs to the authoritative engine. Controllers differ in
  who answers the request, not in whether the request exists.
- When headless play is enabled, the request still exists; a controller answers it.
- "Human" below means the same pending `DecisionRequest` is presented through the local
  or network UI and resolved by the player.
- "Headless" below uses the current controller stack:
  - `Runtime chooser`: deterministic runtime-owned chooser that resolves an emitted
    request without skipping the decision type.
  - `DeployDM`: `DeterministicDeploymentDecisionMaker` for deployment-manager-owned setup
    choices.
  - `Policy`: `HeadlessPolicyDecisionController`, which ranks legal candidates using
    semantic metadata and falls back to the first legal option when needed.
  - `AutoDice`: `HeadlessDecisionAgent` / network `AutoDiceDecisionController`, which
    resolves emitted roll and reroll requests deterministically.
- AI tier labels:
  - `T1`: strategic round/battle posture
  - `T2`: tactical binding of abstract goals to concrete units, targets, regions, or
    setup structure
  - `T3`: micro-execution over already-legal candidates
  - `N/A`: presentation-only or test/example surface, not a gameplay AI policy surface
- Concrete headless policy orchestration is implemented by `AIPolicyOrchestrator` in
  `src/warhammer40k_ai/engine/ai_policy_orchestrator.py`; shared decision surfaces
  such as `MOVE_UNIT`, `SELECT_UNIT`, and `CONFIRM_YES_NO` select components by request
  context. In particular, `SELECT_UNIT` shooting activations route to `shooting_ranker`,
  fight activations route to `fight_ranker`, and non-combat phase selection routes to
  `tactical_orchestrator`.

## Mission And Secondaries

- `CHOOSE_MISSION` - Select a mission-pack entry and terrain layout.
- `DISCARD_SECONDARY` - Discard one or more secondary objectives. `NEW ORDERS`
  choices discard one active Tactical Secondary and draw a replacement; Tactical
  end-of-turn voluntary discard choices may discard one or more active Tactical
  Secondaries and grant the turn player 1CP total through the normal CP-gain cap.

## Deployment And Pre-game

- `ATTACH_LEADER` - Attach a Leader to an eligible Bodyguard unit, or choose none.
- `ATTACH_SUPPORT_ARTILLERY` - Attach joined support or retinue elements, or choose none.
- `DECLARE_RESERVES` - Allocate reserve and strategic-reserve starts.
- `CHOOSE_DEPLOYMENT_ZONE` - Choose the defender's deployment zone.
- `SELECT_NEXT_DEPLOY_UNIT` - Choose the next eligible unit during alternating deployment.
- `ASSIGN_TRANSPORT` - Assign a unit to a transport, or choose none.
- `SHADOW_ASSIGNMENT` - Replace an eligible Officio Assassinorum unit with another valid
  assassin option, or keep the current one.
- `SCOUT_MOVE` - Resolve a pre-game Scout move.
- `CHOOSE_START_OF_BATTLE_KEYWORD` - Choose a start-of-battle keyword or keyed mode.
- `CHOOSE_PLAYER_COLOR` - Select a player's UI color during setup.
- `SELECT_SETUP_REACTIVE_TARGET` - Choose the target for a setup-reactive effect.
- `CHOOSE_SETUP_REACTIVE_ACTION` - Choose which setup-reactive action to take.

## Movement And Positioning

- `SELECT_UNIT` - Choose the next eligible unit to act in a phase step.
- `SELECT_MOVEMENT_ACTION` - Choose move, advance, fall back, or remain.
- `MOVE_UNIT` - Choose movement destination, path, or placement payload.
- `REACTIVE_MOVE` - Choose whether and how to resolve a preview-gated reactive normal
  or fallback-like move specification.
- `SURGE_MOVE` - Choose whether and how to resolve a preview-gated surge move
  specification.
- `SELECT_REACTIVE_RESERVE_EXIT` - Choose whether a preview-gated reactive transition
  places a unit into Strategic Reserves.
- `RESOLVE_COHERENCY` - Remove one additional model to restore coherency.
- `EMBARK` - Embark a unit into a transport.
- `DISEMBARK` - Disembark a unit from a transport. Explicit model positions must be
  wholly within the disembark range using full base/hull geometry, not only base
  center or closest-edge distance.
- `PICK_POINT` - Choose an exact point on the battlefield.
- `PICK_OBJECTIVE` - Choose an objective marker.
- `PICK_TERRAIN_FEATURE` - Choose a terrain feature.
- `SELECT_FLOOR` - Choose a floor or level for placement.

## Shooting And Ranged Attacks

- `SELECT_TOOL_ACTION` - Choose a generic stratagem tool action or skip. Only fully bound legal stratagem payloads are exposed.
- `SELECT_WEAPON` - Choose a weapon or profile to use.
- `DECLARE_SHOTS` - Declare shooting targets and split-fire assignments against legal per-model/per-weapon target candidates.
- `DECLARE_FIRING_DECK` - Select up to the transport's Firing Deck limit as embarked model/weapon/profile entries before `DECLARE_SHOTS`.
- `SELECT_OVERWATCH_SHOOTER` - Choose the unit that will fire Overwatch or an equivalent
  reaction.

## Charges

- `DECLARE_CHARGE` - Declare charge targets.
- `SELECT_HEROIC_INTERVENTION_MODE` - Choose a Heroic Intervention stratagem mode
  before the charge target policy and CP adjustment are applied.

## Fight And Damage Allocation

- `SELECT_FIGHT_TARGETS` - Choose fight targets.
- `DECLARE_MELEE_WEAPONS` - Select melee weapons or profiles.
- `ALLOCATE_MELEE_TARGETS` - Allocate melee attacks to targets.
- `ALLOCATE_TARGETS` - Allocate attacks to targets in a generic multi-target window.
- `SPLIT_ATTACKS` - Split attacks across targets.
- `SELECT_TARGET_MODEL` - Select a target model inside a unit.
- `SELECT_PRECISION_TARGET` - Select a precision target model.
- `ALLOCATE_DAMAGE` - Allocate damage or a model-specific follow-up effect.

## Dice And Rerolls

- `REQUEST_DICE_ROLL` - Resolve an explicit engine-owned dice roll.
- `SELECT_DICE_REROLL` - Select dice to reroll.
- `REROLL_ROLL` - Resolve a generic reroll-choice window.

## Reactive And Special Targeting

- `SELECT_RISE_TO_CHALLENGE` - Choose a Rise to Challenge target.
- `DEATHSTRIKE_ACTION` - Choose a Deathstrike action or target package.
- `SELECT_REVERBERATING_SUMMONS_UNIT` - Choose the unit affected by Reverberating
  Summons.
- `SELECT_EXPLODING_HORRORS_TARGET` - Choose the Exploding Horrors target.
- `SELECT_EXPLODING_HORRORS_MODELS` - Choose the models affected by Exploding Horrors.
- `CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET` - Choose a start-of-shooting Battle-shock
  target.
- `CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET` - Choose a post-shoot Battle-shock target.
- `CHOOSE_BATTLESHOCK_CLEAR_TARGET` - Choose a Battle-shocked unit to clear or rally.
- `CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET` - Choose a post-shoot mortal-wounds target.
- `CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET` - Choose a post-shoot Wracked Agonies
  target.
- `CHOOSE_POST_SHOOT_AFLAME_TARGET` - Choose a post-shoot aflame target.
- `CHOOSE_POST_SHOOT_SUPPRESSION_TARGET` - Choose a post-shoot suppression target.
- `CHOOSE_POST_FIGHT_SUPPRESSION_TARGET` - Choose a post-fight suppression target.
- `SELECT_UNLEASH_HELL_VEHICLE` - Choose an Unleash Hell vehicle or transport.
- `CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET` - Choose a post-shoot leadership-debuff
  target.
- `CHOOSE_DAEMONIC_POISONS_TARGET` - Choose a Daemonic Poisons target.

## Faction, Detachment, And Ability Choices

- `CHOOSE_BLESSINGS` - Choose Blessings of Khorne options.
- `CHOOSE_BLOOD_TITHE` - Choose a Blood Tithe reward.
- `CHOOSE_IDOL_OF_KHORNE` - Choose an Idol of Khorne effect.
- `SELECT_VESSEL_OF_WRATH_MODELS` - Choose Vessel of Wrath models.
- `SELECT_REALM_OF_CHAOS_UNITS` - Choose one or more eligible units for an
  ability-specific selection dialog.
- `CHOOSE_IMPOSSIBLE_ECLIPSE_ZONE` - Choose a Shadow of Chaos area for Impossible
  Eclipse.
- `CHOOSE_VESSEL_OF_WRATH_BLESSING` - Choose a Vessel of Wrath blessing.
- `CHOOSE_RITUALS` - Choose rituals.
- `CHOOSE_CHIVALRIC_OATH` - Choose a Chivalric Oath.
- `CHOOSE_DAEMONIC_ALLEGIANCE` - Choose a Daemonic Allegiance or keyed mode.
- `CHOOSE_DARK_PACT` - Choose a Dark Pact and any linked modifiers.
- `CHOOSE_DOCTRINA` - Choose a Doctrina Imperative.
- `CHOOSE_COMBAT_DOCTRINE` - Choose a Combat Doctrine.
- `CHOOSE_MISSION_TACTIC` - Choose a Mission Tactic.
- `CHOOSE_ANGELIC_LEGACY` - Choose Angelic Legacy abilities.
- `CHOOSE_GRAND_COVEN` - Choose a Grand Coven option.
- `CHOOSE_COMBAT_DRUGS` - Choose Combat Drugs.
- `CHOOSE_MURDEROUS_AGENDA` - Choose a Murderous Agenda contract and target.
- `CHOOSE_HYPER_ADAPTATION` - Choose a Hyper-adaptation.
- `CHOOSE_FRENZY_TARGET` - Choose a Frenzy target.
- `CHOOSE_HARBINGER` - Choose or reroll Harbingers of Dread state.
- `USE_GILDED_CHAMPION` - Choose whether to use Gilded Champion.
- `CHOOSE_MARTIAL_KATAH` - Choose a Martial Katah.
- `CHOOSE_PATH_OF_WARRIOR` - Choose a Path of the Warrior option.
- `CHOOSE_CRUEL_AMUSEMENT` - Choose a Cruel Amusement option.
- `CHOOSE_MASTER_OF_MAGICKS` - Choose a Master of Magicks option.
- `CHOOSE_TECHNOSORCEROUS_AUGMENTATION` - Choose a Technosorcerous Augmentation weapon
  ability.
- `CHOOSE_HARBINGER_OF_DEATH` - Choose a Harbinger of Death option.
- `CHOOSE_DANCE_OF_DEATH` - Choose a Dance of Death option.
- `CHOOSE_BLADEGUARD_STANCE` - Choose a Bladeguard stance.
- `CHOOSE_ADAPTIVE_INSTINCTS` - Choose an Adaptive Instincts imperative.
- `CHOOSE_LIMB_FROM_LIMB` - Choose a Limb from Limb option or target.
- `CHOOSE_RED_WRATH` - Choose a Red Wrath mode.
- `USE_MIRACLE_DIE` - Choose whether and how to use a Miracle Die.
- `CHOOSE_PLAGUE` - Choose a plague or Nurgle's Gift mode.
- `CHOOSE_PLEDGE` - Choose a pledge.
- `CHOOSE_QUARRY` - Choose an ability-specific target, objective, order, mode, or skip.
- `CHOOSE_HYSTERICAL_FRENZY_PSYKER` - Choose a Psyker for Hysterical Frenzy.
- `CHOOSE_GIFT_OF_CHAOS_TARGET` - Choose a Gift of Chaos target unit.
- `CHOOSE_MOMENT_SHACKLE` - Choose a Moment Shackle option.
- `CHOOSE_SHADOW_FORM` - Choose a Shadow Form mode.
- `CHOOSE_VOW` - Choose a Vow.
- `ISSUE_ORDER` - Issue an Order and select its recipient.
- `CHOOSE_WRATHFUL_PRESENCE` - Choose a Wrathful Presence mode.
- `CHOOSE_DAEMON_PRIMARCH_SLAANESH` - Choose a Slaanesh primarch option.
- `CHOOSE_WARMASTER_ABILITY` - Choose The Warmaster ability.
- `USE_CAREEN` - Choose whether to use Careen!.
- `CHOOSE_ASPECT` - Choose an Aspect.
- `USE_LEADING_UNMODIFIED_SIX` - Choose whether to consume a leading unmodified-six
  effect.
- `USE_MODEL_UNMODIFIED_SIX` - Choose whether to consume a model-specific unmodified-six
  effect.
- `CHOOSE_HIT_MODIFIER_IGNORES` - Choose which hit or wound modifier-ignores effect to
  apply.
- `CHOOSE_SKILL_MODIFIER_IGNORES` - Choose which WS or BS modifier-ignores effect to
  apply.
- `CHOOSE_MOVE_MODIFIER_IGNORES` - Choose which move modifier-ignores effect to apply.
- `CHOOSE_ADVANCE_MODIFIER_IGNORES` - Choose which advance modifier-ignores effect to
  apply.
- `CHOOSE_CHARGE_MODIFIER_IGNORES` - Choose which charge modifier-ignores effect to
  apply.
- `CHOOSE_BATTLE_FOCUS_MANEUVER` - Choose a Battle Focus maneuver trigger.
- `CHOOSE_POWER_FROM_PAIN_OPTION` - Choose a Power from Pain option.
- `CHOOSE_MALEFIC_SURGE_UNIT` - Choose the unit for a Malefic Surge window.
- `CHOOSE_MALEFIC_SURGE_ABILITY` - Choose the Malefic Surge ability to apply.
- `SELECT_STRATAGEM_MODE` - Choose a generic modal stratagem payload before applying
  its bound target, resource, or movement semantics.

## Generic Confirmations

- `CONFIRM_MODAL` - Generic modal confirmation.
- `CONFIRM_YES_NO` - Generic yes or no confirmation.
- `CONFIRM_EXAMPLE` - Test or example confirmation.

## Resolution Matrix

The table below is intentionally exhaustive. It is the reference point for how each
`DECISION_*` kind is supposed to be answered once emitted.

| Decision Type | Reachability / Trigger | Human (via UI) | Headless | AI |
| --- | --- | --- | --- | --- |
| `CHOOSE_MISSION` | Mission-selection tooling or manual mission-pick surface. | UI | `Runtime chooser` | `T1` |
| `CONFIRM_MODAL` | Generic modal wrapper or non-gameplay shell. | UI/manual | `N/A` | `N/A` |
| `ATTACH_LEADER` | Declare Battle Formations with unresolved Leader attachment. | UI | `Policy` | `T2` |
| `ATTACH_SUPPORT_ARTILLERY` | Declare Battle Formations with unresolved joined support or retinue attachment. | UI | `Policy` | `T2` |
| `DECLARE_RESERVES` | Declare Battle Formations reserve-allocation window. | UI | `DeployDM` | `T2` |
| `CHOOSE_DEPLOYMENT_ZONE` | Deploy Armies defender zone choice. | UI | `DeployDM` | `T2` |
| `SELECT_NEXT_DEPLOY_UNIT` | Alternating deployment asks for the next eligible unit. | UI | `DeployDM` | `T2` |
| `ASSIGN_TRANSPORT` | Declare Battle Formations transport assignment window. | UI | `Policy` | `T2` |
| `SHADOW_ASSIGNMENT` | Shadow Assignment replacement window for eligible assassin swaps. | UI | `Policy` | `T2` |
| `SCOUT_MOVE` | Pre-battle Scout reposition window. | UI | `Policy` | `T2/T3` |
| `SELECT_FLOOR` | Placement enters a valid multi-floor RUINS choice. | UI | `Policy` | `T3` |
| `CHOOSE_PLAYER_COLOR` | Setup presentation color picker. | UI | `N/A` | `N/A` |
| `SELECT_UNIT` | A phase step needs the next eligible unit to act. | UI | `Policy` | `T2/T3` |
| `SELECT_MOVEMENT_ACTION` | Movement activation needs move, advance, fall back, or remain. | UI | `Policy` | `T3` |
| `MOVE_UNIT` | Deployment, movement, reserves arrival, or reactive placement is required. | UI | `DeployDM` for deployment; otherwise `Policy` | `T2/T3` |
| `REACTIVE_MOVE` | Preview-gated reactive normal or fallback-like move spec is available. | UI | `Policy` | `T3` |
| `SURGE_MOVE` | Preview-gated surge move spec is available, usually with directional end-state constraints. | UI | `Policy` | `T3` |
| `SELECT_REACTIVE_RESERVE_EXIT` | Preview-gated reactive effect can place a unit into Strategic Reserves. | UI | `Policy` | `T3` |
| `RESOLVE_COHERENCY` | Casualties leave a unit out of coherency and one more model must be removed. | UI | `Policy` | `T3` |
| `EMBARK` | A unit may embark into a transport. | UI | `Policy` | `T3` |
| `DISEMBARK` | A unit must or may disembark, including reactive disembark windows. Model-position payloads are validated as wholly within the disembark range using full base/hull geometry. | UI | `Policy` | `T3` |
| `PICK_POINT` | A rule requires an exact battlefield point. | UI | `Policy` | `T3` |
| `PICK_OBJECTIVE` | A rule requires an objective marker. | UI | `Policy` | `T2` |
| `PICK_TERRAIN_FEATURE` | A rule requires a terrain feature. | UI | `Policy` | `T2` |
| `SELECT_TOOL_ACTION` | A generic headless/non-local stratagem window exposes one or more legal tool actions plus skip. Target-required malformed payloads are filtered before exposure and recorded as visible tool-probe diagnostics when required context failed to bind. | UI | `Policy` | `T2/T3` |
| `SELECT_WEAPON` | An activation needs a weapon or profile choice. | UI | `Policy` | `T3` |
| `DECLARE_SHOTS` | A shooting unit must declare legal targets and split fire. | UI | `Policy` | `T3` |
| `DECLARE_FIRING_DECK` | A transport with Firing Deck must choose non-ONE SHOT weapons from up to X eligible embarked models before its shooting declarations. | UI | `Policy` | `T3` |
| `SELECT_OVERWATCH_SHOOTER` | Overwatch or equivalent reaction needs a shooter choice, including authoritative `FIRE OVERWATCH` windows. | UI | `Policy` | `T3` |
| `SELECT_RISE_TO_CHALLENGE` | Rise to Challenge target window opens. | UI | `Policy` | `T3` |
| `SELECT_SETUP_REACTIVE_TARGET` | Setup-reactive rules produce eligible enemy targets. | UI | `Policy` | `T3` |
| `REROLL_ROLL` | A generic reroll-choice window opens. | UI | `Policy` | `T3` |
| `DEATHSTRIKE_ACTION` | Deathstrike targeting or mode window opens. | UI | `Policy` | `T3` |
| `SELECT_REVERBERATING_SUMMONS_UNIT` | Reverberating Summons must identify an affected unit. | UI | `Policy` | `T2/T3` |
| `REQUEST_DICE_ROLL` | Any explicit engine-owned dice roll request. | UI | `AutoDice` | `T3` |
| `SELECT_DICE_REROLL` | Any explicit dice-reroll selection request. | UI | `AutoDice` | `T3` |
| `DECLARE_CHARGE` | A charging unit must declare charge targets. | UI | `Policy` | `T3` |
| `SELECT_HEROIC_INTERVENTION_MODE` | Heroic Intervention exposes multiple preview-gated mode payloads before charge resolution. | UI | `Policy` | `T3` |
| `SELECT_FIGHT_TARGETS` | A fighting unit must choose its fight targets. | UI | `Policy` | `T3` |
| `DECLARE_MELEE_WEAPONS` | A fighting unit must choose melee weapons or profiles. | UI | `Policy` | `T3` |
| `ALLOCATE_MELEE_TARGETS` | A unit can split melee attacks across multiple targets. | UI | `Policy` | `T3` |
| `ALLOCATE_TARGETS` | A general multi-target allocation window opens. | UI | `Policy` | `T3` |
| `SPLIT_ATTACKS` | A split-attacks declaration window opens. | UI | `Policy` | `T3` |
| `SELECT_TARGET_MODEL` | A rule needs a specific model inside the target unit. | UI | `Policy` | `T3` |
| `SELECT_PRECISION_TARGET` | A precision attack needs a specific model target. | UI | `Policy` | `T3` |
| `ALLOCATE_DAMAGE` | Damage or a model-scoped follow-up effect must be allocated. | UI | `Policy` | `T3` |
| `SELECT_EXPLODING_HORRORS_TARGET` | Exploding Horrors needs a target unit. | UI | `Policy` | `T3` |
| `SELECT_EXPLODING_HORRORS_MODELS` | Exploding Horrors needs affected model selections. | UI | `Policy` | `T3` |
| `CHOOSE_BLESSINGS` | World Eaters Blessings of Khorne round-start choice. | UI | `Policy` | `T1` |
| `CHOOSE_BLOOD_TITHE` | Blood Tithe reward spend window. | UI | `Policy` | `T1` |
| `CHOOSE_IDOL_OF_KHORNE` | Idol of Khorne option window. | UI | `Policy` | `T1` |
| `SELECT_VESSEL_OF_WRATH_MODELS` | Vessel of Wrath chooses eligible models. | UI | `Policy` | `T2` |
| `SELECT_REALM_OF_CHAOS_UNITS` | A named ability asks for one or more eligible units. | UI | `Policy` | `T2/T3` |
| `CHOOSE_IMPOSSIBLE_ECLIPSE_ZONE` | Impossible Eclipse needs a Shadow-of-Chaos zone choice. | UI | `Policy` | `T2` |
| `CHOOSE_VESSEL_OF_WRATH_BLESSING` | Vessel of Wrath blessing choice window. | UI | `Policy` | `T1` |
| `CHOOSE_RITUALS` | Ritual selection window opens. | UI | `Policy` | `T1` |
| `CHOOSE_CHIVALRIC_OATH` | Imperial Knights oath selection window. | UI | `Policy` | `T1` |
| `CHOOSE_START_OF_BATTLE_KEYWORD` | A start-of-battle ability must assign a keyword or keyed mode. | UI | `Policy` | `T2` |
| `CHOOSE_DAEMONIC_ALLEGIANCE` | A Daemonic Allegiance or keyed mode must be chosen. | UI | `Policy` | `T1/T2` |
| `CHOOSE_DARK_PACT` | Dark Pact is chosen for an immediate attack sequence. | UI | `Policy` | `T3` |
| `CHOOSE_DOCTRINA` | Adeptus Mechanicus Doctrina Imperative round-start choice. | UI | `Policy` | `T1` |
| `CHOOSE_COMBAT_DOCTRINE` | Combat Doctrine round-start choice. | UI | `Policy` | `T1` |
| `CHOOSE_MISSION_TACTIC` | Mission Tactic round-start choice. | UI | `Policy` | `T1` |
| `CHOOSE_ANGELIC_LEGACY` | Angelic Legacy round-start choice. | UI | `Policy` | `T1` |
| `CHOOSE_GRAND_COVEN` | Grand Coven choice window. | UI | `Policy` | `T1/T2` |
| `CHOOSE_COMBAT_DRUGS` | Combat Drugs round-start choice. | UI | `Policy` | `T1` |
| `CHOOSE_MURDEROUS_AGENDA` | Murderous Agenda must bind a contract and target. | UI | `Policy` | `T2` |
| `CHOOSE_HYPER_ADAPTATION` | Hyper-adaptation battle-start or battle-round choice. | UI | `Policy` | `T1` |
| `CHOOSE_SETUP_REACTIVE_ACTION` | Setup-reactive rules branch into shoot vs charge. | UI | `Policy` | `T3` |
| `CHOOSE_FRENZY_TARGET` | Frenzy target-selection window opens. | UI | `Policy` | `T3` |
| `CHOOSE_HARBINGER` | Chaos Knights Harbingers of Dread choice or reroll window. | UI | `Policy` | `T1` |
| `USE_GILDED_CHAMPION` | Gilded Champion optional-use window opens. | UI | `Policy` | `T3` |
| `CHOOSE_MARTIAL_KATAH` | Martial Katah round-start choice. | UI | `Policy` | `T1` |
| `CHOOSE_PATH_OF_WARRIOR` | Path of the Warrior option window opens. | UI | `Policy` | `T2/T3` |
| `CHOOSE_CRUEL_AMUSEMENT` | Cruel Amusement option window opens. | UI | `Policy` | `T2/T3` |
| `CHOOSE_MASTER_OF_MAGICKS` | Master of Magicks option window opens. | UI | `Policy` | `T2/T3` |
| `CHOOSE_TECHNOSORCEROUS_AUGMENTATION` | Technosorcerous Augmentation must choose a weapon ability. | UI | `Policy` | `T3` |
| `CHOOSE_HARBINGER_OF_DEATH` | Harbinger of Death option window opens. | UI | `Policy` | `T1/T2` |
| `CHOOSE_DANCE_OF_DEATH` | Dance of Death option window opens. | UI | `Policy` | `T2/T3` |
| `CHOOSE_BLADEGUARD_STANCE` | Bladeguard stance selection window opens. | UI | `Policy` | `T1/T2` |
| `CHOOSE_ADAPTIVE_INSTINCTS` | Adaptive Instincts imperative selection opens. | UI | `Policy` | `T1` |
| `CHOOSE_LIMB_FROM_LIMB` | Limb from Limb target or mode choice opens. | UI | `Policy` | `T3` |
| `CHOOSE_RED_WRATH` | Red Wrath mode choice opens. | UI | `Policy` | `T3` |
| `USE_MIRACLE_DIE` | Miracle Die substitution or spend window opens. | UI | `Policy` | `T3` |
| `CHOOSE_PLAGUE` | Plague or Nurgle's Gift mode must be chosen. | UI | `Policy` | `T1` |
| `CHOOSE_PLEDGE` | Pledge choice window opens. | UI | `Policy` | `T1/T2` |
| `CHOOSE_QUARRY` | A named rule asks for a target, objective, order, mode, or skip. | UI | `Policy` | `T2/T3` |
| `CHOOSE_HYSTERICAL_FRENZY_PSYKER` | Hysterical Frenzy must choose an eligible Psyker. | UI | `Policy` | `T2` |
| `CHOOSE_GIFT_OF_CHAOS_TARGET` | Gift of Chaos must choose a target unit. | UI | `Policy` | `T3` |
| `CHOOSE_MOMENT_SHACKLE` | Moment Shackle mode choice opens. | UI | `Policy` | `T3` |
| `CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET` | A post-shoot rule needs one hit or wounded enemy target. | UI | `Policy` | `T3` |
| `CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET` | A start-of-shooting rule needs a Battle-shock target. | UI | `Policy` | `T2/T3` |
| `CHOOSE_BATTLESHOCK_CLEAR_TARGET` | A rally or clear-Battle-shock effect must choose a unit. | UI | `Policy` | `T2` |
| `CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET` | A post-shoot mortal-wounds rule needs a target. | UI | `Policy` | `T3` |
| `CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET` | A post-shoot Wracked Agonies rule needs a target. | UI | `Policy` | `T3` |
| `CHOOSE_POST_SHOOT_AFLAME_TARGET` | A post-shoot aflame rule needs a target. | UI | `Policy` | `T3` |
| `CHOOSE_POST_SHOOT_SUPPRESSION_TARGET` | A post-shoot suppression rule needs a target. | UI | `Policy` | `T3` |
| `CHOOSE_POST_FIGHT_SUPPRESSION_TARGET` | A post-fight suppression rule needs a target. | UI | `Policy` | `T3` |
| `SELECT_UNLEASH_HELL_VEHICLE` | Unleash Hell must choose a vehicle or transport. | UI | `Policy` | `T3` |
| `CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET` | A post-shoot leadership-debuff rule needs a target. | UI | `Policy` | `T3` |
| `CHOOSE_DAEMONIC_POISONS_TARGET` | Daemonic Poisons must choose a target. | UI | `Policy` | `T3` |
| `DISCARD_SECONDARY` | Secondary discard choice opens. `NEW ORDERS` records carry `ability="new_orders"` and `discard_source="new_orders"`. Tactical end-of-turn voluntary discards carry `ability="tactical_secondary_discard"`, `discard_source="tactical_end_turn"`, `discard_timing="end_of_turn"`, `card_slots[]`, and `card_names[]`; own-turn discards set `gain_cp_if_discarded=true`. Achieved-secondary cleanup is automatic scoring cleanup, not this decision. | UI | `Policy` | `T1` |
| `CHOOSE_SHADOW_FORM` | Shadow Form round-start choice opens. | UI | `Policy` | `T1` |
| `CHOOSE_VOW` | Vow battle-start choice opens. | UI | `Policy` | `T1` |
| `ISSUE_ORDER` | An order source must choose an order and recipient. | UI | `Policy` | `T2` |
| `CHOOSE_WRATHFUL_PRESENCE` | Wrathful Presence round-start choice opens. | UI | `Policy` | `T1` |
| `CHOOSE_DAEMON_PRIMARCH_SLAANESH` | A Daemon Primarch Slaanesh mode must be chosen. | UI | `Policy` | `T1` |
| `CHOOSE_WARMASTER_ABILITY` | The Warmaster ability choice opens. | UI | `Policy` | `T1` |
| `USE_CAREEN` | Careen! reactive-use window opens. | UI | `Policy` | `T3` |
| `CONFIRM_YES_NO` | Generic optional-use confirmation window opens. | UI | `Policy` | `T3` |
| `CHOOSE_ASPECT` | Aspect or shrine-aspect choice opens. | UI | `Policy` | `T1/T2` |
| `USE_LEADING_UNMODIFIED_SIX` | A leading unmodified-six effect can be consumed. | UI | `Policy` | `T3` |
| `USE_MODEL_UNMODIFIED_SIX` | A model-specific unmodified-six effect can be consumed. | UI | `Policy` | `T3` |
| `CONFIRM_EXAMPLE` | Test or example confirmation surface. | UI/manual | `N/A` | `N/A` |
| `CHOOSE_HIT_MODIFIER_IGNORES` | Relevant hit or wound modifier-ignore choices exist. | UI | `Policy` | `T3` |
| `CHOOSE_SKILL_MODIFIER_IGNORES` | Relevant BS or WS modifier-ignore choices exist. | UI | `Policy` | `T3` |
| `CHOOSE_MOVE_MODIFIER_IGNORES` | Relevant movement modifier-ignore choices exist. | UI | `Policy` | `T3` |
| `CHOOSE_ADVANCE_MODIFIER_IGNORES` | Relevant advance modifier-ignore choices exist. | UI | `Policy` | `T3` |
| `CHOOSE_CHARGE_MODIFIER_IGNORES` | Relevant charge modifier-ignore choices exist. | UI | `Policy` | `T3` |
| `CHOOSE_BATTLE_FOCUS_MANEUVER` | Battle Focus must choose the maneuver to trigger. | UI | `Policy` | `T2/T3` |
| `CHOOSE_POWER_FROM_PAIN_OPTION` | Power from Pain must choose an available option. | UI | `Policy` | `T1` |
| `CHOOSE_MALEFIC_SURGE_UNIT` | Malefic Surge must choose the source or recipient unit. | UI | `Policy` | `T2` |
| `CHOOSE_MALEFIC_SURGE_ABILITY` | Malefic Surge must choose the ability to apply. | UI | `Policy` | `T1/T2` |
| `SELECT_STRATAGEM_MODE` | A modal stratagem exposes one or more bound mode payloads. | UI | `Policy` | `T2/T3` |

Round-start decision ordering: when a World Eaters army has Angron's `Wrathful Presence`, `CHOOSE_WRATHFUL_PRESENCE` resolves before that army's same-round `CHOOSE_BLESSINGS` request. The Blessings request context records the post-aura Khorne Yahtzee state, including `ctx.rerolls_allowed`, so `The Blood God's Favour` is visible as six available Blessings rerolls in the same battle round.
