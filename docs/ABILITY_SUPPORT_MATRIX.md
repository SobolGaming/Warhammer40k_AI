# Ability support matrix (Wahapedia)

Generated from `wahapedia_data/Abilities.json`, `wahapedia_data/Datasheets_abilities.json`, `wahapedia_data/Detachment_abilities.json`, and `wahapedia_data/Datasheets_detachment_abilities.json` (faction names/links from `wahapedia_data/Factions.json`).

**Definition of status**
- **Supported**: the engine recognizes and applies this mechanic (typically pattern-based).
- **Partial**: some support exists, but key restrictions/timing/text are not fully matched.
- **Not implemented**: no gameplay effect logic wired yet.

## Summary

- Abilities.json rows: 90 (core: 11, faction-specific: 79)
- Detachment_abilities.json rows: 197
- Datasheets_abilities.json rows: 6975

### Datasheet ability row types (from `Datasheets_abilities.json`)

| Type | Rows |
|---|---:|
| Datasheet | 2539 |
| Core | 2019 |
| Faction | 1449 |
| Wargear | 405 |
| Wargear profile | 229 |
| Special (правая колонка) | 168 |
| Fortification (левая колонка) | 94 |
| Primarch | 71 |
| Без заголовка | 1 |

## Recognized mechanics (pattern-based)

These mechanics are currently recognized by searching ability names/descriptions for text patterns:

