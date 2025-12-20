# Stratagem support matrix (Wahapedia)

Generated from `wahapedia_data/Stratagems.json` (and faction names from `wahapedia_data/Factions.json`).

**Definition of status**
- **Implemented**: the stratagem has explicit gameplay logic in the engine (beyond CP spend + logging).
- **Partial**: some gameplay logic exists, but key restrictions/timing/text are not fully matched.
- **Not implemented**: no gameplay effect logic wired yet.
- **Not supported**: currently excluded by game-mode filtering (e.g. Boarding Actions).

## Summary

- Total stratagem rows: 1119
- Core (global) stratagem rows (`faction_id == ""`): 19
- Faction stratagem rows: 1100 (detachment-specific: 1100)

## Core Stratagems

> Note: Boarding Actions (and similar mode-specific) stratagems are present in Wahapedia data, but are not used in standard games by this engine today.

### Boarding Actions

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BATTLEFIELD COMMAND | `000009218003` | Boarding Actions – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not supported** | Boarding Actions are filtered out by `StratagemManager._build_available()`. |
| COMMAND RE-ROLL | `000009218002` | Boarding Actions – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not supported** | Boarding Actions are filtered out by `StratagemManager._build_available()`. |
| COUNTER-OFFENSIVE | `000009218004` | Boarding Actions – Strategic Ploy Stratagem | 2 | Either player’s turn | Fight phase | **Not supported** | Boarding Actions are filtered out by `StratagemManager._build_available()`. |
| EXPLOSIVE CLEARANCE | `000009218006` | Boarding Actions – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not supported** | Boarding Actions are filtered out by `StratagemManager._build_available()`. |
| INSANE BRAVERY | `000009218005` | Boarding Actions – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not supported** | Boarding Actions are filtered out by `StratagemManager._build_available()`. |

### Core

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| COMMAND RE-ROLL | `000008335002` | Core – Battle Tactic Stratagem | 1 | Either player’s turn | Any phase | **Implemented** | Queued on `roll_made`; executes a reroll callback; once-per-turn guard. |
| COUNTER-OFFENSIVE | `000008335003` | Core – Strategic Ploy Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EPIC CHALLENGE | `000008335004` | Core – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FIRE OVERWATCH | `000008335009` | Core – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Implemented** | Queued on enemy movement start/end; resolves shooting with hit-on-6s restriction. |
| GO TO GROUND | `000008335010` | Core – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GRENADE | `000008335006` | Core – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HEROIC INTERVENTION | `000008335012` | Core – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSANE BRAVERY | `000008335005` | Core – Epic Deed Stratagem | 1 | Your turn | Command phase | **Partial** | Implemented as a post-fail Battle-shock cancel (removes Battle-shock). Once-per-battle restriction not enforced; differs from datasheet timing. |
| RAPID INGRESS | `000008335008` | Core – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Implemented** | Queued at end of opponent Movement phase; places a reserves unit immediately. |
| SMOKESCREEN | `000008335011` | Core – Wargear Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TANK SHOCK | `000008335007` | Core – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Core Stratagem

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| NEW ORDERS | `000008539002` | Core Stratagem – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Implemented** | End of your Command phase: discard 1 active Secondary and draw (Leviathan-style). |
| NEW ORDERS | `000009063002` | Core Stratagem – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Implemented** | End of your Command phase: discard 1 active Secondary and draw (Leviathan-style). |
| NEW ORDERS | `000010245002` | Core Stratagem – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Implemented** | End of your Command phase: discard 1 active Secondary and draw (Leviathan-style). |

## Faction Stratagems

### Adepta Sororitas (`AS`) — `https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas`

#### Army of Faith

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ANGELIC DESCENT | `000009038007` | Army of Faith – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BLINDING RADIANCE | `000009038005` | Army of Faith – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DIVINE GUIDANCE | `000009038006` | Army of Faith – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FAITH AND FURY | `000009038004` | Army of Faith – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LIGHT OF THE EMPEROR | `000009038003` | Army of Faith – Battle Tactic Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHIELD OF FAITH | `000009038002` | Army of Faith – Battle Tactic Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Bringers of Flame

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLAZING IRE | `000009034007` | Bringers of Flame – Battle Tactic Stratagem | 2 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CARRY FORTH THE FAITHFUL | `000009034004` | Bringers of Flame – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CLEANSING FLAMES | `000009034005` | Bringers of Flame – Battle Tactic Stratagem | 2 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RIGHTEOUS BLOWS | `000009034003` | Bringers of Flame – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RITES OF FIRE | `000009034006` | Bringers of Flame – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHIELD OF AVERSION | `000009034002` | Bringers of Flame – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Champions of Faith

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BASTION OF FAITH | `000009832006` | Champions of Faith – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INDEFATIGABLE DEDICATION | `000009832007` | Champions of Faith – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PATH OF THE RIGHTEOUS | `000009832005` | Champions of Faith – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHIELD OF DENIAL | `000009832002` | Champions of Faith – Battle Tactic Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUFFER NOT THE UNFAITHFUL | `000009832003` | Champions of Faith – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TO THE HEART OF HERESY | `000009832004` | Champions of Faith – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Hallowed Martyrs

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DIVINE INTERVENTION | `000008469002` | Hallowed Martyrs – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRAISE THE FALLEN | `000008469007` | Hallowed Martyrs – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RIGHTEOUS VENGEANCE | `000008469004` | Hallowed Martyrs – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SANCTIFIED IMMOLATION | `000008469005` | Hallowed Martyrs – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SPIRIT OF THE MARTYR | `000008469006` | Hallowed Martyrs – Strategic Ploy Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUFFERING AND SACRIFICE | `000008469003` | Hallowed Martyrs – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Penitent Host

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BOUNDLESS ZEAL | `000009030006` | Penitent Host – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEVOUT FANATICISM | `000009030007` | Penitent Host – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FINAL REDEMPTION | `000009030002` | Penitent Host – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LASH OF GUILT | `000009030005` | Penitent Host – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PASSION OF THE PENITENT | `000009030004` | Penitent Host – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PURITY OF SUFFERING | `000009030003` | Penitent Host – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Penitents and Pilgrims

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CONTEMPT FOR DEATH | `000009317003` | Penitents and Pilgrims – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FEVERED ZEALOTS | `000009317004` | Penitents and Pilgrims – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SAVAGE FRENZY | `000009317005` | Penitents and Pilgrims – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SLICK WITH GORE | `000009317002` | Penitents and Pilgrims – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Pious Protectors

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| FINAL TESTAMENT | `000009309002` | Pious Protectors – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRAYER OF PRECISION | `000009309003` | Pious Protectors – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RADIANT ILLUMINATION | `000009309005` | Pious Protectors – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REPEL BOARDERS | `000009309004` | Pious Protectors – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Adeptus Custodes (`AC`) — `https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes`

#### Auric Champions

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| EARNING OF A NAME | `000008931005` | Auric Champions – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHOULDER THE MANTLE | `000008931007` | Auric Champions – Epic Deed Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SLAYER OF CHAMPIONS | `000008931002` | Auric Champions – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUPERHUMAN RESERVES | `000008931003` | Auric Champions – Epic Deed Stratagem | 2 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE EMPEROR’S AUSPICE | `000008931004` | Auric Champions – Epic Deed Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VIGIL UNENDING | `000008931006` | Auric Champions – Epic Deed Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Black Ship Guardians

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLADES OF THE VIGILATORS | `000009274002` | Black Ship Guardians – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CORNERED PREY | `000009274004` | Black Ship Guardians – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FOCUSED FEAR | `000009274003` | Black Ship Guardians – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PUNISHMENT OF THE PROSECUTORS | `000009274005` | Black Ship Guardians – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Lions of the Emperor

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DEFIANT TO THE LAST | `000009988003` | Lions of the Emperor – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GILDED CHAMPION | `000009988002` | Lions of the Emperor – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MANOEUVRE AND FIRE | `000009988006` | Lions of the Emperor – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PEERLESS WARRIOR | `000009988004` | Lions of the Emperor – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWIFT AS THE EAGLE | `000009988007` | Lions of the Emperor – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNLEASH THE LIONS | `000009988005` | Lions of the Emperor – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Null Maiden Vigil

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ANATHEMA BLADEMASTERY | `000008927004` | Null Maiden Vigil – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DESPERATION’S PRICE | `000008927002` | Null Maiden Vigil – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PSY-CHAFF VOLLEY | `000008927005` | Null Maiden Vigil – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PSYCHIC ABOMINATIONS | `000008927007` | Null Maiden Vigil – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PURGATION SWEEP | `000008927006` | Null Maiden Vigil – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WITCH HUNTERS | `000008927003` | Null Maiden Vigil – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Shield Host

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARCANE GENETIC ALCHEMY | `000008394002` | Shield Host – Battle Tactic Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ARCHEOTECH MUNITIONS | `000008394007` | Shield Host  – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| AVENGE THE FALLEN | `000008394003` | Shield Host – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MULTIPOTENTIALITY | `000008394005` | Shield Host – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNWAVERING SENTINELS | `000008394004` | Shield Host – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VIGILANCE ETERNAL | `000008394006` | Shield Host – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Solar Spearhead

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| EMPEROR’S VENGEANCE | `000009754003` | Solar Spearhead – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FLAWLESS CONSTRUCTION | `000009754002` | Solar Spearhead – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PUNISHMENT INESCAPABLE | `000009754007` | Solar Spearhead – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELENTLESS PERSECUTION | `000009754006` | Solar Spearhead – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNSTOPPABLE | `000009754005` | Solar Spearhead – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WRATHFUL ADVANCE | `000009754004` | Solar Spearhead – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Talons Of The Emperor

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| EMPEROR’S EXECUTIONERS | `000008922005` | Talons Of The Emperor – Battle Tactic Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EMPYRIC SEVERANCE | `000008922004` | Talons Of The Emperor – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HUNT AS ONE | `000008922002` | Talons Of The Emperor – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHIELD OF HONOUR | `000008922007` | Talons Of The Emperor – Epic Deed Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TALONED PINCER | `000008922006` | Talons Of The Emperor – Battle Tactic Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TALONS INTERLOCKED | `000008922003` | Talons Of The Emperor – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Voyagers in Darkness

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARTIFICER ROUNDS | `000009265004` | Voyagers in Darkness – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| AURIC STORM | `000009265005` | Voyagers in Darkness – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BREACHING BEHEMOTHS | `000009265003` | Voyagers in Darkness – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INESCAPABLE VENGEANCE | `000009265002` | Voyagers in Darkness – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Adeptus Mechanicus (`AdM`) — `https://wahapedia.ru/wh40k10ed/factions/adeptus-mechanicus`

