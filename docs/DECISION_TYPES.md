# Decision Types Catalog

Status: Complete; keep in sync with `src/warhammer40k_ai/engine/decision_kinds.py`.

This catalog enumerates all decision types currently emitted by the engine.
Each decision is represented as a `DecisionRequest` with `candidates[]` and `mask[]`.
For UI mapping, see `docs/NETWORK_SAVELOAD_DESIGN.md`.

## Mission & Secondaries

- `CHOOSE_MISSION` — Select mission combination/layout.
- `DISCARD_SECONDARY` — Discard a secondary objective.

## Deployment & Pre-game

- `ATTACH_LEADER` — Attach leader to bodyguard (or none).
- `ATTACH_SUPPORT_ARTILLERY` — Attach joined support/retinue unit to bodyguard (or none).
- `DECLARE_RESERVES` — Declare units in reserve.
- `ASSIGN_TRANSPORT` — Assign transport to a unit (or none).
- `SHADOW_ASSIGNMENT` — Replace an eligible OFFICIO ASSASSINORUM unit with another valid assassin option (or None).
- `SCOUT_MOVE` — Resolve pre-game scout move.
- `CHOOSE_START_OF_BATTLE_KEYWORD` — Choose start-of-battle keyword.
- `CHOOSE_PLAYER_COLOR` — Select a player's UI color during setup (deterministic quantized hue options).
- `SELECT_SETUP_REACTIVE_TARGET` — Choose target for setup-reactive effects.
- `CHOOSE_SETUP_REACTIVE_ACTION` — Choose which setup-reactive action to use.

## Movement & Positioning

- `SELECT_MOVEMENT_ACTION` — Choose move/advance/fall back/remain.
- `MOVE_UNIT` — Choose movement target/path.
- `RESOLVE_COHERENCY` — Resolve unit coherency placement.
- `EMBARK` — Embark unit into transport.
- `DISEMBARK` — Disembark unit from transport.
- `PICK_POINT` — Choose a point on the battlefield.
- `PICK_OBJECTIVE` — Choose an objective marker.
- `SELECT_FLOOR` — Choose a floor/level for placement.

## Shooting & Ranged Attacks

- `SELECT_WEAPON` — Choose weapon/profile to use.
- `DECLARE_SHOTS` — Declare shooting targets.
- `DECLARE_FIRING_DECK` — Select firing deck participants.
- `SELECT_OVERWATCH_SHOOTER` — Choose unit to fire Overwatch.

## Charges

- `DECLARE_CHARGE` — Declare charge targets.

## Fight & Damage Allocation

- `SELECT_FIGHTER` — Choose unit to fight.
- `SELECT_FIGHT_TARGETS` — Choose fight targets.
- `DECLARE_MELEE_WEAPONS` — Select melee weapons/profiles.
- `ALLOCATE_MELEE_TARGETS` — Allocate melee attacks to targets.
- `ALLOCATE_TARGETS` — Allocate attacks to targets (general).
- `SPLIT_ATTACKS` — Split attacks across targets.
- `SELECT_TARGET_MODEL` — Select target model within a unit.
- `SELECT_PRECISION_TARGET` — Select precision target model.
- `ALLOCATE_DAMAGE` — Allocate damage to models.

## Dice & Rerolls

- `REQUEST_DICE_ROLL` — Resolve a dice roll.
- `SELECT_DICE_REROLL` — Select dice to re-roll.
- `REROLL_ROLL` — Reroll a roll (generic).

## Reactive & Special Targeting

- `SELECT_RISE_TO_CHALLENGE` — Choose Rise to Challenge target.
- `DEATHSTRIKE_ACTION` — Choose Deathstrike action/targeting.
- `SELECT_REVERBERATING_SUMMONS_UNIT` — Choose unit for Reverberating Summons.
- `SELECT_EXPLODING_HORRORS_TARGET` — Choose Exploding Horrors target.
- `SELECT_EXPLODING_HORRORS_MODELS` — Choose models for Exploding Horrors.
- `CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET` — Choose post-shoot Battle-shock target.
- `CHOOSE_BATTLESHOCK_CLEAR_TARGET` — Choose a Battle-shocked unit to rally.
- `CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET` — Choose post-shoot mortal wounds target.
- `CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET` — Choose post-shoot Wracked Agonies target.
- `CHOOSE_POST_SHOOT_SUPPRESSION_TARGET` — Choose post-shoot suppression target.
- `SELECT_UNLEASH_HELL_VEHICLE` — Choose Unleash Hell vehicle/transport.
- `CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET` — Choose post-shoot leadership debuff target.
- `CHOOSE_DAEMONIC_POISONS_TARGET` — Choose Daemonic Poisons target.

## Faction / Detachment / Ability Choices

