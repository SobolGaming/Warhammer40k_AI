# Tournament Field Schema

`TournamentFieldDistribution`, `EventPolicyDescriptor`, and `MatchupContext`
make tournament assumptions explicit for roster evaluation.

Compiler/runtime modules:
- `src/warhammer40k_ai/roster/tournament_field.py`
- `src/warhammer40k_ai/roster/event_policy.py`
- `src/warhammer40k_ai/roster/matchup_context.py`

Stable ids:
- `field_distribution_schema_id`: schema contract for weighted opponent, mission,
  deployment, and terrain distributions
- `field_distribution_id`: deterministic id for a normalized field payload
- `event_policy_schema_id`: schema contract for tournament constraints and event
  norms
- `event_policy_id`: deterministic or explicit id for an event-policy payload
- `matchup_context_schema_id`: schema contract for the compiled roster-evaluation
  context
- `matchup_context_id`: deterministic id for a fully bound
  `(rules_bundle_id, field_distribution_id, event_policy_id, army_blueprint_hash?)`
  evaluation context

Required field families:
- weighted opponent slices or explicit opponent roster blueprints
- mission, deployment, and terrain distributions
- event lock rules for force disposition and other pre-game choices
- pairing mode
- clock metadata
- evaluation-budget metadata

## Research Baseline

Current tournament norms were checked against current official or organizer
sources on April 14, 2026.