#### Cohort Cybernetica

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AUTO-DIVINATORY TARGETING | `000008573003` | Cohort Cybernetica – Battle Tactic Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BENEVOLENCE OF THE OMNISSIAH | `000008573007` | Cohort Cybernetica – Battle Tactic Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MACHINE SPIRIT RESURGENT | `000008573004` | Cohort Cybernetica – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MACHINE SUPERIORITY | `000008573005` | Cohort Cybernetica – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MOTIVE IMPERATIVE | `000008573002` | Cohort Cybernetica – Battle Tactic Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TRANSCENDENT COGITATION | `000008573006` | Cohort Cybernetica – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Data-Psalm Conclave

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CHANT OF THE REMORSELESS FIST | `000008565003` | Data-Psalm Conclave – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INCANTATION OF THE IRON SOUL | `000008565002` | Data-Psalm Conclave – Battle Tactic Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LITANY OF THE ELECTROMANCER | `000008565006` | Data-Psalm Conclave – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LUMINESCENT BLESSING | `000008565007` | Data-Psalm Conclave – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TRIBUTE OF EMPHATIC VENERATION | `000008565005` | Data-Psalm Conclave – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VERSE OF VENGEANCE | `000008565004` | Data-Psalm Conclave – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Electromartyrs

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AUTO-VENGEANCE | `000009282002` | Electromartyrs – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BALLISTIC SYNCHRONY | `000009282003` | Electromartyrs – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OMNI-TARGETERS | `000009282004` | Electromartyrs – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SAVIOUR SYSTEMS | `000009282005` | Electromartyrs – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Explorator Maniple

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AUTO-ORACULAR RETRIEVAL | `000008569005` | Explorator Maniple – Battle Tactic Stratagem | 2 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CACHED ACQUISITION | `000008569002` | Explorator Maniple – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INCENSE EXHAUSTS | `000008569006` | Explorator Maniple – Wargear Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INFOSLAVE SKULL | `000008569004` | Explorator Maniple – Wargear Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRIORITY RECLAMATION | `000008569003` | Explorator Maniple – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REACTIVE SAFEGUARD | `000008569007` | Explorator Maniple – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Haloscreed Battle Clade

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AGGRESSIVE IMPULSE | `000009746005` | Haloscreed Battle Clade – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ANALYTICAL DIVINATION | `000009746007` | Haloscreed Battle Clade – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ERADICATION PROTOCOLS | `000009746002` | Haloscreed Battle Clade – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GUIDED RETREAT | `000009746006` | Haloscreed Battle Clade – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NEURAL OVERLOAD | `000009746004` | Haloscreed Battle Clade – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TARGETING OVERRIDE | `000009746003` | Haloscreed Battle Clade – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Machine Cult

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ELECTROGHEIST VISITATIONS | `000009299002` | Machine Cult – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OMNISSIAH’S GUIDANCE | `000009299003` | Machine Cult – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| POWER OF THE MOTIVE FORCE | `000009299004` | Machine Cult – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TETHER-TENDRILS | `000009299005` | Machine Cult – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Rad-Zone Corps

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AGGRESSOR IMPERATIVE | `000008386004` | Rad-Zone Corps – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BALEFUL HALO | `000008386002` | Rad-Zone Corps – Battle Tactic Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BULWARK IMPERATIVE | `000008386007` | Rad-Zone Corps – Battle Tactic Stratagem | 2 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EXTINCTION ORDER | `000008386003` | Rad-Zone Corps – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LETHAL DOSAGE | `000008386006` | Rad-Zone Corps – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRE-CALIBRATED PURGE SOLUTION | `000008386005` | Rad-Zone Corps – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Response Clade

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ACCESS OVERRIDES | `000009291003` | Response Clade – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INTEGRATIVE WITHDRAWAL | `000009291005` | Response Clade – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRECOGNITATED FIREFIELDS | `000009291004` | Response Clade – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RESPONSIVE SHIELDING | `000009291002` | Response Clade – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Skitarii Hunter Cohort

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BINHARIC OFFENCE | `000008561003` | Skitarii Hunter Cohort – Strategic Ploy Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BIONIC ENDURANCE | `000008561002` | Skitarii Hunter Cohort – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EXPEDITED PURGE PROTOCOL | `000008561004` | Skitarii Hunter Cohort – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ISOLATE AND DESTROY | `000008561005` | Skitarii Hunter Cohort – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PROGRAMMED WITHDRAWAL | `000008561007` | Skitarii Hunter Cohort – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHROUD PROTOCOLS | `000008561006` | Skitarii Hunter Cohort – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Aeldari (`AE`) — `https://wahapedia.ru/wh40k10ed/factions/aeldari`

#### Armoured Warhost

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ANTI‑GRAV REPULSION | `000009770007` | Armoured Warhost – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CLOUDSTRIKE | `000009770005` | Armoured Warhost – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LAYERED WARDS | `000009770002` | Armoured Warhost – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SOULSIGHT | `000009770006` | Armoured Warhost – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWIFT DEPLOYMENT | `000009770003` | Armoured Warhost – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VECTORED ENGINES | `000009770004` | Armoured Warhost – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Army Rules

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| FADE BACK | `000009895007` |  |  |  | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FLITTING SHADOWS | `000009895003` |  |  |  | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OPPORTUNITY SEIZED | `000009895006` |  |  |  | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STAR ENGINES | `000009895004` |  |  |  | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUDDEN STRIKE | `000009895005` |  |  |  | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWIFT AS THE WIND | `000009895002` |  |  |  | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Aspect Host

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DOOM INESCAPABLE | `000009928005` | Aspect Host – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| KHAINE’S VENGEANCE | `000009928007` | Aspect Host – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRETERNATURAL PRECISION | `000009928006` | Aspect Host – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SKYBORNE SANCTUARY | `000009928004` | Aspect Host – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TO THEIR FINAL BREATH | `000009928003` | Aspect Host – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WARRIOR FOCUS | `000009928002` | Aspect Host – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Devoted of Ynnead

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DEATH ANSWERS DEATH | `000009920007` | Devoted of Ynnead – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EMISSARIES OF YNNEAD | `000009920004` | Devoted of Ynnead – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MACABRE RESILIENCE | `000009920003` | Devoted of Ynnead – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PALL OF DREAD | `000009920002` | Devoted of Ynnead – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PARTING THE VEIL | `000009920005` | Devoted of Ynnead – Strategic Ploy Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SOULSIGHT | `000009920006` | Devoted of Ynnead – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Ghosts of the Webway

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLOODY DANCE | `000009916006` | Ghosts of the Webway – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EXIT THE STAGE | `000009916007` | Ghosts of the Webway – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HEROES’ FALL | `000009916003` | Ghosts of the Webway – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MOCKING FLIGHT | `000009916004` | Ghosts of the Webway – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STAGED DEATH | `000009916002` | Ghosts of the Webway – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TRICKSTERS’ RETORT | `000009916005` | Ghosts of the Webway – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Guardian Battlehost

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLADES OF ASURYAN | `000009912006` | Guardian Battlehost – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| COST OF VICTORY | `000009912007` | Guardian Battlehost – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHIELD NODES | `000009912003` | Guardian Battlehost – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TIME TO STRIKE | `000009912005` | Guardian Battlehost – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VAUL’S VENGEANCE | `000009912004` | Guardian Battlehost – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WARDING SALVOES | `000009912002` | Guardian Battlehost – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Khaine’s Arrow

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARTIFICER ROUNDS | `000009326004` | Khaine’s Arrow – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| AURIC STORM | `000009326005` | Khaine’s Arrow – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BLADEFOCUS | `000009326003` | Khaine’s Arrow – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VOID GHOSTS | `000009326002` | Khaine’s Arrow – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Protector Host

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| RAPID AMBUSH | `000009335005` | Protector Host – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHIELD OF BLADES | `000009335004` | Protector Host – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHURIKEN STORM | `000009335003` | Protector Host – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VOID GHOSTS | `000009335002` | Protector Host – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Seer Council

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| FATE INESCAPABLE | `000009924005` | Seer Council – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FOREWARNED | `000009924003` | Seer Council – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ISHA’S FURY | `000009924006` | Seer Council – Epic Deed Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRESENTIMENT OF DREAD | `000009924002` | Seer Council – Strategic Ploy Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PSYCHIC SHIELD | `000009924007` | Seer Council – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNSHROUDED TRUTH | `000009924004` | Seer Council – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Spirit Conclave

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLADES FROM BEYOND | `000009908004` | Spirit Conclave – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CRUSHING STRIDES | `000009908007` | Spirit Conclave – Battle Tactic Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SEER’S EYE | `000009908002` | Spirit Conclave – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SOUL BRIDGE | `000009908005` | Spirit Conclave – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SPIRIT TOKEN | `000009908006` | Spirit Conclave – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WRAITHBONE ARMOUR | `000009908003` | Spirit Conclave – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Star-dancer Masque

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ACROBATIC LEAPS | `000009352005` | Star-dancer Masque – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DARTING STRIKES | `000009352003` | Star-dancer Masque – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SERPENT STRIKE | `000009352004` | Star-dancer Masque – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VOID GHOSTS | `000009352002` | Star-dancer Masque – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Warhost

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLITZING FIREPOWER | `000009900005` | Warhost – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FEIGNED RETREAT | `000009900004` | Warhost – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FIRE AND FADE | `000009900006` | Warhost – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LIGHTNING-FAST REACTIONS | `000009900002` | Warhost – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SKYBORNE SANCTUARY | `000009900003` | Warhost – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WEBWAY TUNNEL | `000009900007` | Warhost – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Windrider Host

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DARING RIDERS | `000009904005` | Windrider Host – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEATH FROM ON HIGH | `000009904002` | Windrider Host – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FOCUSED FIREPOWER | `000009904006` | Windrider Host – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OVERFLIGHT | `000009904003` | Windrider Host – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SPIRALLING EVASION | `000009904007` | Windrider Host – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WIND OF BLADES | `000009904004` | Windrider Host – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Wraiths of the Void

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| D-STRIKE | `000009343004` | Wraiths of the Void – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GUARDIAN CONSTRUCTS | `000009343002` | Wraiths of the Void – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNFLINCHING FIRE | `000009343005` | Wraiths of the Void – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WRAITHSIGHT | `000009343003` | Wraiths of the Void – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Astra Militarum (`AM`) — `https://wahapedia.ru/wh40k10ed/factions/astra-militarum`

#### Bridgehead Strike

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AERIAL EXTRACTION | `000009802006` | Bridgehead Strike – Epic Deed Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BELLICOSA DROP | `000009802002` | Bridgehead Strike – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FIRE AND RELOCATE | `000009802004` | Bridgehead Strike – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FIRING HOT | `000009802003` | Bridgehead Strike – Battle Tactic Stratagem | 2 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ON MY POSITION | `000009802007` | Bridgehead Strike – Epic Deed Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SERVO‑DESIGNATORS | `000009802005` | Bridgehead Strike – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Combined Arms

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| COORDINATED ACTION | `000008381002` | Combined Arms – Battle Tactic Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FIELDS OF FIRE | `000008381005` | Combined Arms – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FLEXIBLE COMMAND | `000008381004` | Combined Arms – Strategic Ploy Stratagem | 2 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSPIRED COMMAND | `000008381006` | Combined Arms – Epic Deed Stratagem | 1 | Opponent’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REINFORCEMENTS! | `000008381003` | Combined Arms – Strategic Ploy Stratagem | 2 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STALWART PROTECTOR | `000008381007` | Combined Arms – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Embarked Regiment

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AGAINST THE ODDS | `000009381002` | Embarked Regiment – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BRUTAL CHOKE POINT | `000009381005` | Embarked Regiment – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DUCK AND COVER | `000009381003` | Embarked Regiment – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IDLE HANDS | `000009381004` | Embarked Regiment – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Hammer of the Emperor

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ABLATIVE PLATING | `000009866007` | Hammer of the Emperor – Wargear Stratagem | 2 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BLAZING ADVANCE | `000009866003` | Hammer of the Emperor – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CRASH THROUGH | `000009866005` | Hammer of the Emperor – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FINAL HOUR | `000009866002` | Hammer of the Emperor – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FURIOUS CANNONADE | `000009866006` | Hammer of the Emperor – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TACTICAL WITHDRAWAL | `000009866004` | Hammer of the Emperor – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Mechanised Assault

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CLEAR AND SECURE | `000009862004` | Mechanised Assault – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HASTY EXTRACTION | `000009862006` | Mechanised Assault – Battle Tactic Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MOVE OUT | `000009862007` | Mechanised Assault – Strategic Ploy Stratagem | 1 | Opponent’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RAPID DISPERSAL | `000009862003` | Mechanised Assault – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWIFT INTERCEPTION | `000009862005` | Mechanised Assault – Battle Tactic Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VOX-RELAY | `000009862002` | Mechanised Assault – Wargear Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Recon Element

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| COURAGEOUS DIVERSION | `000009870005` | Recon Element – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CRACK SHOTS | `000009870002` | Recon Element – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DRAW THEM OUT | `000009870003` | Recon Element – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SCOUTING OUTRIDERS | `000009870007` | Hammer of the Emperor – Battle Tactic Stratagem | 1 | Opponent’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SCRAMBLE FIELD | `000009870004` | Recon Element – Wargear Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TANGLEFOOT GRENADES | `000009870006` | Recon Element – Wargear Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Siege Regiment

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CALLOUS SACRIFICE | `000009858005` | Siege Regiment – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FLARE BURST | `000009858004` | Siege Regiment – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FURIOUS FUSILLADE | `000009858006` | Siege Regiment – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MINEFIELD | `000009858007` | Siege Regiment – Wargear Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OVER THE TOP | `000009858003` | Siege Regiment – Strategic Ploy Stratagem | 2 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TRENCH FIGHTERS | `000009858002` | Siege Regiment – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Tempestus Boarding Regiment

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AGAINST THE ODDS | `000009390002` | Tempestus Boarding Regiment – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BRUTAL CHOKE POINT | `000009390005` | Tempestus Boarding Regiment – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DUCK AND COVER | `000009390003` | Tempestus Boarding Regiment – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IDLE HANDS | `000009390004` | Tempestus Boarding Regiment – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Chaos Daemons (`CD`) — `https://wahapedia.ru/wh40k10ed/factions/chaos-daemons`

