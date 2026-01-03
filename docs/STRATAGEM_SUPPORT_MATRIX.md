# Stratagem support matrix (Wahapedia)

Generated from `wahapedia_data/Stratagems.json` (and faction names from `wahapedia_data/Factions.json`).

**Definition of status**
- **Implemented**: the stratagem has explicit gameplay logic in the engine (beyond CP spend + logging).
- **Partial**: some gameplay logic exists, but key restrictions/timing/text are not fully matched.
- **Not implemented**: no gameplay effect logic wired yet.

## Summary

- Total stratagem rows: 12
- Core (global) stratagem rows (`faction_id == ""`): 12
- Faction stratagem rows: 0 (detachment-specific: 0)
- Excluded (Boarding Actions detachments / mode): 244

## Core Stratagems

### Core

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| COMMAND RE-ROLL | `000008335002` | Core – Battle Tactic Stratagem | 1 | Either player’s turn | Any phase | **Implemented** | Queued on `roll_made`; executes a reroll callback; limited by core once-per-phase stratagem rule (per player). |
| COUNTER-OFFENSIVE | `000008335003` | Core - Strategic Ploy Stratagem | 2 | Either player's turn | Fight phase | **Implemented** | Fight phase: after an enemy unit fights, select a friendly eligible unit to fight next (can override stage). |
| EPIC CHALLENGE | `000008335004` | Core – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Implemented** | Fight phase: when a CHARACTER is selected to fight near an enemy Attached unit; one CHARACTER model’s melee attacks gain [PRECISION] until end of phase. |
| FIRE OVERWATCH | `000008335009` | Core – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Implemented** | Queued on enemy movement start/end; resolves shooting with hit-on-6s restriction. |
| GO TO GROUND | `000008335010` | Core – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Implemented** | Opponent Shooting phase: after targets selected; INFANTRY gains Benefit of Cover + 6++ until end of phase. |
| GRENADE | `000008335006` | Core – Wargear Stratagem | 1 | Your turn | Shooting phase | **Implemented** | Shooting phase: pick a GRENADES unit + eligible enemy within 8"; roll 6D6; 4+ = 1 MW. |
| HEROIC INTERVENTION | `000008335012` | Core – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Implemented** | Queued after an enemy Charge move ends; selects a friendly unit within 6" (non-WALKER VEHICLEs excluded), resolves a charge without the charge bonus. |
| INSANE BRAVERY | `000008335005` | Core – Epic Deed Stratagem | 1 | Your turn | Command phase | **Implemented** | Command phase Battle-shock step: before a unit tests; that unit auto-passes. Once per battle enforced. |
| NEW ORDERS | `000010245002` | Core Stratagem – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Implemented** | End of your Command phase: discard 1 active Secondary and draw. |
| RAPID INGRESS | `000008335008` | Core – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Implemented** | Queued at end of opponent Movement phase; places a reserves unit immediately. |
| SMOKESCREEN | `000008335011` | Core – Wargear Stratagem | 1 | Opponent’s turn | Shooting phase | **Implemented** | Opponent Shooting phase: after targets selected; a SMOKE unit gains Benefit of Cover + Stealth until end of phase. |
| TANK SHOCK | `000008335007` | Core – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Implemented** | Charge phase: after a VEHICLE ends a Charge move; roll D6 equal to a VEHICLE model’s Toughness; 5+ = 1 MW (max 6). |

<!-- Chapter Approved scope: faction/detachment stratagems intentionally omitted -->
