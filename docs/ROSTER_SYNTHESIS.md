# 10th Edition Seeded Roster Synthesis

`PR-MUSTER-008A` adds a deterministic, framework-free roster synthesizer for
10th-edition data. It is a bridge between mustering telemetry (`PR-MUSTER-008`)
and the later 11th-edition `PR-MUSTER-009` through `PR-MUSTER-018` plans.

The synthesizer is legality-first. It proposes `ArmyBlueprint` candidates from
local `wahapedia_data`, validates accepted candidates through
`ArmyMusterer.validate_runtime_legality()`, and exports app-style army-list text
that must round-trip through `parse_army_list_text()`.

## Public API

Use `synthesize_rosters()` from `warhammer40k_ai.roster.roster_synthesis`:

```python
from warhammer40k_ai.roster.roster_synthesis import RosterSynthesisSeed, synthesize_rosters
from warhammer40k_ai.waha_helper import WahaHelper

report = synthesize_rosters(
    RosterSynthesisSeed(
        max_points=2000,
        max_under_cap_allowance=25,
        faction="World Eaters",
        detachment="Khorne Daemonkin",
        style_tags=("melee", "offensive", "daemonkin"),
        include_units=("Lord on Juggernaut",),
    ),
    waha_helper=WahaHelper(),
    rules_bundle_id="rules_bundle:10th_local_wahapedia",
    top_k=3,
    random_seed=13,
)
```

The report includes:

- The normalized seed and 10th-edition schema/provenance ids.
- Ranked legal candidate `ArmyBlueprint`s.
- Point totals and unused points.
- Runtime validation summaries.
- `BuildCapabilityProfile` ids and style-score breakdowns.
- App-style army-list export text and, when an output directory is supplied,
  export paths.
- PR-MUSTER-008-compatible `MusterRecord` candidate files when an output
  directory is supplied.
- Diagnostics for rejected candidates or no-solution point bands.

## Seed Fields

`RosterSynthesisSeed` supports:

- `max_points`: required positive point cap.
- `max_under_cap_allowance`: optional lower bound; for example, `25` at a
  2000-point cap requires candidates to be at least 1975 points.
- `faction`: optional 10th-edition faction. If omitted, the synthesizer performs
  a deterministic breadth pass across supported local factions.
- `chapter`: optional Space Marines chapter. This normalizes the catalog search
  to Space Marines and uses the chapter as the emitted army faction.
- `detachment`: optional detachment. If omitted, candidate generation enumerates
  deterministic regular detachments for the selected faction.
- `style_tags` and `description_text`: soft ranking signals. Recognized concepts
  include `melee`, `ranged-heavy`, `vehicle-heavy`, `infantry-heavy`, `elite`,
  `horde`, `defensive`, `offensive`, `objective-control`, `durable`, and `fast`.
- `include_units`: hard required datasheet names. Unknown names fail before
  proposal.
- `exclude_units`: hard excluded datasheet names. Unknown names fail before
  proposal.

## Catalog And Legality

`RosterSynthesisCatalog` reads local Wahapedia-backed data through `WahaHelper`.
It enumerates:

- Supported 10th-edition factions.
- Regular, non-Boarding Actions detachments.
- Datasheets, roles, model-count bands, points, keywords, faction keywords, and
  basic leader attachment candidates.
- Enhancement rows for detachment provenance and legality-backed fill when
  points allow.

Out-of-scope datasheets are excluded by the existing `WahaHelper` source policy:
Forge World, Legends, Boarding Actions, Crusade, and Kill Team content remain
outside the synthesizer.

Generated candidates are filtered for faction/chapter keyword compatibility,
then validated through `ArmyMusterer.validate_runtime_legality()`. Runtime
validation remains responsible for point caps, warlords, enhancements,
duplicate datasheet limits, Epic Hero limits, attachment legality, detachment
rules, and wargear legality.

Candidates must also pass the minimal Declare Battle Formations reserve
allocation: every unit that must start in Reserves is placed in Reserves and all
other units deploy normally. This prevents the synthesizer from emitting
otherwise valid 2000-point lists whose mandatory reserve footprint already
exceeds the matched-play reserve unit or points caps before any optional reserve
choices are made.

## CLI

The CLI writes a report, candidate blueprints, and army-list text exports:

```bash
python3 scripts/synthesize_roster.py \
  --max-points 2000 \
  --max-under-cap-allowance 25 \
  --faction "World Eaters" \
  --detachment "Khorne Daemonkin" \
  --style "melee offensive daemonkin" \
  --include-unit "Lord on Juggernaut" \
  --top-k 3 \
  --output-dir /tmp/world_eaters_synth
```

Outputs:

- `synthesis_report.json`
- `candidate_01_blueprint.json`
- `candidate_01_army_list.txt`
- `candidate_01_muster_record.json`
- Additional candidate files up to `top_k`

## Current Limits

This is a playable heuristic synthesizer, not a tournament-optimized list
builder. It does not use learned generation, Torch, or 11th-edition assumptions.
Synthesized entries carry deterministic default wargear selections from local
datasheet loadouts, and exported army-list text shows the selected model
wargear. Exact-point generation is not required; when `max_under_cap_allowance`
is omitted, the scorer prefers the closest legal under-cap candidate. Enhancement
assignment is legality-backed and opportunistic: the synthesizer fills unused
points with legal detachment enhancements when possible, but it does not yet
sacrifice otherwise preferred units solely to force an enhancement.

Omitted-faction mode uses a deterministic first-pass proposal per supported
faction to keep corpus generation and tests tractable. Faction-specific
requests perform deeper detachment/style proposal passes.