#### Blood Legion

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLOOD BEGETS SKULLS | `000009816005` | Blood Legion – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FOOLS’ FLIGHT | `000009816006` | Blood Legion – Strategic Ploy Stratagem | 2 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GORE‑HUNGRY ONSLAUGHT | `000009816003` | Blood Legion – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHEATHED IN BRASS | `000009816007` | Blood Legion – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SKULLS BEGET BLOOD | `000009816004` | Blood Legion – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WRATH UNDENIABLE | `000009816002` | Blood Legion – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Daemonic Incursion

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CORRUPT REALSPACE | `000008437002` | Demonic Incursion – Strategic Ploy Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DAEMONIC INVULNERABILITY | `000008437007` | Demonic Incursion – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DENIZENS OF THE WARP | `000008437005` | Demonic Incursion – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DRAUGHT OF TERROR | `000008437004` | Demonic Incursion – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INCORPOREAL TERRORS | `000009548005` | Daemonic Incursion – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSUBSTANTIAL ENTITIES | `000009548004` | Daemonic Incursion – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PARTING BLOWS | `000009548002` | Daemonic Incursion – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE REALM OF CHAOS | `000008437006` | Demonic Incursion – Battle Tactic Stratagem | 1 | Opponent’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNREAL SPEED | `000009548003` | Daemonic Incursion – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WARP SURGE | `000008437003` | Demonic Incursion – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Dread Carnival

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DANCE OF DEATH | `000009573004` | Dread Carnival – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSUBSTANTIAL ENTITIES | `000009573005` | Dread Carnival – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SEDUCTIVE WHISPERS | `000009573002` | Dread Carnival – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SOPORIFIC SCENT | `000009573003` | Dread Carnival – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Infernal Onslaught

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ABJECT HORROR | `000009556003` | Infernal Onslaught – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSUBSTANTIAL ENTITIES | `000009556004` | Infernal Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWIFT AS MURDER | `000009556005` | Infernal Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNSTOPPABLE SLAUGHTERERS | `000009556002` | Infernal Onslaught – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Legion of Excess

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARCHAGONISTS | `000009807003` | Legion of Excess – Battle Tactic Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CAVALCADE OF BLADES | `000009807006` | Legion of Excess – Battle Tactic Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OVERWHELMING EXCESS | `000009807007` | Legion of Excess – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PHANTASMAL LONGING | `000009807005` | Legion of Excess – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SENSORY EXCRUCIATION | `000009807004` | Legion of Excess – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THIEVES OF PAIN | `000009807002` | Legion of Excess – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Pandaemoniac Inferno

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| FATE SYPHONING | `000009581002` | Pandaemoniac Inferno – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FICKLE BLESSINGS | `000009581003` | Pandaemoniac Inferno – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ILLUSORY PRESENCE | `000009581004` | Pandaemoniac Inferno – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSUBSTANTIAL ENTITIES | `000009581005` | Pandaemoniac Inferno – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Plague Legion

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| FEVER VISIONS | `000009820003` | Plague Legion – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FOETID RESURGENCE | `000009820004` | Plague Legion – Strategic Ploy Stratagem | 2 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MURKSHADOWS | `000009820006` | Plague Legion – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PLAGUE OF WOES | `000009820007` | Plague Legion – Strategic Ploy Stratagem | 1 | Opponent’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ROT AND RENEWAL | `000009820005` | Plague Legion – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SEEPING VIRULENCE | `000009820002` | Plague Legion – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Rotten and Rusted

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| FOUL RESILIENCE | `000009565002` | Rotten and Rusted – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GLEEFUL INVASION | `000009565004` | Rotten and Rusted – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSUBSTANTIAL ENTITIES | `000009565005` | Rotten and Rusted – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SICKLY CONTAMINANTS | `000009565003` | Rotten and Rusted – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Scintillating Legion

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DELIRIUM UNMADE | `000009811007` | Scintillating Legion – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FATEBORNE NIGHTMARES | `000009811005` | Scintillating Legion – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FICKLEFIRE | `000009811006` | Scintillating Legion – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FLICKERING REALITY | `000009811004` | Scintillating Legion – Strategic Ploy Stratagem | 1 | Either player’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IMPOSSIBLE ECLIPSE | `000009811002` | Scintillating Legion – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PYROGENESIS | `000009811003` | Scintillating Legion – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Shadow Legion

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BINDING SHADOW | `000009979007` | Shadow Legion – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CHANNELLED WRATH | `000009979003` | Shadow Legion – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEATH DENIED | `000009979004` | Shadow Legion – Battle Tactic Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENCROACHING DARKNESS | `000009979005` | Shadow Legion – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHADE PATH | `000009979006` | Shadow Legion – Battle Tactic Stratagem | 2 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SPITEFUL DEMISE | `000009979002` | Shadow Legion – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Chaos Knights (`QT`) — `https://wahapedia.ru/wh40k10ed/factions/chaos-knights`

#### Iconoclast Fiefdom

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AVENGE THE MASTERS! | `000009766002` | Iconoclast Fiefdom – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRESERVE THE IDOLS | `000009766007` | Iconoclast Fiefdom – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SOUL HUNGER | `000009766004` | Iconoclast Fiefdom – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNRESTRAINED RAGE | `000009766005` | Iconoclast Fiefdom – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WORTHLESS CHATTEL | `000009766006` | Iconoclast Fiefdom – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WRETCHED MASSES | `000009766003` | Iconoclast Fiefdom – Battle Tactic Stratagem | 2 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Traitoris Lance

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| A LONG LEASH | `000008517005` | Traitoris Lance – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DIABOLIC BULWARK | `000008517007` | Traitoris Lance – Wargear Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DISDAIN FOR THE WEAK | `000008517003` | Traitoris Lance – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DREAD HOUNDS | `000008517002` | Traitoris Lance – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| KNIGHTS OF SHADE | `000008517006` | Traitoris Lance – Epic Deed Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PTERRORSHADES | `000008517004` | Traitoris Lance – Wargear Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Chaos Space Marines (`CSM`) — `https://wahapedia.ru/wh40k10ed/factions/chaos-space-marines`

#### Cabal of Chaos

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BALEFUL BLESSING | `000010152002` | Cabal of Chaos – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MUTATION’S CURSE | `000010152004` | Cabal of Chaos – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NO REST IN DEATH | `000010152003` | Cabal of Chaos – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHROUD OF CHAOS | `000010152007` | Cabal of Chaos – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SOULSEEKERS | `000010152005` | Cabal of Chaos – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNHOLY HASTE | `000010152006` | Cabal of Chaos – Epic Deed Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Champions of Chaos

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AGGRESSIVE STRIKE | `000009521005` | Champions of Chaos – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IMPERIOUS ADVANCE | `000009521002` | Champions of Chaos – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INFERNAL PATRONS | `000009521004` | Champions of Chaos – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MALIGN WILL | `000009521003` | Champions of Chaos – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Chaos Cult

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CHOSEN FOR GLORY | `000008982002` | Chaos Cult – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CRAZED FOCUS | `000008982005` | Chaos Cult – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INFERNAL SACRIFICE | `000008982004` | Chaos Cult – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MORTAL THRALLS | `000008982007` | Chaos Cult – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RECKLESS HASTE | `000008982006` | Chaos Cult – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SELFLESS DEMISE | `000008982003` | Chaos Cult – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Creations of Bile

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AUTOSTIMULANTS | `000009774007` | Creations of Bile – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DELAYED MUTATIONS | `000009774005` | Creations of Bile – Strategic Ploy Stratagem | 2 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DIABOLIC REGENERATION | `000009774006` | Creations of Bile – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MASTERS ARE WATCHING | `000009774003` | Creations of Bile – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MONSTROUS VISAGES | `000009774002` | Creations of Bile – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SPECIMENS FOR THE SPIDER | `000009774004` | Creations of Bile – Strategic Ploy Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Deceptors

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| COILS OF DECEPTION | `000008965005` | Deceptors – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DETONATOR | `000008965002` | Deceptors – Wargear Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FROM ALL SIDES | `000008965003` | Deceptors – Battle Tactic Stratagem | 1 | Either player’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PICK THEM OFF | `000008965004` | Deceptors – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELENTLESS PURSUIT | `000008965006` | Deceptors – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SCRAMBLED COORDINATES | `000008965007` | Deceptors – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Dread Talons

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLOODY EXAMPLE | `000008973003` | Dread Talons – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEPTHLESS CRUELTY | `000008973002` | Dread Talons – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MERCILESS PURSUIT | `000008973007` | Dread Talons – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PITILESS HUNTERS | `000008973004` | Dread Talons – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELENTLESS TERROR | `000008973005` | Dread Talons – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SCREAMING DESCENT | `000008973006` | Dread Talons – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Fellhammer Siege-host

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BRUTAL ATTRITION | `000008977003` | Fellhammer Siege-Host – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PERSISTENT ASSAILANTS | `000008977002` | Fellhammer Siege-Host – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PITILESS CANNONADE | `000008977004` | Fellhammer Siege-Host – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| POINT-BLANK DESTRUCTION | `000008977005` | Fellhammer Siege-Host – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SIEGECRAFT | `000008977007` | Fellhammer Siege-Host – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STEADFAST DETERMINATION | `000008977006` | Fellhammer Siege-Host – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Infernal Reavers

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CRUEL EXECUTION | `000009504005` | Infernal Reavers – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INVETERATE MURDERERS | `000009504002` | Infernal Reavers – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LOW CUNNING | `000009504003` | Infernal Reavers – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NEXT PRIZE | `000009504004` | Infernal Reavers – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Pactbound Zealots

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ETERNAL HATE | `000008358003` | Pactbound Zealots – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EYE OF THE GODS | `000008358002` | Pactbound Zealots – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FESTERING MIASMA | `000008358007` | Pactbound Zealots – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PROFANE ZEAL | `000008358004` | Pactbound Zealots – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SKINSHIFT | `000008358005` | Pactbound Zealots – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TORPEFYING REFRAIN | `000008358006` | Pactbound Zealots – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Renegade Raiders

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| OPPORTUNISTIC RAIDERS | `000008969004` | Renegade Raiders – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REAVERS’ HASTE | `000008969007` | Renegade Raiders – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RUINOUS RAID | `000008969006` | Renegade Raiders – Battle Tactic Stratagem | 1 | Your turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SCOUR AND SEIZE | `000008969003` | Renegade Raiders – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNFAILINGLY OBDURATE | `000008969002` | Renegade Raiders – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WARPCHARGED ENGINES | `000008969005` | Renegade Raiders – Wargear Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Soulforged Warpack

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DAEMONIC POSSESION | `000008986004` | Soulforged Warpack – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DESPERATE PLEDGE | `000008986002` | Soulforged Warpack – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FEEDING FRENZY | `000008986007` | Soulforged Warpack – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GLUT OF SOULS | `000008986003` | Soulforged Warpack – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PREDATORY PURSUIT | `000008986006` | Soulforged Warpack – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNSTOPPABLE RAMPAGE | `000008986005` | Soulforged Warpack – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Underdeck Uprising

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CRUDE SABOTAGE | `000009513004` | Underdeck Uprising – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FLEETING MIGHT | `000009513003` | Underdeck Uprising – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INFERNAL ALTARS | `000009513002` | Underdeck Uprising – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STORM THE BRIDGE! | `000009513005` | Underdeck Uprising – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Veterans of the Long War

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLACK CRUSADE | `000008961005` | Veterans of the Long War – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BRINGERS OF DESPAIR | `000008961004` | Veterans of the Long War – Epic Deed Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CONTEMPTUOUS DISREGARD | `000008961003` | Veterans of the Long War – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENDLESS IRE | `000008961002` | Veterans of the Long War – Epic Deed Stratagem | 2 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LET THE GALAXY BURN | `000008961006` | Veterans of the Long War – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MILLENNIA OF EXPERIENCE | `000008961007` | Veterans of the Long War – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Death Guard (`DG`) — `https://wahapedia.ru/wh40k10ed/factions/death-guard`