- `CHOOSE_BLESSINGS` — Choose Blessings of Khorne options.
- `CHOOSE_BLOOD_TITHE` — Choose Blood Tithe reward.
- `CHOOSE_IDOL_OF_KHORNE` — Choose Idol of Khorne effect.
- `SELECT_VESSEL_OF_WRATH_MODELS` — Choose Vessel of Wrath models.
- `SELECT_REALM_OF_CHAOS_UNITS` — Choose up to two units for The Realm of Chaos.
- `CHOOSE_IMPOSSIBLE_ECLIPSE_ZONE` — Choose Shadow of Chaos area for Impossible Eclipse.
- `CHOOSE_VESSEL_OF_WRATH_BLESSING` — Choose Vessel of Wrath blessing.
- `CHOOSE_RITUALS` — Choose rituals.
- `CHOOSE_CHIVALRIC_OATH` — Choose Chivalric Oath.
- `CHOOSE_DAEMONIC_ALLEGIANCE` — Choose Daemonic Allegiance.
- `CHOOSE_DARK_PACT` — Choose Dark Pact (Cabal of Chaos options include `empyric_wellspring_choice`).
- `CHOOSE_DOCTRINA` — Choose Doctrina Imperative.
- `CHOOSE_COMBAT_DOCTRINE` — Choose Combat Doctrine.
- `CHOOSE_ANGELIC_LEGACY` — Choose two Angelic Legacy abilities (Angelic Inheritors).
- `CHOOSE_GRAND_COVEN` — Choose Grand Coven option.
- `CHOOSE_COMBAT_DRUGS` — Choose Combat Drugs.
- `CHOOSE_HYPER_ADAPTATION` — Choose Hyper-adaptation.
- `CHOOSE_FRENZY_TARGET` — Choose Frenzy target.
- `CHOOSE_HARBINGER` — Choose Harbinger.
- `USE_GILDED_CHAMPION` — Use Gilded Champion.
- `CHOOSE_MARTIAL_KATAH` — Choose Martial Katah.
- `CHOOSE_PATH_OF_WARRIOR` — Choose Path of the Warrior.
- `CHOOSE_CRUEL_AMUSEMENT` — Choose Cruel Amusement.
- `CHOOSE_MASTER_OF_MAGICKS` — Choose Master of Magicks.
- `CHOOSE_HARBINGER_OF_DEATH` — Choose Harbinger of Death.
- `CHOOSE_DANCE_OF_DEATH` — Choose Dance of Death.
- `CHOOSE_LIMB_FROM_LIMB` — Choose Limb from Limb target.
- `CHOOSE_RED_WRATH` — Choose Red Wrath option.
- `USE_MIRACLE_DIE` — Use Miracle Die.
- `CHOOSE_PLAGUE` — Choose Plague.
- `CHOOSE_PLEDGE` — Choose Pledge.
- `CHOOSE_QUARRY` — Choose Quarry.
- `CHOOSE_HYSTERICAL_FRENZY_PSYKER` — Choose a Psyker for Hysterical Frenzy.
- `CHOOSE_GIFT_OF_CHAOS_TARGET` — Choose Gift of Chaos target unit.
- `CHOOSE_MOMENT_SHACKLE` — Choose Moment Shackle option.
- `CHOOSE_SHADOW_FORM` — Choose Shadow Form.
- `CHOOSE_VOW` — Choose Vow.
- `ISSUE_ORDER` — Issue an Order.
- `CHOOSE_WRATHFUL_PRESENCE` — Choose Wrathful Presence.
- `CHOOSE_DAEMON_PRIMARCH_SLAANESH` — Choose Slaanesh primarch option.
- `CHOOSE_WARMASTER_ABILITY` — Choose The Warmaster ability.
- `USE_CAREEN` — Use Careen!
- `CHOOSE_ASPECT` — Choose Aspect.
- `USE_LEADING_UNMODIFIED_SIX` — Use leading unmodified six.
- `USE_MODEL_UNMODIFIED_SIX` — Use model unmodified six.
- `CHOOSE_HIT_MODIFIER_IGNORES` — Choose hit modifier ignores.
- `CHOOSE_SKILL_MODIFIER_IGNORES` — Choose skill modifier ignores.
- `CHOOSE_MOVE_MODIFIER_IGNORES` — Choose move modifier ignores.
- `CHOOSE_ADVANCE_MODIFIER_IGNORES` — Choose advance modifier ignores.
- `CHOOSE_CHARGE_MODIFIER_IGNORES` — Choose charge modifier ignores.
- `CHOOSE_BATTLE_FOCUS_MANEUVER` — Choose Battle Focus maneuver.
- `CHOOSE_POWER_FROM_PAIN_OPTION` — Choose Power from Pain option.

## Generic Confirmations

- `CONFIRM_MODAL` — Generic modal confirmation.
- `CONFIRM_YES_NO` — Yes/No confirmation.
- `CONFIRM_EXAMPLE` — Test/example confirmation.
