# Decision Types Catalog (Partial)

Status: Draft (partial list; see `src/warhammer40k_ai/engine/decision_kinds.py` for the authoritative set).

This catalog is a quick reference for engine decision types emitted by the rules engine.
Each decision is represented as a `DecisionRequest` with `candidates[]` and `mask[]`.

## Setup & Mission

- `CHOOSE_MISSION` — Select mission combination and layout.
- `DECLARE_RESERVES` — Confirm reserves allocation.
- `ATTACH_LEADER` — Attach a leader to a bodyguard (or keep unattached).
- `ASSIGN_TRANSPORT` — Assign a transport to a unit (or none).

## Movement & Positioning

- `SELECT_MOVEMENT_ACTION` — Choose move/advance/fall back/remain.
- `MOVE_UNIT` — Provide movement target or path.
- `SCOUT_MOVE` — Pre-game scout move.
- `RESOLVE_COHERENCY` — Resolve unit coherency positioning.
- `EMBARK` / `DISEMBARK` — Embark/disembark from a transport.
- `PICK_POINT` / `PICK_OBJECTIVE` — Generic point/objective selections.

## Shooting & Attacks

- `SELECT_WEAPON` — Choose weapon or profile.
- `DECLARE_SHOTS` — Declare shooting targets.
- `DECLARE_FIRING_DECK` — Select firing deck participants.
- `SELECT_OVERWATCH_SHOOTER` — Choose unit to fire Overwatch.

## Charges & Fight

- `DECLARE_CHARGE` — Declare charge targets.
- `SELECT_FIGHTER` — Choose unit to fight.
- `SELECT_FIGHT_TARGETS` — Choose fight targets.
- `DECLARE_MELEE_WEAPONS` — Select melee weapons or profiles.
- `ALLOCATE_MELEE_TARGETS` / `ALLOCATE_TARGETS` / `SPLIT_ATTACKS` — Allocate attacks and split fire.
- `SELECT_TARGET_MODEL` / `SELECT_PRECISION_TARGET` — Choose specific target models.
- `ALLOCATE_DAMAGE` — Allocate damage to models.

## Dice & Rerolls

- `REQUEST_DICE_ROLL` — Resolve a dice roll.
- `SELECT_DICE_REROLL` — Select dice to re-roll (if available).

## Faction / Detachment / Ability Choices

- `CHOOSE_BLESSINGS`, `CHOOSE_BLOOD_TITHE`, `CHOOSE_RITUALS`, `CHOOSE_PLAGUE`
- `CHOOSE_CHIVALRIC_OATH`, `CHOOSE_DARK_PACT`, `CHOOSE_DOCTRINA`
- `CHOOSE_COMBAT_DOCTRINE`, `CHOOSE_COMBAT_DRUGS`, `CHOOSE_HYPER_ADAPTATION`
- `CHOOSE_VOW`, `CHOOSE_ASPECT`, `CHOOSE_SHADOW_FORM`

## Generic Confirmations

- `CONFIRM_YES_NO` — Yes/No confirmation.
- `CONFIRM_EXAMPLE` — Test/example confirmation.

## Notes

- This list is intentionally incomplete. Always reference `src/warhammer40k_ai/engine/decision_kinds.py`.
- For UI mapping, see `docs/NETWORK_SAVELOAD_DESIGN.md`.