#### Arch-Contaminators

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ALLIES OF ENTROPY | `000009417002` | Arch-Contaminators – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CLOUD OF FLIES | `000009417005` | Arch-Contaminators – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CORROSIVE CURSE | `000009417004` | Arch-Contaminators – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SEED OF CORRUPTION | `000009417003` | Arch-Contaminators – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Champions of Contagion

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLESSINGS OF FILTH | `000010132002` | Champions of Contagion – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEATH’S HEADS | `000010132007` | Champions of Contagion – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GROTESQUE FORTITUDE | `000010132004` | Champions of Contagion – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MALIGNANCE MAGNIFIED | `000010132003` | Champions of Contagion – Battle Tactic Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MOBILE VECTOR | `000010132006` | Champions of Contagion – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RABID INFUSION | `000010132005` | Champions of Contagion – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Death Lord’s Chosen

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLOOMING PESTILENCE | `000010144002` | Death Lord’s Chosen – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GRIM REAPERS | `000010144003` | Death Lord’s Chosen – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MORTARION'S TEACHINGS | `000010144006` | Death Lord’s Chosen – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SICKENING IMPACT | `000010144007` | Death Lord’s Chosen – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SIGNAL POX | `000010144005` | Death Lord’s Chosen – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNDYING SPITE | `000010144004` | Death Lord’s Chosen – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Flyblown Host

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DRONING HORROR | `000009730005` | Flyblown Host – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENERVATING ONSLAUGHT | `000009730006` | Flyblown Host – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EYE OF THE SWARM | `000009730004` | Flyblown Host – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MYPHITIC INVIGORATION | `000009730007` | Flyblown Host – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NAUSEATING PAROXYSMS | `000009730002` | Flyblown Host – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VERMIN CLOUD | `000009730003` | Flyblown Host – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Mortarion’s Hammer

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLIGHTED LAND | `000010128002` | Mortarion’s Hammer – Strategic Ploy Stratagem | 2 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DRAWN TO DESPAIR | `000010128004` | Mortarion’s Hammer – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EYESTINGER STORM | `000010128006` | Mortarion’s Hammer – Strategic Ploy Stratagem | 1 | Opponent’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FONT OF FILTH | `000010128005` | Mortarion’s Hammer – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELENTLESS GRIND | `000010128003` | Mortarion’s Hammer – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STINKING MIRE | `000010128007` | Mortarion’s Hammer – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Shamblerot Vectorium

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| GNAWING HUNGER | `000010140004` | Shamblerot Vectorium – Battle Tactic Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GRIP OF THE WALKING POX | `000010140002` | Shamblerot Vectorium – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HIDDEN AMONGST THE DEAD | `000010140005` | Shamblerot Vectorium – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHAMBLING WALL | `000010140007` | Shamblerot Vectorium – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHOCK AND HORROR | `000010140006` | Shamblerot Vectorium – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SMEARED WITH FILTH | `000010140003` | Shamblerot Vectorium – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Tallyband Summoners

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ALL IS ROT | `000010136004` | Tallyband Summoners – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| AVATARS OF DECAY | `000010136006` | Tallyband Summoners – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CLUTCHING CORRUPTION | `000010136003` | Tallyband Summoners – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FLESHY AVALANCHE | `000010136005` | Tallyband Summoners – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MIRESLICK | `000010136007` | Tallyband Summoners – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PERSISTENT PESTS | `000010136002` | Tallyband Summoners – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Unclean Uprising

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| PATH OF PESTILENCE | `000009409003` | Unclean Uprising – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| POX FLARE | `000009409002` | Unclean Uprising – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHAMBLING ONSLAUGHT | `000009409005` | Unclean Uprising – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE DEAD RISE | `000009409004` | Vectors of Decay – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Vectors of Decay

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CHINKS IN THE ARMOUR | `000009399002` | Vectors of Decay – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GROTESQUE DEMISE | `000009399003` | Vectors of Decay – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INFESTATION | `000009399004` | Embarked Regiment – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SEEPING CORROSION | `000009399005` | Vectors of Decay – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Virulent Vectorium

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CREEPING BLIGHT | `000010124007` | Virulent Vectorium – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DISGUSTINGLY RESILIENT | `000010124003` | Virulent Vectorium – Battle Tactic Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LEECHSPORE ERUPTION | `000010124005` | Virulent Vectorium – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OVERWHELMING GENEROSITY | `000010124006` | Virulent Vectorium – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PLAGUESURGE | `000010124004` | Virulent Vectorium – Epic Deed Stratagem | 2 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PUTRID DETONATION | `000010124002` | Virulent Vectorium – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Drukhari (`DRU`) — `https://wahapedia.ru/wh40k10ed/factions/drukhari`

#### Kabalite Corsairs

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DECKPLATE SWEEPERS | `000009434003` | Kabalite Corsairs – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ELUSIVE DUELLISTS | `000009434002` | Kabalite Corsairs – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OPPORTUNISTIC THIEVES | `000009434005` | Kabalite Corsairs – Strategic Ploy Stratagem | 1 | Your turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TAKE THEM ALIVE | `000009434004` | Kabalite Corsairs – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Painbringers

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| HORRIFYING FORM | `000009451002` | Painbringers – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MOULDED MUSCULATURE | `000009451004` | Painbringers – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TERRIFYING AURA | `000009451005` | Painbringers – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNFEELING ABOMINATIONS | `000009451003` | Painbringers – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Realspace Raiders

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ACROBATIC DISPLAY | `000008510004` | Realspace Raiders – Epic Deed Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ALLIANCE OF AGONY | `000008510005` | Realspace Raiders – Battle Tactic Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSENSIBLE TO PAIN | `000008510007` | Realspace Raiders – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PREY ON THE WEAK | `000008510002` | Realspace Raiders – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| QUICKSILVER REACTIONS | `000008510006` | Realspace Raiders – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STRIKE AND FADE | `000008510003` | Realspace Raiders – Epic Deed Stratagem | 2 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Reaper’s Wager

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DANCE MACABRE | `000009782007` | Reaper’s Wager – Strategic Ploy Stratagem | 2 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FATEFUL ROLE | `000009782003` | Reaper’s Wager – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MALICIOUS FRENZY | `000009782002` | Reaper’s Wager – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MURDERER’S CIRCUS | `000009782004` | Reaper’s Wager – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SCINTILLATING TEMPO | `000009782006` | Reaper’s Wager – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHORTEN THE ODDS | `000009782005` | Reaper’s Wager – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Ship-killer Cult

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| HYPERAGILITY | `000009442002` | Ship-killer Cult – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NO OBSTACLE | `000009442004` | Ship-killer Cult – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PHANTASM GRENADES | `000009442005` | Ship-killer Cult – Wargear Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TOYING WITH THE PREY | `000009442003` | Ship-killer Cult – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Skysplinter Assault

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| NIGHT SHIELD | `000008716007` | Skysplinter Assault – Wargear Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| POUNCE ON THE PREY | `000008716004` | Skysplinter Assault – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SKYBORNE ANNIHILATION | `000008716005` | Skysplinter Assault – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWOOPING MOCKERY | `000008716006` | Skysplinter Assault – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VICIOUS BLADES | `000008716002` | Skysplinter Assault – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WRAITHLIKE RETREAT | `000008716003` | Skysplinter Assault – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Space Lane Raiders

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CREW-THIEVES | `000009426003` | Space Lane Raiders – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHIPBOARD SHADES | `000009426002` | Space Lane Raiders – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VETERAN PIRATES | `000009426005` | Space Lane Raiders – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VOIDSHIP GLADIATORS | `000009426004` | Space Lane Raiders – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Emperor’s Children (`EC`) — `https://wahapedia.ru/wh40k10ed/factions/emperor-s-children`

#### Carnival of Excess

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DARK APPARITIONS | `000010011007` | Carnival of Excess – Strategic Ploy Stratagem | 2 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ECSTATIC SLAUGHTER | `000010011003` | Carnival of Excess – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUSTAINED BY AGONY | `000010011002` | Carnival of Excess – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SYCOPHANTIC SURGE | `000010011005` | Carnival of Excess – Battle Tactic Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNCANNY REACTIONS | `000010011006` | Carnival of Excess – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VIOLENT CRESCENDO | `000010011004` | Carnival of Excess – Strategic Ploy Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Coterie of the Conceited

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF ABHORRENCE | `000010015007` | Coterie of the Conceited – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EMBRACE THE PAIN | `000010015004` | Coterie of the Conceited – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MARTIAL PERFECTION | `000010015005` | Coterie of the Conceited – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PROTECTION OF THE DARK PRINCE | `000010015002` | Coterie of the Conceited – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNBOUND ARROGANCE | `000010015006` | Coterie of the Conceited – Epic Deed Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNSHAKEABLE OPPONENTS | `000010015003` | Coterie of the Conceited – Epic Deed Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Mercurial Host

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CAPRICIOUS REACTIONS | `000009999006` | Mercurial Host – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| COMBAT STIMMS | `000009999003` | Mercurial Host – Battle Tactic Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CRUEL RAIDERS | `000009999007` | Mercurial Host – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DARK VIGOUR | `000009999005` | Mercurial Host – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HONOUR THE PRINCE | `000009999004` | Mercurial Host – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VIOLENT EXCESS | `000009999002` | Mercurial Host – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Peerless Bladesmen

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CRUEL BLADESMAN | `000010003005` | Peerless Bladesmen – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CUT DOWN THE WEAK | `000010003007` | Peerless Bladesmen – Strategic Ploy Stratagem | 2 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEATH ECSTASY | `000010003003` | Peerless Bladesmen – Strategic Ploy Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEFT PARRY | `000010003002` | Peerless Bladesmen – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INCESSANT VIOLENCE | `000010003004` | Peerless Bladesmen – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TERRIFYING SPECTACLE | `000010003006` | Peerless Bladesmen – Strategic Ploy Stratagem | 1 | Opponent’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Rapid Evisceration

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ADVANCE AND CLAIM | `000010007003` | Rapid Evisceration – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CEASELESS ONSLAUGHT | `000010007005` | Rapid Evisceration – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DYNAMIC BREAKTHROUGH | `000010007004` | Rapid Evisceration – Epic Deed Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ONTO THE NEXT | `000010007002` | Rapid Evisceration – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OUTFLANKING STRIKE | `000010007007` | Rapid Evisceration – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REACTIVE DISEMBARKATION | `000010007006` | Rapid Evisceration – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Slaanesh’s Chosen

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BEAUTIFUL DEATH | `000010019003` | Slaanesh’s Chosen – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEVOTED DUELLISTS | `000010019002` | Slaanesh’s Chosen – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DIABOLIC MAJESTY | `000010019005` | Slaanesh’s Chosen – Epic Deed Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HEIGHTENED JEALOUSY | `000010019004` | Slaanesh’s Chosen – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REFUSAL TO BE OUTDONE | `000010019006` | Slaanesh’s Chosen – Battle Tactic Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VENGEFUL SURGE | `000010019007` | Slaanesh’s Chosen – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Genestealer Cults (`GC`) — `https://wahapedia.ru/wh40k10ed/factions/genestealer-cults`