- Current official matched-play baseline:
  [Chapter Approved Tournament Companion v1.4](https://assets.warhammer-community.com/eng_07-01_warhammer_40000_core_rules_chapter_approved_tournament-companion-sqc1af88bj-vzxhp9xmid.pdf)
  treats the companion as the official tournament way to play, uses a
  pre-generated tournament mission pool, excludes Asymmetric War, Twist, and
  Challenger cards from the packet, treats objective markers as flat passable
  40mm markers, recommends Swiss-style pairings with a random first round, and
  ranks tied records by opponent win record before total VP.
- Current official large singles example:
  [Warhammer World Grand Tournament pack](https://warhammerworld.warhammer-community.com/wp-content/uploads/sites/15/2025/02/nQFpBT92eJZsn85n.pdf)
  runs 2,000-point Strike Force armies on 44" x 60" boards across five games,
  expects players to finish inside a 2-hour-45-minute game clock, requires
  Battle Ready armies, and does not use chess clocks.
- Current official small-event example:
  [Shifting Fronts pack](https://warhammerworld.warhammer-community.com/wp-content/uploads/sites/15/2025/12/i1RQ9TbK5A4SAA3S.pdf)
  runs three Incursion-sized games in one day at 1,000 points, pre-selects the
  deployment, primary mission, and Twist for each round, and uses first-round
  random pairings followed by Swiss.
- Current major-organizer hard-clock example:
  [WTC 2025 clock rules](https://worldteamchampionship.com/wp-content/uploads/2025/06/2025-WTC40K-Clock-Rules.pdf)
  mandate chess clocks, use a 4-hour-30-minute team round including pairing and
  admin time, then split the remaining time evenly between players.
- Preview 11e tournament-facing source:
  [#New40k – How your army affects your mission](https://www.warhammer-community.com/en-gb/articles/oefzq9fg/new40k-how-your-army-affects-your-mission/)
  says Force Dispositions are chosen per battle in pick-up play but will usually
  be locked for the whole event in tournaments, and that each mission pairing
  has three recommended terrain layouts.

Practical implications for the ABI:
- `army_points_limit`, `battle_size`, `max_rounds`, and `clock_policy` must be
  explicit because real event shapes range from 1,000-point three-round
  one-day events to 2,000-point five-round GTs and longer mandatory-clock team
  events.
- `pairing_mode` and `pairing_tiebreakers` must be explicit because official
  events use random-first-round Swiss, while other organizers may use different
  hard-clock or pairing procedures.
- Preview-era examples must be labeled as preview or inferred until an official
  event packet exists for that edition frame.

The JSON examples below are intended to match canonical runtime `to_dict()`
output, not just an illustrative shape.

## Example Tournament Field Distribution

```json
{
  "field_distribution_schema_id": "field_distribution_schema:tournament_field_v1",
  "field_distribution_id": "field_distribution:gt_capability_mix_v1",
  "rules_bundle_id": "rules_bundle:2026-04-14",
  "event_policy_id": "event_policy:chapter_approved_10e_singles_v1",
  "terrain_layout_pack_id": "terrain_pack:chapter_approved_2025_26",
  "opponent_slices": [
    {
      "slice_id": "slice:durable_necrons",
      "weight": 1.0,
      "label": "Durable Necrons",
      "faction": "Necrons",
      "detachment_type": null,
      "archetype_tags": ["attrition", "durable"],
      "army_blueprint": null,
      "build_capability_profile_id": "build_capability_profile:durable_necrons_v1",
      "metadata": {
        "source_kind": "archetype_slice"
      }
    },
    {
      "slice_id": "slice:indirect_guard",
      "weight": 2.0,
      "label": "Indirect Guard",
      "faction": "Astra Militarum",
      "detachment_type": null,
      "archetype_tags": ["castle", "indirect"],
      "army_blueprint": null,
      "build_capability_profile_id": "build_capability_profile:indirect_guard_v1",
      "metadata": {
        "source_kind": "archetype_slice"
      }
    },
    {
      "slice_id": "slice:pressure_marines",
      "weight": 3.0,
      "label": "Pressure Marines",
      "faction": "Space Marines",
      "detachment_type": "Gladius Task Force",
      "archetype_tags": ["combined_arms", "mid_board"],
      "army_blueprint": null,
      "build_capability_profile_id": "build_capability_profile:pressure_marines_v1",
      "metadata": {
        "source_kind": "archetype_slice"
      }
    }
  ],
  "mission_distribution": [
    {
      "choice_id": "mission:purge_the_foe",
      "weight": 1.0,
      "label": "Purge the Foe",
      "metadata": {}
    },
    {
      "choice_id": "mission:take_and_hold",
      "weight": 2.0,
      "label": "Take and Hold",
      "metadata": {}
    }
  ],
  "deployment_distribution": [
    {
      "choice_id": "deployment:dawn_of_war",
      "weight": 1.0,
      "label": "Dawn of War",
      "metadata": {}
    },
    {
      "choice_id": "deployment:hammer_and_anvil",
      "weight": 1.0,
      "label": "Hammer and Anvil",
      "metadata": {}
    },
    {
      "choice_id": "deployment:tipping_point",
      "weight": 1.0,
      "label": "Tipping Point",
      "metadata": {}
    }
  ],
  "terrain_distribution": [
    {
      "choice_id": "terrain:layout_1",
      "weight": 1.0,
      "label": "Layout 1",
      "metadata": {}
    },
    {
      "choice_id": "terrain:layout_7",
      "weight": 1.0,
      "label": "Layout 7",
      "metadata": {}
    }
  ],
  "round_count": 5,
  "event_format_name": "Five-round singles GT",
  "pairing_metadata": {
    "intended_mode": "random_first_then_swiss"
  },
  "notes": "Representative GT field for deterministic roster-evaluation sweeps.",
  "metadata": {
    "source_date": "2026-04-14"
  }
}
```

## Example 10th-Style Event Policy

```json
{
  "event_policy_schema_id": "event_policy_schema:tournament_event_policy_v1",
  "event_policy_id": "event_policy:chapter_approved_10e_singles_v1",
  "force_disposition_lock_mode": "flexible",
  "secondary_selection_mode": "fixed_or_tactical",
  "terrain_layout_mode": "recommended_pack_layout",
  "clock_policy": {
    "clock_mode": "shared_round",
    "round_time_minutes": 165,
    "chess_clock_policy": "not_used",
    "pregame_minutes": 15,
    "per_player_time_minutes": null,
    "milestones": [
      {
        "remaining_minutes": 165,
        "label": "start_round"
      },
      {
        "remaining_minutes": 160,
        "label": "pregame_complete"
      },
      {
        "remaining_minutes": 150,
        "label": "deployment_complete"
      },
      {
        "remaining_minutes": 110,
        "label": "battle_round_1_complete"
      },
      {
        "remaining_minutes": 75,
        "label": "battle_round_2_complete"
      },
      {
        "remaining_minutes": 45,
        "label": "battle_round_3_complete"
      },
      {
        "remaining_minutes": 25,
        "label": "battle_round_4_complete"
      },
      {
        "remaining_minutes": 5,
        "label": "judge_permission_for_new_round"
      }
    ],
    "notes": "Round duration and milestones match the February 2025 Warhammer World Grand Tournament player pack.",
    "metadata": {}
  },
  "pairing_mode": "swiss",
  "roster_submission_mode": "submitted_fixed_list",
  "max_rounds": 5,
  "battle_size": "Strike Force",
  "army_points_limit": 2000,
  "board_size": "44\" x 60\"",
  "mission_policy": {
    "mission_pack_id": "mission_pack:chapter_approved_2025_26_v1_4",
    "mission_generation_mode": "pre_generated_tournament_pool",
    "deployment_generation_mode": "paired_with_primary_mission",
    "secondary_selection_mode": "fixed_or_tactical",
    "twists_mode": "not_used",
    "asymmetric_war_mode": "not_used",
    "challenge_mode": "not_used",
    "objective_marker_mode": "flat_40mm_passable",
    "terrain_layout_mode": "recommended_pack_layout",
    "terrain_layout_count_per_pairing": null,
    "notes": "Current official Tournament Companion v1.4 excludes Asymmetric War, Twists, and Challenger cards from the tournament packet.",
    "metadata": {}
  },
  "evaluation_budget": {
    "time_budget_ms": 25000,
    "opponent_sample_cap": 64,
    "pairing_sample_cap": 128,
    "notes": "Deterministic headless-evaluation default for offline roster assessment.",
    "metadata": {}
  },
  "format_name": "Current official 10th-style singles",
  "battle_ready_required": true,
  "pairing_tiebreakers": ["record", "win_path", "random_within_record"],
  "ranking_tiebreakers": ["record", "opponent_win_record", "total_victory_points"],
  "source_references": [
    {
      "label": "Chapter Approved Tournament Companion v1.4",
      "url": "https://assets.warhammer-community.com/eng_07-01_warhammer_40000_core_rules_chapter_approved_tournament-companion-sqc1af88bj-vzxhp9xmid.pdf",
      "published_on": null,
      "note": "Current official tournament baseline accessed April 14, 2026."
    },
    {
      "label": "Warhammer World Grand Tournament pack",
      "url": "https://warhammerworld.warhammer-community.com/wp-content/uploads/sites/15/2025/02/nQFpBT92eJZsn85n.pdf",
      "published_on": "2025-02",
      "note": "Used for a concrete five-round, 165-minute singles event example."
    }
  ],
  "notes": "Represents a concrete current 10th-style singles event shape with Swiss-style pairings, 2,000-point Strike Force rosters, Battle Ready scoring, and the official Chapter Approved tournament mission packet.",
  "metadata": {}
}
```

## Example Preview 11e Event Policy

```json
{
  "event_policy_schema_id": "event_policy_schema:tournament_event_policy_v1",
  "event_policy_id": "event_policy:preview_new40k_locked_force_disposition_v1",
  "force_disposition_lock_mode": "event_locked",
  "secondary_selection_mode": "fixed_or_tactical_persistent_draw",
  "terrain_layout_mode": "mission_pairing_recommended_layouts",
  "clock_policy": {
    "clock_mode": "shared_round",
    "round_time_minutes": 165,
    "chess_clock_policy": "organizer_defined",
    "pregame_minutes": 15,
    "per_player_time_minutes": null,
    "milestones": [],
    "notes": "No official preview event pack has been published as of April 14, 2026, so the round clock shape inherits a current five-round GT example.",
    "metadata": {}
  },
  "pairing_mode": "swiss",
  "roster_submission_mode": "submitted_fixed_list_with_force_disposition",
  "max_rounds": 5,
  "battle_size": "Strike Force",
  "army_points_limit": 2000,
  "board_size": "44\" x 60\"",
  "mission_policy": {
    "mission_pack_id": "mission_pack:preview_new40k_adepticon_2026",
    "mission_generation_mode": "force_disposition_pairing_matrix",
    "deployment_generation_mode": "mission_paired_deployment",
    "secondary_selection_mode": "fixed_or_tactical_persistent_draw",
    "twists_mode": "optional",
    "asymmetric_war_mode": "not_applicable",
    "challenge_mode": "not_applicable",
    "objective_marker_mode": null,
    "terrain_layout_mode": "mission_pairing_recommended_layouts",
    "terrain_layout_count_per_pairing": 3,
    "notes": "Preview articles describe five Force Dispositions, tournament-side event locking at list submission, and three recommended terrain layouts per mission pairing.",
    "metadata": {}
  },
  "evaluation_budget": {
    "time_budget_ms": 25000,
    "opponent_sample_cap": 64,
    "pairing_sample_cap": 128,
    "notes": "Matches the default offline roster-evaluation budget until a final event pack exists.",
    "metadata": {}
  },
  "format_name": "Preview new40k singles",
  "battle_ready_required": null,
  "pairing_tiebreakers": ["record", "win_path", "random_within_record"],
  "ranking_tiebreakers": ["record", "opponent_win_record", "total_victory_points"],
  "source_references": [
    {
      "label": "#New40k – How your army affects your mission",
      "url": "https://www.warhammer-community.com/en-gb/articles/oefzq9fg/new40k-how-your-army-affects-your-mission/",
      "published_on": "2026-04-03",
      "note": "Preview source for Force Dispositions, tournament-side disposition locking, secondary cadence, and paired mission/deployment logic."
    },
    {
      "label": "#New40k – Take cover with updated terrain rules",
      "url": "https://www.warhammer-community.com/articles/xlppkx5s/new40k-take-cover-with-updated-terrain-rules",
      "published_on": "2026-04-08",
      "note": "Preview source for terrain-layout recommendations by mission pairing."
    }
  ],
  "notes": "This is a preview-labeled example, not a claim about a final released event packet. Force-disposition locking and mission-pairing semantics are sourced from April 2026 preview articles; round count and general GT frame are inferred from current official singles norms.",
  "metadata": {
    "preview_status": "inferred_until_official_event_pack"
  }
}
```

## Determinism Notes

- `field_distribution_id` is derived from normalized weight ratios, so reordering
  or uniformly scaling weights does not change the id.
- `matchup_context_id` changes deterministically when the event policy, field,
  rules bundle, or bound roster changes.
- `event_policy_id` can be explicit for named packets or hash-derived for
  ad-hoc local event definitions.