- Supreme Commander (must be Warlord) (Supported)
- Pact of XXX: disallow specific Army Faction (Supported)
- Nurgle’s Gift (Aura): baseline Contagion Range debuff (-1 Toughness to enemies within 3/6/9") (Partial)
- Blessings of Khorne (CSM/WE) (Supported)
- Favoured of Khorne (Blessings rerolls) (Supported)
- Idol of the Blessed Blood (Blessings +1D6) (Supported)
- Reborn in Blood (Angron) (Supported)
- Deep Strike (Supported)
- Infiltrators (Supported)
- Scouts (Supported)
- Stealth (Supported)
- Lone Operative (Supported)
- Deadly Demise (Supported)
- Feel No Pain (Supported)
- Fights First (Supported)
- Fight on Death (Supported)
- Shoot on Death (Supported)
- Redeploy (Supported)
- Advance+Shoot (exact wording) (Supported)
- Fall Back+Shoot (exact wording) (Supported)
- Advance+Charge (exact wording) (Supported)
- Firing Deck (Supported)
- Gain CP on destroy (partial) (Partial)
- Heal on destroy (partial) (Partial)
- Plunging Fire (Supported)

## Core Abilities

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Deadly Demise | `000008339` | 718 | 718 | **Supported** | Deadly Demise |
| Deep Strike | `000008343` | 343 | 343 | **Supported** | Deep Strike |
| Feel No Pain | `000008338` | 113 | 113 | **Supported** | Feel No Pain |
| Fights First | `000008340` | 25 | 25 | **Supported** | Fights First |
| Firing Deck | `000008334` | 59 | 59 | **Supported** | Firing Deck |
| Hover | `000008342` | 57 | 57 | **Not implemented** |  |
| Infiltrators | `000008345` | 69 | 69 | **Supported** | Infiltrators |
| Leader | `000008346` | 406 | 406 | **Supported** | Attached Units supported: attachment eligibility + limits, bodyguard-first wound allocation, Precision allocation into visible CHARACTERS, characteristic delegation (Toughness/Leadership), separation deferred until end of attack sequence, and attached leaders do not double-count for deployment/objectives/reserves. |
| Lone Operative | `000008336` | 50 | 50 | **Supported** | Lone Operative |
| Scouts | `000008344` | 100 | 100 | **Supported** | Scouts |
| Stealth | `000008337` | 79 | 79 | **Supported** | Stealth |

## Faction Abilities

### Adepta Sororitas (`AS`) — `https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Acts of Faith | `000008466` | 36 | 36 | **Not implemented** |  |

### Adeptus Custodes (`AC`) — `https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Martial Ka’tah | `000008391` | 25 | 25 | **Not implemented** |  |

### Adeptus Mechanicus (`AdM`) — `https://wahapedia.ru/wh40k10ed/factions/adeptus-mechanicus`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Doctrina Imperatives | `000008382` | 36 | 36 | **Not implemented** |  |

### Adeptus Titanicus (`TL`) — `https://wahapedia.ru/wh40k10ed/factions/adeptus-titanicus`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Super-heavy Walker | `000008538` | 4 | 4 | **Not implemented** |  |

### Aeldari (`AE`) — `https://wahapedia.ru/wh40k10ed/factions/aeldari`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Battle Focus | `000009894` | 81 | 81 | **Supported** | Battle Focus tokens + Agile Manoeuvres (Swift as the Wind, Flitting Shadows, Star Engines, Sudden Strike, Opportunity Seized, Fade Back). |
| Disparate Paths | `000009896` | 19 | 19 | **Supported** | Army validation allows ASURYANI + HARLEQUINS/YNNARI keywords in Aeldari armies. |

### Astra Militarum (`AM`) — `https://wahapedia.ru/wh40k10ed/factions/astra-militarum`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Voice of Command | `000008377` | 16 | 16 | **Not implemented** |  |

### Chaos Daemons (`CD`) — `https://wahapedia.ru/wh40k10ed/factions/chaos-daemons`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Dark Pacts | `000008359` | 38 | 38 | **Not implemented** |  |
| The Shadow of Chaos | `000008433` | 68 | 68 | **Not implemented** |  |

### Chaos Knights (`QT`) — `https://wahapedia.ru/wh40k10ed/factions/chaos-knights`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Dark Pacts | `000008359` | 17 | 17 | **Not implemented** |  |
| Harbingers of Dread | `000008512` | 20 | 20 | **Not implemented** |  |
| Super-heavy Walker | `000008513` | 14 | 14 | **Not implemented** |  |

### Chaos Space Marines (`CSM`) — `https://wahapedia.ru/wh40k10ed/factions/chaos-space-marines`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Blessings of Khorne | `000008428` | 1 | 1 | **Supported** | Blessings of Khorne (CSM/WE). |
| Cabal of Sorcerers | `000008424` | 1 | 1 | **Supported** | Lone Operative |
| Dark Pacts | `000008359` | 103 | 103 | **Not implemented** |  |
| Nurgle’s Gift (Aura) | `000008396` | 1 | 1 | **Partial** | Nurgle’s Gift (Aura): baseline Contagion Range debuff (-1 Toughness to enemies within 3/6/9") |
| Thrill Seekers | `000009994` | 1 | 1 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |

### Death Guard (`DG`) — `https://wahapedia.ru/wh40k10ed/factions/death-guard`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Nurgle’s Gift (Aura) | `000008396` | 65 | 65 | **Partial** | Nurgle’s Gift (Aura): baseline Contagion Range debuff (-1 Toughness to enemies within 3/6/9") |
| Pact of Decay | `000010120` | 6 | 6 | **Supported** | Pact of Decay: disallow Plague Legions as Army Faction. |

### Drukhari (`DRU`) — `https://wahapedia.ru/wh40k10ed/factions/drukhari`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Battle Focus | `000009894` | 10 | 10 | **Supported** | Battle Focus tokens + Agile Manoeuvres (Swift as the Wind, Flitting Shadows, Star Engines, Sudden Strike, Opportunity Seized, Fade Back). |
| Disparate Paths | `000009896` | 8 | 8 | **Supported** | Army validation allows DRUKHARI + HARLEQUINS/YNNARI keywords. |
| Power from Pain | `000008507` | 30 | 30 | **Not implemented** |  |

### Emperor’s Children (`EC`) — `https://wahapedia.ru/wh40k10ed/factions/emperor-s-children`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Pact of Excess | `000009995` | 5 | 5 | **Supported** | Pact of Excess: disallow Legions of Excess as Army Faction. |
| Thrill Seekers | `000009994` | 17 | 17 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |

### Genestealer Cults (`GC`) — `https://wahapedia.ru/wh40k10ed/factions/genestealer-cults`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Cult Ambush | `000008501` | 7 | 7 | **Not implemented** |  |
| Shadow in the Warp | `000000707` | 4 | 4 | **Not implemented** |  |
| Synapse | `000000705` | 13 | 13 | **Not implemented** |  |

### Grey Knights (`GK`) — `https://wahapedia.ru/wh40k10ed/factions/grey-knights`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Gate of Infinity | `000010345` | 20 | 20 | **Not implemented** |  |

### Imperial Agents (`AoI`) — `https://wahapedia.ru/wh40k10ed/factions/imperial-agents`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Assigned Agents | `000008452` | 45 | 45 | **Not implemented** |  |
| Kill Team | `000008519` | 5 | 5 | **Not implemented** |  |

### Imperial Knights (`QI`) — `https://wahapedia.ru/wh40k10ed/factions/imperial-knights`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Code Chivalric | `000008458` | 21 | 21 | **Not implemented** |  |
| Doctrina Imperatives | `000008382` | 5 | 5 | **Not implemented** |  |
| Super-heavy Walker | `000008460` | 18 | 18 | **Not implemented** |  |

### Leagues of Votann (`LoV`) — `https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Prioritised Efficiency | `000010432` | 21 | 21 | **Not implemented** |  |

### Necrons (`NEC`) — `https://wahapedia.ru/wh40k10ed/factions/necrons`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Reanimation Protocols | `000008369` | 63 | 63 | **Not implemented** |  |

### Orks (`ORK`) — `https://wahapedia.ru/wh40k10ed/factions/orks`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Waaagh! | `000003676` | 86 | 86 | **Supported** | Advance+Charge (exact wording) |

### Space Marines (`SM`) — `https://wahapedia.ru/wh40k10ed/factions/space-marines`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Assigned Agents | `000008452` | 1 | 1 | **Not implemented** |  |
| Curse of the Wulfen | `000010256` | 4 | 4 | **Not implemented** |  |
| Kill Team | `000008519` | 1 | 1 | **Not implemented** |  |
| Mission Tactics | `000008521` | 10 | 10 | **Not implemented** |  |
| Oath of Moment | `000008350` | 275 | 275 | **Not implemented** |  |
| Templar Vows | `000008526` | 19 | 19 | **Supported** | Advance+Charge (exact wording) |

### Thousand Sons (`TS`) — `https://wahapedia.ru/wh40k10ed/factions/thousand-sons`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Cabal of Sorcerers | `000008424` | 13 | 13 | **Supported** | Lone Operative |
| Pact of Sorcery | `000010190` | 6 | 6 | **Supported** | Pact of Sorcery: disallow Scintillating Legions as Army Faction. |

### Tyranids (`TYR`) — `https://wahapedia.ru/wh40k10ed/factions/tyranids`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Shadow in the Warp | `000000707` | 16 | 16 | **Not implemented** |  |
| Synapse | `000000705` | 55 | 55 | **Not implemented** |  |

### T’au Empire (`TAU`) — `https://wahapedia.ru/wh40k10ed/factions/t-au-empire`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| For the Greater Good | `000008439` | 41 | 41 | **Not implemented** |  |

### Unaligned Forces (`UN`) — `https://wahapedia.ru/wh40k10ed/factions/unaligned-forces`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Unaligned Forces | `000008537` | 20 | 20 | **Not implemented** |  |

### World Eaters (`WE`) — `https://wahapedia.ru/wh40k10ed/factions/world-eaters`

| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Blessings of Khorne | `000008428` | 53 | 53 | **Supported** | Blessings of Khorne (CSM/WE). |
| Pact of Blood | `000010071` | 5 | 5 | **Supported** | Pact of Blood: disallow Blood Legions as Army Faction. |

## Detachment Abilities

### Adepta Sororitas (`AS`) — `https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas`

#### Army of Faith

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Sacred Rites | `000009036` | 36 | 36 | **Not implemented** |  |

#### Bringers of Flame

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Fervent Purgation | `000009032` | 36 | 36 | **Not implemented** |  |

#### Champions of Faith

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Righteous Purpose | `000009830` | 36 | 36 | **Not implemented** |  |

#### Hallowed Martyrs

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| The Blood of Martyrs | `000008468` | 36 | 36 | **Not implemented** |  |

#### Penitent Host

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Desperate for Redemption | `000009028` | 5 | 5 | **Not implemented** |  |

### Adeptus Custodes (`AC`) — `https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes`

#### Auric Champions

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Assemblage of Might | `000008929` | 8 | 8 | **Not implemented** |  |

#### Lions of the Emperor

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Against All Odds | `000009986` | 20 | 20 | **Not implemented** |  |

#### Null Maiden Vigil

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Creeping Dread (Aura) | `000008924` | 6 | 6 | **Not implemented** |  |

#### Shield Host

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Martial Mastery | `000008393` | 25 | 25 | **Not implemented** |  |

#### Solar Spearhead

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Auric Armour | `000009752` | 9 | 9 | **Not implemented** |  |

#### Talons Of The Emperor

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Revered Companions | `000008920` | 31 | 31 | **Supported** | Feel No Pain |

### Adeptus Mechanicus (`AdM`) — `https://wahapedia.ru/wh40k10ed/factions/adeptus-mechanicus`

#### Cohort Cybernetica

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Cyber-Psalm Programming | `000008571` | 2 | 2 | **Not implemented** |  |

#### Data-Psalm Conclave

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Benedictions Of The Omnissiah | `000008563` | 12 | 12 | **Not implemented** |  |

#### Explorator Maniple

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Acquisition At Any Cost | `000008567` | 36 | 36 | **Not implemented** |  |

#### Haloscreed Battle Clade

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Noospheric Transference | `000009744` | 36 | 36 | **Supported** | Advance+Charge (exact wording), Stealth |

#### Rad-Zone Corps

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Rad-bombardment | `000008384` | 36 | 36 | **Not implemented** |  |

#### Skitarii Hunter Cohort

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Stealth Optimisation | `000008559` | 13 | 13 | **Supported** | Stealth |

### Aeldari (`AE`) — `https://wahapedia.ru/wh40k10ed/factions/aeldari`

#### Armoured Warhost

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Skilled Crews | `000009768` | 23 | 23 | **Not implemented** |  |

#### Aspect Host

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Path of the Warrior | `000009926` | 16 | 16 | **Not implemented** |  |

#### Devoted of Ynnead

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Strength from Death | `000009918` | 8 | 8 | **Supported** | Fights First |

#### Ghosts of the Webway

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Acrobatic Onslaught | `000009914` | 8 | 8 | **Not implemented** |  |

#### Guardian Battlehost

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Defend at All Costs | `000009910` | 7 | 7 | **Not implemented** |  |

#### Serpent’s Brood

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Boons of the Brood | `000010648` | 8 | 8 | **Not implemented** |  |

#### Spirit Conclave

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Shepherds of the Dead | `000009906` | 11 | 11 | **Not implemented** |  |

#### Warhost

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Martial Grace | `000009898` | 93 | 93 | **Not implemented** |  |

#### Windrider Host

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Ride the Wind | `000009902` | 7 | 7 | **Not implemented** |  |

### Astra Militarum (`AM`) — `https://wahapedia.ru/wh40k10ed/factions/astra-militarum`

#### Bridgehead Strike

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Fire Zone Purge | `000009799` | 3 | 3 | **Not implemented** |  |
| Only the Best | `000009798` | 44 | 44 | **Not implemented** |  |

#### Combined Arms

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Born Soldiers | `000008379` | 67 | 67 | **Not implemented** |  |

#### Grizzled Company

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Ruthless Discipline | `000010636` | 128 | 128 | **Not implemented** |  |

#### Hammer of the Emperor

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Iron Tread | `000009864` | 41 | 41 | **Not implemented** |  |

#### Mechanised Assault

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Armoured Fist | `000009860` | 43 | 43 | **Not implemented** |  |

#### Recon Element

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Masters of Camouflage | `000009868` | 30 | 30 | **Not implemented** |  |

#### Siege Regiment

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Artillery Support | `000009856` | 128 | 128 | **Supported** | Stealth |

### Chaos Daemons (`CD`) — `https://wahapedia.ru/wh40k10ed/factions/chaos-daemons`

#### Blood Legion

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Blood Tainted | `000009814` | 14 | 14 | **Not implemented** |  |
| Murdercall | `000009813` | 14 | 14 | **Not implemented** |  |

#### Daemonic Incursion

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Warp Rifts | `000008436` | 68 | 68 | **Supported** | Deep Strike |

#### Legion of Excess

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Beguiling Aura | `000009804` | 18 | 18 | **Not implemented** |  |
| Seductive Gambit | `000009805` | 18 | 18 | **Supported** | Fights First |

#### Plague Legion

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Melancholic Miasma | `000009818` | 15 | 15 | **Not implemented** |  |

#### Scintillating Legion

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Fates in Flux | `000009809` | 18 | 18 | **Not implemented** |  |

#### Shadow Legion

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| First Prince of Chaos | `000009978` | 87 | 87 | **Supported** | Advance+Shoot (exact wording), Deep Strike |
| Thralls of the First Prince | `000009976` | 87 | 87 | **Not implemented** |  |

### Chaos Knights (`QT`) — `https://wahapedia.ru/wh40k10ed/factions/chaos-knights`

#### Houndpack Lance

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Marked Prey | `000010311` | 6 | 6 | **Not implemented** |  |

#### Iconoclast Fiefdom

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Dreaded Masters | `000009764` | 14 | 14 | **Not implemented** |  |

#### Infernal Lance

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Malefic Surge | `000010303` | 20 | 20 | **Supported** | Feel No Pain |

#### Lords of Dread

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Tyrannical Court | `000010307` | 20 | 20 | **Not implemented** |  |

#### Traitoris Lance

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Paragons of Terror | `000008518` | 20 | 20 | **Not implemented** |  |

### Chaos Space Marines (`CSM`) — `https://wahapedia.ru/wh40k10ed/factions/chaos-space-marines`

#### Cabal of Chaos

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Empyric Wellspring | `000010150` | 107 | 107 | **Not implemented** |  |

#### Chaos Cult

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Desperate Devotion | `000008979` | 17 | 17 | **Not implemented** |  |

#### Creations of Bile

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Experimental Augmentations | `000009772` | 33 | 33 | **Not implemented** |  |

#### Deceptors

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Masters of Misdirection | `000008963` | 29 | 29 | **Supported** | Infiltrators |

#### Dread Talons

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Terror Descends (Aura) | `000008971` | 107 | 107 | **Not implemented** |  |

#### Fellhammer Siege-host

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Iron Fortitude | `000008975` | 90 | 90 | **Not implemented** |  |

#### Nightmare Hunt

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Terror Made Manifest | `000010640` | 107 | 107 | **Not implemented** |  |

#### Pactbound Zealots

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Marks of Chaos | `000008362` | 107 | 107 | **Not implemented** |  |

#### Renegade Raiders

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Raiders and Reavers | `000008967` | 107 | 107 | **Not implemented** |  |

#### Soulforged Warpack

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Debt to the Soul Forge | `000008984` | 11 | 11 | **Not implemented** |  |

#### Veterans of the Long War

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Focus of Hatred | `000008959` | 90 | 90 | **Not implemented** |  |

### Death Guard (`DG`) — `https://wahapedia.ru/wh40k10ed/factions/death-guard`

#### Champions of Contagion

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Manifold Maladies | `000010130` | 61 | 61 | **Partial** | Nurgle’s Gift (Aura): baseline Contagion Range debuff (-1 Toughness to enemies within 3/6/9") |

#### Death Lord’s Chosen

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Deadly Vectors | `000010142` | 61 | 61 | **Not implemented** |  |

#### Flyblown Host

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Verminous Haze | `000009728` | 18 | 18 | **Supported** | Scouts, Stealth |

#### Mortarion’s Hammer

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Miasmic Bombardment | `000010126` | 61 | 61 | **Not implemented** |  |

#### Shamblerot Vectorium

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Numberless Horde | `000010138` | 67 | 67 | **Not implemented** |  |

#### Tallyband Summoners

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Reverberant Rancidity | `000010134` | 67 | 67 | **Partial** | Nurgle’s Gift (Aura): baseline Contagion Range debuff (-1 Toughness to enemies within 3/6/9") |

#### Virulent Vectorium

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Worldblight | `000010122` | 61 | 61 | **Partial** | Nurgle’s Gift (Aura): baseline Contagion Range debuff (-1 Toughness to enemies within 3/6/9") |

### Drukhari (`DRU`) — `https://wahapedia.ru/wh40k10ed/factions/drukhari`

#### Covenite Coterie

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Stitchflesh Abominations | `000010583` | 6 | 6 | **Not implemented** |  |

#### Kabalite Cartel

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Murderous Agenda | `000010587` | 12 | 12 | **Not implemented** |  |

#### Realspace Raiders

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Alliance of Agony | `000010572` | 9 | 9 | **Not implemented** |  |

#### Reaper’s Wager

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Callous Competition | `000009780` | 43 | 43 | **Not implemented** |  |

#### Skysplinter Assault

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Rain Of Cruelty | `000008714` | 18 | 18 | **Not implemented** |  |

#### Spectacle of Spite

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Combat Drugs | `000010579` | 5 | 5 | **Not implemented** |  |

### Emperor’s Children (`EC`) — `https://wahapedia.ru/wh40k10ed/factions/emperor-s-children`

#### Carnival of Excess

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Daemonic Empowerment | `000010009` | 9 | 9 | **Not implemented** |  |

#### Coterie of the Conceited

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Pledges to the Dark Prince | `000010013` | 17 | 17 | **Not implemented** |  |

#### Court of the Phoenician

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Master of the Pageant | `000010653` | 17 | 17 | **Not implemented** |  |
| Sensational Performance | `000010652` | 17 | 17 | **Not implemented** |  |

#### Mercurial Host

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Quicksilver Grace | `000009997` | 17 | 17 | **Not implemented** |  |

#### Peerless Bladesmen

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Exquisite Swordsmanship | `000010001` | 17 | 17 | **Not implemented** |  |

#### Rapid Evisceration

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Mechanised Murder | `000010005` | 11 | 11 | **Not implemented** |  |

#### Slaanesh’s Chosen

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Internal Rivalries | `000010017` | 7 | 7 | **Not implemented** |  |

### Genestealer Cults (`GC`) — `https://wahapedia.ru/wh40k10ed/factions/genestealer-cults`

#### Biosanctic Broodsurge

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Hypermorphic Fury | `000009074` | 3 | 3 | **Not implemented** |  |

#### Brood Brother Auxilia

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Integrated Tactics | `000009082` | 123 | 123 | **Not implemented** |  |

#### Final Day

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Psionic Parasitism | `000009826` | 36 | 36 | **Not implemented** |  |

#### Host of Ascension

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| A Perfect Ambush | `000009066` | 25 | 25 | **Not implemented** |  |

#### Outlander Claw

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Rapid Takeover | `000009078` | 12 | 12 | **Not implemented** |  |

#### Xenocreed Congregation

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Unquestioning Fanaticism | `000009070` | 4 | 4 | **Supported** | Feel No Pain |

### Grey Knights (`GK`) — `https://wahapedia.ru/wh40k10ed/factions/grey-knights`

#### Augurium Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Prescient Redeployment | `000010363` | 31 | 31 | **Supported** | Redeploy |

#### Banishers

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Channelled Force | `000010355` | 31 | 31 | **Not implemented** |  |

#### Brotherhood Strike

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Fury of Titan | `000010347` | 31 | 31 | **Supported** | Deep Strike |

#### Hallowed Conclave

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Duty Before All | `000010351` | 9 | 9 | **Supported** | Fall Back+Shoot (exact wording) |

#### Sanctic Spearhead

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Mailed Fist | `000010359` | 14 | 14 | **Not implemented** |  |

#### Warpbane Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Hallowed Ground | `000009776` | 31 | 31 | **Not implemented** |  |

### Imperial Agents (`AoI`) — `https://wahapedia.ru/wh40k10ed/factions/imperial-agents`

#### Imperialis Fleet

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| At all Costs | `000009137` | 45 | 45 | **Not implemented** |  |

#### Ordo Hereticus Purgation Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Root out Heresy | `000009129` | 14 | 14 | **Not implemented** |  |

#### Ordo Malleus Daemon Hunters

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Destroy the Daemonic | `000009133` | 9 | 9 | **Not implemented** |  |

#### Ordo Xenos Alien Hunters

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Deathwatch Mission Tactics | `000009125` | 12 | 12 | **Not implemented** |  |

#### Veiled Blade Elimination Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Extremis Sanction | `000009756` | 4 | 4 | **Not implemented** |  |

### Imperial Knights (`QI`) — `https://wahapedia.ru/wh40k10ed/factions/imperial-knights`

#### Gate Warden Lance

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Dauntless Defenders | `000010496` | 22 | 22 | **Not implemented** |  |

#### Questor Forgepact

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Cogbound Alliance | `000009760` | 27 | 27 | **Not implemented** |  |

#### Questoris Companions

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Heroes of Legend | `000010500` | 22 | 22 | **Not implemented** |  |
| Valour’s Reward | `000010501` | 22 | 22 | **Not implemented** |  |

#### Spearhead-At-Arms

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Knightly Teachings | `000010505` | 22 | 22 | **Not implemented** |  |

#### Valourstrike Lance

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Bold Gallantry | `000010492` | 22 | 22 | **Not implemented** |  |

### Leagues of Votann (`LoV`) — `https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann`

#### Brandfast Oathband

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Mobile Sensor Relays | `000010446` | 19 | 19 | **Not implemented** |  |

#### Dêlve Assault Shift

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Fury From The Dêlve | `000010442` | 1 | 1 | **Supported** | Deep Strike |

#### Hearthband

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Methodical Annihilation | `000009822` | 21 | 21 | **Not implemented** |  |

#### Hearthfyre Arsenal

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Optimal Application | `000010450` | 6 | 6 | **Not implemented** |  |

#### Needgaârd Oathband

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Martial Leverage | `000010434` | 21 | 21 | **Not implemented** |  |

#### Persecution Prospect

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Assailed From Every Angle | `000010438` | 21 | 21 | **Not implemented** |  |

### Necrons (`NEC`) — `https://wahapedia.ru/wh40k10ed/factions/necrons`

#### Annihilation Legion

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Annihilation Protocol | `000008542` | 8 | 8 | **Not implemented** |  |

#### Awakened Dynasty

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Command Protocols | `000008370` | 16 | 16 | **Not implemented** |  |

#### Canoptek Court

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Power Matrix | `000008545` | 17 | 17 | **Not implemented** |  |

#### Hypercrypt Legion

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Hyperphasing | `000008553` | 63 | 63 | **Not implemented** |  |

#### Obeisance Phalanx

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Worthy Foes | `000008549` | 11 | 11 | **Not implemented** |  |

#### Starshatter Arsenal

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Relentless Onslaught | `000009748` | 63 | 63 | **Not implemented** |  |

### Orks (`ORK`) — `https://wahapedia.ru/wh40k10ed/factions/orks`

#### Bully Boyz

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Da Boss Is Watchin’ | `000008884` | 11 | 11 | **Not implemented** |  |

#### Da Big Hunt

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Da Hunt Is On | `000008867` | 9 | 9 | **Not implemented** |  |

#### Dread Mob

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Try Dat Button! | `000008875` | 17 | 17 | **Not implemented** |  |

#### Green Tide

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Mob Mentality | `000008880` | 1 | 1 | **Not implemented** |  |

#### Kult of Speed

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Adrenaline Junkies | `000008871` | 23 | 23 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |

#### More Dakka!

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Dakka! Dakka! Dakka! | `000009990` | 41 | 41 | **Not implemented** |  |

#### Taktikal Brigade

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Lissen ’Ere | `000009794` | 17 | 17 | **Supported** | Stealth |

#### War Horde

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Get Stuck In | `000008365` | 86 | 86 | **Not implemented** |  |

### Space Marines (`SM`) — `https://wahapedia.ru/wh40k10ed/factions/space-marines`

#### 1st Company Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Extremis-level Threat | `000008493` | 296 | 296 | **Not implemented** |  |

#### Angelic Inheritors

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Legacy of the Angel | `000009834` | 296 | 296 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |

#### Anvil Siege Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Shield of the Imperium | `000008473` | 296 | 296 | **Not implemented** |  |

#### Black Spear Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Mission Tactics | `000008521` | 283 | 283 | **Not implemented** |  |

#### Blade of Ultramar

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Mastered Doctrines | `000010632` | 296 | 296 | **Supported** | Advance+Charge (exact wording), Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |

#### Champions of Fenris

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| The Great Wolf Watches | `000009850` | 181 | 181 | **Not implemented** |  |

#### Companions of Vehemence

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Righteous Fervour | `000010391` | 296 | 296 | **Not implemented** |  |

#### Company of Hunters

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Masters Of Manoeuvre | `000008777` | 296 | 296 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |

#### Emperor’s Shield

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Wrath of Dorn | `000010459` | 296 | 296 | **Not implemented** |  |

#### Firestorm Assault Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Close-range Eradication | `000008481` | 296 | 296 | **Not implemented** |  |

#### Forgefather’s Seekers

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Vulkan’s Quest | `000010367` | 296 | 296 | **Not implemented** |  |

#### Gladius Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Combat Doctrines | `000008355` | 296 | 296 | **Supported** | Advance+Charge (exact wording), Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |

#### Godhammer Assault Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Shock and Awe | `000010399` | 296 | 296 | **Not implemented** |  |

#### Hammer of Avernii

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Calculated Annihilation | `000010620` | 296 | 296 | **Not implemented** |  |
| Recalculating | `000010621` | 296 | 296 | **Not implemented** |  |

#### Inner Circle Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Vowed Target | `000008773` | 21 | 21 | **Not implemented** |  |

#### Ironstorm Spearhead

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Armoured Wrath | `000008477` | 296 | 296 | **Not implemented** |  |

#### Liberator Assault Group

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Red Thirst | `000008374` | 296 | 296 | **Not implemented** |  |

#### Librarius Conclave

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Psychic Disciplines | `000009784` | 10 | 10 | **Not implemented** |  |

#### Lion’s Blade Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| In The Lion’s Claws | `000009732` | 296 | 296 | **Not implemented** |  |

#### Rage-cursed Onslaught

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Maddened Ferocity | `000010644` | 296 | 296 | **Not implemented** |  |

#### Saga of the Beastslayer

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Legendary Slayers | `000010268` | 296 | 296 | **Not implemented** |  |

#### Saga of the Bold

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Heroes All | `000010264` | 41 | 41 | **Not implemented** |  |

#### Saga of the Great Wolf

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Howling Onslaught | `000010658` | 296 | 296 | **Not implemented** |  |
| Master of Wolves | `000010657` | 296 | 296 | **Not implemented** |  |

#### Saga of the Hunter

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Pack’s Quarry | `000010260` | 41 | 41 | **Not implemented** |  |

#### Shadowmark Talon

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Masters of Shadow | `000010463` | 296 | 296 | **Not implemented** |  |
| Unparalleled Tactician | `000010464` | 1 | 1 | **Not implemented** |  |

#### Spearpoint Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Storm-swift Onslaught | `000010626` | 296 | 296 | **Supported** | Advance+Charge (exact wording) |
| Wrath of the First Khan | `000010627` | 296 | 296 | **Not implemented** |  |

#### Stormlance Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Lightning Assault | `000008485` | 296 | 296 | **Supported** | Advance+Charge (exact wording) |

#### The Angelic Host

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Upon Wings of Fire | `000009189` | 22 | 22 | **Supported** | Deep Strike |

#### The Lost Brethren

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| A Noble Death in Combat | `000009185` | 8 | 8 | **Not implemented** |  |

#### Unforgiven Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Grim Resolve | `000008770` | 296 | 296 | **Not implemented** |  |

#### Vanguard Spearhead

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Shadow Masters | `000008489` | 296 | 296 | **Not implemented** |  |

#### Vindication Task Force

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Purge and Sanctify | `000010395` | 9 | 9 | **Not implemented** |  |

#### Wrath of the Rock

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Dutiful Tenacity | `000010154` | 185 | 185 | **Not implemented** |  |

#### Wrathful Procession

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Zealous Litanies | `000009842` | 296 | 296 | **Not implemented** |  |

### Thousand Sons (`TS`) — `https://wahapedia.ru/wh40k10ed/factions/thousand-sons`

#### Changehost of Deceit

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Infernal Pacts | `000010196` | 60 | 60 | **Not implemented** |  |

#### Grand Coven

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Kindred Sorcery | `000010192` | 54 | 54 | **Not implemented** |  |

#### Hexwarp Thrallband

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Flow of Magic | `000009740` | 54 | 54 | **Not implemented** |  |

#### Rubricae Phalanx

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| All is Dust | `000010204` | 2 | 2 | **Not implemented** |  |

#### Warpforged Cabal

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Warpfire Infusion | `000010208` | 36 | 36 | **Supported** | Deadly Demise |

#### Warpmeld Pact

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Warpmeld Sacrifice | `000010200` | 6 | 6 | **Not implemented** |  |

### Tyranids (`TYR`) — `https://wahapedia.ru/wh40k10ed/factions/tyranids`

#### Assimilation Swarm

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Feed the Swarm | `000008411` | 5 | 5 | **Not implemented** |  |

#### Crusher Stampede

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Enraged Behemoths | `000008403` | 27 | 27 | **Not implemented** |  |

#### Invasion Fleet

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Hyper-adaptations | `000008356` | 55 | 55 | **Not implemented** |  |

#### Subterranean Assault

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Surprise Assault | `000010146` | 55 | 55 | **Not implemented** |  |

#### Synaptic Nexus

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Synaptic Imperatives | `000008420` | 55 | 55 | **Not implemented** |  |

#### Unending Swarm

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Insurmountable Odds | `000008407` | 4 | 4 | **Not implemented** |  |

#### Vanguard Onslaught

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Questing Tendrils | `000008415` | 55 | 55 | **Not implemented** |  |

#### Warrior Bioform Onslaught

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Leader-beasts | `000009736` | 3 | 3 | **Not implemented** |  |

### T’au Empire (`TAU`) — `https://wahapedia.ru/wh40k10ed/factions/t-au-empire`

#### Auxiliary Cadre

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Integrated Command Structure | `000009838` | 62 | 62 | **Supported** | Stealth |

#### Experimental Prototype Cadre

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Superior Craftsmanship | `000009982` | 62 | 62 | **Not implemented** |  |

#### Kauyon

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Patient Hunter | `000008441` | 62 | 62 | **Not implemented** |  |

#### Kroot Hunting Pack

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Hunter’s Instincts | `000008818` | 11 | 11 | **Not implemented** |  |
| Skirmish Fighters | `000008819` | 11 | 11 | **Not implemented** |  |

#### Mont’ka

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Killing Blow | `000008810` | 62 | 62 | **Not implemented** |  |

#### Retaliation Cadre

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Bonded Heroes | `000008814` | 17 | 17 | **Not implemented** |  |

### World Eaters (`WE`) — `https://wahapedia.ru/wh40k10ed/factions/world-eaters`

#### Berzerker Warband

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Relentless Rage | `000008430` | 53 | 53 | **Supported** | Berzerker Warband detachment ability (WE). |

#### Cult of Blood

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Idols of Khorne | `000010073` | 11 | 11 | **Supported** | Idol of the Blessed Blood (Blessings +1D6) |

#### Goretrack Onslaught

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Rush to the Fray | `000010085` | 53 | 53 | **Not implemented** |  |

#### Khorne Daemonkin

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Blood Tithe | `000010077` | 58 | 58 | **Not implemented** | World Eaters – Khorne Daemonkin detachment mechanic; not implemented yet. |

#### Possessed Slaughterband

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Brazen Fury | `000010081` | 3 | 3 | **Not implemented** |  |

#### Vessels of Wrath

| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |
|---|---:|---:|---:|---|---|
| Wrath of Khorne | `000009846` | 9 | 9 | **Supported** | Blessings of Khorne (World Eaters) |

## Datasheet-sourced Abilities (no `ability_id`)

These come directly from `Datasheets_abilities.json` rows where `ability_id` is empty (per-datasheet named rules). They are grouped by the row `type` field (e.g. Datasheet/Wargear/Wargear profile/Special/etc.).

### Datasheet

#### Adepta Sororitas (`AS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Cherub | 3 | 3 | **Not implemented** |  |
| Sacred Command | 2 | 2 | **Not implemented** |  |
| Abbess Sanctorum | 1 | 1 | **Not implemented** |  |
| Angelic Ascent | 1 | 1 | **Not implemented** |  |
| Anguish of the Unredeemed | 1 | 1 | **Not implemented** |  |
| Auto-Tapestry of the Emperor’s Judgement | 1 | 1 | **Not implemented** |  |
| Cherubs | 1 | 1 | **Not implemented** |  |
| Consecrated Ground | 1 | 1 | **Not implemented** |  |
| Daemonbreaker | 1 | 1 | **Not implemented** |  |
| Death Cult | 1 | 1 | **Not implemented** |  |
| Defenders of the Faith | 1 | 1 | **Not implemented** |  |
| Devastating Refrain | 1 | 1 | **Supported** | Deadly Demise |
| Divine Deliverance | 1 | 1 | **Not implemented** |  |
| Embodied Prophecy | 1 | 1 | **Not implemented** |  |
| Emergency Combat Embarkation | 1 | 1 | **Not implemented** |  |
| Endless Suffering | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Executioner of Heretics (Aura) | 1 | 1 | **Not implemented** |  |
| Extremis Trigger Word | 1 | 1 | **Not implemented** |  |
| Fiery Conviction | 1 | 1 | **Not implemented** |  |
| Fury of the Righteous | 1 | 1 | **Not implemented** |  |
| Healing Tears | 1 | 1 | **Not implemented** |  |
| Holy Cover | 1 | 1 | **Not implemented** |  |
| Holy Judgement | 1 | 1 | **Not implemented** |  |
| Impetuous Fervour | 1 | 1 | **Not implemented** |  |
| Instrument of the Emperor’s Wrath | 1 | 1 | **Not implemented** |  |
| Laud Hailer | 1 | 1 | **Not implemented** |  |
| Lifewards | 1 | 1 | **Supported** | Feel No Pain |
| Litany of Deeds | 1 | 1 | **Not implemented** |  |
| Medicus Ministorum | 1 | 1 | **Supported** | Feel No Pain |
| Ministorum Sermon | 1 | 1 | **Not implemented** |  |
| Miraculous Intervention | 1 | 1 | **Not implemented** |  |
| Mysterious Saviours | 1 | 1 | **Not implemented** |  |
| Overseer of Redemption | 1 | 1 | **Not implemented** |  |
| Purge and Cleanse | 1 | 1 | **Not implemented** |  |
| Rapturous Blows | 1 | 1 | **Not implemented** |  |
| Recount the Deeds of the Saints | 1 | 1 | **Not implemented** |  |
| Relics of the Matriarchs | 1 | 1 | **Not implemented** |  |
| Righteous Awareness | 1 | 1 | **Not implemented** |  |
| Righteous Paragons | 1 | 1 | **Not implemented** |  |
| Righteous Repugnance | 1 | 1 | **Not implemented** |  |
| Righteous Smiting | 1 | 1 | **Not implemented** |  |
| Rites of Castigation | 1 | 1 | **Not implemented** |  |
| Sacred Healing | 1 | 1 | **Not implemented** |  |
| Self Repair | 1 | 1 | **Not implemented** |  |
| Solemn Procession | 1 | 1 | **Not implemented** |  |
| Spiritual Fortitude | 1 | 1 | **Supported** | Feel No Pain |
| Stanchion of Holy Martyrs | 1 | 1 | **Not implemented** |  |
| Stirring Rhetoric | 1 | 1 | **Not implemented** |  |
| Storm of Retribution | 1 | 1 | **Not implemented** |  |
| Sworn Protectors | 1 | 1 | **Not implemented** |  |
| The Emperor’s Grace | 1 | 1 | **Not implemented** |  |
| The Pulpit of Saint Holline’s Basilica | 1 | 1 | **Not implemented** |  |
| Unflinching Determination | 1 | 1 | **Not implemented** |  |
| Zealot | 1 | 1 | **Not implemented** |  |

#### Adeptus Custodes (`AC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Daughters of the Abyss | 4 | 4 | **Supported** | Feel No Pain |
| Strategic Mastery | 3 | 3 | **Not implemented** |  |
| Daughter of the Abyss | 2 | 2 | **Supported** | Feel No Pain |
| From Golden Light | 2 | 2 | **Not implemented** |  |
| Stand Vigil | 2 | 2 | **Not implemented** |  |
| Turbo-boost | 2 | 2 | **Not implemented** |  |
| Advanced Firepower | 1 | 1 | **Not implemented** |  |
| Assault Dropship | 1 | 1 | **Not implemented** |  |
| Assault Ramp | 1 | 1 | **Not implemented** |  |
| Auramite and Adamantine | 1 | 1 | **Not implemented** |  |
| Captain-General | 1 | 1 | **Not implemented** |  |
| Corner the Quarry | 1 | 1 | **Not implemented** |  |
| Deft Parry | 1 | 1 | **Not implemented** |  |
| Devoted to Destruction | 1 | 1 | **Not implemented** |  |
| Disintegration Beams | 1 | 1 | **Not implemented** |  |
| Dread Foe | 1 | 1 | **Not implemented** |  |
| Fire Support | 1 | 1 | **Not implemented** |  |
| Galatus Shield | 1 | 1 | **Not implemented** |  |
| Golden Laurels | 1 | 1 | **Not implemented** |  |
| Guardian Eternal | 1 | 1 | **Not implemented** |  |
| Heavy Assault Infantry | 1 | 1 | **Not implemented** |  |
| Hero of Lion’s Gate | 1 | 1 | **Not implemented** |  |
| Implacable Vanguard | 1 | 1 | **Not implemented** |  |
| Infernus Firebombs | 1 | 1 | **Not implemented** |  |
| Living Fortress | 1 | 1 | **Supported** | Feel No Pain |
| Martial Inspiration | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Master of the Stances | 1 | 1 | **Not implemented** |  |
| Merciless Hunter | 1 | 1 | **Not implemented** |  |
| Moment Shackle | 1 | 1 | **Not implemented** |  |
| No Foe Shall Stand | 1 | 1 | **Not implemented** |  |
| Purity of Execution | 1 | 1 | **Not implemented** |  |
| Quicksilver Execution | 1 | 1 | **Not implemented** |  |
| Resolute Will | 1 | 1 | **Not implemented** |  |
| Sanctified Flames | 1 | 1 | **Not implemented** |  |
| Saturation Volleys | 1 | 1 | **Not implemented** |  |
| Seeker’s Instincts | 1 | 1 | **Not implemented** |  |
| Self Repair | 1 | 1 | **Not implemented** |  |
| Sentinel Storm | 1 | 1 | **Not implemented** |  |
| Slayers of Tyrants | 1 | 1 | **Not implemented** |  |
| Strike from the Skies | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Sweeping Advance | 1 | 1 | **Not implemented** |  |
| Swift Onslaught | 1 | 1 | **Not implemented** |  |
| Swooping Dive | 1 | 1 | **Not implemented** |  |
| Tactical Perception | 1 | 1 | **Supported** | Fights First |
| Tenacious Spirit | 1 | 1 | **Not implemented** |  |
| Unyielding Ancient | 1 | 1 | **Supported** | Deadly Demise |

#### Adeptus Mechanicus (`AdM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Broad Spectrum Data-tether | 5 | 5 | **Not implemented** |  |
| Mindlock | 2 | 2 | **Not implemented** |  |
| Achillan Eye | 1 | 1 | **Not implemented** |  |
| Aerial Deployment | 1 | 1 | **Not implemented** |  |
| Battle Protocols | 1 | 1 | **Not implemented** |  |
| Blind Barrage | 1 | 1 | **Not implemented** |  |
| Blistering Salvoes | 1 | 1 | **Not implemented** |  |
| Bomb Rack | 1 | 1 | **Not implemented** |  |
| Bound Creation | 1 | 1 | **Supported** | Feel No Pain |
| Breaching Command | 1 | 1 | **Not implemented** |  |
| Canticles of the Omnissiah | 1 | 1 | **Not implemented** |  |
| Cogitative Instincts | 1 | 1 | **Not implemented** |  |
| Control Edict | 1 | 1 | **Not implemented** |  |
| Data-spike | 1 | 1 | **Not implemented** |  |
| Defend the Divine Work | 1 | 1 | **Not implemented** |  |
| Dread Snipers | 1 | 1 | **Not implemented** |  |
| Dynamic Efficiency | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Electro-infusion | 1 | 1 | **Not implemented** |  |
| Electro-shock | 1 | 1 | **Not implemented** |  |
| Elevated Strider | 1 | 1 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |
| Emanatus Force Field (Aura) | 1 | 1 | **Not implemented** |  |
| Enginseer | 1 | 1 | **Supported** | Lone Operative |
| Fire Support | 1 | 1 | **Not implemented** |  |
| Focused Hunters | 1 | 1 | **Not implemented** |  |
| Galvanic Field | 1 | 1 | **Not implemented** |  |
| Line-breakers | 1 | 1 | **Not implemented** |  |
| Lord of the Machine Cult | 1 | 1 | **Supported** | Feel No Pain |
| Mechanicus Bodyguard | 1 | 1 | **Supported** | Lone Operative |
| Network Override | 1 | 1 | **Not implemented** |  |
| Neurostatic Interference (Aura) | 1 | 1 | **Not implemented** |  |
| Objective Scouted | 1 | 1 | **Not implemented** |  |
| Omnissiah’s Blessing | 1 | 1 | **Supported** | Feel No Pain |
| Optimised Gait | 1 | 1 | **Not implemented** |  |
| Rad-saturation (Aura) | 1 | 1 | **Not implemented** |  |
| Repulsor Grid | 1 | 1 | **Not implemented** |  |
| Ride the Thermals | 1 | 1 | **Not implemented** |  |
| Robotic Bodyguard | 1 | 1 | **Supported** | Feel No Pain |
| Scuttling Walker | 1 | 1 | **Not implemented** |  |
| Searing Conflagration | 1 | 1 | **Not implemented** |  |
| Seekers of Divine Arcana | 1 | 1 | **Not implemented** |  |
| Self-repair Mechanisms | 1 | 1 | **Not implemented** |  |
| Sentinel Directives | 1 | 1 | **Not implemented** |  |
| Servo-skull Uplink | 1 | 1 | **Not implemented** |  |
| Strafing Run | 1 | 1 | **Not implemented** |  |
| Tactica Obliqua | 1 | 1 | **Not implemented** |  |
| Termite Assault | 1 | 1 | **Not implemented** |  |
| Titan Guard | 1 | 1 | **Not implemented** |  |
| Vengeance for the Omnissiah | 1 | 1 | **Not implemented** |  |
| Voices in the Code | 1 | 1 | **Not implemented** |  |

#### Adeptus Titanicus (`TL`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Striding Colossus | 4 | 4 | **Not implemented** |  |
| Flank Speed | 1 | 1 | **Not implemented** |  |
| God-machine | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Titanic Fire Support | 1 | 1 | **Not implemented** |  |
| Wrath of the Omnissiah | 1 | 1 | **Not implemented** |  |

#### Aeldari (`AE`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Path of Command | 3 | 3 | **Not implemented** |  |
| Psychic Communion (Psychic) | 3 | 3 | **Not implemented** |  |
| Psychic Guidance | 3 | 3 | **Not implemented** |  |
| Support Weapon | 3 | 3 | **Not implemented** |  |
| Branching Fates (Psychic) | 2 | 2 | **Not implemented** |  |
| Crewed Platform | 2 | 2 | **Not implemented** |  |
| Path of the Outcast | 2 | 2 | **Not implemented** |  |
| Titanic Advance | 2 | 2 | **Not implemented** |  |
| Towering Wraith Construct | 2 | 2 | **Not implemented** |  |
| Acrobatic | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Acrobatic Grace | 1 | 1 | **Not implemented** |  |
| Aethersails | 1 | 1 | **Not implemented** |  |
| Agile | 1 | 1 | **Not implemented** |  |
| Arcane Cover | 1 | 1 | **Not implemented** |  |
| Assured Destruction | 1 | 1 | **Not implemented** |  |
| Bladestorm | 1 | 1 | **Not implemented** |  |
| Blitz | 1 | 1 | **Not implemented** |  |
| Blur of Movement | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Bonesinger | 1 | 1 | **Supported** | Lone Operative |
| Bringer of the True Death | 1 | 1 | **Not implemented** |  |
| Burning Lance | 1 | 1 | **Not implemented** |  |
| Cegorach’s Favour | 1 | 1 | **Not implemented** |  |
| Choreographer of War | 1 | 1 | **Not implemented** |  |
| Cloudbreakers | 1 | 1 | **Not implemented** |  |
| Cloudstrider | 1 | 1 | **Supported** | Deep Strike |
| Cruel Amusement | 1 | 1 | **Not implemented** |  |
| Cry of the Wind | 1 | 1 | **Not implemented** |  |
| Crystal Matrix | 1 | 1 | **Not implemented** |  |
| Crystalline Targeting | 1 | 1 | **Not implemented** |  |
| D-rift | 1 | 1 | **Not implemented** |  |
| Dance of Death | 1 | 1 | **Not implemented** |  |
| Death is Not Enough | 1 | 1 | **Not implemented** |  |
| Devastating Assault | 1 | 1 | **Not implemented** |  |
| Diviner of Futures | 1 | 1 | **Not implemented** |  |
| Doom (Psychic) | 1 | 1 | **Not implemented** |  |
| Empowered by Death | 1 | 1 | **Supported** | Fights First |
| Empyric Ambush | 1 | 1 | **Not implemented** |  |
| Ethereal Form | 1 | 1 | **Not implemented** |  |
| Eviscerating Fly-by | 1 | 1 | **Not implemented** |  |
| Extreme Mobility | 1 | 1 | **Not implemented** |  |
| Face of Death | 1 | 1 | **Not implemented** |  |
| Fated Hero | 1 | 1 | **Not implemented** |  |
| Fire Support | 1 | 1 | **Not implemented** |  |
| Flawless Poise | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Fleet of Foot | 1 | 1 | **Not implemented** |  |
| Flickerjump | 1 | 1 | **Not implemented** |  |
| Fog of Dreams (Psychic) | 1 | 1 | **Not implemented** |  |
| Fortification | 1 | 1 | **Not implemented** |  |
| Grenade Pack Flyover | 1 | 1 | **Not implemented** |  |
| Guide (Psychic) | 1 | 1 | **Not implemented** |  |
| Hand of Asuryan | 1 | 1 | **Not implemented** |  |
| Harassment Fire | 1 | 1 | **Not implemented** |  |
| Harvester of Souls | 1 | 1 | **Not implemented** |  |
| Herald of Ynnead | 1 | 1 | **Not implemented** |  |
| Hero of Iyanden | 1 | 1 | **Not implemented** |  |
| Horrify (Psychic) | 1 | 1 | **Not implemented** |  |
| Hunter Unseen | 1 | 1 | **Not implemented** |  |
| Indomitable Strength of Will | 1 | 1 | **Not implemented** |  |
| Inescapable Accuracy | 1 | 1 | **Not implemented** |  |
| Inevitable Death | 1 | 1 | **Not implemented** |  |
| Interceptor | 1 | 1 | **Not implemented** |  |
| Into the Foe | 1 | 1 | **Not implemented** |  |
| Lanced Obliteration | 1 | 1 | **Supported** | Deadly Demise |
| Lightning Assault | 1 | 1 | **Not implemented** |  |
| Lithe Embarkation | 1 | 1 | **Not implemented** |  |
| Malevolent Souls | 1 | 1 | **Not implemented** |  |
| Mandiblasters | 1 | 1 | **Not implemented** |  |
| Mindshock Pod (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Misfortune (Psychic) | 1 | 1 | **Not implemented** |  |
| Molten Form | 1 | 1 | **Not implemented** |  |
| Monofilament Snare | 1 | 1 | **Not implemented** |  |
| Monofilament Web | 1 | 1 | **Not implemented** |  |
| No Escape | 1 | 1 | **Not implemented** |  |
| Overlord | 1 | 1 | **Not implemented** |  |
| Piratical Raiders | 1 | 1 | **Not implemented** |  |
| Point-blank Devastation | 1 | 1 | **Not implemented** |  |
| Polychromatic Camouflage | 1 | 1 | **Not implemented** |  |
| Prince of Corsairs | 1 | 1 | **Supported** | Redeploy |
| Protect (Psychic) | 1 | 1 | **Not implemented** |  |
| Psytronome Shaper | 1 | 1 | **Not implemented** |  |
| Rapid Embarkation | 1 | 1 | **Not implemented** |  |
| Reaper of Souls | 1 | 1 | **Not implemented** |  |
| Reaver Band | 1 | 1 | **Not implemented** |  |
| Reavers of the Void | 1 | 1 | **Not implemented** |  |
| Reborn Mastermind | 1 | 1 | **Not implemented** |  |
| Reckless Abandon | 1 | 1 | **Not implemented** |  |
| Revenant Jet Pack | 1 | 1 | **Not implemented** |  |
| Ride the Wind | 1 | 1 | **Not implemented** |  |
| Runes of Battle (Psychic) | 1 | 1 | **Not implemented** |  |
| Runes of Fortune (Psychic) | 1 | 1 | **Not implemented** |  |
| Sadistic Raiders | 1 | 1 | **Not implemented** |  |
| Shade of Twilight | 1 | 1 | **Not implemented** |  |
| Shadow Hunter | 1 | 1 | **Not implemented** |  |
| Shadow of Death (Aura) | 1 | 1 | **Not implemented** |  |
| Skyfire | 1 | 1 | **Not implemented** |  |
| Skyhunter | 1 | 1 | **Not implemented** |  |
| Skyleap | 1 | 1 | **Supported** | Redeploy |
| Sonic Destruction | 1 | 1 | **Not implemented** |  |
| Speed of Vaul | 1 | 1 | **Not implemented** |  |
| Spirit Mark (Psychic) | 1 | 1 | **Not implemented** |  |
| Spiritseer | 1 | 1 | **Supported** | Lone Operative |
| Storm of Blades | 1 | 1 | **Not implemented** |  |
| Storm of Silence | 1 | 1 | **Not implemented** |  |
| Stormblades | 1 | 1 | **Not implemented** |  |
| Strafing Run | 1 | 1 | **Not implemented** |  |
| Structural Collapse | 1 | 1 | **Not implemented** |  |
| Superlative Strategist | 1 | 1 | **Not implemented** |  |
| Sustained Assault | 1 | 1 | **Not implemented** |  |
| Swift Demise | 1 | 1 | **Not implemented** |  |
| Tactical Acumen | 1 | 1 | **Not implemented** |  |
| Target Acquisition | 1 | 1 | **Not implemented** |  |
| Tears of Isha (Psychic) | 1 | 1 | **Not implemented** |  |
| The Bloody-Handed (Aura) | 1 | 1 | **Not implemented** |  |
| The Path Least Travelled | 1 | 1 | **Supported** | Redeploy |
| Titan Hunter | 1 | 1 | **Not implemented** |  |
| Titanic Agility | 1 | 1 | **Not implemented** |  |
| Titanic Strides | 1 | 1 | **Not implemented** |  |
| Tormentors | 1 | 1 | **Not implemented** |  |
| Treacherous Illusion (Psychic) | 1 | 1 | **Not implemented** |  |
| Unquenchable Resolve | 1 | 1 | **Not implemented** |  |
| War Construct | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Wave Serpent Shield | 1 | 1 | **Not implemented** |  |
| Way of the Blade | 1 | 1 | **Supported** | Fights First |
| Way of the Shaper (Psychic) | 1 | 1 | **Supported** | Feel No Pain |
| Webway Shunt Generator | 1 | 1 | **Not implemented** |  |
| Webway Strike | 1 | 1 | **Not implemented** |  |
| Whirling Death | 1 | 1 | **Not implemented** |  |
| Whispering Web | 1 | 1 | **Not implemented** |  |
| Word of the Phoenix (Psychic) | 1 | 1 | **Not implemented** |  |
| Yvraine’s Champion | 1 | 1 | **Supported** | Feel No Pain |

#### Astra Militarum (`AM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Reinforced Cover | 4 | 4 | **Not implemented** |  |
| Earthshaker Rounds | 3 | 3 | **Not implemented** |  |
| Suppression Bombardment | 3 | 3 | **Not implemented** |  |
| Aerial Deployment | 2 | 2 | **Not implemented** |  |
| Fire Support | 2 | 2 | **Not implemented** |  |
| Flak Battery | 2 | 2 | **Not implemented** |  |
| Furious Barrage | 2 | 2 | **Not implemented** |  |
| Mindlock | 2 | 2 | **Not implemented** |  |
| Mobile Command Vehicle | 2 | 2 | **Not implemented** |  |
| Mount Up! | 2 | 2 | **Not implemented** |  |
| Ogryn Bodyguard | 2 | 2 | **Supported** | Feel No Pain |
| Pinning Bombardment | 2 | 2 | **Not implemented** |  |
| Political Overwatch | 2 | 2 | **Not implemented** |  |
| Rearm, Reload, Fire | 2 | 2 | **Not implemented** |  |
| Rolling Fortress | 2 | 2 | **Not implemented** |  |
| Shoot Sharp and Scarper | 2 | 2 | **Not implemented** |  |
| Summary Execution | 2 | 2 | **Not implemented** |  |
| Tank Hunter | 2 | 2 | **Not implemented** |  |
| Vox-net | 2 | 2 | **Not implemented** |  |
| A Hearty ‘Pick Me Up’ | 1 | 1 | **Not implemented** |  |
| Ablative Plating | 1 | 1 | **Not implemented** |  |
| Aeronautica Commander | 1 | 1 | **Not implemented** |  |
| Agile Dogfighter | 1 | 1 | **Not implemented** |  |
| Airborne Insertion | 1 | 1 | **Not implemented** |  |
| Ancient Conquest | 1 | 1 | **Not implemented** |  |
| Anti-armour Gunship | 1 | 1 | **Not implemented** |  |
| Armour Obliteration | 1 | 1 | **Supported** | Deadly Demise |
| Armoured Aggressor | 1 | 1 | **Not implemented** |  |
| Armoured Defender | 1 | 1 | **Not implemented** |  |
| Armoured Frontis | 1 | 1 | **Not implemented** |  |
| Armoured Spearhead | 1 | 1 | **Not implemented** |  |
| Artillery Commander | 1 | 1 | **Not implemented** |  |
| Auspex Surveyor | 1 | 1 | **Not implemented** |  |
| Battlefield Control | 1 | 1 | **Not implemented** |  |
| Battlefield Dominance | 1 | 1 | **Not implemented** |  |
| Been There, Seen it, Killed it | 1 | 1 | **Not implemented** |  |
| Blistering Advance | 1 | 1 | **Not implemented** |  |
| Bomb Drop | 1 | 1 | **Not implemented** |  |
| Bring it Down! | 1 | 1 | **Not implemented** |  |
| Cadia Stands! | 1 | 1 | **Not implemented** |  |
| Called Shots | 1 | 1 | **Not implemented** |  |
| Close-quarters Warfare | 1 | 1 | **Not implemented** |  |
| Close-range Devastation | 1 | 1 | **Not implemented** |  |
| Close-range Titan Killer | 1 | 1 | **Not implemented** |  |
| Cold Steel and Courage | 1 | 1 | **Not implemented** |  |
| Concussive Wave | 1 | 1 | **Not implemented** |  |
| Covering Fire | 1 | 1 | **Not implemented** |  |
| Covert Stealth Team | 1 | 1 | **Supported** | Redeploy, Stealth |
| Daring Recon | 1 | 1 | **Not implemented** |  |
| Death Befitting An Officer | 1 | 1 | **Not implemented** |  |
| Deathstrike Missile | 1 | 1 | **Not implemented** |  |
| Defence Line | 1 | 1 | **Not implemented** |  |
| Demolition Charges | 1 | 1 | **Supported** | Deadly Demise |
| Desert Riders | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Divination (Psychic) | 1 | 1 | **Not implemented** |  |
| Emplacement Platform | 1 | 1 | **Not implemented** |  |
| Enginseer | 1 | 1 | **Supported** | Lone Operative |
| Explosive Death | 1 | 1 | **Not implemented** |  |
| Fiery Vengeance | 1 | 1 | **Not implemented** |  |
| Final Duty | 1 | 1 | **Not implemented** |  |
| Flush Them Out | 1 | 1 | **Not implemented** |  |
| Fortification | 1 | 1 | **Not implemented** |  |
| Get Back in the Fight | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Grenadiers | 1 | 1 | **Not implemented** |  |
| Grim Demeanour | 1 | 1 | **Not implemented** |  |
| Grim Determination | 1 | 1 | **Not implemented** |  |
| Gung-ho Command | 1 | 1 | **Not implemented** |  |
| Gung-ho Executioners | 1 | 1 | **Not implemented** |  |
| Gunship Barrage | 1 | 1 | **Not implemented** |  |
| Harker’s Hellraisers | 1 | 1 | **Not implemented** |  |
| Heroic Example | 1 | 1 | **Not implemented** |  |
| Holy Piety | 1 | 1 | **Not implemented** |  |
| Horsemasters | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Jungle Fighters | 1 | 1 | **Not implemented** |  |
| Leading the Charge | 1 | 1 | **Not implemented** |  |
| Lesk’s Heroes | 1 | 1 | **Not implemented** |  |
| Like Fighting a Shadow | 1 | 1 | **Not implemented** |  |
| Line-breaker | 1 | 1 | **Not implemented** |  |
| Lord Castellan | 1 | 1 | **Not implemented** |  |
| Malign Wardings(Psychic) | 1 | 1 | **Supported** | Feel No Pain |
| Mark the Target | 1 | 1 | **Not implemented** |  |
| Medicae Medi-packs | 1 | 1 | **Supported** | Feel No Pain |
| Meteoric Descent | 1 | 1 | **Supported** | Deep Strike |
| Mobile Hunter-killer | 1 | 1 | **Not implemented** |  |
| Mobile Hunter-killers | 1 | 1 | **Not implemented** |  |
| Mow Down the Enemy | 1 | 1 | **Not implemented** |  |
| Omnissiah’s Blessing | 1 | 1 | **Not implemented** |  |
| One-man Army | 1 | 1 | **Not implemented** |  |
| Outflank | 1 | 1 | **Not implemented** |  |
| Overwhelming Short-range Firepower | 1 | 1 | **Not implemented** |  |
| Payback Time | 1 | 1 | **Not implemented** |  |
| Point-blank Barrage | 1 | 1 | **Not implemented** |  |
| Power Overload | 1 | 1 | **Not implemented** |  |
| Powerful Volley | 1 | 1 | **Not implemented** |  |
| Powerlifter Charge | 1 | 1 | **Not implemented** |  |
| Precision Drop | 1 | 1 | **Supported** | Deep Strike |
| Primed and Ready | 1 | 1 | **Not implemented** |  |
| Psychic Barrier (Psychic) | 1 | 1 | **Not implemented** |  |
| Rapid Deployment | 1 | 1 | **Not implemented** |  |
| Recovery Vehicle | 1 | 1 | **Not implemented** |  |
| Remorseless Barrage | 1 | 1 | **Not implemented** |  |
| Rugged Reliability | 1 | 1 | **Not implemented** |  |
| Screening Line | 1 | 1 | **Not implemented** |  |
| Senior Officer | 1 | 1 | **Not implemented** |  |
| Sentinel Directives | 1 | 1 | **Not implemented** |  |
| Sentry Programming | 1 | 1 | **Not implemented** |  |
| Servo-sentry | 1 | 1 | **Supported** | Deep Strike |
| Shock Troops | 1 | 1 | **Not implemented** |  |
| Siege Bombardment | 1 | 1 | **Not implemented** |  |
| Storm Troopers | 1 | 1 | **Not implemented** |  |
| Subterranean Assault | 1 | 1 | **Supported** | Deep Strike |
| Support Vehicle | 1 | 1 | **Not implemented** |  |
| Tactical Genius | 1 | 1 | **Not implemented** |  |
| Tanith Camo-cloaks | 1 | 1 | **Not implemented** |  |
| Tank-killer | 1 | 1 | **Not implemented** |  |
| Targeting Coordinates | 1 | 1 | **Not implemented** |  |
| Tempestor Prime | 1 | 1 | **Not implemented** |  |
| The Collegiate Astrolex | 1 | 1 | **Supported** | Redeploy |
| The Lord Solar | 1 | 1 | **Not implemented** |  |
| The Ratling Twins | 1 | 1 | **Not implemented** |  |
| Thunderous Head-butt | 1 | 1 | **Not implemented** |  |
| Titan-killer | 1 | 1 | **Not implemented** |  |
| Tough to Kill | 1 | 1 | **Not implemented** |  |
| Tracking Target | 1 | 1 | **Not implemented** |  |
| Transport Support | 1 | 1 | **Not implemented** |  |
| Tremor Quake | 1 | 1 | **Not implemented** |  |
| Turbo-boost | 1 | 1 | **Not implemented** |  |
| Unstable Payload | 1 | 1 | **Supported** | Deadly Demise |
| Urban Warfare | 1 | 1 | **Not implemented** |  |
| Vengeance for the Omnissiah | 1 | 1 | **Not implemented** |  |
| Wall of Muscle | 1 | 1 | **Not implemented** |  |
| War Hymns | 1 | 1 | **Not implemented** |  |
| Warrior Elite | 1 | 1 | **Not implemented** |  |
| Well-stocked Supplies | 1 | 1 | **Not implemented** |  |
| Withering Hail | 1 | 1 | **Not implemented** |  |

#### Chaos Daemons (`CD`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Lord of Chaos | 7 | 7 | **Not implemented** |  |
| Altered Reality (Psychic) | 2 | 2 | **Not implemented** |  |
| Brutal Example | 2 | 2 | **Not implemented** |  |
| Cutting Down the Foe | 2 | 2 | **Not implemented** |  |
| Fearsome (Aura) | 2 | 2 | **Not implemented** |  |
| Feculent Despair (Aura, Psychic) | 2 | 2 | **Not implemented** |  |
| Flames of Change (Psychic) | 2 | 2 | **Not implemented** |  |
| For the Dark Gods | 2 | 2 | **Not implemented** |  |
| Fortification | 2 | 2 | **Not implemented** |  |
| Greater Daemon of Khorne (Aura) | 2 | 2 | **Not implemented** |  |
| Greater Daemon of Nurgle (Aura) | 2 | 2 | **Not implemented** |  |
| Greater Daemon of Slaanesh (Aura) | 2 | 2 | **Not implemented** |  |
| Greater Daemon of Tzeentch (Aura) | 2 | 2 | **Not implemented** |  |
| Hysterical Frenzy (Psychic) | 2 | 2 | **Not implemented** |  |
| Master of Magicks (Psychic) | 2 | 2 | **Not implemented** |  |
| Mesmerising Form | 2 | 2 | **Not implemented** |  |
| Nurgle’s Rot (Psychic) | 2 | 2 | **Not implemented** |  |
| Pack Leader | 2 | 2 | **Not implemented** |  |
| Prey of the Blood God | 2 | 2 | **Not implemented** |  |
| Relentless Carnage | 2 | 2 | **Not implemented** |  |
| Split | 2 | 2 | **Not implemented** |  |
| Symphony of Pain (Psychic) | 2 | 2 | **Not implemented** |  |
| Tormentbringer (Aura) | 2 | 2 | **Not implemented** |  |
| A Gory Path | 1 | 1 | **Not implemented** |  |
| Accursed Horde | 1 | 1 | **Not implemented** |  |
| Bane of Cowards | 1 | 1 | **Not implemented** |  |
| Beast Handler | 1 | 1 | **Not implemented** |  |
| Beastmaster | 1 | 1 | **Not implemented** |  |
| Bestial Raiders | 1 | 1 | **Not implemented** |  |
| Blazing Warpfire (Psychic) | 1 | 1 | **Not implemented** |  |
| Blessed by the Plague God | 1 | 1 | **Not implemented** |  |
| Blood Throne | 1 | 1 | **Not implemented** |  |
| Bloodmaster | 1 | 1 | **Not implemented** |  |
| Bloody Stampede | 1 | 1 | **Not implemented** |  |
| Bounding Assault | 1 | 1 | **Not implemented** |  |
| Bounding Leaps | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Brass Stampede | 1 | 1 | **Not implemented** |  |
| Champion Slayer | 1 | 1 | **Not implemented** |  |
| Chance for Glory | 1 | 1 | **Not implemented** |  |
| Changecaster | 1 | 1 | **Not implemented** |  |
| Chosen Marauders | 1 | 1 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |
| Cover | 1 | 1 | **Not implemented** |  |
| Covering Fire | 1 | 1 | **Not implemented** |  |
| Cruel Hunter | 1 | 1 | **Not implemented** |  |
| Cursed Flames | 1 | 1 | **Not implemented** |  |
| Cursed Wardings (Psychic) | 1 | 1 | **Supported** | Feel No Pain |
| Cut Off Their Escape | 1 | 1 | **Not implemented** |  |
| Daemon Lord of Khorne (Aura) | 1 | 1 | **Not implemented** |  |
| Daemon Lord of Nurgle (Aura) | 1 | 1 | **Not implemented** |  |
| Daemon Lord of Slaanesh (Aura) | 1 | 1 | **Not implemented** |  |
| Daemon Lord of Tzeentch (Aura) | 1 | 1 | **Not implemented** |  |
| Daemonic Lord | 1 | 1 | **Supported** | Lone Operative |
| Daemonkin (Psychic) | 1 | 1 | **Not implemented** |  |
| Dark Favour (Psychic) | 1 | 1 | **Not implemented** |  |
| Dark Ritual | 1 | 1 | **Not implemented** |  |
| Dark Zealotry | 1 | 1 | **Not implemented** |  |
| Dazzling Acrobatics | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Death Hex (Psychic) | 1 | 1 | **Not implemented** |  |
| Death’s Heads | 1 | 1 | **Not implemented** |  |
| Delightful Agonies | 1 | 1 | **Not implemented** |  |
| Deluge of Nurgle (Aura) | 1 | 1 | **Not implemented** |  |
| Demagogue | 1 | 1 | **Not implemented** |  |
| Despoilers | 1 | 1 | **Not implemented** |  |
| Devastating Charge | 1 | 1 | **Not implemented** |  |
| Discordant Disruption (Aura) | 1 | 1 | **Not implemented** |  |
| Disease of Mirth (Aura) | 1 | 1 | **Not implemented** |  |
| Diseased Cover | 1 | 1 | **Not implemented** |  |
| Eldritch Flames (Psychic) | 1 | 1 | **Not implemented** |  |
| Emissary of the Blood God (Aura) | 1 | 1 | **Not implemented** |  |
| Emissary of the Great Mutator (Aura) | 1 | 1 | **Not implemented** |  |
| Emissary of the Plague God (Aura) | 1 | 1 | **Not implemented** |  |
| Emissary of the Prince of Excess (Aura) | 1 | 1 | **Not implemented** |  |
| Enforcer | 1 | 1 | **Not implemented** |  |
| Exploding Horrors | 1 | 1 | **Not implemented** |  |
| Faithful Flock | 1 | 1 | **Not implemented** |  |
| Fateskimmer | 1 | 1 | **Not implemented** |  |
| Fiery Faith | 1 | 1 | **Not implemented** |  |
| Fluxmaster | 1 | 1 | **Not implemented** |  |
| Formidably Resilient | 1 | 1 | **Not implemented** |  |
| Formless Horror | 1 | 1 | **Not implemented** |  |
| Gift of Chaos (Psychic) | 1 | 1 | **Not implemented** |  |
| Gift of Poxes (Psychic) | 1 | 1 | **Not implemented** |  |
| Grotesque Regeneration | 1 | 1 | **Not implemented** |  |
| Harbinger of Death | 1 | 1 | **Not implemented** |  |
| Harmonic Alignment | 1 | 1 | **Not implemented** |  |
| Horrible Fascination(Psychic) | 1 | 1 | **Not implemented** |  |
| Horrifying Beauty | 1 | 1 | **Not implemented** |  |
| Hunters from the Warp | 1 | 1 | **Not implemented** |  |
| Infected Outbreak | 1 | 1 | **Not implemented** |  |
| Infernal Engines of Torment | 1 | 1 | **Not implemented** |  |
| Infernal Speed | 1 | 1 | **Not implemented** |  |
| Jolly Gutpipes | 1 | 1 | **Not implemented** |  |
| Keep Counting! | 1 | 1 | **Not implemented** |  |
| Lethal Caress | 1 | 1 | **Not implemented** |  |
| Lord of Decapitations | 1 | 1 | **Not implemented** |  |
| Lord of Fate | 1 | 1 | **Supported** | Feel No Pain |
| Malefic Destruction | 1 | 1 | **Not implemented** |  |
| Malign Sacrifice | 1 | 1 | **Not implemented** |  |
| Meet Your Quota! | 1 | 1 | **Not implemented** |  |
| Mischief and Confusion | 1 | 1 | **Not implemented** |  |
| Mischief Makers | 1 | 1 | **Not implemented** |  |
| Mischief Makers (Aura) | 1 | 1 | **Not implemented** |  |
| Monarch of the Hunt | 1 | 1 | **Not implemented** |  |
| Murderlust | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Mutated Bodyguard | 1 | 1 | **Supported** | Feel No Pain |
| No Prey Can Evade | 1 | 1 | **Not implemented** |  |
| Ogryn Combat Stimms | 1 | 1 | **Not implemented** |  |
| One Head Looks Back (Aura) | 1 | 1 | **Not implemented** |  |
| One Head Looks Forward | 1 | 1 | **Not implemented** |  |
| Pouncing Leap | 1 | 1 | **Not implemented** |  |
| Poxbringer | 1 | 1 | **Not implemented** |  |
| Prescience (Psychic) | 1 | 1 | **Not implemented** |  |
| Prey on the Weak | 1 | 1 | **Not implemented** |  |
| Prince of Darkness (Aura) | 1 | 1 | **Supported** | Stealth |
| Prince of Slaanesh | 1 | 1 | **Not implemented** |  |
| Psychic Barrier (Psychic) | 1 | 1 | **Not implemented** |  |
| P’tarix’s Sorcerous Syphon (Aura) | 1 | 1 | **Not implemented** |  |
| Rage Embodied (Aura) | 1 | 1 | **Not implemented** |  |
| Regenerating Monstrosity | 1 | 1 | **Not implemented** |  |
| Revolting Regeneration | 1 | 1 | **Not implemented** |  |
| Rider of the Immaterial Winds | 1 | 1 | **Supported** | Redeploy |
| Sacrificial Dagger | 1 | 1 | **Not implemented** |  |
| Scuttling Walker | 1 | 1 | **Not implemented** |  |
| Scythed Impact | 1 | 1 | **Not implemented** |  |
| Seed the Garden of Nurgle | 1 | 1 | **Not implemented** |  |
| Shadow Form | 1 | 1 | **Not implemented** |  |
| Shadow of Khorne (Aura) | 1 | 1 | **Not implemented** |  |
| Shroud of Flies (Aura) | 1 | 1 | **Supported** | Stealth |
| Skullmaster’s Fury | 1 | 1 | **Not implemented** |  |
| Skulls for Khorne | 1 | 1 | **Not implemented** |  |
| Skulls of the Fallen | 1 | 1 | **Not implemented** |  |
| Slashing Dive | 1 | 1 | **Not implemented** |  |
| Soporific Musk | 1 | 1 | **Not implemented** |  |
| Stabilisation Talons | 1 | 1 | **Not implemented** |  |
| Storm of Mutating Sorcery (Psychic) | 1 | 1 | **Not implemented** |  |
| Sullen Malevolence (Aura) | 1 | 1 | **Not implemented** |  |
| Swallow Energy (Psychic) | 1 | 1 | **Supported** | Feel No Pain |
| Tally of Pestilence | 1 | 1 | **Not implemented** |  |
| Terrifying Assault | 1 | 1 | **Not implemented** |  |
| The Dark Master (Aura) | 1 | 1 | **Not implemented** |  |
| The Eternal Dance | 1 | 1 | **Not implemented** |  |
| Tranceweaver | 1 | 1 | **Not implemented** |  |
| Twisted Defence Force | 1 | 1 | **Not implemented** |  |
| Unholy Bloodshed | 1 | 1 | **Not implemented** |  |
| Unholy Speed | 1 | 1 | **Not implemented** |  |
| Unholy Vigour | 1 | 1 | **Not implemented** |  |
| Veterans of the Long War | 1 | 1 | **Not implemented** |  |
| Virulent Blessing (Psychic) | 1 | 1 | **Not implemented** |  |
| Voltagheist Field | 1 | 1 | **Not implemented** |  |
| Wall of Muscle | 1 | 1 | **Not implemented** |  |
| Warp Spines | 1 | 1 | **Not implemented** |  |
| Warp Strike | 1 | 1 | **Supported** | Redeploy |
| Warptime (Psychic) | 1 | 1 | **Not implemented** |  |
| Xirat’p’s Sorcerous Barrages (Psychic) | 1 | 1 | **Not implemented** |  |

#### Chaos Knights (`QT`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Brutal Example | 2 | 2 | **Not implemented** |  |
| For the Dark Gods | 2 | 2 | **Not implemented** |  |
| Accursed Horde | 1 | 1 | **Not implemented** |  |
| Bastion of Corruption | 1 | 1 | **Not implemented** |  |
| Bastion of Firepower | 1 | 1 | **Not implemented** |  |
| Beastmaster | 1 | 1 | **Not implemented** |  |
| Bestial Raiders | 1 | 1 | **Not implemented** |  |
| Bloodlust | 1 | 1 | **Not implemented** |  |
| Brigand | 1 | 1 | **Not implemented** |  |
| Close-range Killers (Aura) | 1 | 1 | **Not implemented** |  |
| Consumed with Hunger (Aura) | 1 | 1 | **Not implemented** |  |
| Covering Fire | 1 | 1 | **Not implemented** |  |
| Cursed Flames | 1 | 1 | **Not implemented** |  |
| Cursed Wardings (Psychic) | 1 | 1 | **Supported** | Feel No Pain |
| Dark Fervour (Aura) | 1 | 1 | **Not implemented** |  |
| Dark Ritual | 1 | 1 | **Not implemented** |  |
| Dread Dominion (Aura) | 1 | 1 | **Not implemented** |  |
| Enforcer | 1 | 1 | **Not implemented** |  |
| Executioner | 1 | 1 | **Not implemented** |  |
| Faithful Flock | 1 | 1 | **Not implemented** |  |
| Fearsome (Aura) | 1 | 1 | **Not implemented** |  |
| Fiery Faith | 1 | 1 | **Not implemented** |  |
| Frenzied Rampage (Aura) | 1 | 1 | **Not implemented** |  |
| Grav-pinned | 1 | 1 | **Not implemented** |  |
| Huntmaster (Aura) | 1 | 1 | **Not implemented** |  |
| Huntsman | 1 | 1 | **Not implemented** |  |
| Infernal Aegis (Aura) | 1 | 1 | **Not implemented** |  |
| Karnivore | 1 | 1 | **Not implemented** |  |
| Macro-extinction Protocols | 1 | 1 | **Not implemented** |  |
| Methodical Destruction | 1 | 1 | **Not implemented** |  |
| Mischief Makers (Aura) | 1 | 1 | **Not implemented** |  |
| Mutated Bodyguard | 1 | 1 | **Supported** | Feel No Pain |
| Obsessive Ruthlessness | 1 | 1 | **Not implemented** |  |
| Offerings for the Dark Gods (Aura) | 1 | 1 | **Not implemented** |  |
| Ogryn Combat Stimms | 1 | 1 | **Not implemented** |  |
| Preysight (Aura) | 1 | 1 | **Not implemented** |  |
| Protection Protocols | 1 | 1 | **Not implemented** |  |
| Psychic Barrier (Psychic) | 1 | 1 | **Not implemented** |  |
| Repair Auto-simulacra | 1 | 1 | **Not implemented** |  |
| Searing Flames | 1 | 1 | **Not implemented** |  |
| Seething Hatred | 1 | 1 | **Not implemented** |  |
| Shock Charge | 1 | 1 | **Not implemented** |  |
| Stalker | 1 | 1 | **Not implemented** |  |
| Storm of Bolts | 1 | 1 | **Not implemented** |  |
| Sunderer of Fortresses | 1 | 1 | **Not implemented** |  |
| Taskmaster (Aura) | 1 | 1 | **Not implemented** |  |
| Twisted Defence Force | 1 | 1 | **Not implemented** |  |
| Unrestrained Terror (Aura) | 1 | 1 | **Not implemented** |  |
| Voltagheist Field | 1 | 1 | **Not implemented** |  |
| Vortex Terrors (Psychic) | 1 | 1 | **Not implemented** |  |
| Wall of Muscle | 1 | 1 | **Not implemented** |  |
| Warp Storms (Psychic) | 1 | 1 | **Not implemented** |  |

#### Chaos Space Marines (`CSM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Lord of Chaos | 9 | 9 | **Not implemented** |  |
| Assault Ramp | 4 | 4 | **Not implemented** |  |
| Aerial Assault | 2 | 2 | **Supported** | Deep Strike |
| Armoured Spearhead | 2 | 2 | **Not implemented** |  |
| Brutal Example | 2 | 2 | **Not implemented** |  |
| Fearsome (Aura) | 2 | 2 | **Not implemented** |  |
| For the Dark Gods | 2 | 2 | **Not implemented** |  |
| Interceptor | 2 | 2 | **Not implemented** |  |
| Prescience (Psychic) | 2 | 2 | **Not implemented** |  |
| Super-heavy Walker | 2 | 2 | **Not implemented** |  |
| Accursed Horde | 1 | 1 | **Not implemented** |  |
| Agent of Discord (Aura) | 1 | 1 | **Not implemented** |  |
| Airborne Predator | 1 | 1 | **Not implemented** |  |
| Altered Reality (Psychic) | 1 | 1 | **Not implemented** |  |
| Annihilator | 1 | 1 | **Not implemented** |  |
| Armoured Resilience | 1 | 1 | **Not implemented** |  |
| Ascended Daemon | 1 | 1 | **Not implemented** |  |
| Aspire to Glory | 1 | 1 | **Not implemented** |  |
| Atomantic Arc-reactor | 1 | 1 | **Not implemented** |  |
| Beastmaster | 1 | 1 | **Not implemented** |  |
| Bestial Raiders | 1 | 1 | **Not implemented** |  |
| Blood Surge | 1 | 1 | **Not implemented** |  |
| Bloodlust | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Bloody Stampede | 1 | 1 | **Not implemented** |  |
| Bomb Rack | 1 | 1 | **Not implemented** |  |
| Bringers of Change | 1 | 1 | **Not implemented** |  |
| Chance for Glory | 1 | 1 | **Not implemented** |  |
| Chirurgeon | 1 | 1 | **Not implemented** |  |
| Chosen Marauders | 1 | 1 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |
| Corrupt Machine Spirits | 1 | 1 | **Not implemented** |  |
| Covering Fire | 1 | 1 | **Not implemented** |  |
| Cruel Hunter | 1 | 1 | **Not implemented** |  |
| Cursed Flames | 1 | 1 | **Not implemented** |  |
| Cursed Wardings (Psychic) | 1 | 1 | **Supported** | Feel No Pain |
| Cut Off Their Escape | 1 | 1 | **Not implemented** |  |
| Daemonforge | 1 | 1 | **Not implemented** |  |
| Daemonic Destruction | 1 | 1 | **Not implemented** |  |
| Daemonic Ordnance | 1 | 1 | **Not implemented** |  |
| Daemonkin (Psychic) | 1 | 1 | **Not implemented** |  |
| Dark Ascension (Aura) | 1 | 1 | **Not implemented** |  |
| Dark Blessing (Aura) | 1 | 1 | **Not implemented** |  |
| Dark Champion | 1 | 1 | **Not implemented** |  |
| Dark Destiny | 1 | 1 | **Not implemented** |  |
| Dark Favour (Psychic) | 1 | 1 | **Not implemented** |  |
| Dark Ritual | 1 | 1 | **Not implemented** |  |
| Dark Zealotry | 1 | 1 | **Not implemented** |  |
| Death Frenzy | 1 | 1 | **Not implemented** |  |
| Death Hex (Psychic) | 1 | 1 | **Not implemented** |  |
| Demagogue | 1 | 1 | **Not implemented** |  |
| Deredeo Strike | 1 | 1 | **Not implemented** |  |
| Despoilers | 1 | 1 | **Not implemented** |  |
| Destructor | 1 | 1 | **Not implemented** |  |
| Devoted to Destruction | 1 | 1 | **Not implemented** |  |
| Dreadclaw Assault | 1 | 1 | **Not implemented** |  |
| Duty Eternal | 1 | 1 | **Not implemented** |  |
| Enforcer | 1 | 1 | **Not implemented** |  |
| Enhanced Warriors | 1 | 1 | **Not implemented** |  |
| Enrage Machine Spirits | 1 | 1 | **Not implemented** |  |
| Even In Death I Serve | 1 | 1 | **Supported** | Deadly Demise |
| Faithful Flock | 1 | 1 | **Not implemented** |  |
| Feculent Despair (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Ferocious Assault | 1 | 1 | **Not implemented** |  |
| Fiery Faith | 1 | 1 | **Not implemented** |  |
| Flames of Change (Psychic) | 1 | 1 | **Not implemented** |  |
| Flying Horror | 1 | 1 | **Not implemented** |  |
| Formidably Resilient | 1 | 1 | **Not implemented** |  |
| Fortification | 1 | 1 | **Not implemented** |  |
| Gift of Chaos (Psychic) | 1 | 1 | **Not implemented** |  |
| Gift of Poxes (Psychic) | 1 | 1 | **Not implemented** |  |
| Guns Blazing | 1 | 1 | **Not implemented** |  |
| Hamadrya’s Knowledge (Psychic) | 1 | 1 | **Not implemented** |  |
| Head Taker | 1 | 1 | **Not implemented** |  |
| Herald of the Apocalypse (Aura) | 1 | 1 | **Not implemented** |  |
| Hovering Death | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Indentured Daemon Engines | 1 | 1 | **Supported** | Lone Operative |
| Infernal Regeneration | 1 | 1 | **Supported** | Deadly Demise |
| Infernal Speed | 1 | 1 | **Not implemented** |  |
| Infused with the Blessings of Nurgle | 1 | 1 | **Not implemented** |  |
| Inviolable Transport | 1 | 1 | **Not implemented** |  |
| Kharybdis Assault | 1 | 1 | **Not implemented** |  |
| Line-breaker | 1 | 1 | **Not implemented** |  |
| Lord of Fate | 1 | 1 | **Supported** | Feel No Pain |
| Malevolent Locus (Aura) | 1 | 1 | **Not implemented** |  |
| Malign Cover | 1 | 1 | **Not implemented** |  |
| Malign Sacrifice | 1 | 1 | **Not implemented** |  |
| Master of Mechanisms | 1 | 1 | **Not implemented** |  |
| Mind-breaking Mutations (Aura) | 1 | 1 | **Not implemented** |  |
| Mischief Makers (Aura) | 1 | 1 | **Not implemented** |  |
| Mutated Bodyguard | 1 | 1 | **Supported** | Feel No Pain |
| Ogryn Combat Stimms | 1 | 1 | **Not implemented** |  |
| Outmanoeuvre | 1 | 1 | **Not implemented** |  |
| Pinning Bombardment | 1 | 1 | **Not implemented** |  |
| Plough Through the Enemy | 1 | 1 | **Not implemented** |  |
| Powerful Volley | 1 | 1 | **Not implemented** |  |
| Psychic Barrier (Psychic) | 1 | 1 | **Not implemented** |  |
| Red Corsairs | 1 | 1 | **Supported** | Redeploy |
| Reorder Reality | 1 | 1 | **Not implemented** |  |
| Revolting Regeneration | 1 | 1 | **Not implemented** |  |
| Rolling Fortress | 1 | 1 | **Not implemented** |  |
| Rotating Death | 1 | 1 | **Not implemented** |  |
| Runes of the Blood God | 1 | 1 | **Supported** | Feel No Pain |
| Sacrificial Dagger | 1 | 1 | **Not implemented** |  |
| Scuttling Gait | 1 | 1 | **Not implemented** |  |
| Scuttling Walker | 1 | 1 | **Not implemented** |  |
| Self Repair | 1 | 1 | **Not implemented** |  |
| Siege Crawler | 1 | 1 | **Not implemented** |  |
| Siege Shield | 1 | 1 | **Not implemented** |  |
| Soul Eater | 1 | 1 | **Not implemented** |  |
| Spirit Thief | 1 | 1 | **Not implemented** |  |
| Stabilisation Talons | 1 | 1 | **Not implemented** |  |
| Strafing Run | 1 | 1 | **Not implemented** |  |
| Sunderer of Fortresses | 1 | 1 | **Not implemented** |  |
| Surgeon Acolyte | 1 | 1 | **Not implemented** |  |
| Swift Assault | 1 | 1 | **Not implemented** |  |
| Termite Assault | 1 | 1 | **Not implemented** |  |
| Terrifying Assault | 1 | 1 | **Not implemented** |  |
| Terrifying Crescendo | 1 | 1 | **Not implemented** |  |
| The Tyrant of Badab | 1 | 1 | **Not implemented** |  |
| The Warmaster | 1 | 1 | **Not implemented** |  |
| Titan-killer | 1 | 1 | **Not implemented** |  |
| Trophy Taker | 1 | 1 | **Not implemented** |  |
| Twisted Defence Force | 1 | 1 | **Not implemented** |  |
| Unholy Bloodshed | 1 | 1 | **Not implemented** |  |
| Unholy Mechanisms (Aura) | 1 | 1 | **Not implemented** |  |
| Unholy Power | 1 | 1 | **Not implemented** |  |
| Veterans of the Long War | 1 | 1 | **Not implemented** |  |
| Visions of Suffering (Psychic) | 1 | 1 | **Not implemented** |  |
| Voltagheist Field | 1 | 1 | **Not implemented** |  |
| Wall of Muscle | 1 | 1 | **Not implemented** |  |
| Warp Rift Firepower | 1 | 1 | **Not implemented** |  |
| Warp Strike | 1 | 1 | **Supported** | Redeploy |
| Warp-sighted Butcher | 1 | 1 | **Not implemented** |  |
| Warpsmith | 1 | 1 | **Supported** | Lone Operative |
| Warptime (Psychic) | 1 | 1 | **Not implemented** |  |

#### Death Guard (`DG`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Assault Ramp | 4 | 4 | **Not implemented** |  |
| Aerial Assault | 2 | 2 | **Supported** | Deep Strike |
| Chaos Lord | 2 | 2 | **Not implemented** |  |
| Desiccation Conduit (Aura) | 2 | 2 | **Not implemented** |  |
| Hovering Death | 2 | 2 | **Supported** | Fall Back+Shoot (exact wording) |
| Interceptor | 2 | 2 | **Not implemented** |  |
| Armoured Resilience | 1 | 1 | **Not implemented** |  |
| Armoured Spearhead | 1 | 1 | **Not implemented** |  |
| Atomantic Arc-reactor | 1 | 1 | **Not implemented** |  |
| Barrage of Filth | 1 | 1 | **Not implemented** |  |
| Blessed Icon of Disease | 1 | 1 | **Not implemented** |  |
| Blight Bombardment | 1 | 1 | **Not implemented** |  |
| Blinding Spray | 1 | 1 | **Supported** | Fights First |
| Blistering Fusillade | 1 | 1 | **Not implemented** |  |
| Bomb Rack | 1 | 1 | **Not implemented** |  |
| Curse of the Walking Pox | 1 | 1 | **Not implemented** |  |
| Daemon Lord of Nurgle (Aura) | 1 | 1 | **Not implemented** |  |
| Death Approaches | 1 | 1 | **Supported** | Deep Strike |
| Death Guard Defenders | 1 | 1 | **Supported** | Lone Operative |
| Death’s Heads | 1 | 1 | **Not implemented** |  |
| Deluge of Nurgle (Aura) | 1 | 1 | **Not implemented** |  |
| Deredeo Strike | 1 | 1 | **Not implemented** |  |
| Diseased Cover | 1 | 1 | **Not implemented** |  |
| Diseased Malice | 1 | 1 | **Not implemented** |  |
| Duty Eternal | 1 | 1 | **Not implemented** |  |
| Eater Plague (Psychic) | 1 | 1 | **Supported** | Lone Operative |
| Enfeebling Miasma (Aura) | 1 | 1 | **Not implemented** |  |
| Even In Death I Serve | 1 | 1 | **Supported** | Deadly Demise |
| Explosive Blight | 1 | 1 | **Not implemented** |  |
| Extraction of Fresh Disease | 1 | 1 | **Not implemented** |  |
| Fearsome (Aura) | 1 | 1 | **Not implemented** |  |
| Feculent Despair (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Ferocious Assault | 1 | 1 | **Not implemented** |  |
| Fevered Strategist | 1 | 1 | **Not implemented** |  |
| Fire Support | 1 | 1 | **Not implemented** |  |
| Fortification | 1 | 1 | **Not implemented** |  |
| Foul Infusion | 1 | 1 | **Not implemented** |  |
| Froth-spattered Frenzy | 1 | 1 | **Not implemented** |  |
| Gift of Contagion (Psychic) | 1 | 1 | **Not implemented** |  |
| Gift of Poxes | 1 | 1 | **Not implemented** |  |
| Gift of Poxes (Psychic) | 1 | 1 | **Not implemented** |  |
| Grotesque Regeneration | 1 | 1 | **Not implemented** |  |
| Hail of Corrosive Disease | 1 | 1 | **Not implemented** |  |
| Horrifying Visage | 1 | 1 | **Not implemented** |  |
| Host of Plagues | 1 | 1 | **Not implemented** |  |
| Infected Outbreak | 1 | 1 | **Not implemented** |  |
| Infectious Bloodshed | 1 | 1 | **Not implemented** |  |
| Inflamed Infections | 1 | 1 | **Not implemented** |  |
| Infused with the Blessings of Nurgle | 1 | 1 | **Not implemented** |  |
| Inviolable Transport | 1 | 1 | **Not implemented** |  |
| Lethal Ichor | 1 | 1 | **Not implemented** |  |
| Line-breaker | 1 | 1 | **Not implemented** |  |
| Lord of Chaos | 1 | 1 | **Not implemented** |  |
| Lord of the Death Guard | 1 | 1 | **Not implemented** |  |
| Malicious Calculations | 1 | 1 | **Not implemented** |  |
| Metalophagic Infection | 1 | 1 | **Not implemented** |  |
| Miasma of Pestilence (Aura) | 1 | 1 | **Not implemented** |  |
| Mischief Makers | 1 | 1 | **Not implemented** |  |
| Mischief Makers (Aura) | 1 | 1 | **Not implemented** |  |
| Nurgle’s Rot (Psychic) | 1 | 1 | **Not implemented** |  |
| Pestilent Fallout (Psychic) | 1 | 1 | **Not implemented** |  |
| Pestilent Familiar (Psychic) | 1 | 1 | **Not implemented** |  |
| Pinning Bombardment | 1 | 1 | **Not implemented** |  |
| Powerful Volley | 1 | 1 | **Not implemented** |  |
| Putrefying Stink | 1 | 1 | **Not implemented** |  |
| Putrescent Fog (Aura) | 1 | 1 | **Not implemented** |  |
| Putrescent Vitality (Psychic) | 1 | 1 | **Not implemented** |  |
| Revolting Regeneration | 1 | 1 | **Not implemented** |  |
| Rolling Fortress | 1 | 1 | **Not implemented** |  |
| Rotating Death | 1 | 1 | **Not implemented** |  |
| Scuttling Walker | 1 | 1 | **Not implemented** |  |
| Sevenfold Chant | 1 | 1 | **Not implemented** |  |
| Shroud of Disease | 1 | 1 | **Not implemented** |  |
| Sickening Vitality | 1 | 1 | **Not implemented** |  |
| Silent Bodyguard | 1 | 1 | **Supported** | Feel No Pain |
| Spore-laced Shock Waves | 1 | 1 | **Not implemented** |  |
| Strafing Run | 1 | 1 | **Not implemented** |  |
| Sunderer of Fortresses | 1 | 1 | **Not implemented** |  |
| Tainted Narthecium | 1 | 1 | **Not implemented** |  |
| Tank Hunters | 1 | 1 | **Not implemented** |  |
| Termite Assault | 1 | 1 | **Not implemented** |  |
| The Destroyer Hive | 1 | 1 | **Not implemented** |  |
| Titan-killer | 1 | 1 | **Not implemented** |  |
| Tocsin of Misery (Aura) | 1 | 1 | **Not implemented** |  |
| Unclean Icon | 1 | 1 | **Not implemented** |  |
| Unholy Resilience | 1 | 1 | **Not implemented** |  |
| Vector of Disease | 1 | 1 | **Not implemented** |  |
| Virulent Aura | 1 | 1 | **Not implemented** |  |
| Virulent Blessing (Psychic) | 1 | 1 | **Not implemented** |  |

#### Drukhari (`DRU`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Eradicate the Foe | 2 | 2 | **Not implemented** |  |
| Acrobatic Gladiators (Pain) | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Acrobatic Grace | 1 | 1 | **Not implemented** |  |
| Aerialists | 1 | 1 | **Not implemented** |  |
| Agonising Suppression (Pain) | 1 | 1 | **Not implemented** |  |
| Airborne Evasion | 1 | 1 | **Not implemented** |  |
| Archon of the Poisoned Tongue (Pain) | 1 | 1 | **Not implemented** |  |
| Archon’s Will | 1 | 1 | **Not implemented** |  |
| Assassins’ Poisons (Pain) | 1 | 1 | **Not implemented** |  |
| Battlefield Butchery (Pain) | 1 | 1 | **Not implemented** |  |
| Beastmaster | 1 | 1 | **Not implemented** |  |
| Blitz | 1 | 1 | **Not implemented** |  |
| Bloody Spectacle | 1 | 1 | **Not implemented** |  |
| Blur of Blades | 1 | 1 | **Supported** | Fights First |
| Blur of Movement | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Brides of Death (Pain) | 1 | 1 | **Not implemented** |  |
| Cegorach’s Favour | 1 | 1 | **Not implemented** |  |
| Choreographer of War | 1 | 1 | **Not implemented** |  |
| Court of the Archon | 1 | 1 | **Supported** | Feel No Pain |
| Cruel Amusement | 1 | 1 | **Not implemented** |  |
| Cruel Enforcers | 1 | 1 | **Not implemented** |  |
| Dance of Death | 1 | 1 | **Not implemented** |  |
| Deadly Retinue (Pain) | 1 | 1 | **Not implemented** |  |
| Death is Not Enough | 1 | 1 | **Not implemented** |  |
| Decapitating Strikes (Pain) | 1 | 1 | **Not implemented** |  |
| Devious Mastermind | 1 | 1 | **Not implemented** |  |
| Devoted to Pain | 1 | 1 | **Not implemented** |  |
| Electromagentic Cascade (Pain) | 1 | 1 | **Not implemented** |  |
| Engine of Destruction (Pain) | 1 | 1 | **Not implemented** |  |
| Eviscerating Fly-by | 1 | 1 | **Not implemented** |  |
| Experimental Enhancements (Pain) | 1 | 1 | **Not implemented** |  |
| Fade Away (Pain) | 1 | 1 | **Supported** | Redeploy |
| Father of Pain | 1 | 1 | **Supported** | Feel No Pain |
| Fear Incarnate (Aura) | 1 | 1 | **Not implemented** |  |
| Fleshcraft (Pain) | 1 | 1 | **Not implemented** |  |
| Fog of Dreams (Psychic) | 1 | 1 | **Not implemented** |  |
| Goaded Savagery (Pain) | 1 | 1 | **Not implemented** |  |
| Ground Attack Craft | 1 | 1 | **Not implemented** |  |
| Ground-attack Craft | 1 | 1 | **Not implemented** |  |
| Hatred Eternal (Pain) | 1 | 1 | **Not implemented** |  |
| Horrific Regeneration | 1 | 1 | **Not implemented** |  |
| Lithe Agility (Pain) | 1 | 1 | **Not implemented** |  |
| Macro-steroids (Pain) | 1 | 1 | **Not implemented** |  |
| Master of Blades (Pain) | 1 | 1 | **Not implemented** |  |
| Matchless Swiftness (Pain) | 1 | 1 | **Not implemented** |  |
| Mind Like a Steel Trap (Aura) | 1 | 1 | **Not implemented** |  |
| Mindless Killing Machines (Pain) | 1 | 1 | **Not implemented** |  |
| Monstrous Charge | 1 | 1 | **Not implemented** |  |
| Murderous Crossfire | 1 | 1 | **Not implemented** |  |
| No Escape | 1 | 1 | **Not implemented** |  |
| Nowhere to Hide (Pain) | 1 | 1 | **Not implemented** |  |
| Nowhere to Run (Pain) | 1 | 1 | **Not implemented** |  |
| Onslaught | 1 | 1 | **Not implemented** |  |
| Overlord | 1 | 1 | **Not implemented** |  |
| Pain Adept | 1 | 1 | **Not implemented** |  |
| Pain Engine (Aura) | 1 | 1 | **Not implemented** |  |
| Pain Parasite (Pain) | 1 | 1 | **Not implemented** |  |
| Piratical Raiders | 1 | 1 | **Not implemented** |  |
| Polychromatic Camouflage | 1 | 1 | **Not implemented** |  |
| Precognisant | 1 | 1 | **Supported** | Redeploy |
| Rapid Deployment (Pain) | 1 | 1 | **Not implemented** |  |
| Rapid Embarkation | 1 | 1 | **Not implemented** |  |
| Reaver Band | 1 | 1 | **Not implemented** |  |
| Reavers of the Void | 1 | 1 | **Not implemented** |  |
| Reckless Abandon | 1 | 1 | **Not implemented** |  |
| Sadistic Raiders (Pain) | 1 | 1 | **Not implemented** |  |
| Sculptor of Torments (Pain) | 1 | 1 | **Not implemented** |  |
| Scything Charge | 1 | 1 | **Not implemented** |  |
| Shade Weavers | 1 | 1 | **Not implemented** |  |
| Shredding Fire (Pain) | 1 | 1 | **Not implemented** |  |
| Silent Executioner | 1 | 1 | **Not implemented** |  |
| Skyboard Evasion | 1 | 1 | **Not implemented** |  |
| Skyleap | 1 | 1 | **Supported** | Redeploy |
| Splinter Racks (Pain) | 1 | 1 | **Not implemented** |  |
| Storm of Blades | 1 | 1 | **Not implemented** |  |
| Swooping Descent (Pain) | 1 | 1 | **Supported** | Deep Strike |
| Thrilling Spectacle | 1 | 1 | **Not implemented** |  |
| Tormentors | 1 | 1 | **Not implemented** |  |
| Torture Device | 1 | 1 | **Not implemented** |  |
| Torturer’s Craft | 1 | 1 | **Not implemented** |  |
| Treacherous Illusion (Psychic) | 1 | 1 | **Not implemented** |  |
| Vanguard of the Dark City | 1 | 1 | **Not implemented** |  |
| Void Mine | 1 | 1 | **Not implemented** |  |
| Winged Strike (Pain) | 1 | 1 | **Not implemented** |  |

#### Emperor’s Children (`EC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| A Challenge Worthy of Skill | 1 | 1 | **Not implemented** |  |
| Airborne Predator | 1 | 1 | **Not implemented** |  |
| Assault Ramp | 1 | 1 | **Not implemented** |  |
| Assault Vehicle | 1 | 1 | **Not implemented** |  |
| Daemon Lord of Slaanesh (Aura) | 1 | 1 | **Not implemented** |  |
| Daemon Primarch of Slaanesh | 1 | 1 | **Not implemented** |  |
| Daemonic Destruction | 1 | 1 | **Not implemented** |  |
| Daemonic Patrons | 1 | 1 | **Not implemented** |  |
| Daemonic Poisons | 1 | 1 | **Not implemented** |  |
| Doom Siren | 1 | 1 | **Not implemented** |  |
| Duellist’s Hubris | 1 | 1 | **Supported** | Fights First |
| Ecstatic Death | 1 | 1 | **Not implemented** |  |
| Euphoric Strikes | 1 | 1 | **Not implemented** |  |
| Excessive Assault | 1 | 1 | **Not implemented** |  |
| Excessive Vigour (Aura) | 1 | 1 | **Not implemented** |  |
| Glutton for Punishment | 1 | 1 | **Not implemented** |  |
| Horrifying Beauty | 1 | 1 | **Not implemented** |  |
| Lethal Obsession | 1 | 1 | **Not implemented** |  |
| Lord of Excess | 1 | 1 | **Supported** | Lone Operative |
| Mesmerising Form | 1 | 1 | **Not implemented** |  |
| Monarch of the Hunt | 1 | 1 | **Not implemented** |  |
| No Prey Can Evade | 1 | 1 | **Not implemented** |  |
| Objective Defiled | 1 | 1 | **Not implemented** |  |
| Obsessive Annunciation | 1 | 1 | **Not implemented** |  |
| Perfectionists | 1 | 1 | **Not implemented** |  |
| Scuttling Horrors | 1 | 1 | **Not implemented** |  |
| Serpentine | 1 | 1 | **Not implemented** |  |
| Soporific Musk | 1 | 1 | **Not implemented** |  |
| Stimulated by Pain | 1 | 1 | **Not implemented** |  |
| Terrifying Crescendo | 1 | 1 | **Not implemented** |  |
| Unholy Speed | 1 | 1 | **Not implemented** |  |
| Warped Interference (Psychic) | 1 | 1 | **Not implemented** |  |
| Wracking Agonies (Psychic) | 1 | 1 | **Not implemented** |  |

#### Genestealer Cults (`GC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Reinforced Cover | 4 | 4 | **Not implemented** |  |
| Earthshaker Rounds | 3 | 3 | **Not implemented** |  |
| Feeder Tendrils | 3 | 3 | **Not implemented** |  |
| Suppression Bombardment | 3 | 3 | **Not implemented** |  |
| Fire Support | 2 | 2 | **Not implemented** |  |
| Flak Battery | 2 | 2 | **Not implemented** |  |
| Furious Barrage | 2 | 2 | **Not implemented** |  |
| Mindlock | 2 | 2 | **Not implemented** |  |
| Mobile Command Vehicle | 2 | 2 | **Not implemented** |  |
| Mount Up! | 2 | 2 | **Not implemented** |  |
| Pinning Bombardment | 2 | 2 | **Not implemented** |  |
| Primed and Ready | 2 | 2 | **Not implemented** |  |
| Psychic Familiar | 2 | 2 | **Not implemented** |  |
| Rearm, Reload, Fire | 2 | 2 | **Not implemented** |  |
| Rolling Fortress | 2 | 2 | **Not implemented** |  |
| Tank Hunter | 2 | 2 | **Not implemented** |  |
| Vox-net | 2 | 2 | **Not implemented** |  |
| A Plan Generations in the Making | 1 | 1 | **Not implemented** |  |
| Ablative Plating | 1 | 1 | **Not implemented** |  |
| Aerial Seeding | 1 | 1 | **Not implemented** |  |
| Aeronautica Commander | 1 | 1 | **Not implemented** |  |
| Alpha Invader | 1 | 1 | **Not implemented** |  |
| Alpha Warrior | 1 | 1 | **Not implemented** |  |
| Ancient Conquest | 1 | 1 | **Not implemented** |  |
| Armour Obliteration | 1 | 1 | **Supported** | Deadly Demise |
| Armoured Aggressor | 1 | 1 | **Not implemented** |  |
| Armoured Defender | 1 | 1 | **Not implemented** |  |
| Armoured Frontis | 1 | 1 | **Not implemented** |  |
| Armoured Spearhead | 1 | 1 | **Not implemented** |  |
| Artillery Commander | 1 | 1 | **Not implemented** |  |
| Auspex Surveyor | 1 | 1 | **Not implemented** |  |
| Battlefield Analysis | 1 | 1 | **Not implemented** |  |
| Battlefield Control | 1 | 1 | **Not implemented** |  |
| Battlefield Dominance | 1 | 1 | **Not implemented** |  |
| Bio-horror Disruption (Psychic) | 1 | 1 | **Not implemented** |  |
| Biological Warfare | 1 | 1 | **Not implemented** |  |
| Blistering Advance | 1 | 1 | **Not implemented** |  |
| Bodyguard | 1 | 1 | **Supported** | Feel No Pain |
| Bring it Down! | 1 | 1 | **Not implemented** |  |
| Brood Surge | 1 | 1 | **Not implemented** |  |
| Cadia Stands! | 1 | 1 | **Not implemented** |  |
| Called Shots | 1 | 1 | **Not implemented** |  |
| Claimed for the Cult | 1 | 1 | **Not implemented** |  |
| Cloaked Assassin | 1 | 1 | **Not implemented** |  |
| Close-quarters Warfare | 1 | 1 | **Not implemented** |  |
| Close-range Devastation | 1 | 1 | **Not implemented** |  |
| Close-range Titan Killer | 1 | 1 | **Not implemented** |  |
| Concussive Wave | 1 | 1 | **Not implemented** |  |
| Cosmic Horror (Psychic) | 1 | 1 | **Not implemented** |  |
| Covering Fire | 1 | 1 | **Not implemented** |  |
| Creeping Shadow | 1 | 1 | **Not implemented** |  |
| Crossfire | 1 | 1 | **Not implemented** |  |
| Cult Demagogue | 1 | 1 | **Not implemented** |  |
| Cult Infiltration | 1 | 1 | **Not implemented** |  |
| Daring Recon | 1 | 1 | **Not implemented** |  |
| Death Befitting An Officer | 1 | 1 | **Not implemented** |  |
| Death Blow | 1 | 1 | **Not implemented** |  |
| Death From Below | 1 | 1 | **Not implemented** |  |
| Deathstrike Missile | 1 | 1 | **Not implemented** |  |
| Decoys and Misdirection | 1 | 1 | **Supported** | Redeploy |
| Defence Line | 1 | 1 | **Not implemented** |  |
| Demolition Charges | 1 | 1 | **Supported** | Deadly Demise |
| Demolition Run | 1 | 1 | **Not implemented** |  |
| Desert Riders | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Divination (Psychic) | 1 | 1 | **Not implemented** |  |
| Emplacement Platform | 1 | 1 | **Not implemented** |  |
| Explosive Death | 1 | 1 | **Not implemented** |  |
| Fear of the Unseen (Aura) | 1 | 1 | **Not implemented** |  |
| Final Duty | 1 | 1 | **Not implemented** |  |
| Flush Them Out | 1 | 1 | **Not implemented** |  |
| Fortification | 1 | 1 | **Not implemented** |  |
| Get Back in the Fight | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Grenadiers | 1 | 1 | **Not implemented** |  |
| Grim Demeanour | 1 | 1 | **Not implemented** |  |
| Grim Determination | 1 | 1 | **Not implemented** |  |
| Grinding Clearance | 1 | 1 | **Not implemented** |  |
| Gung-ho Command | 1 | 1 | **Not implemented** |  |
| Gung-ho Executioners | 1 | 1 | **Not implemented** |  |
| Heroic Example | 1 | 1 | **Not implemented** |  |
| Heroic Fusillade | 1 | 1 | **Not implemented** |  |
| Horsemasters | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Hulking Bodyguards | 1 | 1 | **Not implemented** |  |
| Hypersensory Abilities | 1 | 1 | **Not implemented** |  |
| Hypersensory Array | 1 | 1 | **Not implemented** |  |
| Industrialised Destruction | 1 | 1 | **Not implemented** |  |
| It Itches! | 1 | 1 | **Not implemented** |  |
| Jungle Fighters | 1 | 1 | **Not implemented** |  |
| Lesk’s Heroes | 1 | 1 | **Not implemented** |  |
| Line-breaker | 1 | 1 | **Not implemented** |  |
| Malign Wardings(Psychic) | 1 | 1 | **Supported** | Feel No Pain |
| Manufactorum Cover | 1 | 1 | **Not implemented** |  |
| Mark the Target | 1 | 1 | **Not implemented** |  |
| Master Outrider | 1 | 1 | **Not implemented** |  |
| Medicae Medi-packs | 1 | 1 | **Supported** | Feel No Pain |
| Meteoric Descent | 1 | 1 | **Supported** | Deep Strike |
| Might From Beyond | 1 | 1 | **Not implemented** |  |
| Mind Control (Psychic) | 1 | 1 | **Not implemented** |  |
| Mobile Hunter-killer | 1 | 1 | **Not implemented** |  |
| Mobile Hunter-killers | 1 | 1 | **Not implemented** |  |
| Mow Down the Enemy | 1 | 1 | **Not implemented** |  |
| Neural Disruption | 1 | 1 | **Not implemented** |  |
| Nexus of Devotion | 1 | 1 | **Supported** | Feel No Pain |
| Outflank | 1 | 1 | **Not implemented** |  |
| Outrider Gangs | 1 | 1 | **Not implemented** |  |
| Overwhelming Short-range Firepower | 1 | 1 | **Not implemented** |  |
| Parasitic Infection | 1 | 1 | **Not implemented** |  |
| Paroxysm (Psychic) | 1 | 1 | **Not implemented** |  |
| Pheromone Trail | 1 | 1 | **Not implemented** |  |
| Planted Explosives | 1 | 1 | **Not implemented** |  |
| Political Overwatch | 1 | 1 | **Not implemented** |  |
| Pouncing Leap | 1 | 1 | **Not implemented** |  |
| Power Overload | 1 | 1 | **Not implemented** |  |
| Powerful Volley | 1 | 1 | **Not implemented** |  |
| Powerlifter Charge | 1 | 1 | **Not implemented** |  |
| Priority Target | 1 | 1 | **Not implemented** |  |
| Psionic Shield (Psychic) | 1 | 1 | **Not implemented** |  |
| Psychic Barrier (Psychic) | 1 | 1 | **Not implemented** |  |
| Psychic Spoor | 1 | 1 | **Not implemented** |  |
| Psychological Saboteur (Aura) | 1 | 1 | **Not implemented** |  |
| Rapid Deployment | 1 | 1 | **Not implemented** |  |
| Recovery Vehicle | 1 | 1 | **Not implemented** |  |
| Regenerating Gene-mass | 1 | 1 | **Not implemented** |  |
| Remorseless Barrage | 1 | 1 | **Not implemented** |  |
| Rugged Reliability | 1 | 1 | **Not implemented** |  |
| Scrambler Array | 1 | 1 | **Not implemented** |  |
| Screening Line | 1 | 1 | **Not implemented** |  |
| Senior Officer | 1 | 1 | **Not implemented** |  |
| Sentinel Directives | 1 | 1 | **Not implemented** |  |
| Sentry Programming | 1 | 1 | **Not implemented** |  |
| Shock Troops | 1 | 1 | **Not implemented** |  |
| Siege Bombardment | 1 | 1 | **Not implemented** |  |
| Spiritual Leader | 1 | 1 | **Not implemented** |  |
| Subterranean Assault | 1 | 1 | **Supported** | Deep Strike |
| Subterranean Tunnels | 1 | 1 | **Supported** | Deep Strike |
| Sudden Assault | 1 | 1 | **Supported** | Fights First |
| Summary Execution | 1 | 1 | **Not implemented** |  |
| Summon the Cult | 1 | 1 | **Not implemented** |  |
| Support Vehicle | 1 | 1 | **Not implemented** |  |
| Swift and Deadly | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Tank-killer | 1 | 1 | **Not implemented** |  |
| Targeting Coordinates | 1 | 1 | **Not implemented** |  |
| Tectonic Fragdrill | 1 | 1 | **Not implemented** |  |
| Terror From The Deep | 1 | 1 | **Supported** | Deep Strike |
| The Chosen One | 1 | 1 | **Not implemented** |  |
| Titan-killer | 1 | 1 | **Not implemented** |  |
| Tracking Target | 1 | 1 | **Not implemented** |  |
| Transport Support | 1 | 1 | **Not implemented** |  |
| Tremor Quake | 1 | 1 | **Not implemented** |  |
| Turbo-boost | 1 | 1 | **Not implemented** |  |
| Twisted Science | 1 | 1 | **Not implemented** |  |
| Underground Egress | 1 | 1 | **Not implemented** |  |
| Unstable Payload | 1 | 1 | **Supported** | Deadly Demise |
| Urban Warfare | 1 | 1 | **Not implemented** |  |
| Voice of New Truths | 1 | 1 | **Not implemented** |  |
| Warrior Elite | 1 | 1 | **Not implemented** |  |
| Will of the Hive Mind | 1 | 1 | **Not implemented** |  |
| Winged Swarm | 1 | 1 | **Not implemented** |  |
| Withering Hail | 1 | 1 | **Not implemented** |  |

#### Grey Knights (`GK`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Assault Ramp | 3 | 3 | **Not implemented** |  |
| Warrior Strategist | 2 | 2 | **Not implemented** |  |
| Aerial Assault | 1 | 1 | **Supported** | Deep Strike |
| Armoured Resilience | 1 | 1 | **Not implemented** |  |
| Attuned Onslaught (Psychic) | 1 | 1 | **Not implemented** |  |
| Blessing of the Omnissiah | 1 | 1 | **Not implemented** |  |
| Champion of the Order of Purifiers (Psychic) | 1 | 1 | **Not implemented** |  |
| Clarion of Haste (Psychic) | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Exemplar of the Silvered Host | 1 | 1 | **Not implemented** |  |
| Eye of Judgement (Psychic) | 1 | 1 | **Not implemented** |  |
| Fire Focus | 1 | 1 | **Not implemented** |  |
| Fire Support | 1 | 1 | **Not implemented** |  |
| Force Edge (Psychic) | 1 | 1 | **Not implemented** |  |
| Foresight (Psychic) | 1 | 1 | **Not implemented** |  |
| Guardians of the Machine | 1 | 1 | **Not implemented** |  |
| Guidance of the Ancients (Psychic) | 1 | 1 | **Not implemented** |  |
| Haloed in Soulfire (Psychic) | 1 | 1 | **Not implemented** |  |
| Hammer Aflame (Psychic) | 1 | 1 | **Not implemented** |  |
| Hammerhand (Psychic) | 1 | 1 | **Not implemented** |  |
| Indomitable Spirit (Psychic) | 1 | 1 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |
| Inspiring Exemplar | 1 | 1 | **Not implemented** |  |
| Interceptor | 1 | 1 | **Not implemented** |  |
| Litanies of Sanctity | 1 | 1 | **Not implemented** |  |
| Might of Titan (Psychic) | 1 | 1 | **Not implemented** |  |
| Mindlock | 1 | 1 | **Not implemented** |  |
| One With the Warp (Psychic) | 1 | 1 | **Supported** | Deep Strike |
| Personal Teleporters | 1 | 1 | **Not implemented** |  |
| Retinue | 1 | 1 | **Supported** | Deep Strike |
| Righteous Persecution | 1 | 1 | **Not implemented** |  |
| Sanctic Hood | 1 | 1 | **Supported** | Feel No Pain |
| Sanctifying Ritual (Psychic) | 1 | 1 | **Not implemented** |  |
| Sanctity of Purpose | 1 | 1 | **Not implemented** |  |
| Sanctuary (Psychic) | 1 | 1 | **Not implemented** |  |
| Strafing Run | 1 | 1 | **Not implemented** |  |
| Surge of Wrath (Psychic) | 1 | 1 | **Not implemented** |  |
| Techmarine | 1 | 1 | **Supported** | Lone Operative |
| Truesilver Aegis (Aura) | 1 | 1 | **Supported** | Feel No Pain |
| Untouchable Purity | 1 | 1 | **Supported** | Feel No Pain |
| Wisdom of the Ancients (Aura) | 1 | 1 | **Not implemented** |  |
| Zealous Path | 1 | 1 | **Not implemented** |  |

#### Imperial Agents (`AoI`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Authority of the Inquisition | 7 | 7 | **Not implemented** |  |
| Backroom Deals | 3 | 3 | **Supported** | Infiltrators |
| Warrant of Trade | 3 | 3 | **Supported** | Redeploy |
| Death to the Alien | 2 | 2 | **Not implemented** |  |
| Power of the Rosette | 2 | 2 | **Not implemented** |  |
| Self Repair | 2 | 2 | **Not implemented** |  |
| A Weaponsmith, Not a Warlord | 1 | 1 | **Not implemented** |  |
| Abomination | 1 | 1 | **Supported** | Feel No Pain |
| Acrobatic Escape | 1 | 1 | **Not implemented** |  |
| Blackstar Cluster Launcher | 1 | 1 | **Not implemented** |  |
| Breaching Team | 1 | 1 | **Not implemented** |  |
| CAT Unit | 1 | 1 | **Not implemented** |  |
| Catechism of Death | 1 | 1 | **Not implemented** |  |
| Cherub | 1 | 1 | **Not implemented** |  |
| Deadshot | 1 | 1 | **Supported** | Lone Operative |
| Dedication to Duty | 1 | 1 | **Not implemented** |  |
| Defenders of the Faith | 1 | 1 | **Not implemented** |  |
| Dominate Will (Psychic) | 1 | 1 | **Not implemented** |  |
| Etheric Emergence | 1 | 1 | **Supported** | Deep Strike |
| Evade and Survive | 1 | 1 | **Not implemented** |  |
| Fortis Doctrines | 1 | 1 | **Not implemented** |  |
| Frenzon | 1 | 1 | **Supported** | Advance+Shoot (exact wording) |
| Gaze into the Empyrean (Psychic) | 1 | 1 | **Not implemented** |  |
| Gheistskull | 1 | 1 | **Not implemented** |  |
| Grim Spectres | 1 | 1 | **Not implemented** |  |
| Hammerhand (Psychic) | 1 | 1 | **Not implemented** |  |
| Holy Hatred | 1 | 1 | **Not implemented** |  |
| Imperial Law | 1 | 1 | **Not implemented** |  |
| Incensor Cherub | 1 | 1 | **Not implemented** |  |
| Inconceivable Augmentation | 1 | 1 | **Not implemented** |  |
| Indomitor Doctrines | 1 | 1 | **Not implemented** |  |
| Kill Team | 1 | 1 | **Not implemented** |  |
| Lord of Deceit (Aura) | 1 | 1 | **Not implemented** |  |
| Loyal Henchmen | 1 | 1 | **Not implemented** |  |
| Malefic Warding | 1 | 1 | **Not implemented** |  |
| Malefic Wardings (Psychic) | 1 | 1 | **Not implemented** |  |
| Malus Codicium | 1 | 1 | **Not implemented** |  |
| Masters of Close Confines | 1 | 1 | **Not implemented** |  |
| Merciless Judgement | 1 | 1 | **Not implemented** |  |
| Ministorum Sermon | 1 | 1 | **Not implemented** |  |
| No Mercy | 1 | 1 | **Not implemented** |  |
| Overkill | 1 | 1 | **Not implemented** |  |
| Proteus Doctrines | 1 | 1 | **Not implemented** |  |
| Psychic Veil (Psychic) | 1 | 1 | **Not implemented** |  |
| Psyoculum | 1 | 1 | **Not implemented** |  |
| Purge and Cleanse | 1 | 1 | **Not implemented** |  |
| Rapid Deployment | 1 | 1 | **Not implemented** |  |
| Rites of Battle | 1 | 1 | **Not implemented** |  |
| Shieldbreaker | 1 | 1 | **Not implemented** |  |
| Soulless Horror | 1 | 1 | **Not implemented** |  |
| Spectrus Doctrines | 1 | 1 | **Supported** | Redeploy |
| Spy Network | 1 | 1 | **Not implemented** |  |
| Strategic Knowledge | 1 | 1 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |
| Tactical Instinct | 1 | 1 | **Not implemented** |  |
| Teleport Homer | 1 | 1 | **Not implemented** |  |
| Terminatus Assault | 1 | 1 | **Not implemented** |  |
| Third Eye (Psychic) | 1 | 1 | **Not implemented** |  |
| Throne of Judgement (Aura) | 1 | 1 | **Not implemented** |  |
| Turbo-boost | 1 | 1 | **Not implemented** |  |
| Unflinching | 1 | 1 | **Not implemented** |  |
| Unstoppable Champion | 1 | 1 | **Not implemented** |  |
| Unsubtle Crusader | 1 | 1 | **Supported** | Scouts |
| Vox-cast Proclamations (Aura) | 1 | 1 | **Not implemented** |  |
| Ward Against the Malefic Arts | 1 | 1 | **Not implemented** |  |
| Xenos Hunter | 1 | 1 | **Not implemented** |  |
| Zealot | 1 | 1 | **Not implemented** |  |

#### Imperial Knights (`QI`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Ion Aegis (Aura) | 2 | 2 | **Not implemented** |  |
| Acheron’s Duty (Bondsman) | 1 | 1 | **Not implemented** |  |
| Aggressive Assault | 1 | 1 | **Not implemented** |  |
| Atrapos’ Duty (Bondsman) | 1 | 1 | **Not implemented** |  |
| Bastion of Firepower | 1 | 1 | **Not implemented** |  |
| Castigator’s Duty (Bondsman) | 1 | 1 | **Not implemented** |  |
| Chainbreaker | 1 | 1 | **Not implemented** |  |
| Control Edict | 1 | 1 | **Not implemented** |  |
| Crusader’s Duty (Bondsman) | 1 | 1 | **Not implemented** |  |
| Data-spike | 1 | 1 | **Not implemented** |  |
| Defend the Divine Work | 1 | 1 | **Not implemented** |  |
| Defender’s Duty (Bondsman) | 1 | 1 | **Not implemented** |  |
| Errant’s Duty (Bondsman) | 1 | 1 | **Not implemented** |  |
| Exemplar of the Code | 1 | 1 | **Not implemented** |  |
| Gallant’s Duty (Bondsman) | 1 | 1 | **Not implemented** |  |
| Galvanic Field | 1 | 1 | **Not implemented** |  |
| Grav-pinned | 1 | 1 | **Not implemented** |  |
| Impetuous Glory | 1 | 1 | **Not implemented** |  |
| Lancer’s Duty (Bondsman) | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Legendary Freeblade | 1 | 1 | **Not implemented** |  |
| Lord of the Machine Cult | 1 | 1 | **Supported** | Feel No Pain |
| Macro-extinction Protocols | 1 | 1 | **Not implemented** |  |
| Magaera’s Duty (Bondsman) | 1 | 1 | **Not implemented** |  |
| Martial Pride | 1 | 1 | **Not implemented** |  |
| Mentor (Bondsman) | 1 | 1 | **Not implemented** |  |
| Objective Scouted | 1 | 1 | **Not implemented** |  |
| Paladin’s Duty (Bondsman) | 1 | 1 | **Not implemented** |  |
| Protection Protocols | 1 | 1 | **Not implemented** |  |
| Punishing Salvoes | 1 | 1 | **Not implemented** |  |
| Rad-saturation (Aura) | 1 | 1 | **Not implemented** |  |
| Repair Auto-simulacra | 1 | 1 | **Not implemented** |  |
| Searing Flames | 1 | 1 | **Not implemented** |  |
| Seasoned Noble | 1 | 1 | **Not implemented** |  |
| Selfless Protector | 1 | 1 | **Not implemented** |  |
| Servo-skull Uplink | 1 | 1 | **Not implemented** |  |
| Shock Charge | 1 | 1 | **Not implemented** |  |
| Storm of Bolts | 1 | 1 | **Not implemented** |  |
| Styrix’s Duty (Bondsman) | 1 | 1 | **Not implemented** |  |
| Sunderer of Fortresses | 1 | 1 | **Not implemented** |  |
| Suppression Protocols | 1 | 1 | **Not implemented** |  |
| Thin Their Ranks | 1 | 1 | **Not implemented** |  |
| Thundershock | 1 | 1 | **Not implemented** |  |
| Titan Hunter | 1 | 1 | **Not implemented** |  |
| Warden’s Duty (Bondsman) | 1 | 1 | **Not implemented** |  |

#### Leagues of Votann (`LoV`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Ancestral Fortune | 1 | 1 | **Not implemented** |  |
| Blistering Advance | 1 | 1 | **Not implemented** |  |
| Breaching Fire | 1 | 1 | **Not implemented** |  |
| Brôkhyr Guild Support | 1 | 1 | **Supported** | Lone Operative |
| Computational Mastermind | 1 | 1 | **Not implemented** |  |
| Cyberstimms | 1 | 1 | **Not implemented** |  |
| Decisive Destruction | 1 | 1 | **Not implemented** |  |
| Destabilising Quakes | 1 | 1 | **Not implemented** |  |
| Exemplar of the Einhyr | 1 | 1 | **Not implemented** |  |
| Forgewrought Expertise | 1 | 1 | **Not implemented** |  |
| Fortify (Psychic) | 1 | 1 | **Supported** | Feel No Pain |
| Geomantic Hunters | 1 | 1 | **Not implemented** |  |
| Grim Efficiency | 1 | 1 | **Not implemented** |  |
| Grimnyr’s Regard | 1 | 1 | **Not implemented** |  |
| Grudge-fuelled Fortitude | 1 | 1 | **Not implemented** |  |
| Kindred Hero | 1 | 1 | **Not implemented** |  |
| Luck Has. Need Keeps. Toil Earns | 1 | 1 | **Not implemented** |  |
| Mass Driver Accelerators | 1 | 1 | **Not implemented** |  |
| Merciless Eradication | 1 | 1 | **Not implemented** |  |
| MultiCOG Targeting | 1 | 1 | **Not implemented** |  |
| Multispectral Visor | 1 | 1 | **Not implemented** |  |
| Opportunistic Manoeuvre | 1 | 1 | **Not implemented** |  |
| Outflanking Mag-riders | 1 | 1 | **Not implemented** |  |
| Panspectral Scanning | 1 | 1 | **Not implemented** |  |
| Pragmatic Hunters | 1 | 1 | **Not implemented** |  |
| Predictive Guidance | 1 | 1 | **Not implemented** |  |
| Purge Response | 1 | 1 | **Not implemented** |  |
| Resource Transmutation | 1 | 1 | **Not implemented** |  |
| Scanner Uplinks | 1 | 1 | **Not implemented** |  |
| Science Guild Support | 1 | 1 | **Supported** | Lone Operative |
| Seized Opportunity | 1 | 1 | **Not implemented** |  |
| Subterranean Explosives | 1 | 1 | **Not implemented** |  |
| Unhinged Vengeance | 1 | 1 | **Not implemented** |  |

#### Necrons (`NEC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Necrodermis | 4 | 4 | **Not implemented** |  |
| My Will Be Done | 2 | 2 | **Not implemented** |  |
| Phase-shifted Cover | 2 | 2 | **Not implemented** |  |
| Adaptive Strategy | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Advanced Quantum Shielding | 1 | 1 | **Not implemented** |  |
| Aggressor Guardian | 1 | 1 | **Not implemented** |  |
| Ancient Collector | 1 | 1 | **Not implemented** |  |
| Ancient Cover | 1 | 1 | **Not implemented** |  |
| Atavistic Instigation | 1 | 1 | **Not implemented** |  |
| Atomic Energy Manipulator | 1 | 1 | **Not implemented** |  |
| Bound Creation | 1 | 1 | **Supported** | Feel No Pain |
| Canoptek Swarm | 1 | 1 | **Not implemented** |  |
| Carrier Wave (Aura) | 1 | 1 | **Not implemented** |  |
| Chittering swarm | 1 | 1 | **Not implemented** |  |
| Chronometron | 1 | 1 | **Not implemented** |  |
| Crimson Harvest | 1 | 1 | **Not implemented** |  |
| Damaged Armour | 1 | 1 | **Not implemented** |  |
| Death Sphere Bombardment | 1 | 1 | **Not implemented** |  |
| Destroyer Cult | 1 | 1 | **Not implemented** |  |
| Drain Life | 1 | 1 | **Not implemented** |  |
| Driven by Hatred | 1 | 1 | **Not implemented** |  |
| Engrammatic Logic | 1 | 1 | **Not implemented** |  |
| Eternity Gate | 1 | 1 | **Supported** | Redeploy |
| Evasion Engrams | 1 | 1 | **Not implemented** |  |
| Flesh Hunger | 1 | 1 | **Not implemented** |  |
| Fortification | 1 | 1 | **Not implemented** |  |
| Ghostwalk Mantle | 1 | 1 | **Supported** | Fights First |
| Grand Illusion | 1 | 1 | **Supported** | Redeploy |
| Grand Strategist | 1 | 1 | **Not implemented** |  |
| Gravitational Field | 1 | 1 | **Not implemented** |  |
| Gravitic Pulse | 1 | 1 | **Not implemented** |  |
| Guardian Protocols | 1 | 1 | **Not implemented** |  |
| Harassment Swarm (Aura) | 1 | 1 | **Not implemented** |  |
| Harbinger of Despair | 1 | 1 | **Not implemented** |  |
| Harbinger of Destruction | 1 | 1 | **Not implemented** |  |
| Hard-wired for Destruction | 1 | 1 | **Not implemented** |  |
| Hyperspace Hunters | 1 | 1 | **Not implemented** |  |
| Illuminor | 1 | 1 | **Supported** | Lone Operative |
| Implacable Eradication | 1 | 1 | **Not implemented** |  |
| Implacable Resilience | 1 | 1 | **Not implemented** |  |
| Inescapable Death | 1 | 1 | **Not implemented** |  |
| Living Lightning | 1 | 1 | **Supported** | Lone Operative |
| Lord of Deceit (Aura) | 1 | 1 | **Not implemented** |  |
| Lord of the Pyrrhian Eternals | 1 | 1 | **Not implemented** |  |
| Lord of the Storm | 1 | 1 | **Not implemented** |  |
| Malevolent Arcing | 1 | 1 | **Not implemented** |  |
| Master Chronomancer | 1 | 1 | **Not implemented** |  |
| Matter Absorption | 1 | 1 | **Not implemented** |  |
| Mechanical Augmentation (Aura) | 1 | 1 | **Not implemented** |  |
| Mind in the Machine | 1 | 1 | **Not implemented** |  |
| Multi-threat Eliminator | 1 | 1 | **Not implemented** |  |
| Nanoscarab Reanimation Beam (Aura) | 1 | 1 | **Not implemented** |  |
| Nightmare Shroud (Aura) | 1 | 1 | **Not implemented** |  |
| Obelisk Node Control | 1 | 1 | **Not implemented** |  |
| Optimised for Slaughter | 1 | 1 | **Not implemented** |  |
| Overwhelming Obliteration | 1 | 1 | **Not implemented** |  |
| Phase Shift Generator (Aura) | 1 | 1 | **Not implemented** |  |
| Phased Cover | 1 | 1 | **Not implemented** |  |
| Powers of the C’tan | 1 | 1 | **Not implemented** |  |
| Quantum Invader | 1 | 1 | **Not implemented** |  |
| Reanimation Nodes (Aura) | 1 | 1 | **Supported** | Feel No Pain |
| Relentless Combatants | 1 | 1 | **Not implemented** |  |
| Relentless March | 1 | 1 | **Not implemented** |  |
| Repair Barge | 1 | 1 | **Not implemented** |  |
| Rites of Reanimation | 1 | 1 | **Supported** | Feel No Pain |
| Self-destruction | 1 | 1 | **Not implemented** |  |
| Sentinel Construct | 1 | 1 | **Not implemented** |  |
| Snaking Ambush | 1 | 1 | **Not implemented** |  |
| Surrogate Hosts | 1 | 1 | **Not implemented** |  |
| Systematic Vigour | 1 | 1 | **Not implemented** |  |
| Targeting Relay | 1 | 1 | **Not implemented** |  |
| Technomancer | 1 | 1 | **Not implemented** |  |
| Tectonic Reverberations | 1 | 1 | **Not implemented** |  |
| Teleportation Matrix | 1 | 1 | **Not implemented** |  |
| Terrifying Monstrosity | 1 | 1 | **Not implemented** |  |
| The Lord’s Will | 1 | 1 | **Not implemented** |  |
| The Silent King | 1 | 1 | **Not implemented** |  |
| The Stars Are Right | 1 | 1 | **Not implemented** |  |
| The Vargard’s Duty | 1 | 1 | **Supported** | Feel No Pain |
| Their Number is Legion | 1 | 1 | **Not implemented** |  |
| Timesplinter Mantle | 1 | 1 | **Not implemented** |  |
| Titanic Walker | 1 | 1 | **Not implemented** |  |
| Transdimensional Displacement | 1 | 1 | **Not implemented** |  |
| Transient Madness | 1 | 1 | **Not implemented** |  |
| Translocation Beams | 1 | 1 | **Not implemented** |  |
| Translocation Shroud | 1 | 1 | **Not implemented** |  |
| Tunnelling Horrors | 1 | 1 | **Supported** | Redeploy |
| United In Destruction | 1 | 1 | **Not implemented** |  |
| Voice of the Triarch | 1 | 1 | **Not implemented** |  |
| Weapon Sentinels | 1 | 1 | **Not implemented** |  |
| Whirling Onslaught | 1 | 1 | **Not implemented** |  |
| Wraith Form | 1 | 1 | **Not implemented** |  |
| Ziggurat Dock | 1 | 1 | **Not implemented** |  |

#### Orks (`ORK`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| More Dakka | 5 | 5 | **Not implemented** |  |
| Dok’s Toolz | 3 | 3 | **Supported** | Feel No Pain |
| Mekaniak | 3 | 3 | **Not implemented** |  |
| Bomb Squigs | 2 | 2 | **Not implemented** |  |
| Clankin’ Forward | 2 | 2 | **Not implemented** |  |
| Dead Rippy | 2 | 2 | **Not implemented** |  |
| Deff from Above | 2 | 2 | **Not implemented** |  |
| Drive-by Dakka | 2 | 2 | **Not implemented** |  |
| Fortification | 2 | 2 | **Not implemented** |  |
| Hold Still and Say ‘Aargh!’ | 2 | 2 | **Not implemented** |  |
| Might is Right | 2 | 2 | **Not implemented** |  |
| Pyromaniaks | 2 | 2 | **Not implemented** |  |
| Ramshackle Cover | 2 | 2 | **Not implemented** |  |
| Speedboss | 2 | 2 | **Not implemented** |  |
| Splat! | 2 | 2 | **Not implemented** |  |
| Aerial Deployment | 1 | 1 | **Not implemented** |  |
| Beastboss | 1 | 1 | **Not implemented** |  |
| Beastly Rage | 1 | 1 | **Not implemented** |  |
| Big an’ Shooty | 1 | 1 | **Not implemented** |  |
| Big an’ Stompy | 1 | 1 | **Not implemented** |  |
| Big Booms | 1 | 1 | **Not implemented** |  |
| Bizarrely Resilient | 1 | 1 | **Not implemented** |  |
| Blastajet Attack Run | 1 | 1 | **Not implemented** |  |
| Boom Bomb | 1 | 1 | **Not implemented** |  |
| Burna Bomb | 1 | 1 | **Not implemented** |  |
| Buzzer Squigs | 1 | 1 | **Not implemented** |  |
| Da Bigger Dey Are, da Better Dey Drop | 1 | 1 | **Supported** | Deadly Demise |
| Da Bigger Dey iz... | 1 | 1 | **Not implemented** |  |
| Da Biggest and da Best | 1 | 1 | **Not implemented** |  |
| Da Biggest Booms | 1 | 1 | **Not implemented** |  |
| Da Boss Iz Watchin’ | 1 | 1 | **Not implemented** |  |
| Da Boss’ Ladz | 1 | 1 | **Not implemented** |  |
| Da Jump (Psychic) | 1 | 1 | **Not implemented** |  |
| Da Revolushun! | 1 | 1 | **Not implemented** |  |
| Dakkastorm | 1 | 1 | **Not implemented** |  |
| Dat’s Our Loot! | 1 | 1 | **Not implemented** |  |
| Dead Brutal | 1 | 1 | **Not implemented** |  |
| Ded Glowy Ammo (Aura) | 1 | 1 | **Not implemented** |  |
| Deranged Snotling Assault | 1 | 1 | **Not implemented** |  |
| Drill Boss | 1 | 1 | **Not implemented** |  |
| Drill Through | 1 | 1 | **Not implemented** |  |
| Drive-by Krumpin' | 1 | 1 | **Not implemented** |  |
| Dust Trails (Aura) | 1 | 1 | **Not implemented** |  |
| Fix Dat Armour Up | 1 | 1 | **Not implemented** |  |
| Flashiest Gitz | 1 | 1 | **Not implemented** |  |
| Fuel-mixa Grot | 1 | 1 | **Not implemented** |  |
| Full Throttle | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Furious Barrage | 1 | 1 | **Not implemented** |  |
| Gargantsmasha | 1 | 1 | **Not implemented** |  |
| Gargantuan | 1 | 1 | **Not implemented** |  |
| Get Da Good Bitz | 1 | 1 | **Not implemented** |  |
| Ghazghkull’s Waaagh! Banner (Aura) | 1 | 1 | **Not implemented** |  |
| Grot Riggers | 1 | 1 | **Not implemented** |  |
| Gun-crazy Show-offs | 1 | 1 | **Not implemented** |  |
| Has Yoo Been a Good Little Grot This Year? | 1 | 1 | **Not implemented** |  |
| High-octane Fuel | 1 | 1 | **Not implemented** |  |
| Interceptor | 1 | 1 | **Not implemented** |  |
| Krumpin’ Time | 1 | 1 | **Supported** | Feel No Pain |
| Kunnin’ Infiltrator | 1 | 1 | **Supported** | Infiltrators |
| Kustom Force Field | 1 | 1 | **Not implemented** |  |
| Mad Dok | 1 | 1 | **Supported** | Feel No Pain |
| Mega Carnage | 1 | 1 | **Not implemented** |  |
| Mekboy | 1 | 1 | **Supported** | Lone Operative |
| Monster Hunters | 1 | 1 | **Not implemented** |  |
| On Da Hunt | 1 | 1 | **Not implemented** |  |
| One Last Kill | 1 | 1 | **Not implemented** |  |
| One Scalpel Short of a Medpack | 1 | 1 | **Not implemented** |  |
| Outflank | 1 | 1 | **Not implemented** |  |
| Piston-driven Brutality | 1 | 1 | **Not implemented** |  |
| Plant the Waaagh! Banner | 1 | 1 | **Not implemented** |  |
| Plummeting Descent | 1 | 1 | **Not implemented** |  |
| Prophet of Da Great Waaagh! | 1 | 1 | **Not implemented** |  |
| Ramshackle but Rugged | 1 | 1 | **Not implemented** |  |
| Red Skull Kommandos | 1 | 1 | **Not implemented** |  |
| Redistributin’ da Gifts | 1 | 1 | **Not implemented** |  |
| Rivetin’ Dakka | 1 | 1 | **Not implemented** |  |
| Roar of Mork (Psychic) | 1 | 1 | **Not implemented** |  |
| Rolling Fortress | 1 | 1 | **Not implemented** |  |
| Runtherd | 1 | 1 | **Not implemented** |  |
| Sawbonez | 1 | 1 | **Not implemented** |  |
| Scatter! | 1 | 1 | **Not implemented** |  |
| Shokk Tunnel | 1 | 1 | **Not implemented** |  |
| Shokk-boosta | 1 | 1 | **Not implemented** |  |
| Shooty Power Trip | 1 | 1 | **Not implemented** |  |
| Shoutin’ Pole (Aura) | 1 | 1 | **Not implemented** |  |
| Single-minded Predator | 1 | 1 | **Not implemented** |  |
| Sneaky Surprise | 1 | 1 | **Not implemented** |  |
| Special Dose | 1 | 1 | **Not implemented** |  |
| Spiked Ram | 1 | 1 | **Not implemented** |  |
| Spirit of Gork (Psychic) | 1 | 1 | **Not implemented** |  |
| Squig Mine | 1 | 1 | **Not implemented** |  |
| Stompin’ Forward | 1 | 1 | **Not implemented** |  |
| Strafing Run | 1 | 1 | **Not implemented** |  |
| Super Runts | 1 | 1 | **Supported** | Scouts |
| Tank Hunters | 1 | 1 | **Not implemented** |  |
| Tellyporta Tech | 1 | 1 | **Supported** | Deep Strike |
| Thievin’ Scavengers | 1 | 1 | **Not implemented** |  |
| Thundering Stampede | 1 | 1 | **Not implemented** |  |
| Trample | 1 | 1 | **Not implemented** |  |
| Trophy Hunters | 1 | 1 | **Not implemented** |  |
| Unstable Oracle | 1 | 1 | **Not implemented** |  |
| Waaagh! Effigy (Aura) | 1 | 1 | **Not implemented** |  |
| Waaagh! Energy | 1 | 1 | **Not implemented** |  |
| Walking Bastion | 1 | 1 | **Not implemented** |  |
| Wall of Dakka | 1 | 1 | **Not implemented** |  |
| Wild Ride | 1 | 1 | **Not implemented** |  |
| Workshop | 1 | 1 | **Partial** | Heal on destroy (partial) |

#### Space Marines (`SM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Assault Ramp | 11 | 11 | **Not implemented** |  |
| Black Rage | 10 | 10 | **Not implemented** |  |
| Rites of Battle | 10 | 10 | **Not implemented** |  |
| Astartes Banner | 9 | 9 | **Not implemented** |  |
| Honour or Death | 7 | 7 | **Not implemented** |  |
| Litany of Hate | 6 | 6 | **Not implemented** |  |
| Psychic Hood | 6 | 6 | **Supported** | Feel No Pain |
| Tactical Precision | 6 | 6 | **Not implemented** |  |
| Teleport Homer | 6 | 6 | **Not implemented** |  |
| Inspiring Leader | 5 | 5 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |
| Narthecium | 5 | 5 | **Not implemented** |  |
| Sanguinary Priest | 4 | 4 | **Supported** | Feel No Pain |
| Blessing of the Omnissiah | 3 | 3 | **Not implemented** |  |
| Blood Chalice | 3 | 3 | **Not implemented** |  |
| Death Vision of Sanguinius | 3 | 3 | **Not implemented** |  |
| Hunting Hounds | 3 | 3 | **Not implemented** |  |
| Pack Leader | 3 | 3 | **Not implemented** |  |
| Unbreakable Duty | 3 | 3 | **Supported** | Feel No Pain |
| Vanguard Assault | 3 | 3 | **Not implemented** |  |
| Vengeance of the Omnissiah | 3 | 3 | **Not implemented** |  |
| Aerial Assault | 2 | 2 | **Supported** | Deep Strike |
| An Honourable Death in Combat | 2 | 2 | **Not implemented** |  |
| Annihilator | 2 | 2 | **Not implemented** |  |
| Aquilon Optics | 2 | 2 | **Not implemented** |  |
| Armorium Cherub | 2 | 2 | **Not implemented** |  |
| Armoured Resilience | 2 | 2 | **Not implemented** |  |
| Armoured Spearhead | 2 | 2 | **Not implemented** |  |
| Assault Vehicle | 2 | 2 | **Not implemented** |  |
| Catechism of Death | 2 | 2 | **Not implemented** |  |
| Death to the Alien | 2 | 2 | **Not implemented** |  |
| Designer’s Note | 2 | 2 | **Not implemented** |  |
| Drop Pod Assault | 2 | 2 | **Not implemented** |  |
| Duty Eternal | 2 | 2 | **Not implemented** |  |
| Ferocious Assault | 2 | 2 | **Not implemented** |  |
| Finest Hour | 2 | 2 | **Not implemented** |  |
| Fire and Redeploy | 2 | 2 | **Supported** | Redeploy |
| Fire Support | 2 | 2 | **Not implemented** |  |
| Forlorn Hero | 2 | 2 | **Supported** | Advance+Charge (exact wording), Scouts |
| Fury of the First | 2 | 2 | **Not implemented** |  |
| Gene-seed Recovery | 2 | 2 | **Not implemented** |  |
| Guerrilla Tactics | 2 | 2 | **Supported** | Redeploy |
| Hammer of Wrath | 2 | 2 | **Not implemented** |  |
| High King of Fenris | 2 | 2 | **Not implemented** |  |
| Interceptor | 2 | 2 | **Not implemented** |  |
| Into the Foe | 2 | 2 | **Not implemented** |  |
| Iron Priest | 2 | 2 | **Supported** | Lone Operative |
| Martial Superiority | 2 | 2 | **Not implemented** |  |
| Master Tactician | 2 | 2 | **Not implemented** |  |
| Mental Fortress (Psychic) | 2 | 2 | **Not implemented** |  |
| Outrider Escort | 2 | 2 | **Not implemented** |  |
| Pinning Bombardment | 2 | 2 | **Not implemented** |  |
| Righteous Zeal | 2 | 2 | **Not implemented** |  |
| Rotating Death | 2 | 2 | **Not implemented** |  |
| Self Repair | 2 | 2 | **Not implemented** |  |
| Sentinel Protocols | 2 | 2 | **Not implemented** |  |
| Spiritual Leader | 2 | 2 | **Not implemented** |  |
| Strafing Run | 2 | 2 | **Not implemented** |  |
| Suppression Fire | 2 | 2 | **Not implemented** |  |
| Swift Assault | 2 | 2 | **Not implemented** |  |
| Techmarine | 2 | 2 | **Supported** | Lone Operative |
| Tempormortis | 2 | 2 | **Supported** | Fights First |
| Terminatus Assault | 2 | 2 | **Not implemented** |  |
| Wisdom of the Ancients (Aura) | 2 | 2 | **Not implemented** |  |
| Aerial Deployment | 1 | 1 | **Not implemented** |  |
| Aggressive Hunter | 1 | 1 | **Not implemented** |  |
| Alpha Hunter | 1 | 1 | **Supported** | Scouts |
| Alpha Predator | 1 | 1 | **Not implemented** |  |
| Ancient Tactician | 1 | 1 | **Not implemented** |  |
| Angelic Visage | 1 | 1 | **Not implemented** |  |
| Angel’s Wrath | 1 | 1 | **Not implemented** |  |
| Annihilator Protocols | 1 | 1 | **Not implemented** |  |
| Anvil of Endurance | 1 | 1 | **Not implemented** |  |
| Armour of Faith | 1 | 1 | **Not implemented** |  |
| Armour of Fate | 1 | 1 | **Not implemented** |  |
| Atomantic Arc-reactor | 1 | 1 | **Not implemented** |  |
| Aura of Fervour (Aura) | 1 | 1 | **Not implemented** |  |
| Author of the Codex | 1 | 1 | **Not implemented** |  |
| Ballistus Strike | 1 | 1 | **Not implemented** |  |
| Battle-lust | 1 | 1 | **Not implemented** |  |
| Berserk Charge | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Berserk Fury | 1 | 1 | **Not implemented** |  |
| Bestial Fury | 1 | 1 | **Not implemented** |  |
| Bestial Rage | 1 | 1 | **Not implemented** |  |
| Blackstar Cluster Launcher | 1 | 1 | **Not implemented** |  |
| Blackwing Mantle | 1 | 1 | **Not implemented** |  |
| Bladeguard | 1 | 1 | **Not implemented** |  |
| Born of Wolves | 1 | 1 | **Not implemented** |  |
| Braziers of Judgement | 1 | 1 | **Not implemented** |  |
| Brutalis Charge | 1 | 1 | **Not implemented** |  |
| Catechism of Fire | 1 | 1 | **Not implemented** |  |
| Ceramite Cover | 1 | 1 | **Not implemented** |  |
| Cerebrex Logic Engine | 1 | 1 | **Supported** | Redeploy, Scouts |
| Chainsword Doctrines | 1 | 1 | **Not implemented** |  |
| Champion of the Kingsguard | 1 | 1 | **Not implemented** |  |
| Chosen Companions | 1 | 1 | **Not implemented** |  |
| Chronus | 1 | 1 | **Supported** | Lone Operative |
| Close In for the Kill | 1 | 1 | **Not implemented** |  |
| Close-quarters Firepower | 1 | 1 | **Not implemented** |  |
| Cold and Calculating | 1 | 1 | **Not implemented** |  |
| Combat Disembarkation | 1 | 1 | **Not implemented** |  |
| Combat Squads | 1 | 1 | **Not implemented** |  |
| Combat Support | 1 | 1 | **Not implemented** |  |
| Command Squad | 1 | 1 | **Not implemented** |  |
| Concealed Positions | 1 | 1 | **Not implemented** |  |
| Condemnatory Annihilation | 1 | 1 | **Not implemented** |  |
| Crewed Artillery | 1 | 1 | **Not implemented** |  |
| Crusade of Wrath | 1 | 1 | **Not implemented** |  |
| Cunning Hunters | 1 | 1 | **Not implemented** |  |
| Cut Off Their Escape | 1 | 1 | **Not implemented** |  |
| Dark Angels Bodyguard | 1 | 1 | **Supported** | Lone Operative |
| Deadly Stalkers | 1 | 1 | **Not implemented** |  |
| Deadly Terror | 1 | 1 | **Not implemented** |  |
| Death Mask of Sanguinius | 1 | 1 | **Not implemented** |  |
| Death-hold | 1 | 1 | **Not implemented** |  |
| Deathstorm Assault | 1 | 1 | **Not implemented** |  |
| Deathwing | 1 | 1 | **Not implemented** |  |
| Decimator Protocols | 1 | 1 | **Not implemented** |  |
| Deeds of Heroism | 1 | 1 | **Not implemented** |  |
| Defensive Array | 1 | 1 | **Not implemented** |  |
| Deployment Complete | 1 | 1 | **Not implemented** |  |
| Deredeo Strike | 1 | 1 | **Not implemented** |  |
| Destructor | 1 | 1 | **Not implemented** |  |
| Driven by Fury | 1 | 1 | **Not implemented** |  |
| Echo of the Ravenspire | 1 | 1 | **Not implemented** |  |
| Embittered | 1 | 1 | **Not implemented** |  |
| Emergency Combat Embarkation | 1 | 1 | **Not implemented** |  |
| Engulfing Fear (Psychic) | 1 | 1 | **Not implemented** |  |
| Enmity for the Unworthy | 1 | 1 | **Not implemented** |  |
| Evade and Survive | 1 | 1 | **Not implemented** |  |
| Even In Death I Serve | 1 | 1 | **Supported** | Deadly Demise |
| Executioner | 1 | 1 | **Not implemented** |  |
| Exemplar of Hate | 1 | 1 | **Not implemented** |  |
| Exhortation of Rage | 1 | 1 | **Not implemented** |  |
| Exploit Their Cowardice | 1 | 1 | **Not implemented** |  |
| Feared Interrogator | 1 | 1 | **Not implemented** |  |
| Fearsome Assault | 1 | 1 | **Not implemented** |  |
| Fervour of the Ancients (Aura) | 1 | 1 | **Not implemented** |  |
| Fire Discipline | 1 | 1 | **Not implemented** |  |
| For the Chapter! | 1 | 1 | **Not implemented** |  |
| For the Khan! | 1 | 1 | **Not implemented** |  |
| Forgefather | 1 | 1 | **Not implemented** |  |
| Fortification | 1 | 1 | **Not implemented** |  |
| Fortis Doctrines | 1 | 1 | **Not implemented** |  |
| Frenzied Reprisal | 1 | 1 | **Not implemented** |  |
| Frozen Prey | 1 | 1 | **Not implemented** |  |
| Fury Unbound | 1 | 1 | **Not implemented** |  |
| Gift of the Iron Wolf | 1 | 1 | **Not implemented** |  |
| Gifted Commander | 1 | 1 | **Not implemented** |  |
| Glory of Ultramar | 1 | 1 | **Not implemented** |  |
| Grand Master of the Deathwing | 1 | 1 | **Not implemented** |  |
| Grand Master of the Ravenwing | 1 | 1 | **Supported** | Advance+Shoot (exact wording) |
| Guardian of the Lost | 1 | 1 | **Not implemented** |  |
| Guiding Hand | 1 | 1 | **Not implemented** |  |
| Guile of the Wolf (Aura) | 1 | 1 | **Not implemented** |  |
| Hailstrike | 1 | 1 | **Not implemented** |  |
| Hammer Blow | 1 | 1 | **Not implemented** |  |
| Hammerstrike | 1 | 1 | **Not implemented** |  |
| Headhunters | 1 | 1 | **Not implemented** |  |
| Headstrong | 1 | 1 | **Not implemented** |  |
| Healing Balms | 1 | 1 | **Not implemented** |  |
| Heirs of Azkaellon | 1 | 1 | **Not implemented** |  |
| Heroic Last Stand | 1 | 1 | **Not implemented** |  |
| High Marshal | 1 | 1 | **Not implemented** |  |
| Honour Guard | 1 | 1 | **Not implemented** |  |
| Honour Guard of Macragge | 1 | 1 | **Supported** | Feel No Pain |
| Honour of the Chapter | 1 | 1 | **Not implemented** |  |
| Hood of Hellfire | 1 | 1 | **Supported** | Feel No Pain |
| Hunter Missile Targeting | 1 | 1 | **Not implemented** |  |
| Huskarl to the Jarl | 1 | 1 | **Supported** | Feel No Pain |
| Icon of Obstinacy | 1 | 1 | **Not implemented** |  |
| Icon of Old Caliban (Aura) | 1 | 1 | **Supported** | Stealth |
| Incendiary Terror | 1 | 1 | **Not implemented** |  |
| Indomitable Assault | 1 | 1 | **Not implemented** |  |
| Indomitor Doctrines | 1 | 1 | **Not implemented** |  |
| Inner Circle | 1 | 1 | **Not implemented** |  |
| Inspirational Exemplar | 1 | 1 | **Not implemented** |  |
| Inspired Retribution | 1 | 1 | **Not implemented** |  |
| Interception Strike | 1 | 1 | **Not implemented** |  |
| Intractable Will | 1 | 1 | **Not implemented** |  |
| Inviolable Transport | 1 | 1 | **Not implemented** |  |
| Iron Father | 1 | 1 | **Supported** | Lone Operative |
| Isolate and Destroy | 1 | 1 | **Not implemented** |  |
| Judgement of the Omnissiah | 1 | 1 | **Not implemented** |  |
| Judgement of the Weak | 1 | 1 | **Not implemented** |  |
| Keep the Banner High | 1 | 1 | **Not implemented** |  |
| Knight Champion of Macragge | 1 | 1 | **Not implemented** |  |
| Knights of Caliban | 1 | 1 | **Not implemented** |  |
| Last Laugh | 1 | 1 | **Not implemented** |  |
| Lead From the Front | 1 | 1 | **Supported** | Scouts |
| Legacy of Jerulas | 1 | 1 | **Not implemented** |  |
| Legendary Tenacity | 1 | 1 | **Not implemented** |  |
| Let Loose the Wolves | 1 | 1 | **Not implemented** |  |
| Lightning Assault | 1 | 1 | **Not implemented** |  |
| Lightning-fast Manoeuvres | 1 | 1 | **Not implemented** |  |
| Line-breaker | 1 | 1 | **Not implemented** |  |
| Litanies of the Devout | 1 | 1 | **Not implemented** |  |
| Lord of Slaughter | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Lord of the Pyroclasts | 1 | 1 | **Not implemented** |  |
| Lord of the Wolfkin | 1 | 1 | **Not implemented** |  |
| Lost to Fury | 1 | 1 | **Not implemented** |  |
| Magna-grapple | 1 | 1 | **Not implemented** |  |
| Mantle of the Troll King | 1 | 1 | **Not implemented** |  |
| Mark the Target | 1 | 1 | **Not implemented** |  |
| Martial Honour | 1 | 1 | **Not implemented** |  |
| Mass of Doom | 1 | 1 | **Not implemented** |  |
| Master of Deceit | 1 | 1 | **Supported** | Redeploy |
| Master of Manoeuvre | 1 | 1 | **Not implemented** |  |
| Master of Prescience (Psychic) | 1 | 1 | **Not implemented** |  |
| Master of Shadows | 1 | 1 | **Not implemented** |  |
| Master of the Fleet | 1 | 1 | **Supported** | Deep Strike |
| Master of the Forge | 1 | 1 | **Not implemented** |  |
| Masterful Tactician | 1 | 1 | **Not implemented** |  |
| Meteoric Descent | 1 | 1 | **Supported** | Deep Strike |
| Might of Heroes (Psychic) | 1 | 1 | **Not implemented** |  |
| Mindlock | 1 | 1 | **Not implemented** |  |
| Miraculous Saviour | 1 | 1 | **Not implemented** |  |
| Morkai’s Howl | 1 | 1 | **Not implemented** |  |
| Mortis Strike | 1 | 1 | **Not implemented** |  |
| Multi-spectrum Array | 1 | 1 | **Not implemented** |  |
| Murder-maker (Aura) | 1 | 1 | **Not implemented** |  |
| Nowhere to Hide | 1 | 1 | **Not implemented** |  |
| Oath of Rynn | 1 | 1 | **Not implemented** |  |
| Oathbound | 1 | 1 | **Not implemented** |  |
| Objective Secured | 1 | 1 | **Not implemented** |  |
| Omni-scramblers | 1 | 1 | **Not implemented** |  |
| Orbital Comms Array (Aura) | 1 | 1 | **Not implemented** |  |
| Outflank | 1 | 1 | **Not implemented** |  |
| Overcharged Engines | 1 | 1 | **Not implemented** |  |
| Overwhelming Short-range Firepower | 1 | 1 | **Not implemented** |  |
| Pelt of the Doppegangrel | 1 | 1 | **Not implemented** |  |
| Pious Fervour | 1 | 1 | **Not implemented** |  |
| Powerful Volley | 1 | 1 | **Not implemented** |  |
| Predatory Instinct | 1 | 1 | **Not implemented** |  |
| Press the Attack | 1 | 1 | **Not implemented** |  |
| Primarch of the First Legion | 1 | 1 | **Not implemented** |  |
| Prioritised Eradication | 1 | 1 | **Not implemented** |  |
| Priority Objective Identified | 1 | 1 | **Not implemented** |  |
| Priority Target Acquisition | 1 | 1 | **Not implemented** |  |
| Rampart | 1 | 1 | **Not implemented** |  |
| Reaping Tally | 1 | 1 | **Not implemented** |  |
| Recitation of Faith | 1 | 1 | **Supported** | Feel No Pain |
| Redeemer of the Lost | 1 | 1 | **Not implemented** |  |
| Refuse to Accept Defeat | 1 | 1 | **Not implemented** |  |
| Refuse to Yield | 1 | 1 | **Not implemented** |  |
| Remorseless Persecution | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Reposition Under Covering Fire | 1 | 1 | **Not implemented** |  |
| Rites of Tempering | 1 | 1 | **Supported** | Feel No Pain |
| Rolling Fortress | 1 | 1 | **Not implemented** |  |
| Rugged Resilience | 1 | 1 | **Not implemented** |  |
| Savage Frenzy | 1 | 1 | **Not implemented** |  |
| Savage Fury | 1 | 1 | **Not implemented** |  |
| Seeker of Lost Relics | 1 | 1 | **Supported** | Feel No Pain |
| Sentry Programming | 1 | 1 | **Not implemented** |  |
| Shadowmaster | 1 | 1 | **Not implemented** |  |
| Shield of Sanguinius (Aura, Psychic) | 1 | 1 | **Supported** | Feel No Pain |
| Shock Assault | 1 | 1 | **Not implemented** |  |
| Shrouding (Psychic) | 1 | 1 | **Supported** | Stealth |
| Siege Captain | 1 | 1 | **Not implemented** |  |
| Siege Shield | 1 | 1 | **Not implemented** |  |
| Siege-breaker Protocols | 1 | 1 | **Not implemented** |  |
| Sigismund’s Heir | 1 | 1 | **Not implemented** |  |
| Signum | 1 | 1 | **Not implemented** |  |
| Signum Array | 1 | 1 | **Not implemented** |  |
| Silent Fury | 1 | 1 | **Not implemented** |  |
| Skilled Riders | 1 | 1 | **Not implemented** |  |
| Skyfire Protocols | 1 | 1 | **Not implemented** |  |
| Slayer’s Oath | 1 | 1 | **Not implemented** |  |
| Spear of Chogoris | 1 | 1 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |
| Specialised Weapon System | 1 | 1 | **Not implemented** |  |
| Spectrus Doctrines | 1 | 1 | **Supported** | Redeploy |
| Speed of the Hunter | 1 | 1 | **Not implemented** |  |
| Stabilised Disembarkation | 1 | 1 | **Not implemented** |  |
| Stasis Bomb | 1 | 1 | **Not implemented** |  |
| Sternguard Focus | 1 | 1 | **Not implemented** |  |
| Storm Assault | 1 | 1 | **Not implemented** |  |
| Storm of Vengeance | 1 | 1 | **Not implemented** |  |
| Strafing Enfilade | 1 | 1 | **Not implemented** |  |
| Strategic Dispersal | 1 | 1 | **Not implemented** |  |
| Strategic Knowledge | 1 | 1 | **Supported** | Advance+Shoot (exact wording), Fall Back+Shoot (exact wording) |
| Strikes of Retribution | 1 | 1 | **Not implemented** |  |
| Sunderer of Fortresses | 1 | 1 | **Not implemented** |  |
| Supreme Grand Master | 1 | 1 | **Not implemented** |  |
| Surgical Precision | 1 | 1 | **Not implemented** |  |
| Tactical Instinct | 1 | 1 | **Not implemented** |  |
| Talonmaster | 1 | 1 | **Supported** | Lone Operative |
| Talonstrike Doctrines | 1 | 1 | **Not implemented** |  |
| Tank Commander | 1 | 1 | **Not implemented** |  |
| Target Elimination | 1 | 1 | **Not implemented** |  |
| Target Priority | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Target Sighted | 1 | 1 | **Not implemented** |  |
| Targeter Optics | 1 | 1 | **Not implemented** |  |
| Tempered Ferocity | 1 | 1 | **Not implemented** |  |
| Tempest’s Wrath (Psychic) | 1 | 1 | **Not implemented** |  |
| Temple Relics | 1 | 1 | **Not implemented** |  |
| Termite Assault | 1 | 1 | **Not implemented** |  |
| Terror Troops (Aura) | 1 | 1 | **Not implemented** |  |
| The Emperor’s Shield | 1 | 1 | **Not implemented** |  |
| The Fierce Eye | 1 | 1 | **Not implemented** |  |
| The Great Wolf | 1 | 1 | **Not implemented** |  |
| The Imperium’s Sword | 1 | 1 | **Not implemented** |  |
| The Quickening (Psychic) | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| The Red Grail | 1 | 1 | **Not implemented** |  |
| The Spiritshield Helm | 1 | 1 | **Supported** | Feel No Pain |
| Thunderous Charge | 1 | 1 | **Not implemented** |  |
| Thunderous Impact | 1 | 1 | **Not implemented** |  |
| Thunderstrike | 1 | 1 | **Not implemented** |  |
| Titan-killer | 1 | 1 | **Not implemented** |  |
| To the Last | 1 | 1 | **Not implemented** |  |
| Total Obliteration | 1 | 1 | **Not implemented** |  |
| Transfixing Gaze (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Tremor Shells | 1 | 1 | **Not implemented** |  |
| Trophy Taker | 1 | 1 | **Not implemented** |  |
| Turbo-boost | 1 | 1 | **Not implemented** |  |
| Tyrannic War Veterans | 1 | 1 | **Not implemented** |  |
| Ultramarines Bodyguard | 1 | 1 | **Supported** | Lone Operative |
| Ultramarines Honour Guard | 1 | 1 | **Not implemented** |  |
| Unflinching | 1 | 1 | **Not implemented** |  |
| Unorthodox Strategist (Aura) | 1 | 1 | **Not implemented** |  |
| Unstoppable Champion | 1 | 1 | **Not implemented** |  |
| Unto the Anvil | 1 | 1 | **Not implemented** |  |
| Unyielding in the Face of the Foe | 1 | 1 | **Not implemented** |  |
| Vanquish the Foe | 1 | 1 | **Not implemented** |  |
| Vehement Aggression | 1 | 1 | **Not implemented** |  |
| Veil of Time (Psychic) | 1 | 1 | **Not implemented** |  |
| Vengeful Exhortation | 1 | 1 | **Not implemented** |  |
| Violent Fury | 1 | 1 | **Not implemented** |  |
| Virtuous Onslaught | 1 | 1 | **Not implemented** |  |
| Visions of Heresy | 1 | 1 | **Not implemented** |  |
| Vivispectrum | 1 | 1 | **Not implemented** |  |
| Voice of Experience | 1 | 1 | **Not implemented** |  |
| War Howl | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Warden of the Imperium Nihilus | 1 | 1 | **Not implemented** |  |
| Watch Master | 1 | 1 | **Not implemented** |  |
| Whirlwind of Gore | 1 | 1 | **Not implemented** |  |
| Wind Walker (Psychic) | 1 | 1 | **Not implemented** |  |
| Wings of Sanguinius (Psychic) | 1 | 1 | **Not implemented** |  |
| Wrathful Rampage | 1 | 1 | **Not implemented** |  |
| Zealot’s Fervour | 1 | 1 | **Not implemented** |  |

#### Thousand Sons (`TS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Assault Ramp | 4 | 4 | **Not implemented** |  |
| Aerial Assault | 2 | 2 | **Supported** | Deep Strike |
| Empyric Guidance (Psychic) | 2 | 2 | **Not implemented** |  |
| Interceptor | 2 | 2 | **Not implemented** |  |
| Split | 2 | 2 | **Not implemented** |  |
| Aetherstride (Psychic) | 1 | 1 | **Supported** | Deep Strike |
| Ambushing Hunters | 1 | 1 | **Supported** | Redeploy |
| Arcane Shield (Psychic) | 1 | 1 | **Not implemented** |  |
| Arch-Sorcerer of Tzeentch (Psychic) | 1 | 1 | **Not implemented** |  |
| Armoured Resilience | 1 | 1 | **Not implemented** |  |
| Armoured Spearhead | 1 | 1 | **Not implemented** |  |
| Atomantic Arc-reactor | 1 | 1 | **Not implemented** |  |
| Bestial Prophet | 1 | 1 | **Not implemented** |  |
| Binding Tendrils (Psychic) | 1 | 1 | **Not implemented** |  |
| Blazing Salvoes | 1 | 1 | **Not implemented** |  |
| Bomb Rack | 1 | 1 | **Not implemented** |  |
| Bounding Leaps | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Bringers of Change | 1 | 1 | **Not implemented** |  |
| Daemon Lord of Tzeentch (Aura) | 1 | 1 | **Not implemented** |  |
| Deredeo Strike | 1 | 1 | **Not implemented** |  |
| Destroyer of Futures | 1 | 1 | **Not implemented** |  |
| Devoted to Destruction | 1 | 1 | **Not implemented** |  |
| Duty Eternal | 1 | 1 | **Not implemented** |  |
| Ensorcelled Annihilation | 1 | 1 | **Not implemented** |  |
| Ensorcelled Destruction | 1 | 1 | **Not implemented** |  |
| Even In Death I Serve | 1 | 1 | **Supported** | Deadly Demise |
| Exploding Horrors | 1 | 1 | **Not implemented** |  |
| Ferocious Assault | 1 | 1 | **Not implemented** |  |
| Flame-wreathed | 1 | 1 | **Not implemented** |  |
| Glamour of Tzeentch (Aura, Psychic) | 1 | 1 | **Supported** | Stealth |
| Glimpse of Eternity (Psychic) | 1 | 1 | **Not implemented** |  |
| Hunter of Souls | 1 | 1 | **Not implemented** |  |
| Illusions of Tzeentch (Psychic) | 1 | 1 | **Not implemented** |  |
| Immaterial Flare (Aura) | 1 | 1 | **Not implemented** |  |
| Inviolable Transport | 1 | 1 | **Not implemented** |  |
| Line-breaker | 1 | 1 | **Not implemented** |  |
| Lord of Chaos | 1 | 1 | **Not implemented** |  |
| Lord of Fate | 1 | 1 | **Supported** | Feel No Pain |
| Lord of the Planet of the Sorcerers (Psychic) | 1 | 1 | **Not implemented** |  |
| Malefic Maelstrom (Psychic) | 1 | 1 | **Not implemented** |  |
| Malign Trickery | 1 | 1 | **Not implemented** |  |
| Marked by Fate (Psychic) | 1 | 1 | **Not implemented** |  |
| Master of Magicks (Psychic) | 1 | 1 | **Not implemented** |  |
| Mutating Vortex (Aura) | 1 | 1 | **Not implemented** |  |
| One Head Looks Back (Aura) | 1 | 1 | **Not implemented** |  |
| One Head Looks Forward | 1 | 1 | **Not implemented** |  |
| Pinning Bombardment | 1 | 1 | **Not implemented** |  |
| Powerful Volley | 1 | 1 | **Not implemented** |  |
| Prophesied Doom | 1 | 1 | **Not implemented** |  |
| Prophetic Sentinels | 1 | 1 | **Not implemented** |  |
| Rebind Rubricae (Psychic) | 1 | 1 | **Not implemented** |  |
| Regenerating Monstrosities | 1 | 1 | **Not implemented** |  |
| Rites of Coalescence | 1 | 1 | **Not implemented** |  |
| Rolling Fortress | 1 | 1 | **Not implemented** |  |
| Rotating Death | 1 | 1 | **Not implemented** |  |
| Sacrificial Blessing | 1 | 1 | **Not implemented** |  |
| Scryer of Fates (Psychic) | 1 | 1 | **Supported** | Redeploy |
| Scuttling Walker | 1 | 1 | **Not implemented** |  |
| Servile Pawns | 1 | 1 | **Supported** | Lone Operative |
| Siege Shield | 1 | 1 | **Not implemented** |  |
| Slashing Dive | 1 | 1 | **Not implemented** |  |
| Snarling Protector | 1 | 1 | **Not implemented** |  |
| Sorcerous Support | 1 | 1 | **Not implemented** |  |
| Spirit Snare | 1 | 1 | **Not implemented** |  |
| Strafing Run | 1 | 1 | **Not implemented** |  |
| Sullen Malevolence (Aura) | 1 | 1 | **Not implemented** |  |
| Sunderer of Fortresses | 1 | 1 | **Not implemented** |  |
| Termite Assault | 1 | 1 | **Not implemented** |  |
| Terrifying Assault | 1 | 1 | **Not implemented** |  |
| Titan-killer | 1 | 1 | **Not implemented** |  |
| Twisted Sorceries (Psychic) | 1 | 1 | **Not implemented** |  |
| Unearthly Power | 1 | 1 | **Not implemented** |  |

#### Tyranids (`TYR`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Feeder Tendrils | 3 | 3 | **Not implemented** |  |
| Bio-minefield | 2 | 2 | **Not implemented** |  |
| Floating Death | 2 | 2 | **Not implemented** |  |
| Singular Purpose | 2 | 2 | **Supported** | Feel No Pain |
| Will of the Hive Mind | 2 | 2 | **Not implemented** |  |
| Adaptable Predators | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Adaptive Instincts | 1 | 1 | **Not implemented** |  |
| Aerial Seeding | 1 | 1 | **Not implemented** |  |
| Airborne Predator | 1 | 1 | **Not implemented** |  |
| Alpha Invader | 1 | 1 | **Not implemented** |  |
| Alpha Leader | 1 | 1 | **Not implemented** |  |
| Alpha Warrior | 1 | 1 | **Not implemented** |  |
| Apex-beast | 1 | 1 | **Not implemented** |  |
| Bio-stimulus | 1 | 1 | **Not implemented** |  |
| Blistering Assault | 1 | 1 | **Not implemented** |  |
| Bounding Leap | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Brood Progenitor (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Burning Spray | 1 | 1 | **Not implemented** |  |
| Chitinous Horrors | 1 | 1 | **Not implemented** |  |
| Chitinous Horrors (Aura) | 1 | 1 | **Not implemented** |  |
| Death Blow | 1 | 1 | **Not implemented** |  |
| Death From Below | 1 | 1 | **Not implemented** |  |
| Death Scream | 1 | 1 | **Not implemented** |  |
| Defensive Stance | 1 | 1 | **Not implemented** |  |
| Digestion Spine | 1 | 1 | **Not implemented** |  |
| Disruption Bombardment | 1 | 1 | **Not implemented** |  |
| Domination of the Hive Mind (Aura) | 1 | 1 | **Not implemented** |  |
| Encephalic Diffusion (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Enhanced Toxic Miasma | 1 | 1 | **Not implemented** |  |
| Fear of the Unseen (Aura) | 1 | 1 | **Not implemented** |  |
| Feeding Frenzy | 1 | 1 | **Not implemented** |  |
| Foul Spores (Aura) | 1 | 1 | **Supported** | Stealth |
| Frenzied Metabolism | 1 | 1 | **Not implemented** |  |
| Grasping Tendrils | 1 | 1 | **Not implemented** |  |
| Grisly Spectacle | 1 | 1 | **Not implemented** |  |
| Guardian Organism | 1 | 1 | **Supported** | Feel No Pain |
| Harpoon Barbs | 1 | 1 | **Not implemented** |  |
| Hive Commander | 1 | 1 | **Not implemented** |  |
| Hive Defences | 1 | 1 | **Not implemented** |  |
| Hypersensory Array | 1 | 1 | **Not implemented** |  |
| Hypertoxic Miasma (Aura) | 1 | 1 | **Not implemented** |  |
| Hypnotic Gaze (Psychic) | 1 | 1 | **Not implemented** |  |
| Irresistible Force | 1 | 1 | **Not implemented** |  |
| It Itches! | 1 | 1 | **Not implemented** |  |
| Malign Presence (Aura) | 1 | 1 | **Not implemented** |  |
| Neural Disruption | 1 | 1 | **Not implemented** |  |
| Neurocytes | 1 | 1 | **Not implemented** |  |
| Neuroloids | 1 | 1 | **Not implemented** |  |
| Node Lash (Psychic) | 1 | 1 | **Not implemented** |  |
| Onslaught (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Overgrown Barbs | 1 | 1 | **Not implemented** |  |
| Parasitic Infection | 1 | 1 | **Not implemented** |  |
| Paroxysm (Psychic) | 1 | 1 | **Not implemented** |  |
| Pheromone Trail | 1 | 1 | **Not implemented** |  |
| Pouncing Leap | 1 | 1 | **Not implemented** |  |
| Prey Adaptation | 1 | 1 | **Not implemented** |  |
| Psychic Terror (Psychic) | 1 | 1 | **Not implemented** |  |
| Psychological Saboteur (Aura) | 1 | 1 | **Not implemented** |  |
| Resilient Organism | 1 | 1 | **Not implemented** |  |
| Seed Mucolids | 1 | 1 | **Not implemented** |  |
| Seed Spore Mines | 1 | 1 | **Not implemented** |  |
| Skulking Horrors | 1 | 1 | **Not implemented** |  |
| Spawn Termagants | 1 | 1 | **Not implemented** |  |
| Spirit Leech (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Spore Mine Cysts | 1 | 1 | **Not implemented** |  |
| Stalking Forward | 1 | 1 | **Not implemented** |  |
| Subterranean Tunnels | 1 | 1 | **Supported** | Deep Strike |
| Symbiotic Targeting | 1 | 1 | **Not implemented** |  |
| Terror From The Deep | 1 | 1 | **Supported** | Deep Strike |
| Unnatural Resilience | 1 | 1 | **Supported** | Feel No Pain |
| Unstoppable Monster | 1 | 1 | **Not implemented** |  |
| Vanguard Predator | 1 | 1 | **Not implemented** |  |
| Vicious Insight | 1 | 1 | **Not implemented** |  |
| Warp Field (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Winged Swarm | 1 | 1 | **Not implemented** |  |

#### T’au Empire (`TAU`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Fortification | 5 | 5 | **Not implemented** |  |
| Battlesuit Support System | 4 | 4 | **Supported** | Fall Back+Shoot (exact wording) |
| Weapon Support System | 4 | 4 | **Not implemented** |  |
| Targeting Array | 3 | 3 | **Not implemented** |  |
| Tidewall Cover | 3 | 3 | **Not implemented** |  |
| Armour Hunter | 2 | 2 | **Not implemented** |  |
| DS8 Support Turret | 2 | 2 | **Not implemented** |  |
| Reinforced Cover | 2 | 2 | **Not implemented** |  |
| Advanced Armour | 1 | 1 | **Supported** | Feel No Pain |
| Advanced Scouting | 1 | 1 | **Not implemented** |  |
| Aerial Disengagement | 1 | 1 | **Not implemented** |  |
| Aggressive Deployment | 1 | 1 | **Not implemented** |  |
| Agile Combatant | 1 | 1 | **Supported** | Fall Back+Shoot (exact wording) |
| Agile Dogfighter | 1 | 1 | **Not implemented** |  |
| Air Caste Colossus | 1 | 1 | **Not implemented** |  |
| Airborne Agility | 1 | 1 | **Not implemented** |  |
| Assassin | 1 | 1 | **Not implemented** |  |
| Bounty Hunters | 1 | 1 | **Not implemented** |  |
| Breach and Clear | 1 | 1 | **Not implemented** |  |
| Coldstar Commander | 1 | 1 | **Not implemented** |  |
| Coordinated Leadership | 1 | 1 | **Not implemented** |  |
| Coordinated Strike | 1 | 1 | **Not implemented** |  |
| Crack Shot | 1 | 1 | **Not implemented** |  |
| Crisis Commander | 1 | 1 | **Not implemented** |  |
| Drone Escort | 1 | 1 | **Not implemented** |  |
| Drone Harassment Tactics | 1 | 1 | **Not implemented** |  |
| Droneport | 1 | 1 | **Not implemented** |  |
| Duality Shield | 1 | 1 | **Not implemented** |  |
| Eclipse Field Generator | 1 | 1 | **Not implemented** |  |
| Enforcer Commander | 1 | 1 | **Not implemented** |  |
| Failure Is Not an Option | 1 | 1 | **Supported** | Feel No Pain |
| Fieldcraft | 1 | 1 | **Not implemented** |  |
| Fire and Fade | 1 | 1 | **Not implemented** |  |
| Fireknife | 1 | 1 | **Not implemented** |  |
| Forward Observers | 1 | 1 | **Not implemented** |  |
| Ground Strike Fighter | 1 | 1 | **Not implemented** |  |
| Heavy Walker | 1 | 1 | **Not implemented** |  |
| Hero of the Empire (Aura) | 1 | 1 | **Not implemented** |  |
| High-intensity Markerlights | 1 | 1 | **Not implemented** |  |
| Hunting Hounds | 1 | 1 | **Not implemented** |  |
| Inspirational Defiance | 1 | 1 | **Not implemented** |  |
| Jammer Array | 1 | 1 | **Not implemented** |  |
| Jet Pack Insertion | 1 | 1 | **Supported** | Deep Strike |
| Kroot Ambush | 1 | 1 | **Supported** | Redeploy |
| Kroot Linebreakers | 1 | 1 | **Not implemented** |  |
| Kroot Packmates | 1 | 1 | **Not implemented** |  |
| Loping Pounce | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Loping Stride | 1 | 1 | **Not implemented** |  |
| Martial Warrior | 1 | 1 | **Not implemented** |  |
| Nova Burst | 1 | 1 | **Not implemented** |  |
| Nova Charge | 1 | 1 | **Not implemented** |  |
| Nova Shielding | 1 | 1 | **Not implemented** |  |
| Orbital Comms Array (Aura) | 1 | 1 | **Not implemented** |  |
| Outflank | 1 | 1 | **Not implemented** |  |
| Paradox of Duality | 1 | 1 | **Not implemented** |  |
| Photon Casters | 1 | 1 | **Not implemented** |  |
| Precise Targeting | 1 | 1 | **Not implemented** |  |
| Pulse Bombs | 1 | 1 | **Not implemented** |  |
| Puretide's Teachings | 1 | 1 | **Not implemented** |  |
| Rapid Deployment | 1 | 1 | **Not implemented** |  |
| Rites of Feasting | 1 | 1 | **Supported** | Feel No Pain |
| Ritual Butchery | 1 | 1 | **Not implemented** |  |
| Root of Honour | 1 | 1 | **Not implemented** |  |
| Sentinel Protocols | 1 | 1 | **Not implemented** |  |
| Starscythe | 1 | 1 | **Not implemented** |  |
| Stealth Drones | 1 | 1 | **Supported** | Stealth |
| Strafing Run | 1 | 1 | **Not implemented** |  |
| Structural Analyser | 1 | 1 | **Not implemented** |  |
| Sunforge | 1 | 1 | **Not implemented** |  |
| Super-heavy Walker | 1 | 1 | **Not implemented** |  |
| Support System | 1 | 1 | **Not implemented** |  |
| Suppression Volley | 1 | 1 | **Not implemented** |  |
| Supreme Loyalty (Aura) | 1 | 1 | **Not implemented** |  |
| Target Uploaded | 1 | 1 | **Not implemented** |  |
| Thunderous Pounce | 1 | 1 | **Not implemented** |  |
| Tidewall Defence Platform | 1 | 1 | **Not implemented** |  |
| Titan Hunter | 1 | 1 | **Not implemented** |  |
| Titan-killer | 1 | 1 | **Not implemented** |  |
| Trail Finding | 1 | 1 | **Not implemented** |  |
| Turbo-jets | 1 | 1 | **Not implemented** |  |
| Velocity Tracker | 1 | 1 | **Not implemented** |  |
| Volley Fire | 1 | 1 | **Not implemented** |  |
| War Leader | 1 | 1 | **Not implemented** |  |
| Way of the Short Blade | 1 | 1 | **Not implemented** |  |
| XV02 Pilot Battlesuit | 1 | 1 | **Not implemented** |  |

#### Unaligned Forces (`UN`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Reinforced Cover | 16 | 16 | **Not implemented** |  |
| Roof Access | 6 | 6 | **Not implemented** |  |
| Defence Line | 3 | 3 | **Not implemented** |  |
| Battlements | 2 | 2 | **Not implemented** |  |
| Trench Line | 2 | 2 | **Not implemented** |  |
| Automated Defences | 1 | 1 | **Not implemented** |  |
| Disruptive Influence (Aura) | 1 | 1 | **Not implemented** |  |
| Drone Commander (Aura) | 1 | 1 | **Not implemented** |  |
| Emergency Plasma Vents | 1 | 1 | **Not implemented** |  |
| Fearsome Assault | 1 | 1 | **Not implemented** |  |
| Fortress | 1 | 1 | **Not implemented** |  |
| Frenzy | 1 | 1 | **Not implemented** |  |
| Gates | 1 | 1 | **Not implemented** |  |
| Inviolable Bastion | 1 | 1 | **Not implemented** |  |
| Projected Void Shields (Aura) | 1 | 1 | **Not implemented** |  |
| Repair Aircraft | 1 | 1 | **Not implemented** |  |
| Skyshield | 1 | 1 | **Not implemented** |  |
| Stronghold | 1 | 1 | **Not implemented** |  |
| Threat Level Rising | 1 | 1 | **Not implemented** |  |
| Tremor Quake | 1 | 1 | **Not implemented** |  |
| Vantage Point | 1 | 1 | **Not implemented** |  |
| Vortex | 1 | 1 | **Not implemented** |  |

#### World Eaters (`WE`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Assault Ramp | 4 | 4 | **Not implemented** |  |
| Aerial Assault | 2 | 2 | **Supported** | Deep Strike |
| Interceptor | 2 | 2 | **Not implemented** |  |
| Super-heavy Walker | 2 | 2 | **Not implemented** |  |
| A Worthy Skull | 1 | 1 | **Not implemented** |  |
| Aggressive Advance | 1 | 1 | **Not implemented** |  |
| Airborne Predator | 1 | 1 | **Not implemented** |  |
| Armoured Resilience | 1 | 1 | **Not implemented** |  |
| Armoured Spearhead | 1 | 1 | **Not implemented** |  |
| Atomantic Arc-reactor | 1 | 1 | **Not implemented** |  |
| Bane of Cowards | 1 | 1 | **Not implemented** |  |
| Beacons of Rage (Aura) | 1 | 1 | **Not implemented** |  |
| Berzerker Frenzy | 1 | 1 | **Not implemented** |  |
| Blood Surge | 1 | 1 | **Not implemented** |  |
| Blood-hungry Annihilator | 1 | 1 | **Not implemented** |  |
| Bloodied Terror | 1 | 1 | **Not implemented** |  |
| Bloodlust | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Bloody Fury | 1 | 1 | **Not implemented** |  |
| Bloody Stampede | 1 | 1 | **Not implemented** |  |
| Bomb Rack | 1 | 1 | **Not implemented** |  |
| Brass Stampede | 1 | 1 | **Not implemented** |  |
| Crush All Who Stand Before Us | 1 | 1 | **Not implemented** |  |
| Daemon Lord of Khorne (Aura) | 1 | 1 | **Not implemented** |  |
| Deredeo Strike | 1 | 1 | **Not implemented** |  |
| Devastating Assault | 1 | 1 | **Not implemented** |  |
| Devoted to Destruction | 1 | 1 | **Not implemented** |  |
| Direct the Slaughter | 1 | 1 | **Not implemented** |  |
| Duty Eternal | 1 | 1 | **Not implemented** |  |
| Even In Death I Serve | 1 | 1 | **Supported** | Deadly Demise |
| Ferocious Assault | 1 | 1 | **Not implemented** |  |
| Fire Riders | 1 | 1 | **Supported** | Deep Strike |
| Forwards, for Blood! | 1 | 1 | **Not implemented** |  |
| Frenzy | 1 | 1 | **Not implemented** |  |
| Furious Onslaught | 1 | 1 | **Not implemented** |  |
| Hunters from the Warp | 1 | 1 | **Not implemented** |  |
| Idol of Blessed Blood | 1 | 1 | **Supported** | Blessings of Khorne (World Eaters), Idol of the Blessed Blood (Blessings +1D6) |
| Inviolable Transport | 1 | 1 | **Not implemented** |  |
| Legendary Killer | 1 | 1 | **Not implemented** |  |
| Line-breaker | 1 | 1 | **Not implemented** |  |
| Loping Speed | 1 | 1 | **Not implemented** |  |
| Lord of Murder | 1 | 1 | **Supported** | Lone Operative |
| Meet Any Challenge | 1 | 1 | **Not implemented** |  |
| Murderlust | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Objective Ravaged | 1 | 1 | **Not implemented** |  |
| Pinning Bombardment | 1 | 1 | **Not implemented** |  |
| Possessed Lord | 1 | 1 | **Not implemented** |  |
| Powerful Volley | 1 | 1 | **Not implemented** |  |
| Punishing Suppression | 1 | 1 | **Not implemented** |  |
| Rage Embodied (Aura) | 1 | 1 | **Not implemented** |  |
| Rage Eternal | 1 | 1 | **Not implemented** |  |
| Reborn in Blood | 1 | 1 | **Supported** | Blessings of Khorne (World Eaters), Deep Strike, Reborn in Blood (Angron) |
| Relentless Carnage | 1 | 1 | **Not implemented** |  |
| Rend and Tear | 1 | 1 | **Not implemented** |  |
| Rolling Fortress | 1 | 1 | **Not implemented** |  |
| Rotating Death | 1 | 1 | **Not implemented** |  |
| Runes of the Blood God | 1 | 1 | **Supported** | Feel No Pain |
| Savage Exaltation | 1 | 1 | **Not implemented** |  |
| Scuttling Gait | 1 | 1 | **Not implemented** |  |
| Scuttling Walker | 1 | 1 | **Not implemented** |  |
| Strafing Run | 1 | 1 | **Not implemented** |  |
| Sunderer of Fortresses | 1 | 1 | **Not implemented** |  |
| Super-heavy War Engine | 1 | 1 | **Not implemented** |  |
| Swooping Predator | 1 | 1 | **Not implemented** |  |
| Termite Assault | 1 | 1 | **Not implemented** |  |
| The Betrayer | 1 | 1 | **Not implemented** |  |
| The Scent of Blood | 1 | 1 | **Not implemented** |  |
| Titan-killer | 1 | 1 | **Not implemented** |  |
| To Slake its Rage | 1 | 1 | **Supported** | Advance+Charge (exact wording) |
| Unleash Wrath | 1 | 1 | **Not implemented** |  |
| Wrathful Presence | 1 | 1 | **Not implemented** |  |

### Fortification (левая колонка)

#### Adepta Sororitas (`AS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| ATTACHED UNIT | 2 | 2 | **Supported** | Scouts |

#### Adeptus Mechanicus (`AdM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| ATTACHED UNIT | 1 | 1 | **Not implemented** |  |

#### Aeldari (`AE`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| SUPPORT ARTILLERY | 3 | 3 | **Not implemented** |  |
| TRAVELLING PLAYERS | 3 | 3 | **Not implemented** |  |
| ASPECT TRAINING | 1 | 1 | **Supported** | Fights First, Infiltrators, Scouts, Stealth |
| AVATAR OFTHE WHISPERING GOD | 1 | 1 | **Not implemented** |  |
| PATH OF DAMNATION | 1 | 1 | **Not implemented** |  |
| SERVANT OF THE WHISPERING GOD | 1 | 1 | **Not implemented** |  |
| SERVANT OFTHE WHISPERING GOD | 1 | 1 | **Not implemented** |  |

#### Astra Militarum (`AM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| FORTIFICATION | 4 | 4 | **Not implemented** |  |
| LOYAL PROTECTOR | 2 | 2 | **Not implemented** |  |
| ORDERS | 2 | 2 | **Not implemented** |  |

#### Chaos Daemons (`CD`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| DAEMONIC ALLEGIANCE | 1 | 1 | **Not implemented** |  |

#### Death Guard (`DG`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| DEPLOYMENT | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Drukhari (`DRU`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| TRAVELLING PLAYERS | 3 | 3 | **Not implemented** |  |
| COURT OF THE ARCHON | 1 | 1 | **Not implemented** |  |
| MONSTROUS HULKS | 1 | 1 | **Not implemented** |  |
| PATH OF DAMNATION | 1 | 1 | **Not implemented** |  |

#### Emperor’s Children (`EC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| LORD OF THE HOST | 1 | 1 | **Supported** | Infiltrators, Scouts |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Genestealer Cults (`GC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| FORTIFICATION | 5 | 5 | **Not implemented** |  |
| ORDERS | 1 | 1 | **Not implemented** |  |

#### Imperial Agents (`AoI`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| ATTACHED UNIT | 5 | 5 | **Not implemented** |  |
| TRANSPORT | 3 | 3 | **Not implemented** |  |
| INQUISITORIAL AGENT | 1 | 1 | **Not implemented** |  |
| INQUISITORIAL RETINUE | 1 | 1 | **Not implemented** |  |

#### Imperial Knights (`QI`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| USING SIR HEKHTUR | 1 | 1 | **Not implemented** |  |

#### Necrons (`NEC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| FORTIFICATION | 3 | 3 | **Not implemented** |  |
| CANOPTEK RETINUE | 1 | 1 | **Not implemented** |  |
| VANGUARD PROTOCOLS | 1 | 1 | **Supported** | Scouts |

#### Orks (`ORK`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| ATTACHED UNIT | 1 | 1 | **Not implemented** |  |
| PATROL SQUAD | 1 | 1 | **Not implemented** |  |

#### Space Marines (`SM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| INSPIRING COMMANDER | 5 | 5 | **Not implemented** |  |
| ATTACHED UNIT | 3 | 3 | **Not implemented** |  |
| CAPTAIN OF THE HONOUR GUARD | 1 | 1 | **Not implemented** |  |
| CHAPTER MASTER OF THE RAVEN GUARD | 1 | 1 | **Supported** | Lone Operative |
| CHOSEN OF THE EMPEROR | 1 | 1 | **Not implemented** |  |
| CRIMSON FISTS | 1 | 1 | **Not implemented** |  |
| EMBARKING WITHIN TRANSPORTS | 1 | 1 | **Not implemented** |  |
| FLESH TEARERS | 1 | 1 | **Not implemented** |  |
| FORCE OF UNTAMED DESTRUCTION | 1 | 1 | **Not implemented** |  |
| HONOUR GUARD OF MACRAGGE | 1 | 1 | **Not implemented** |  |
| LORD CALGAR | 1 | 1 | **Not implemented** |  |

#### Thousand Sons (`TS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Unaligned Forces (`UN`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| FORTIFICATION | 16 | 16 | **Not implemented** |  |
| MIGHTY EDIFICE | 1 | 1 | **Not implemented** |  |

#### World Eaters (`WE`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| LORD OF THE EIGHTBOUND | 1 | 1 | **Supported** | Deep Strike, Scouts |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

### Primarch

#### Adepta Sororitas (`AS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Censer of the Sacred Rose (Aura) | 1 | 1 | **Not implemented** |  |
| FORTIFICATION | 1 | 1 | **Not implemented** |  |
| Icon of the Valorous Heart (Aura) | 1 | 1 | **Supported** | Feel No Pain |
| Petals of the Bloody Rose (Aura) | 1 | 1 | **Not implemented** |  |
| Simulacrum of the Argent Shroud (Aura) | 1 | 1 | **Not implemented** |  |
| Simulacrum of the Ebon Chalice (Aura) | 1 | 1 | **Not implemented** |  |
| The Fiery Heart (Aura) | 1 | 1 | **Not implemented** |  |

#### Adeptus Mechanicus (`AdM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Invocation of Machine Vengeance | 1 | 1 | **Not implemented** |  |
| Mantra of Discipline | 1 | 1 | **Not implemented** |  |
| Shroudpsalm (Aura) | 1 | 1 | **Supported** | Stealth |

#### Chaos Daemons (`CD`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Creature of Khorne | 2 | 2 | **Not implemented** |  |
| Creature of Nurgle | 2 | 2 | **Not implemented** |  |
| Creature of Slaanesh | 2 | 2 | **Not implemented** |  |
| Creature of Tzeentch | 2 | 2 | **Not implemented** |  |
| Daemon Prince of Khorne | 2 | 2 | **Not implemented** |  |
| Daemon Prince of Nurgle | 2 | 2 | **Not implemented** |  |
| Daemon Prince of Slaanesh | 2 | 2 | **Not implemented** |  |
| Daemon Prince of Tzeentch | 2 | 2 | **Not implemented** |  |
| Pall of Despair (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Shadow Lord (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Wreathed in Shadows (Aura, Psychic) | 1 | 1 | **Not implemented** |  |

#### Chaos Space Marines (`CSM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Daemonic Allegiance | 2 | 2 | **Not implemented** |  |
| Khorne | 2 | 2 | **Not implemented** |  |
| Nurgle | 2 | 2 | **Not implemented** |  |
| Slaanesh | 2 | 2 | **Not implemented** |  |
| Tzeentch | 2 | 2 | **Not implemented** |  |
| Lord of the Traitor Legions (Aura) | 1 | 1 | **Not implemented** |  |
| Mark of Chaos Ascendant (Aura) | 1 | 1 | **Not implemented** |  |
| Paragon of Hatred (Aura) | 1 | 1 | **Not implemented** |  |

#### Death Guard (`DG`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Boon of Death | 1 | 1 | **Not implemented** |  |
| Diseased Influence | 1 | 1 | **Not implemented** |  |
| Inflamed Reprisal | 1 | 1 | **Not implemented** |  |

#### Drukhari (`DRU`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Aethersails | 1 | 1 | **Not implemented** |  |
| Masters of the Shadowed Sky | 1 | 1 | **Not implemented** |  |
| Speed of the Kill | 1 | 1 | **Not implemented** |  |
| Visions of Butchery | 1 | 1 | **Not implemented** |  |

#### Emperor’s Children (`EC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Beguiling Form | 1 | 1 | **Not implemented** |  |
| Daemonic Speed | 1 | 1 | **Supported** | Fights First |
| Enthralling Hypnosis (Aura) | 1 | 1 | **Not implemented** |  |

#### Necrons (`NEC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Phaeron of the Blades (Aura) | 1 | 1 | **Not implemented** |  |
| Phaeron of the Stars (Aura) | 1 | 1 | **Not implemented** |  |
| Relentless March (Aura) | 1 | 1 | **Not implemented** |  |

#### Space Marines (`SM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Banner of the Emperor Victorious | 1 | 1 | **Not implemented** |  |
| Column from the Major Altar | 1 | 1 | **Not implemented** |  |
| Martial Exemplar (Aura) | 1 | 1 | **Not implemented** |  |
| Master of Battle | 1 | 1 | **Not implemented** |  |
| Mist-wreathed Shadow Realms | 1 | 1 | **Not implemented** |  |
| No Hiding From the Watchers (Aura) | 1 | 1 | **Supported** | Feel No Pain |
| Primarch of the XIII (Aura) | 1 | 1 | **Not implemented** |  |
| Supreme Strategist | 1 | 1 | **Not implemented** |  |
| Water from the Stoup of Elucidation | 1 | 1 | **Not implemented** |  |

#### Thousand Sons (`TS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Impossible Form (Psychic) | 1 | 1 | **Not implemented** |  |
| Time Flux (Aura, Psychic) | 1 | 1 | **Not implemented** |  |
| Treason of Tzeentch (Psychic) | 1 | 1 | **Not implemented** |  |

#### Unaligned Forces (`UN`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| MIGHTY EDIFICE | 1 | 1 | **Not implemented** |  |

#### World Eaters (`WE`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Driven by Ultimate Rage (Aura) | 1 | 1 | **Not implemented** |  |
| Overwhelming Wrath (Aura) | 1 | 1 | **Not implemented** |  |
| The Blood God’s Favour | 1 | 1 | **Supported** | Blessings of Khorne (World Eaters) |

### Special (правая колонка)

#### Adepta Sororitas (`AS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Holy Mission | 1 | 1 | **Supported** | Infiltrators, Scouts |
| Holy Vanguard | 1 | 1 | **Supported** | Scouts |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Adeptus Custodes (`AC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| CUSTODIAN GUARD | 2 | 2 | **Not implemented** |  |
| JETBIKE OUTRIDERS | 1 | 1 | **Not implemented** |  |
| JUMP PACKS | 1 | 1 | **Not implemented** |  |
| LIONS OF THE EMPEROR | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Adeptus Mechanicus (`AdM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| SECUTARII | 2 | 2 | **Not implemented** |  |
| SERVITOR BODYGUARD | 1 | 1 | **Not implemented** |  |
| SERVITOR RETINUE | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |
| SYDONIAN SENTINEL | 1 | 1 | **Not implemented** |  |

#### Aeldari (`AE`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| CORSAIRS | 1 | 1 | **Not implemented** |  |
| DEPLOYMENT | 1 | 1 | **Not implemented** |  |

#### Astra Militarum (`AM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| ORDERS | 14 | 14 | **Not implemented** |  |
| EMBARKING | 3 | 3 | **Supported** | Firing Deck |
| ARTILLERY TEAM | 2 | 2 | **Not implemented** |  |
| ATTACHÉS | 1 | 1 | **Not implemented** |  |
| COMPACT | 1 | 1 | **Not implemented** |  |
| DEPLOYMENT | 1 | 1 | **Not implemented** |  |
| GRENADIER SQUAD | 1 | 1 | **Not implemented** |  |
| LONER | 1 | 1 | **Not implemented** |  |
| SERVITOR RETINUE | 1 | 1 | **Not implemented** |  |
| SNIPER TEAMS | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Chaos Daemons (`CD`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| DAEMONIC ALLEGIANCE | 5 | 5 | **Not implemented** |  |
| GRANDFATHER'S BLESSING | 2 | 2 | **Not implemented** |  |
| OGRYNS | 2 | 2 | **Not implemented** |  |
| HEAVY WEAPONS TEAM | 1 | 1 | **Not implemented** |  |
| HORRORS ARE PINK. HORRORS ARE BLUE. WHEREONCE THERE WAS ONE, NOW THERE ARE TWO. | 1 | 1 | **Not implemented** |  |
| MANIFESTATION OF DESTRUCTION | 1 | 1 | **Not implemented** |  |
| SERVANTS OF THE ABYSS | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Chaos Knights (`QT`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| OGRYNS | 2 | 2 | **Not implemented** |  |
| HEAVY WEAPONS TEAM | 1 | 1 | **Not implemented** |  |
| SERVANTS OF THE ABYSS | 1 | 1 | **Not implemented** |  |

#### Chaos Space Marines (`CSM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| OGRYNS | 2 | 2 | **Not implemented** |  |
| ATTACHED UNIT | 1 | 1 | **Not implemented** |  |
| CULT OF DESTRUCTION | 1 | 1 | **Not implemented** |  |
| HEAVY WEAPONS TEAM | 1 | 1 | **Not implemented** |  |
| SERVANTS OF THE ABYSS | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Death Guard (`DG`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| POSSESSED | 1 | 1 | **Not implemented** |  |

#### Drukhari (`DRU`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| ARCHON’S RETINUE | 1 | 1 | **Supported** | Scouts |
| CORSAIRS | 1 | 1 | **Not implemented** |  |

#### Genestealer Cults (`GC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| ORDERS | 7 | 7 | **Not implemented** |  |
| EMBARKING | 3 | 3 | **Supported** | Firing Deck |
| ARTILLERY TEAM | 2 | 2 | **Not implemented** |  |
| ATTACHÉS | 1 | 1 | **Not implemented** |  |
| COMPACT | 1 | 1 | **Not implemented** |  |
| DEPLOYMENT | 1 | 1 | **Not implemented** |  |
| GRENADIER SQUAD | 1 | 1 | **Not implemented** |  |
| HUNTER ORGANISM | 1 | 1 | **Not implemented** |  |
| SERVITOR RETINUE | 1 | 1 | **Not implemented** |  |
| SNIPER TEAMS | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Grey Knights (`GK`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| SERVITOR RETINUE | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Imperial Agents (`AoI`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| SHADOW ASSIGNMENT | 4 | 4 | **Not implemented** |  |
| ATTACHED UNIT | 2 | 2 | **Not implemented** |  |
| CASSIUS | 1 | 1 | **Not implemented** |  |
| INQUISITORIAL HENCHMEN | 1 | 1 | **Not implemented** |  |
| NAVY BODYGUARD | 1 | 1 | **Not implemented** |  |
| Rites of Teleportation | 1 | 1 | **Supported** | Deep Strike |

#### Necrons (`NEC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| ENSLAVED STAR GOD | 4 | 4 | **Not implemented** |  |
| CRYPTEK RETINUE | 1 | 1 | **Not implemented** |  |
| C’TAN SHARD | 1 | 1 | **Not implemented** |  |
| DEPLOYMENT | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |
| TRIARCHAL MENHIRS | 1 | 1 | **Not implemented** |  |

#### Orks (`ORK`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| SPEED FREEKS | 3 | 3 | **Not implemented** |  |
| ATTACHED UNIT | 1 | 1 | **Not implemented** |  |
| BIG GUNZ | 1 | 1 | **Not implemented** |  |
| BODYGUARD | 1 | 1 | **Not implemented** |  |
| SPEED FREEKS MOB | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

#### Space Marines (`SM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| ATTACHED UNIT | 20 | 20 | **Not implemented** |  |
| ATTACHED UNITS | 6 | 6 | **Not implemented** |  |
| DEATH COMPANY | 2 | 2 | **Not implemented** |  |
| SUPREME COMMANDER | 2 | 2 | **Supported** | Supreme Commander (must be Warlord) |
| TYCHO | 2 | 2 | **Not implemented** |  |
| Attached Unit | 1 | 1 | **Not implemented** |  |
| CASSIUS | 1 | 1 | **Not implemented** |  |
| COMMAND SQUAD BODYGUARD | 1 | 1 | **Not implemented** |  |
| COMPANY HEROES | 1 | 1 | **Not implemented** |  |
| LAST SURVIVOR | 1 | 1 | **Not implemented** |  |
| LOGAN GRIMNAR | 1 | 1 | **Not implemented** |  |
| MASTER OF MISCHIEF | 1 | 1 | **Not implemented** |  |
| SERVITOR RETINUE | 1 | 1 | **Not implemented** |  |
| TANK COMMANDER | 1 | 1 | **Not implemented** |  |
| WOLFKIN | 1 | 1 | **Not implemented** |  |

#### Thousand Sons (`TS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| HORRORS ARE PINK. HORRORS ARE BLUE. WHEREONCE THERE WAS ONE, NOW THERE ARE TWO. | 1 | 1 | **Not implemented** |  |

#### Tyranids (`TYR`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| HUNTER ORGANISM | 1 | 1 | **Not implemented** |  |

#### T’au Empire (`TAU`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| BODYGUARD | 1 | 1 | **Not implemented** |  |
| INDEPENDENT POWER | 1 | 1 | **Not implemented** |  |
| SUPREME COMMANDER | 1 | 1 | **Supported** | Supreme Commander (must be Warlord) |

### Wargear

#### Adepta Sororitas (`AS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Simulacrum Imperialis | 4 | 4 | **Not implemented** |  |
| Sacred Banner | 2 | 2 | **Not implemented** |  |
| Anchorite Sarcophagus | 1 | 1 | **Not implemented** |  |
| Null Rod | 1 | 1 | **Supported** | Feel No Pain |
| Rod of Office | 1 | 1 | **Not implemented** |  |
| Salvationist Medikit | 1 | 1 | **Not implemented** |  |

#### Adeptus Custodes (`AC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Vexilla | 3 | 3 | **Not implemented** |  |
| Praesidium Shield | 1 | 1 | **Not implemented** |  |
| Praesidium shield | 1 | 1 | **Not implemented** |  |
| Tarsis Buckler | 1 | 1 | **Not implemented** |  |

#### Adeptus Mechanicus (`AdM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Enhanced data-tether | 5 | 5 | **Not implemented** |  |
| Omnispex | 4 | 4 | **Not implemented** |  |
| Chaff Launcher | 3 | 3 | **Not implemented** |  |
| Command Uplink | 3 | 3 | **Not implemented** |  |
| Broad spectrum data-tether | 1 | 1 | **Not implemented** |  |

#### Aeldari (`AE`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Aspect Shrine Token | 7 | 7 | **Not implemented** |  |
| Flip Belt | 5 | 5 | **Not implemented** |  |
| Scattershield | 3 | 3 | **Not implemented** |  |
| Mistshield | 2 | 2 | **Not implemented** |  |
| Shimmershield | 2 | 2 | **Not implemented** |  |
| Channeller Stones | 1 | 1 | **Not implemented** |  |
| Cluster Caltrops | 1 | 1 | **Not implemented** |  |
| Faolchú | 1 | 1 | **Not implemented** |  |
| Forceshield | 1 | 1 | **Not implemented** |  |
| Grav-talon | 1 | 1 | **Not implemented** |  |
| Phantasm Grenade Launcher | 1 | 1 | **Not implemented** |  |
| Serpent Shield | 1 | 1 | **Not implemented** |  |
| Shadow Field | 1 | 1 | **Not implemented** |  |
| The Scorpion’s Bite | 1 | 1 | **Not implemented** |  |

#### Astra Militarum (`AM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Vox-caster | 6 | 6 | **Not implemented** |  |
| Master Vox | 4 | 4 | **Not implemented** |  |
| Regimental Standard | 4 | 4 | **Not implemented** |  |
| Medi-pack | 3 | 3 | **Not implemented** |  |
| Brute Shield | 2 | 2 | **Not implemented** |  |
| Slabshield | 2 | 2 | **Not implemented** |  |
| Alchemyk Counteragents | 1 | 1 | **Supported** | Feel No Pain |
| Command Rod | 1 | 1 | **Not implemented** |  |
| Death Korps Medi-pack | 1 | 1 | **Not implemented** |  |
| Defence Searchlight | 1 | 1 | **Not implemented** |  |
| Demolition Gear | 1 | 1 | **Not implemented** |  |
| Heavy Bombs | 1 | 1 | **Not implemented** |  |
| Inferno Bombs | 1 | 1 | **Not implemented** |  |
| Melta Mine | 1 | 1 | **Not implemented** |  |
| Ratling Battlemutt | 1 | 1 | **Not implemented** |  |
| Regimental Banner | 1 | 1 | **Not implemented** |  |
| Remote Mine | 1 | 1 | **Not implemented** |  |
| Servo-scribes | 1 | 1 | **Not implemented** |  |

#### Chaos Daemons (`CD`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Daemonic Icon | 8 | 8 | **Not implemented** |  |
| Instrument of Chaos | 8 | 8 | **Not implemented** |  |
| Chaos Icon | 4 | 4 | **Not implemented** |  |
| Collar of Khorne | 2 | 2 | **Supported** | Feel No Pain |
| Brass Collar of Bloody Vengeance | 1 | 1 | **Supported** | Feel No Pain |
| Chaos Familiar | 1 | 1 | **Not implemented** |  |
| Shining Aegis | 1 | 1 | **Not implemented** |  |

#### Chaos Knights (`QT`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Chaos Icon | 1 | 1 | **Not implemented** |  |

#### Chaos Space Marines (`CSM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Chaos Icon | 5 | 5 | **Not implemented** |  |
| Chaos Familiar | 1 | 1 | **Not implemented** |  |
| Explorator Augury Web | 1 | 1 | **Not implemented** |  |
| Icon of Despair (Aura) | 1 | 1 | **Not implemented** |  |
| Icon of Flame | 1 | 1 | **Not implemented** |  |
| Icon of Khorne | 1 | 1 | **Supported** | Blessings of Khorne (World Eaters) |
| Thunderhawk Cluster Bombs | 1 | 1 | **Not implemented** |  |
| Voice Eater | 1 | 1 | **Not implemented** |  |

#### Death Guard (`DG`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Daemonic Icon | 2 | 2 | **Not implemented** |  |
| Icon of Despair (Aura) | 2 | 2 | **Not implemented** |  |
| Instrument of Chaos | 2 | 2 | **Not implemented** |  |
| Diseased Icon | 1 | 1 | **Not implemented** |  |
| Explorator Augury Web | 1 | 1 | **Not implemented** |  |
| Thunderhawk Cluster Bombs | 1 | 1 | **Not implemented** |  |

#### Drukhari (`DRU`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Flip Belt | 5 | 5 | **Not implemented** |  |
| Phantasm Grenade Launcher | 3 | 3 | **Not implemented** |  |
| Kabalite Icon | 2 | 2 | **Not implemented** |  |
| Mistshield | 2 | 2 | **Not implemented** |  |
| Channeller Stones | 1 | 1 | **Not implemented** |  |
| Cluster Caltrops | 1 | 1 | **Not implemented** |  |
| Faolchú | 1 | 1 | **Not implemented** |  |
| Grav-talon | 1 | 1 | **Not implemented** |  |
| Incubi Shrine Token | 1 | 1 | **Not implemented** |  |
| Shadowfield | 1 | 1 | **Not implemented** |  |
| Soul Trap | 1 | 1 | **Not implemented** |  |
| Stimm-needler | 1 | 1 | **Not implemented** |  |

#### Emperor’s Children (`EC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Daemonic Icon | 2 | 2 | **Not implemented** |  |
| Icon of Excess | 2 | 2 | **Not implemented** |  |
| Instrument of Chaos | 2 | 2 | **Not implemented** |  |
| Shining Aegis | 1 | 1 | **Not implemented** |  |

#### Genestealer Cults (`GC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Vox-caster | 5 | 5 | **Not implemented** |  |
| Cult Icon | 4 | 4 | **Not implemented** |  |
| Master Vox | 3 | 3 | **Not implemented** |  |
| Regimental Standard | 3 | 3 | **Not implemented** |  |
| Medi-pack | 2 | 2 | **Not implemented** |  |
| Alchemicus Familiar | 1 | 1 | **Not implemented** |  |
| Alchemyk Counteragents | 1 | 1 | **Supported** | Feel No Pain |
| Death Korps Medi-pack | 1 | 1 | **Not implemented** |  |
| Defence Searchlight | 1 | 1 | **Not implemented** |  |
| Flare Launcher | 1 | 1 | **Not implemented** |  |
| Melta Mine | 1 | 1 | **Not implemented** |  |
| Regimental Banner | 1 | 1 | **Not implemented** |  |
| Remote Mine | 1 | 1 | **Not implemented** |  |
| Servo-scribes | 1 | 1 | **Not implemented** |  |
| Spotter | 1 | 1 | **Not implemented** |  |
| Survey Augur | 1 | 1 | **Not implemented** |  |

#### Grey Knights (`GK`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Ancient’s Banner | 2 | 2 | **Not implemented** |  |
| Apothecary's Narthecium | 1 | 1 | **Not implemented** |  |
| Apothecary’s Narthecium | 1 | 1 | **Not implemented** |  |
| Thunderhawk Cluster Bombs | 1 | 1 | **Not implemented** |  |

#### Imperial Agents (`AoI`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Astartes Shield | 4 | 4 | **Not implemented** |  |
| Jump Pack | 4 | 4 | **Not implemented** |  |
| Blessed Wardings | 2 | 2 | **Not implemented** |  |
| Nuncio Aquila | 2 | 2 | **Not implemented** |  |
| Psychic Gifts | 2 | 2 | **Not implemented** |  |
| Storm Shield | 2 | 2 | **Not implemented** |  |
| Ancient’s Banner | 1 | 1 | **Not implemented** |  |
| Arbites Medi-kit | 1 | 1 | **Not implemented** |  |
| Auspex Array | 1 | 1 | **Not implemented** |  |
| Bound Daemon | 1 | 1 | **Not implemented** |  |
| Endurant Shield | 1 | 1 | **Not implemented** |  |
| Glovodan Psyber-eagle | 1 | 1 | **Not implemented** |  |
| Healing Serum | 1 | 1 | **Not implemented** |  |
| Helix Gauntlet | 1 | 1 | **Supported** | Feel No Pain |
| Infernum Halo-launcher | 1 | 1 | **Not implemented** |  |
| Infiltrator Comms Array | 1 | 1 | **Supported** | Infiltrators |
| Narthecium | 1 | 1 | **Not implemented** |  |
| Nuncio Aquila (Aura) | 1 | 1 | **Not implemented** |  |
| Psychic Hood | 1 | 1 | **Supported** | Feel No Pain |
| Salvationist Medikit | 1 | 1 | **Not implemented** |  |
| Simulacrum Imperialis | 1 | 1 | **Not implemented** |  |
| Simulacrum Imperials | 1 | 1 | **Not implemented** |  |
| Soulguilt Scanner | 1 | 1 | **Not implemented** |  |
| Tome-skull | 1 | 1 | **Not implemented** |  |
| Vox-skull | 1 | 1 | **Not implemented** |  |

#### Imperial Knights (`QI`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Enhanced data-tether | 2 | 2 | **Not implemented** |  |
| Omnispex | 2 | 2 | **Not implemented** |  |

#### Leagues of Votann (`LoV`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Teleport Crest | 3 | 3 | **Supported** | Deep Strike |
| Weavefield Crest | 3 | 3 | **Not implemented** |  |
| Panspectral Scanner | 2 | 2 | **Not implemented** |  |
| Preymark Crest | 2 | 2 | **Not implemented** |  |
| Rampart Crest | 2 | 2 | **Not implemented** |  |
| Smoke Launcher | 2 | 2 | **Not implemented** |  |
| Multiwave Comms Array | 1 | 1 | **Not implemented** |  |
| Rollbar Searchlight | 1 | 1 | **Not implemented** |  |

#### Necrons (`NEC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Resurrection Orb | 5 | 5 | **Not implemented** |  |
| Gloom Prism (Aura) | 3 | 3 | **Supported** | Feel No Pain |
| Plasmacyte | 2 | 2 | **Not implemented** |  |
| Accelerator Mandible | 1 | 1 | **Not implemented** |  |
| Dispersion Shield | 1 | 1 | **Not implemented** |  |
| Fabricator Claw Array (Aura) | 1 | 1 | **Supported** | Feel No Pain |
| Nanoscarab Amulet | 1 | 1 | **Supported** | Feel No Pain |
| Nanoscarab Projector | 1 | 1 | **Not implemented** |  |
| Nebuloscope | 1 | 1 | **Not implemented** |  |
| Shadowloom | 1 | 1 | **Supported** | Stealth |
| Shieldvanes | 1 | 1 | **Not implemented** |  |

#### Orks (`ORK`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Ammo Runt | 2 | 2 | **Not implemented** |  |
| Bomb Squigs | 2 | 2 | **Not implemented** |  |
| Grot Orderly | 2 | 2 | **Not implemented** |  |
| Kustom Force Field | 2 | 2 | **Not implemented** |  |
| Small Bomms | 2 | 2 | **Not implemented** |  |
| Big Bomms | 1 | 1 | **Not implemented** |  |
| Blastajet Force Field | 1 | 1 | **Not implemented** |  |
| Distraction Grot | 1 | 1 | **Not implemented** |  |
| Grot Assistant | 1 | 1 | **Not implemented** |  |
| Grot Helper | 1 | 1 | **Not implemented** |  |
| Grot Oiler | 1 | 1 | **Not implemented** |  |
| Pulsa Rokkit | 1 | 1 | **Not implemented** |  |
| ’Ard Case | 1 | 1 | **Supported** | Firing Deck |

#### Space Marines (`SM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Storm Shield | 17 | 17 | **Not implemented** |  |
| Relic Shield | 6 | 6 | **Not implemented** |  |
| Astartes Shield | 5 | 5 | **Not implemented** |  |
| Blizzard Shield | 2 | 2 | **Not implemented** |  |
| Death Totem | 2 | 2 | **Not implemented** |  |
| Haywire Mine | 2 | 2 | **Not implemented** |  |
| Helix Gauntlet | 2 | 2 | **Supported** | Feel No Pain |
| Infiltrator Comms Array | 2 | 2 | **Supported** | Infiltrators |
| Orbital Comms Array (Aura) | 2 | 2 | **Not implemented** |  |
| Shield Dome | 2 | 2 | **Not implemented** |  |
| Watcher in the Dark | 2 | 2 | **Supported** | Feel No Pain |
| Auspex Array | 1 | 1 | **Not implemented** |  |
| Banner of Macragge | 1 | 1 | **Not implemented** |  |
| Book of Salvation | 1 | 1 | **Not implemented** |  |
| Centurion Assault Launcher | 1 | 1 | **Not implemented** |  |
| Explorator Augury Web | 1 | 1 | **Not implemented** |  |
| Grapnel Launcher | 1 | 1 | **Not implemented** |  |
| Grenade Harness | 1 | 1 | **Not implemented** |  |
| Infernum Halo-launcher | 1 | 1 | **Not implemented** |  |
| Instigator Bolt Carbine | 1 | 1 | **Not implemented** |  |
| Ironclad Assault Launchers | 1 | 1 | **Not implemented** |  |
| Jump Pack | 1 | 1 | **Not implemented** |  |
| Magna-grapple | 1 | 1 | **Not implemented** |  |
| Psychic Hood | 1 | 1 | **Supported** | Feel No Pain |
| Reiver Grav-chute | 1 | 1 | **Supported** | Deep Strike |
| Sanguinary Banner | 1 | 1 | **Not implemented** |  |
| Smoke Launchers | 1 | 1 | **Not implemented** |  |
| Terminator Storm Shield | 1 | 1 | **Not implemented** |  |
| The Lion Helm | 1 | 1 | **Supported** | Feel No Pain |
| Thunderhawk Cluster Bombs | 1 | 1 | **Not implemented** |  |

#### Thousand Sons (`TS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Brayhorn | 1 | 1 | **Not implemented** |  |
| Daemonic Icon | 1 | 1 | **Not implemented** |  |
| Explorator Augury Web | 1 | 1 | **Not implemented** |  |
| Herd Banner | 1 | 1 | **Not implemented** |  |
| Icon of Flame | 1 | 1 | **Not implemented** |  |
| Instrument of Chaos | 1 | 1 | **Not implemented** |  |
| Thunderhawk Cluster Bombs | 1 | 1 | **Not implemented** |  |

#### T’au Empire (`TAU`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Battlesuit Support System | 6 | 6 | **Supported** | Fall Back+Shoot (exact wording) |
| Weapon Support System | 6 | 6 | **Not implemented** |  |
| Shield Generator | 5 | 5 | **Not implemented** |  |
| Advanced Guardian Drone | 1 | 1 | **Not implemented** |  |
| Baggage Harness (Aura) | 1 | 1 | **Not implemented** |  |
| Blacklight Marker Drones | 1 | 1 | **Not implemented** |  |
| Command-link Drone (Aura) | 1 | 1 | **Not implemented** |  |
| Grav-inhibitor Drone | 1 | 1 | **Not implemented** |  |
| Homing Beacon | 1 | 1 | **Not implemented** |  |
| Hover Drone | 1 | 1 | **Not implemented** |  |
| Markerlight | 1 | 1 | **Not implemented** |  |
| Oversight Drone | 1 | 1 | **Not implemented** |  |
| Pech’ra | 1 | 1 | **Not implemented** |  |
| Pulse Accelerator Drone | 1 | 1 | **Not implemented** |  |
| Recon Drone | 1 | 1 | **Supported** | Infiltrators |
| Transport Bay | 1 | 1 | **Not implemented** |  |

#### Unaligned Forces (`UN`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Comms Antenna | 4 | 4 | **Not implemented** |  |
| Borewyrm Infestation | 1 | 1 | **Not implemented** |  |

#### World Eaters (`WE`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Daemonic Icon | 2 | 2 | **Not implemented** |  |
| Icon of Khorne | 2 | 2 | **Supported** | Blessings of Khorne (World Eaters) |
| Instrument of Chaos | 2 | 2 | **Not implemented** |  |
| Collar of Khorne | 1 | 1 | **Supported** | Feel No Pain |
| Explorator Augury Web | 1 | 1 | **Not implemented** |  |
| Thunderhawk Cluster Bombs | 1 | 1 | **Not implemented** |  |

### Wargear profile

#### Adepta Sororitas (`AS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 7 | 7 | **Not implemented** |  |

#### Adeptus Custodes (`AC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 2 | 2 | **Not implemented** |  |

#### Aeldari (`AE`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Linked Fire | 1 | 1 | **Not implemented** |  |

#### Astra Militarum (`AM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 45 | 45 | **Not implemented** |  |
| Plasma Warhead | 1 | 1 | **Not implemented** |  |

#### Chaos Daemons (`CD`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Reverberating Summons | 1 | 1 | **Not implemented** |  |

#### Chaos Knights (`QT`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Conversion | 2 | 2 | **Not implemented** |  |

#### Chaos Space Marines (`CSM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 9 | 9 | **Not implemented** |  |
| Conversion | 3 | 3 | **Not implemented** |  |
| Impaled | 1 | 1 | **Not implemented** |  |

#### Death Guard (`DG`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 8 | 8 | **Not implemented** |  |
| Conversion | 1 | 1 | **Not implemented** |  |
| Reverberating Summons | 1 | 1 | **Not implemented** |  |

#### Drukhari (`DRU`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 1 | 1 | **Not implemented** |  |

#### Genestealer Cults (`GC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 46 | 46 | **Not implemented** |  |
| Plasma Warhead | 1 | 1 | **Not implemented** |  |

#### Grey Knights (`GK`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 6 | 6 | **Not implemented** |  |

#### Imperial Agents (`AoI`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 5 | 5 | **Not implemented** |  |
| Psychic Assassin | 1 | 1 | **Not implemented** |  |

#### Imperial Knights (`QI`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Conversion | 3 | 3 | **Not implemented** |  |

#### Leagues of Votann (`LoV`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Conversion | 2 | 2 | **Not implemented** |  |
| One Shot | 1 | 1 | **Not implemented** |  |
| Overcharge | 1 | 1 | **Not implemented** |  |

#### Necrons (`NEC`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 2 | 2 | **Not implemented** |  |

#### Orks (`ORK`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 2 | 2 | **Not implemented** |  |
| Snagged | 2 | 2 | **Not implemented** |  |
| Bubblechukka | 1 | 1 | **Not implemented** |  |
| Dead Choppy | 1 | 1 | **Not implemented** |  |

#### Space Marines (`SM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 36 | 36 | **Not implemented** |  |
| Conversion | 3 | 3 | **Not implemented** |  |

#### Thousand Sons (`TS`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 8 | 8 | **Not implemented** |  |
| Conversion | 1 | 1 | **Not implemented** |  |

#### Tyranids (`TYR`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Harpooned | 1 | 1 | **Not implemented** |  |

#### T’au Empire (`TAU`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 12 | 12 | **Not implemented** |  |
| Hooked | 1 | 1 | **Not implemented** |  |

#### World Eaters (`WE`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| One Shot | 8 | 8 | **Not implemented** |  |
| Conversion | 1 | 1 | **Not implemented** |  |
| Impaled | 1 | 1 | **Not implemented** |  |

### Без заголовка

#### Space Marines (`SM`)

| Ability | Occurrences (rows) | Datasheets | Status | Notes |
|---|---:|---:|---|---|
| Designer’s Note | 1 | 1 | **Not implemented** |  |