#### Biosanctic Broodsurge

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BIO-HORROR REVELATION | `000009076007` | Biosanctic Broodsurge – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EVASIVE VANGUARD | `000009076002` | Biosanctic Broodsurge – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GENE-TWISTED MUSCLE | `000009076004` | Biosanctic Broodsurge – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HYPER-METABOLIC VIGOUR | `000009076005` | Biosanctic Broodsurge – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SAINTLY PAROXYSM | `000009076003` | Biosanctic Broodsurge – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STIMULATED BIO-SURGE | `000009076006` | Biosanctic Broodsurge – Battle Tactic Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Brood Brother Auxilia

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| A DARK NETWORK | `000009085007` | Brood Brother Auxilia – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ACCEPTABLE LOSSES | `000009085005` | Brood Brother Auxilia – Strategic Ploy Stratagem | 2 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IN THE SHADOW OF IRON | `000009085002` | Brood Brother Auxilia – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REGIMENTAL REINFORCEMENTS | `000009085003` | Brood Brother Auxilia – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUPPRESS AND OVERWHELM | `000009085004` | Brood Brother Auxilia – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SYMBIOTIC DESTRUCTION | `000009085006` | Brood Brother Auxilia – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Cult Unveiled

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| FOR THE BROOD | `000009461004` | Cult Unveiled – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LURKING MENACE | `000009461005` | Cult Unveiled – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OUT OF HIDING | `000009461003` | Cult Unveiled – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PLANNED EXTRACTION | `000009461002` | Cult Unveiled – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Final Day

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AVENGE THE STAR CHILDREN | `000009828004` | Final Day – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DARTING ATTACKS | `000009828006` | Final Day – Strategic Ploy Stratagem | 1 | Your turn | Shooting or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DIVINE IMPERATIVE | `000009828005` | Final Day – Battle Tactic Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HYPERFEROCITY | `000009828002` | Final Day – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PSI SURGE | `000009828003` | Final Day – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RESISTANCE TUNNELS | `000009828007` | Final Day – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Genespawn Onslaught

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| GROWING DREAD | `000009469005` | Genespawn Onslaught – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MONSTROUS MOMENTUM | `000009469002` | Genespawn Onslaught – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SOLDIERS OF THE STAR CHILDREN | `000009469004` | Genespawn Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNSTOPPABLE BRUTES | `000009469003` | Genespawn Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Host of Ascension

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| A DEADLY SNARE | `000009068007` | Host of Ascension – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| COORDINATED TRAP | `000009068002` | Host of Ascension – Battle Tactic Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LYING IN WAIT | `000009068005` | Host of Ascension – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRIMED AND READIED | `000009068003` | Host of Ascension – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RETURN TO THE SHADOWS | `000009068006` | Host of Ascension – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TUNNEL CRAWLERS | `000009068004` | Host of Ascension – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Infestation Swarm

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| HUNTING GROUNDS | `000009477004` | Infestation Swarm – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HYPERADRENAL REFLEXES | `000009477002` | Infestation Swarm – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OUTFLANK | `000009477005` | Infestation Swarm – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PERVASIVE DREAD | `000009477003` | Infestation Swarm – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Outlander Claw

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ALONG SHADOWED TRAILS | `000009080002` | Outlander Claw – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CLOSE-RANGE SHOOT-OUT | `000009080004` | Outlander Claw – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEFT MANOEUVRING | `000009080006` | Outlander Claw – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEVOTED CREW | `000009080003` | Outlander Claw – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENCIRCLING THE PREY | `000009080007` | Outlander Claw – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RAPID FEINT | `000009080005` | Outlander Claw – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Xenocreed Congregation

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| FRENZIED DEVOTION | `000009072003` | Xenocreed Congregation – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE DOWNTRODDEN RISE | `000009072006` | Xenocreed Congregation – Strategic Ploy Stratagem | 2 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE PATH OF ANGUISH | `000009072007` | Xenocreed Congregation – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TIRELESS FERVOUR | `000009072004` | Xenocreed Congregation – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TRANSCENDENT CELERITY | `000009072005` | Xenocreed Congregation – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VENGEANCE FOR THE MARTYR! | `000009072002` | Xenocreed Congregation – Epic Deed Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Grey Knights (`GK`) — `https://wahapedia.ru/wh40k10ed/factions/grey-knights`

#### Baneslayer Strike

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOURED AEGIS | `000009494002` | Baneslayer Strike – Epic Deed Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PSYBOLT AMMUNITION | `000009494005` | Baneslayer Strike – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELENTLESS BOARDERS | `000009494004` | Baneslayer Strike – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SANCTIC CIRCLE | `000009494003` | Baneslayer Strike – Epic Deed Stratagem | 2 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Teleport Strike Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DEATH FROM THE WARP | `000008457003` | Teleport Strike Force – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HALOED IN SOULFIRE | `000008457007` | Teleport Strike Force – Strategic Ploy Stratagem | 2 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MISTS OF DEIMOS | `000008457005` | Teleport Strike Force – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PROGNISTICATED ARRIVAL | `000008457004` | Teleport Strike Force – Epic Deed Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RADIANT STRIKE | `000008457006` | Teleport Strike Force – Battle Tactic Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TRUESILVER ARMOUR | `000008457002` | Teleport Strike Force – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Void Purge Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BREACH-SHOCK | `000009486002` | Void Purge Force – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HEXBANE WARDS | `000009486003` | Void Purge Force – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SANCTIFIED SLAUGHTER | `000009486005` | Void Purge Force – Battle Tactic Stratagem | 1 | Your turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TRANSLOCATION | `000009486004` | Void Purge Force – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Warpbane Task Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AEGIS ETERNAL | `000009778006` | Warpbane Task Force – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FIRES OF COVENANT | `000009778005` | Warpbane Task Force – Battle Tactic Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FLAMES OF SANCTITY | `000009778003` | Warpbane Task Force – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HALLOWED BEACON | `000009778004` | Warpbane Task Force – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REPELLING SPHERE | `000009778007` | Warpbane Task Force – Battle Tactic Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SANCTIFIED KILL ZONE | `000009778002` | Warpbane Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Imperial Agents (`AoI`) — `https://wahapedia.ru/wh40k10ed/factions/imperial-agents`

#### Imperialis Fleet

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CLOSE-QUARTERS BARRAGE | `000009139004` | Imperialis Fleet – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DISPLACER FIELD | `000009139006` | Imperialis Fleet – Wargear Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EMPEROR’S WILL | `000009139005` | Imperialis Fleet – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MASTERS OF THE VOID | `000009139003` | Imperialis Fleet – Epic Deed Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SELFLESS BODYGUARD | `000009139007` | Imperialis Fleet – Epic Deed Stratagem | 1 | Opponent’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VIOLENT ACQUISITION | `000009139002` | Imperialis Fleet – Strategic Ploy Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Interdiction Team

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARBITRARY EXECUTION | `000009370004` | Interdiction Team – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CRACKDOWN | `000009370002` | Interdiction Team – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DUTY AND DEATH | `000009370003` | Interdiction Team – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INESCAPABLE JUDGEMENT | `000009370005` | Interdiction Team – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Ordo Hereticus Purgation Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DISPENSE JUSTICE | `000009131003` | Purgation Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EXACT PUNISHMENT | `000009131007` | Purgation Force – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EXECUTION ORDER | `000009131005` | Purgation Force – Epic Deed Stratagem | 2 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INVIOLATE JURISDICTION | `000009131004` | Purgation Force – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LINE OF FIRE | `000009131006` | Purgation Force – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STUN GRENADES | `000009131002` | Purgation Force – Wargear Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Ordo Malleus Daemon Hunters

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| HEXAGRAMMIC WARDS | `000009135006` | Daemon Hunters – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PSYBOLT AMMUNITION | `000009135007` | Daemon Hunters – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RITES OF EXORCISM | `000009135003` | Daemon Hunters – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RITUAL OF WARDING | `000009135002` | Daemon Hunters – Strategic Ploy Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STEEL HEART | `000009135004` | Daemon Hunters – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TRUESILVER ARMOUR | `000009135005` | Daemon Hunters – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Ordo Xenos Alien Hunters

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ADAPTIVE TACTICS | `000009127003` | Alien Hunters – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ARMOUR OF CONTEMPT | `000009127002` | Alien Hunters – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DRAGONFIRE ROUNDS | `000009127005` | Alien Hunters – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HELLFIRE ROUNDS | `000009127004` | Alien Hunters – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| KRAKEN ROUNDS | `000009127006` | Alien Hunters – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RAPID TACTICAL RELOCATION | `000009127007` | Alien Hunters – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Veiled Blade Elimination Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLIND GRENADES | `000009758006` | Veiled Blade Elimination Force – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENSNARING TRAP | `000009758007` | Veiled Blade Elimination Force – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HYPERSTIMMS | `000009758003` | Veiled Blade Elimination Force – Battle Tactic Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ORBITAL OVERSIGHT | `000009758005` | Veiled Blade Elimination Force – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRIME TARGET | `000009758002` | Veiled Blade Elimination Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WILL‑SAPPING SALVO | `000009758004` | Veiled Blade Elimination Force – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Voidship’s Company

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AMMO RATIONS | `000009361003` | Voidship’s Company – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BOARDING DRILL | `000009361004` | Voidship’s Company – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BREACH AND CLEAR | `000009361002` | Voidship’s Company – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHIP’S WATCH | `000009361005` | Voidship’s Company – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Imperial Knights (`QI`) — `https://wahapedia.ru/wh40k10ed/factions/imperial-knights`

#### Noble Lance

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ROTATE ION SHIELDS | `000008465003` | Noble Lance – Wargear Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHOULDER THE BURDEN | `000008465007` | Noble Lance – Battle Tactic Stratagem | 2 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SQUIRES' DUTY | `000008465002` | Noble Lance – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THUNDERSTOMP | `000008465004` | Noble Lance – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TROPHY CLAIM | `000008465006` | Noble Lance – Epic Deed Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VALIANT LAST STAND | `000008465005` | Noble Lance – Epic Deed Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Questor Forgepact

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AGGRESSION BEGETS AGGRESSION | `000009762006` | Questor Forgepact – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BONDED IMPERATIVE | `000009762004` | Questor Forgepact – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MACHINE FOCUS | `000009762005` | Questor Forgepact – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OMNISSIAH’S GRACE | `000009762002` | Questor Forgepact – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THRONEGHEIST FURY | `000009762007` | Questor Forgepact – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VENGEANCE OF THE MACHINE CULT | `000009762003` | Questor Forgepact – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Leagues of Votann (`LoV`) — `https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann`

#### Hearthband

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BRËKKEKNOTS | `000009824002` | Hearthband – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FURY OF THE HEARTH | `000009824007` | Hearthband – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MATERIALISATION MATRICES | `000009824006` | Hearthband – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUPERIOR CRAFTSMANSHIP | `000009824004` | Hearthband – Battle Tactic Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SURE OF PURPOSE | `000009824003` | Hearthband – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNYIELDING AGGRESSION | `000009824005` | Hearthband – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Hearthfire Strike

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ECONOMY OF AGGRESSION | `000009538004` | Hearthfire Strike – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GRAVITRONIC PULSE | `000009538005` | Hearthfire Strike – Battle Tactic Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PAN-SPECTRAL VISUALISER | `000009538003` | Hearthfire Strike – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WEAVEFIELD FLARE | `000009538002` | Hearthfire Strike – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Oathband

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ANCESTRAL SENTENCE | `000008499004` | Oathband – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NEWFOUND NEMESIS | `000008499006` | Oathband – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ORDERED RETREAT | `000008499003` | Oathband – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REACTIVE REPRISAL | `000008499005` | Oathband – Battle Tactic Stratagem | 2 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VOID ARMOUR | `000008499007` | Oathband – Wargear Stratagem | 1 | Opponent’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WARRIOR PRIDE | `000008499002` | Oathband – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Void Salvagers

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CORRIDOR COVERED | `000009530005` | Void Salvagers – Battle Tactic Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| JUDGED AND PUNISHED | `000009530004` | Void Salvagers – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| POINT-BLANK FIRE | `000009530003` | Void Salvagers – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELIC CYPHER | `000009530002` | Void Salvagers – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Necrons (`NEC`) — `https://wahapedia.ru/wh40k10ed/factions/necrons`

#### Annihilation Legion

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLOOD-FUELLED CRUELTY | `000008405006` | Annihilation Legion – Battle Tactic Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSANITY’S IRE | `000008405007` | Annihilation Legion  – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MASKS OF DEATH | `000008405002` | Annihilation Legion  – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MURDEROUS REANIMATION | `000008405004` | Annihilation Legion – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PITILESS HUNTERS | `000008405005` | Annihilation Legion – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE SPOOR OF FRAILTY | `000008405003` | Annihilation Legion – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Awakened Dynasty

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| PROTOCOL OF THE CONQUERING TYRANT | `000008371006` | Awakened Dynasty – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PROTOCOL OF THE ETERNAL REVENANT | `000008371002` | Awakened Dynasty – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PROTOCOL OF THE HUNGRY VOID | `000008371004` | Awakened Dynasty – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PROTOCOL OF THE SUDDEN STORM | `000008371005` | Awakened Dynasty – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PROTOCOL OF THE UNDYING LEGIONS | `000008371003` | Awakened Dynasty – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PROTOCOL OF THE VENGEFUL STARS | `000008371007` | Awakened Dynasty – Strategic Ploy Stratagem | 2 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Canoptek Court

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| COUNTERTEMPORAL SHIFT | `000008547006` | Canoptek Court – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CURSE OF THE CRYPTEK | `000008547002` | Canoptek Court – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CYNOSURE OF ERADICATION | `000008547003` | Canoptek Court – Battle Tactic Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REACTIVE SUBROUTINES | `000008547005` | Canoptek Court – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SOLAR PULSE | `000008547004` | Canoptek Court – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUBOPTIMAL FACADE | `000008547007` | Canoptek Court – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Canoptek Harvesters

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| NANOSCARAB VIRUS | `000009605005` | Canoptek Harvesters – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PHASE-SHIFT | `000009605004` | Canoptek Harvesters – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| QUANTUM FLARE-SHIELD | `000009605003` | Canoptek Harvesters – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TARGETING ALGORITHMS | `000009605002` | Canoptek Harvesters – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Deranged Outcasts

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BATHED IN BLOOD | `000009597002` | Deranged Outcasts – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RUSH TO SLAUGHTER | `000009597004` | Deranged Outcasts – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHADOW STALKERS | `000009597003` | Deranged Outcasts – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TERRIFYING AMBUSH | `000009597005` | Deranged Outcasts – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Hypercrypt Legion

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| COSMIC PRECISION | `000008555005` | Hypercrypt Legion – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DIMENSIONAL CORRIDOR | `000008555006` | Hypercrypt Legion – Strategic Ploy Stratagem | 2 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENTROPIC DAMPING | `000008555007` | Hypercrypt Legion – Wargear Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HYPERPHASIC RECALL | `000008555002` | Hypercrypt Legion – Strategic Ploy Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| QUANTUM DEFLECTION | `000008555003` | Hypercrypt Legion – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REANIMATION CRYPTS | `000008555004` | Hypercrypt Legion – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Obeisance Phalanx

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ENSLAVED ARTIFICE | `000008551003` | Obeisance Phalanx – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NANOASSEMBLY PROTOCOLS | `000008551004` | Obeisance Phalanx – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SENTINELS OF ETERNITY | `000008551005` | Obeisance Phalanx – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUFFER NO RIVAL | `000008551006` | Obeisance Phalanx – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TERRITORIAL OBSESSION | `000008551007` | Obeisance Phalanx – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| YOUR TIME IS NIGH | `000008551002` | Obeisance Phalanx – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Starshatter Arsenal

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CHRONOSHIFT | `000009750004` | Starshatter Arsenal – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DIMENSIONAL TUNNEL | `000009750005` | Starshatter Arsenal – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENDLESS SERVITUDE | `000009750006` | Starshatter Arsenal – Strategic Ploy Stratagem | 1 | Your turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MERCILESS RECLAMATION | `000009750002` | Starshatter Arsenal – Battle Tactic Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REACTIVE REPOSITION | `000009750007` | Starshatter Arsenal – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNYIELDING FORMS | `000009750003` | Starshatter Arsenal – Battle Tactic Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Tomb Ship Complement

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CONCENTRATED ATOMISATION | `000009589004` | Tomb Ship Complement – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DISINTEGRATION BEAMS | `000009589005` | Tomb Ship Complement – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DISRUPTION FIELDS | `000009589002` | Tomb Ship Complement – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNWAVERING DEFENCE | `000009589003` | Tomb Ship Complement – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Orks (`ORK`) — `https://wahapedia.ru/wh40k10ed/factions/orks`

#### Bully Boyz

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ALWAYS LOOKIN’ FER A FIGHT | `000008886004` | Bully Boyz – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ARMED TO DATEEF | `000008886002` | Bully Boyz – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CRUSHING IMPACT | `000008886005` | Bully Boyz – Epic Deed Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CUT’EM DOWN | `000008886006` | Bully Boyz – Battle Tactic Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HULKING BRUTES | `000008886007` | Bully Boyz – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TOO ARROGANT TO DIE | `000008886003` | Bully Boyz – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Da Big Hunt

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DAT ONE’S EVEN BIGGA! | `000008869004` | Da Big Hunt – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DRAG IT DOWN | `000008869002` | Da Big Hunt – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSTINCTIVE HUNTERS | `000008869007` | Da Big Hunt – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STALKIN’ TAKTIKS | `000008869006` | Da Big Hunt – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNSTOPPABLE MOMENTUM | `000008869003` | Da Big Hunt – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WHERE D’YA FINK YOU’RE GOING? | `000008869005` | Da Big Hunt – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Dread Mob

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BIGGER SHELLS FOR BIGGER GITZ | `000008878004` | Dread Mob – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CONNIVING RUNTS | `000008878006` | Dread Mob – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DAKKA! DAKKA! DAKKA! | `000008878005` | Dread Mob – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EXTRA GUBBINZ | `000008878007` | Dread Mob – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| KLANKIN’ KLAWS | `000008878002` | Dread Mob – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUPERFUELLED BOILER | `000008878003` | Dread Mob – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Green Tide

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BRAGGIN’ RIGHTS | `000008882004` | Green Tide – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BULLDOZER BRUTALITY | `000008882003` | Green Tide – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| COME ON LADZ! | `000008882005` | Green Tide – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| COMPETITIVE STREAK | `000008882002` | Green Tide – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GO GET ’EM! | `000008882007` | Green Tide – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TIDE OF MUSCLE | `000008882006` | Green Tide – Epic Deed Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Kaptin Killers

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CORNERED AND KRUMPED | `000009624005` | Kaptin Killers – Battle Tactic Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LOOT ON THE MOVE | `000009624002` | Kaptin Killers – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PILE THROUGH | `000009624003` | Kaptin Killers – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PIT FIGHTER | `000009624004` | Kaptin Killers – Epic Deed Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Kult of Speed

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLITZA FIRE | `000008873005` | Kult of Speed – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DAKKASTORM | `000008873004` | Kult of Speed – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FULL THROTTLE! | `000008873006` | Kult of Speed – Battle Tactic Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MORE GITZ OVER ’ERE! | `000008873007` | Kult of Speed – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SPEEDIEST FREEKS | `000008873002` | Kult of Speed – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SQUIG FLINGIN’ | `000008873003` | Kult of Speed – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### More Dakka!

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CALL DAT DAKKA? | `000009992007` | More Dakka! – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GET STUCK IN, LADZ! | `000009992003` | More Dakka! – Epic Deed Stratagem | 2 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HUGE SHOW-OFFS | `000009992004` | More Dakka! – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LONG, UNCONTROLLED BURSTS | `000009992005` | More Dakka! – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ORKS IS STILL ORKS | `000009992002` | More Dakka! – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SPESHUL SHELLS | `000009992006` | More Dakka! – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Ramship Raiders

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| EAGER TO FIGHT | `000009616004` | Ramship Raiders – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENRAGED RUSH | `000009616005` | Ramship Raiders – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PILE THROUGH | `000009616002` | Ramship Raiders – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RAMBOYZ RAMPAGE | `000009616003` | Ramship Raiders – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Taktikal Brigade

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DAT’S OURS | `000009796002` | Taktikal Brigade – Strategic Ploy Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DED SNEAKY | `000009796007` | Taktikal Brigade – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FIGHT PROPPA | `000009796003` | Taktikal Brigade – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| KRUNCHIN’ DESCENT | `000009796005` | Taktikal Brigade – Battle Tactic Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ON TO DA NEXT | `000009796006` | Taktikal Brigade – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TAKTIKAL RETREAT | `000009796004` | Taktikal Brigade – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### War Horde

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CAREEN! | `000008366002` | War Horde – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ERE WE GO | `000008366007` | War Horde – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MOB RULE | `000008366006` | War Horde – Battle Tactic Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ORKS IS NEVER BEATEN | `000008366003` | War Horde – Epic Deed Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNBRIDLED CARNAGE | `000008366004` | War Horde – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ’ARD AS NAILS | `000008366005` | War Horde – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Space Marines (`SM`) — `https://wahapedia.ru/wh40k10ed/factions/space-marines`

#### 1st Company Task Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000008495002` | 1st Company Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DUTY AND HONOUR | `000008495005` | 1st Company Task Force – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HEROES OF THE CHAPTER | `000008495003` | 1st Company Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LEGENDARY FORTITUDE | `000008495007` | 1st Company Task Force – Battle Tactic Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ORBITAL TELEPORTARIUM | `000008495006` | 1st Company Task Force – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TERRIFYING PROFICIENCY | `000008495004` | 1st Company Task Force – Strategic Ploy Stratagem | 1 | Your turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Angelic Inheritors

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000009836002` | Angelic Inheritors – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FOCUSED FURY | `000009836003` | Angelic Inheritors – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IN THE SHADOW OF GREAT WINGS | `000009836006` | Angelic Inheritors – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INSTANT OF GRACE | `000009836004` | Angelic Inheritors – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STRIKE NOW FOR GLORY | `000009836005` | Angelic Inheritors – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNTO THE BURNING SKIES | `000009836007` | Angelic Inheritors – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Anvil Siege Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000008475002` | Anvil Siege Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BATTLE DRILL RECALL | `000008475006` | Anvil Siege Force – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HAIL OF VENGEANCE | `000008475007` | Anvil Siege Force – Strategic Ploy Stratagem | 2 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NO THREAT TOO GREAT | `000008475005` | Anvil Siege Force – Battle Tactic Stratagem | 2 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NOT ONE BACKWARDS STEP | `000008475004` | Anvil Siege Force – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RIGID DISCIPLINE | `000008475003` | Anvil Siege Force – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Black Spear Task Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ADAPTIVE TACTICS | `000008523003` | Black Spear Task Force – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ARMOUR OF CONTEMPT | `000008523002` | Black Spear Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DRAGONFIRE ROUNDS | `000008523006` | Black Spear Task Force – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HELLFIRE ROUNDS | `000008523004` | Black Spear Task Force – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| KRAKEN ROUNDS | `000008523005` | Black Spear Task Force – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SITE-TO-SITE TELEPORTATION | `000008523007` | Black Spear Task Force – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Boarding Strike

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CERAMITE BULWARK | `000009241003` | Boarding Strike – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DUTY AND DEFIANCE | `000009241004` | Boarding Strike – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IN THE EMPEROR’S NAME | `000009241002` | Boarding Strike – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VOX-AMPLIFIED ROAR | `000009241005` | Boarding Strike – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Champions of Fenris

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000009852003` | Champions of Fenris – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CHILLING HOWL | `000009852005` | Champions of Fenris – Strategic Ploy Stratagem | 1 | Opponent’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ONRUSHING STORM | `000009852007` | Champions of Fenris – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PREYTAKER’S EYE | `000009852002` | Champions of Fenris – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RUNES OF CLAIMING | `000009852004` | Champions of Fenris – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STALKING WOLVES | `000009852006` | Champions of Fenris – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Champions of Russ

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000008531002` | Champions of Russ – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEATH HOWL | `000008531005` | Champions of Russ – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GO FOR THE THROAT | `000008531003` | Champions of Russ – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELENTLESS ASSAULT | `000008531007` | Champions of Russ – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RUNIC WARDS | `000008531004` | Champions of Russ – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WARRIOR PRIDE | `000008531006` | Champions of Russ – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Company of Hunters

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000008779003` | Company Of Hunters – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEATH ON THE WIND | `000008779005` | Company Of Hunters – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HIGH-SPEED FOCUS | `000008779006` | Company Of Hunters – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HUNTERS’ TRAIL | `000008779002` | Company Of Hunters – Strategic Ploy Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RAPID REAPPRAISAL | `000008779007` | Company Of Hunters – Battle Tactic Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TALON STRIKE | `000008779004` | Company Of Hunters – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Firestorm Assault Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000008483002` | Firestorm Assault Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BURNING VENGEANCE | `000008483007` | Firestorm Assault Force – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CRUCIBLE OF BATTLE | `000008483003` | Firestorm Assault Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IMMOLATION PROTOCOLS | `000008483005` | Firestorm Assault Force – Battle Tactic Stratagem | 2 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ONSLAUGHT OF FIRE | `000008483006` | Firestorm Assault Force – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RAPID EMBARKATION | `000008483004` | Firestorm Assault Force – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Gladius Task Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ADAPTIVE STRATEGY | `000008352005` | Gladius Task Force – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ARMOUR OF CONTEMPT | `000008352002` | Gladius Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HONOUR THE CHAPTER | `000008352004` | Gladius Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ONLY IN DEATH DOES DUTY END | `000008352003` | Gladius Task Force – Epic Deed Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SQUAD TACTICS | `000008352007` | Gladius Task Force – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STORM OF FIRE | `000008352006` | Gladius Task Force – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Inner Circle Task Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000008775002` | Inner Circle Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DUTY UNTO DEATH | `000008775004` | Inner Circle Task Force – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MARTIAL MASTERY | `000008775003` | Inner Circle Task Force – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELIC TELEPORTARIUM | `000008775005` | Inner Circle Task Force – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNMATCHED FORTITUDE | `000008775007` | Inner Circle Task Force – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WRATH OF THE LION | `000008775006` | Inner Circle Task Force – Epic Deed Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Ironstorm Spearhead

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ANCIENT FURY | `000008479006` | Ironstorm Spearhead – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ARMOUR OF CONTEMPT | `000008479003` | Ironstorm Spearhead – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MERCY IS WEAKNESS | `000008479004` | Ironstorm Spearhead – Battle Tactic Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| POWER OF THE MACHINE SPIRIT | `000008479007` | Ironstorm Spearhead – Epic Deed Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNBOWED CONVICTION | `000008479002` | Ironstorm Spearhead – Battle Tactic Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VENGEFUL ANIMUS | `000008479005` | Ironstorm Spearhead – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Liberator Assault Group

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AGGRESSIVE ONSLAUGHT | `000008375006` | Liberator Assault Group – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ANGELIC GRACE | `000008375002` | Liberator Assault Group – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ARMOUR OF CONTEMPT | `000008375003` | Liberator Assault Group – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RED RAMPAGE | `000008375005` | Liberator Assault Group – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELENTLESS ASSAULT | `000008375007` | Liberator Assault Group – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SAVAGE ECHOES | `000008375004` | Liberator Assault Group – Battle Tactic Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Librarius Conclave

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000009791003` | Librarius Conclave – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ASSAIL | `000009791006` | Librarius Conclave – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FIERY SHIELD | `000009791004` | Librarius Conclave – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IRON ARM | `000009791005` | Librarius Conclave – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRESCIENT PRECISION | `000009791007` | Librarius Conclave – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SENSORY ASSAULT | `000009791002` | Librarius Conclave – Strategic Ploy Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Lion’s Blade Task Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000009734003` | Lion’s Blade Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ILLUMINATING FIRE | `000009734006` | Lion’s Blade Task Force – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INESCAPABLE WRATH | `000009734007` | Lion’s Blade Task Force – Strategic Ploy Stratagem | 2 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| KNIGHTS OF IRON | `000009734005` | Lion’s Blade Task Force – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OVERPOWERING EXACTION | `000009734002` | Lion’s Blade Task Force – Strategic Ploy Stratagem | 1 | Either player’s turn | Command or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STRENGTH IN UNITY | `000009734004` | Lion’s Blade Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Pilum Strike Team

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ENHANCED EFFICIENCY | `000009249003` | Pilum Strike Team – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FIGHTING RETREAT | `000009249004` | Pilum Strike Team – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| KNIFE WORK | `000009249002` | Pilum Strike Team – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MASTER MARKSMEN | `000009249005` | Pilum Strike Team – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Righteous Crusaders

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000008527006` | Righteous Crusaders – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CRUSADER'S WRATH | `000008527005` | Righteous Crusaders – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEVOUT PUSH | `000008527007` | Righteous Crusaders – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FERVENT ACCLAMATION | `000008527003` | Righteous Crusaders – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NO ESCAPE | `000008527002` | Righteous Crusaders – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VICIOUS RIPOSTE | `000008527004` | Righteous Crusaders – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Stormlance Task Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000008487002` | Stormlance Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BLITZING FUSILLADE | `000008487003` | Stormlance Task Force – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FULL THROTTLE | `000008487004` | Stormlance Task Force – Wargear Stratagem | 2 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RIDE HARD, RIDE FAST | `000008487006` | Stormlance Task Force – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHOCK ASSAULT | `000008487005` | Stormlance Task Force – Battle Tactic Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WIND-SWIFT EVASION | `000008487007` | Stormlance Task Force – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Terminator Assault

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CARVE A PATH | `000009256004` | Terminator Assault – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CLEANSING SWEEP | `000009256005` | Terminator Assault – Battle Tactic Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FOCUSING SHRINE | `000009256003` | Terminator Assault – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TOWER OF STRENGTH | `000009256002` | Terminator Assault – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### The Angelic Host

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ANGEL’S SACRIFICE | `000009191004` | The Angelic Host – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ARMOUR OF CONTEMPT | `000009191003` | The Angelic Host – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEATH FROM THE SKIES | `000009191007` | The Angelic Host – Epic Deed Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DESCENT OF ANGELS | `000009191006` | The Angelic Host – Epic Deed Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MARTIAL EXEMPLARS | `000009191005` | The Angelic Host – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNBRIDLED ARDOUR | `000009191002` | The Angelic Host – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### The Lost Brethren

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000009187003` | The Lost Brethren – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FINAL RETRIBUTION | `000009187004` | The Lost Brethren – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FURIOUS ONSLAUGHT | `000009187005` | The Lost Brethren – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GLORIOUS SACRIFICE | `000009187002` | The Lost Brethren – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LOST TO RAGE | `000009187006` | The Lost Brethren – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WRATHFUL RAMPAGE | `000009187007` | The Lost Brethren – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Unforgiven Task Force

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000008389002` | Unforgiven Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FIRE DISCIPLINE | `000008389005` | Unforgiven Task Force – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GRIM RETRIBUTION | `000008389006` | Unforgiven Task Force – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INTRACTABLE | `000008389004` | Unforgiven Task Force – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNBREAKABLE LINES | `000008389007` | Unforgiven Task Force – Battle Tactic Stratagem | 2 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNFORGIVEN FURY | `000008389003` | Unforgiven Task Force – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Vanguard Spearhead

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| A DEADLY PRIZE | `000008491002` | Vanguard Spearhead – Wargear Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ARMOUR OF CONTEMPT | `000008491003` | Vanguard Spearhead – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CALCULATED FEINT | `000008491006` | Vanguard Spearhead – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GUERRILLA TACTICS | `000008491007` | Vanguard Spearhead – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STRIKE FROM THE SHADOWS | `000008491005` | Vanguard Spearhead – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SURGICAL STRIKES | `000008491004` | Vanguard Spearhead – Battle Tactic Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Wrath of the Rock

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000010161004` | Wrath of the Rock – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INESCAPABLE JUSTICE | `000010161002` | Wrath of the Rock – Battle Tactic Stratagem | 2 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LEONINE AGGRESSION | `000010161007` | Wrath of the Rock – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LION’S WILL | `000010161003` | Wrath of the Rock – Strategic Ploy Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELICS OF THE DARK AGE | `000010161006` | Wrath of the Rock – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TACTICAL MASTERY | `000010161005` | Wrath of the Rock – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Wrathful Procession

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARMOUR OF CONTEMPT | `000009844003` | Wrathful Procession – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BRUTE FERVOUR | `000009844005` | Wrathful Procession – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| CASTIGATE THE DEMAGOGUES | `000009844004` | Wrathful Procession – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FUELLED BY FAITH | `000009844002` | Wrathful Procession – Battle Tactic Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RELENTLESS MOMENTUM | `000009844006` | Wrathful Procession – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| VOICE OF DEVOTION | `000009844007` | Wrathful Procession – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Thousand Sons (`TS`) — `https://wahapedia.ru/wh40k10ed/factions/thousand-sons`

#### Changehost of Deceit

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CHRONOSORCEROUS BLEED | `000010198006` | Changehost of Deceit – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DECEPTIVE GLAMOUR | `000010198003` | Changehost of Deceit – Strategic Ploy Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ETHEREAL PHANTASM | `000010198004` | Changehost of Deceit – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FRACTAL DISJUNCTION | `000010198005` | Changehost of Deceit – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GLIMMERSHIFT PORTAL | `000010198007` | Changehost of Deceit – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SULPHUROUS VEIL | `000010198002` | Changehost of Deceit – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Chosen Cabal

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| COSTLY BLESSING | `000009655002` | Chosen Cabal – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EMPYRIC DESECRATION | `000009655003` | Chosen Cabal – Epic Deed Stratagem | 1 | Your turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INFERNO BOLTERS | `000009655004` | Chosen Cabal – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TZEENTCH’S BOON | `000009655005` | Chosen Cabal – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Devoted Thralls

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BESTIAL SURGE | `000009664005` | Devoted Thralls – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FELL SACRIFICE | `000009664004` | Devoted Thralls – Strategic Ploy Stratagem | 1 | Opponent’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FLESH CHANGE | `000009664003` | Devoted Thralls – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PSYCHIC INGRESS | `000009664002` | Devoted Thralls – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Fateseekers

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ENDURING ANIMUS | `000009673002` | Fateseekers – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INVISIBLE ASSAILANTS | `000009673005` | Fateseekers – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PHANTASMIC MUNITIONS | `000009673004` | Fateseekers – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STRATEGIC VISION | `000009673003` | Fateseekers – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Grand Coven

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARCANE FOCUS | `000010194006` | Grand Coven – Epic Deed Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DESECRATION OF WORLDS | `000010194005` | Grand Coven – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DESTINED BY FATE | `000010194003` | Grand Coven – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEVASTATING SORCERY | `000010194007` | Grand Coven – Battle Tactic Stratagem | 2 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EGOTISTICAL POWER | `000010194004` | Grand Coven – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PSYCHIC DOMINION | `000010194002` | Grand Coven – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Hexwarp Thrallband

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| KALEIDOSCOPIC TEMPEST | `000009742007` | Hexwarp Thrallband – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SCOURING WARPFLAME | `000009742006` | Hexwarp Thrallband – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STRANDS OF TIME | `000009742004` | Hexwarp Thrallband – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THROUGH THE VEIL | `000009742005` | Hexwarp Thrallband – Epic Deed Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WARDING HEX | `000009742002` | Hexwarp Thrallband – Epic Deed Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WRATH OF THE DOOMED | `000009742003` | Hexwarp Thrallband – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Rubricae Phalanx

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ARDENT AUTOMATA | `000010206002` | Rubricae Phalanx – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IMPLACABLE GUARDIANS | `000010206006` | Rubricae Phalanx – Strategic Ploy Stratagem | 2 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INEXORABLE ADVANCE | `000010206003` | Rubricae Phalanx – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INFERNAL FUSILLADE | `000010206004` | Rubricae Phalanx – Wargear Stratagem | 2 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REVENGE OF THE RUBRICAE | `000010206005` | Rubricae Phalanx – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNWAVERING PHALANX | `000010206007` | Rubricae Phalanx – Battle Tactic Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Warpforged Cabal

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CYBERSPIRIT MACHINATIONS | `000010210004` | Warpforged Cabal – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENSORCELLED INFUSION | `000010210006` | Warpforged Cabal – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HEX-MARKED ARMOUR | `000010210002` | Warpforged Cabal – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MALEVOLENT ANIMUS | `000010210005` | Warpforged Cabal – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MUTATE LANDSCAPE | `000010210003` | Warpforged Cabal – Epic Deed Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WARPFLAME GARGOYLES | `000010210007` | Warpforged Cabal – Wargear Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Warpmeld Pact

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLESSED TRANSMUTATIONS | `000010202005` | Warpmeld Pact – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DERANGED FEROCITY | `000010202004` | Warpmeld Pact – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GIFT OF CHANGE | `000010202002` | Warpmeld Pact – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TOUCHED BY TZEENTCH | `000010202006` | Warpmeld Pact – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TWISTED MIRAGE | `000010202007` | Warpmeld Pact – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WARPED VICISSITUDE | `000010202003` | Warpmeld Pact – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### Tyranids (`TYR`) — `https://wahapedia.ru/wh40k10ed/factions/tyranids`

#### Assimilation Swarm

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ABLATIVE CARAPACE | `000008413005` | Assimilation Swarm – Epic Deed Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BROODGUARD IMPULSE | `000008413002` | Assimilation Swarm – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RAPACIOUS HUNGER | `000008413007` | Assimilation Swarm – Battle Tactic Stratagem | 1 | Your turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RECLAIM BIOMASS | `000008413003` | Assimilation Swarm – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SECURE BIOMASS | `000008413006` | Assimilation Swarm – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TYRANNOFORMED | `000008413004` | Assimilation Swarm – Strategic Ploy Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Biotide

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| LIVING AVALANCHE | `000009700002` | Biotide – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ONRUSHING HORDE | `000009700005` | Biotide – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SQUIRMING MASSES | `000009700003` | Biotide – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWARM HUNTERS | `000009700004` | Biotide – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Boarding Swarm

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ADRENALISED SLAUGHTER | `000009691003` | Boarding Swarm – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| LITHE KILLERS | `000009691002` | Boarding Swarm – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PREDATORY POUNCE | `000009691005` | Boarding Swarm – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TALON-TIP SWARM | `000009691004` | Boarding Swarm – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Crusher Stampede

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| CORROSIVE VISCERA | `000008422002` | Crusher Stampede – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MASSIVE IMPACT | `000008422007` | Crusher Stampede – Epic Deed Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RAMPAGING MONSTROSITIES | `000008422003` | Crusher Stampede – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SAVAGE ROAR | `000008422004` | Crusher Stampede – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWARM-GUIDED SALVOES | `000008422006` | Crusher Stampede – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNTRAMMELLED FEROCITY | `000008422005` | Crusher Stampede – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Infestation Swarm

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| HUNTING GROUNDS | `000009725004` | Infestation Swarm – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HYPERADRENAL REFLEXES | `000009725002` | Infestation Swarm – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OUTFLANK | `000009725005` | Infestation Swarm – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PERVASIVE DREAD | `000009725003` | Infestation Swarm – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Invasion Fleet

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ADRENAL SURGE | `000008349003` | Invasion Fleet – Battle Tactic Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DEATH FRENZY | `000008349004` | Invasion Fleet – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENDLESS SWARM | `000008349007` | Invasion Fleet – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OVERRUN | `000008349005` | Invasion Fleet – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PREDATORY IMPERATIVE | `000008349006` | Invasion Fleet – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RAPID REGENERATION | `000008349002` | Invasion Fleet – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Subterranean Assault

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ADAPTIVE OPTIMISATION | `000010148002` | Subterranean Assault – Wargear Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENFILADING EMERGENCE | `000010148004` | Subterranean Assault – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REPLENISHING SWARMS | `000010148003` | Subterranean Assault – Wargear Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RETREAT BELOW | `000010148007` | Subterranean Assault – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWARMING ASSAULT | `000010148006` | Subterranean Assault – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TUNNEL NETWORK | `000010148005` | Subterranean Assault – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Synaptic Nexus

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| IMPERATIVE DOMINANCE | `000008556006` | Synaptic Nexus – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IRRESISTIBLE WILL | `000008556004` | Synaptic Nexus – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OVERRIDE INSTINCTS | `000008556007` | Synaptic Nexus – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REINFORCED HIVE NODE | `000008556005` | Synaptic Nexus – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SYNAPTIC CHANNELLING | `000008556003` | Synaptic Nexus – Battle Tactic Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE SMOTHERING SHADOW | `000008556002` | Synaptic Nexus – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Tyranid Attack

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BIO-ACID SURGE | `000009682002` | Tyranid Attack – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EXPENDABLE BIOMASS | `000009682004` | Tyranid Attack – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HIVE SIGHT | `000009682005` | Tyranid Attack – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PHAGIC SPORES | `000009682003` | Tyranid Attack – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Unending Swarm

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BOUNDING ADVANCE | `000008409006` | Unending Swarm – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PRESERVATION IMPERATIVE | `000008409007` | Unending Swarm – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWARMING MASSES | `000008409005` | Unending Swarm – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SYNAPTIC GOADING | `000008409002` | Unending Swarm – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TEEMING MASSES | `000008409004` | Unending Swarm – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNENDING WAVES | `000008409003` | Unending Swarm – Strategic Ploy Stratagem | 2 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Vanguard Onslaught

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ASSASSIN BEASTS | `000008418003` | Vanguard Onslaught – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HYPERSENSORY SCILLIA | `000008418005` | Vanguard Onslaught – Strategic Ploy Stratagem | 2 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INVISIBLE HUNTER | `000008418007` | Vanguard Onslaught – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SEEDED BROODS | `000008418004` | Vanguard Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SURPRISE ASSAULT | `000008418002` | Vanguard Onslaught – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNSEEN LURKERS | `000008418006` | Vanguard Onslaught – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Warrior Bioform Onslaught

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| PARASITIC PAYLOAD | `000009738006` | Warrior Bioform Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RESTORATIVE IMPULSE | `000009738004` | Warrior Bioform Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SPONTANEOUS HYPERCORROSION | `000009738003` | Warrior Bioform Onslaught – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SYNAPTIC AMPLIFICATION | `000009738002` | Warrior Bioform Onslaught – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SYNAPTIC MICRONODES | `000009738005` | Warrior Bioform Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SYNAPTIC SHIELD | `000009738007` | Warrior Bioform Onslaught – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### T’au Empire (`TAU`) — `https://wahapedia.ru/wh40k10ed/factions/t-au-empire`

#### Auxiliary Cadre

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ALIEN EXPERTISE | `000009840006` | Auxiliary Cadre – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EXPERIMENTAL MODIFICATIONS | `000009840002` | Auxiliary Cadre – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GUIDED FIRE | `000009840007` | Auxiliary Cadre – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| INTERLOCKING MANOUEVRES | `000009840004` | Auxiliary Cadre – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MULTISENSORY SCANNING | `000009840003` | Auxiliary Cadre – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PHEROMONE WAYPOINTS | `000009840005` | Auxiliary Cadre – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Experimental Prototype Cadre

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AUTOMATED REPAIR DRONES | `000009984002` | Experimental Prototype Cadre – Strategic Ploy Stratagem | 1 | Either player’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EXPERIMENTAL AMMUNITION | `000009984005` | Experimental Prototype Cadre – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EXPERIMENTAL WEAPONRY | `000009984004` | Experimental Prototype Cadre – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| NEUROWEB SYSTEM JAMMER | `000009984007` | Experimental Prototype Cadre – Wargear Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| REACTIVE IMPACT DAMPENERS | `000009984003` | Experimental Prototype Cadre – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THREAT ASSESSMENT ANALYSER | `000009984006` | Experimental Prototype Cadre – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Kauyon

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| A TEMPTING TRAP | `000008443002` | Kauyon – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| COMBAT EMBARKATION | `000008443005` | Kauyon – Wargear Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| COORDINATE TO ENGAGE | `000008443004` | Kauyon – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PHOTON GRENADES | `000008443006` | Kauyon – Wargear Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| POINT-BLANK AMBUSH | `000008443003` | Kauyon – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WALL OF MIRRORS | `000008443007` | Kauyon – Battle Tactic Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Kroot Hunting Pack

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| A TRAP WELL LAID | `000008822003` | Kroot Hunting Pack – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| EMP GRENADES | `000008822004` | Kroot Hunting Pack – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GUERRILLA WARRIORS | `000008822006` | Kroot Hunting Pack – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HIDDEN HUNTERS | `000008822007` | Kroot Hunting Pack – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| JOIN THE HUNT | `000008822002` | Kroot Hunting Pack – Battle Tactic Stratagem | 2 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE GRISLY FEAST | `000008822005` | Kroot Hunting Pack – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Kroot Raiding Party

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BOARDING BLADES | `000009646002` | Kroot Raiding Party – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BRUTE FORCE | `000009646004` | Kroot Raiding Party – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SWEEPING AMBUSH | `000009646003` | Kroot Raiding Party – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TANGLEBOMB BOLAS | `000009646005` | Kroot Raiding Party – Wargear Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Mont’ka

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AGGRESSIVE MOBILITY | `000008812003` | Mont’ka – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| COMBAT DEBARKATION | `000008812005` | Mont’ka – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| COUNTERFIRE DEFENCE SYSTEMS | `000008812007` | Mont’ka – Wargear Stratagem | 2 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FOCUSED FIRE | `000008812004` | Mont’ka – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PINPOINT COUNTER-OFFENSIVE | `000008812002` | Mont’ka – Battle Tactic Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PULSE ONSLAUGHT | `000008812006` | Mont’ka – Strategic Ploy Stratagem | 2 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Retaliation Cadre

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| FAIL-SAFE DETONATOR | `000008816002` | Retaliation Cadre – Epic Deed Stratagem | 2 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GRAV-INHIBITOR FIELD | `000008816007` | Retaliation Cadre – Strategic Ploy Stratagem | 1 | Opponent’s turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| STIMM INJECTORS | `000008816003` | Retaliation Cadre – Wargear Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE ARRO’KON PROTOCOL | `000008816005` | Retaliation Cadre – Battle Tactic Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE SHORTENED BLADE | `000008816004` | Retaliation Cadre – Strategic Ploy Stratagem | 2 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| THE TORCHSTAR GAMBIT | `000008816006` | Retaliation Cadre – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Starfire Cadre

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| FIRING LINE | `000009637002` | Starfire Cadre – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PULSE BARRAGE | `000009637005` | Starfire Cadre – Battle Tactic Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RESPONSIVE VOLLEY | `000009637004` | Starfire Cadre – Battle Tactic Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RETREATING FIRE | `000009637003` | Starfire Cadre – Strategic Ploy Stratagem | 1 | Your turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

### World Eaters (`WE`) — `https://wahapedia.ru/wh40k10ed/factions/world-eaters`

#### Berzerker Warband

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| APOPLECTIC FRENZY | `000008431006` | Berzerker Warband – Strategic Ploy Stratagem | 1 | Your turn | Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BERZERKER’S WRATH | `000008431007` | Berzerker Warband – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BLOOD OFFERING | `000008431002` | Berzerker Warband – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FRENZIED RESILIENCE | `000008431004` | Berzerker Warband – Battle Tactic Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HACK AND SLASH | `000008431003` | Berzerker Warband – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SKULLS FOR THE SKULL THRONE! | `000008431005` | Berzerker Warband – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Boarding Butchers

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| COWARDS’ BANE | `000009709005` | Boarding Butchers – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SAVAGE RESILIENCE | `000009709004` | Boarding Butchers – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| TERRIFYING SCREAMS | `000009709002` | Boarding Butchers – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNSTOPPABLE RAGE | `000009709003` | Boarding Butchers – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Cult of Blood

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLOODTHIRSTY HORDE | `000010075005` | Cult of Blood – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BLOODY VENGEANCE | `000010075002` | Cult of Blood – Epic Deed Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BRAZEN IDOL | `000010075007` | Cult of Blood – Epic Deed Stratagem | 2 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DRAWN TO THE SLAUGHTER | `000010075003` | Cult of Blood – Strategic Ploy Stratagem | 2 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FAIL NOT THE BLOOD GOD | `000010075006` | Cult of Blood – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IN THE SHADOW OF BRASS IDOLS | `000010075004` | Cult of Blood – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Goretrack Onslaught

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| AGGRESSIVE DISEMBARKATION | `000010087004` | Goretrack Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| ENDLESS PURSUIT OF VIOLENCE | `000010087002` | Goretrack Onslaught – Strategic Ploy Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FULL-THROTTLE ASSAULT | `000010087005` | Goretrack Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FURY UNLEASHED | `000010087007` | Goretrack Onslaught – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SMASH THROUGH | `000010087003` | Goretrack Onslaught – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| UNRELENTING ADVANCE | `000010087006` | Goretrack Onslaught – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Khorne Daemonkin

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| A WORTHY SKULL | `000010079004` | Khorne Daemonkin – Epic Deed Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BLESSING OF BURNING BLOOD | `000010079005` | Khorne Daemonkin – Battle Tactic Stratagem | 1 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DAEMONIC FURY | `000010079003` | Khorne Daemonkin – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DAEMONTIDE | `000010079006` | Khorne Daemonkin – Strategic Ploy Stratagem | 1 | Your turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MURDER-CALL | `000010079007` | Khorne Daemonkin – Strategic Ploy Stratagem | 1 | Opponent’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SUMMONED BY SLAUGHTER | `000010079002` | Khorne Daemonkin – Strategic Ploy Stratagem | 1 | Either player’s turn | Any phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Possessed Slaughterband

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| DAEMONIC RESISTANCE | `000010083002` | Possessed Slaughterband – Battle Tactic Stratagem | 2 | Either player’s turn | Shooting or Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| DAEMONIC STRENGTH | `000010083003` | Possessed Slaughterband – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| HORRIFYING VIOLENCE | `000010083007` | Possessed Slaughterband – Strategic Ploy Stratagem | 1 | Opponent’s turn | Command phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| IMMORTAL FURY | `000010083004` | Possessed Slaughterband – Battle Tactic Stratagem | 2 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RAPID MANIFESTATION | `000010083005` | Possessed Slaughterband – Strategic Ploy Stratagem | 1 | Your turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| WARP STALKERS | `000010083006` | Possessed Slaughterband – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Skullsworn

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| BLOOD RITE | `000009717002` | Skullsworn – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| FURIOUS MOMENTUM | `000009717003` | Skullsworn – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| RUINOUS RAMPAGE | `000009717004` | Skullsworn – Strategic Ploy Stratagem | 1 | Your turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| SHOCKING ONSLAUGHT | `000009717005` | Skullsworn – Battle Tactic Stratagem | 1 | Opponent’s turn | Movement or Charge phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |

#### Vessels of Wrath

| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |
|---|---:|---|---:|---|---|---|---|
| ASPIRE TO INFAMY | `000009848002` | Vessels of Wrath – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| BRAZEN CONTEMPT | `000009848007` | Vessels of Wrath – Battle Tactic Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| GORY DEDICATION | `000009848004` | Vessels of Wrath – Strategic Ploy Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| MEET FORCE WITH FORCE | `000009848006` | Vessels of Wrath – Strategic Ploy Stratagem | 1 | Opponent’s turn | Shooting phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| OVERSHADOWED BY NONE | `000009848003` | Vessels of Wrath – Battle Tactic Stratagem | 1 | Either player’s turn | Fight phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
| PUNISH THE CRAVEN | `000009848005` | Vessels of Wrath – Strategic Ploy Stratagem | 1 | Opponent’s turn | Movement phase | **Not implemented** | No effect logic currently wired (would just spend CP and log a warning). |
