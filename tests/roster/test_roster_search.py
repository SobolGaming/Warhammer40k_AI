from __future__ import annotations

import json
from pathlib import Path

import pytest

from warhammer40k_ai.ml import ArtifactManifestStore
from warhammer40k_ai.roster.army_build import ArmyBlueprint, DetachmentSelection, EnhancementAssignment, RosterEntry
from warhammer40k_ai.roster.event_policy import (
    chapter_approved_10e_event_policy,
    preview_new40k_event_policy,
)
from warhammer40k_ai.roster.roster_edit_actions import (
    AddUnitEntryAction,
    AssignEnhancementAction,
    ChangeWargearChoiceAction,
    MutateForceDispositionAction,
    SelectWarlordAction,
)
from warhammer40k_ai.roster.roster_repair import validate_blueprint_runtime_legality
from warhammer40k_ai.roster.roster_search import (
    HeuristicRosterEvaluator,
    RosterSearchConfig,
    search_rosters,
)
from warhammer40k_ai.roster.tournament_field import OpponentSlice, TournamentFieldDistribution, WeightedChoice
from warhammer40k_ai.waha_helper import WahaHelper


@pytest.fixture(scope="module")
def waha_helper() -> WahaHelper:
    return WahaHelper()


def _seed_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Space Marines",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="det_gladius",
                detachment_type="Gladius Task Force",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="entry_captain",
                name="Captain",
                count=1,
                detachment_selection_id="det_gladius",
            ),
            RosterEntry(
                entry_id="entry_intercessors",
                name="Intercessor Squad",
                count=5,
                detachment_selection_id="det_gladius",
            ),
        ],
        allowed_force_dispositions=["Assault", "Siege"],
    )


def _scoring_evaluator(blueprint: ArmyBlueprint) -> dict[str, object]:
    grenade_launcher = 1.0 if "Astartes grenade launcher" in set(blueprint.unit_entries[1].wargear) else 0.0
    score = float(len(blueprint.unit_entries) + grenade_launcher)
    return {
        "score": score,
        "utility_decomposition": {
            "score": score,
            "unit_count": len(blueprint.unit_entries),
            "grenade_launcher_bonus": grenade_launcher,
        },
        "evaluation_summary": {
            "primary_detachment_type": blueprint.primary_detachment_type,
        },
    }


def _local_path_scoring_evaluator(blueprint: ArmyBlueprint) -> dict[str, object]:
    force_disposition_bonus = 10.0 if blueprint.force_disposition == "Siege" else 0.0
    bladeguard_bonus = 1.0 if any(entry.entry_id == "entry_bladeguard" for entry in blueprint.unit_entries) else 0.0
    grenade_launcher_bonus = 0.1 if any(
        entry.entry_id == "entry_intercessors" and "Astartes grenade launcher" in set(entry.wargear)
        for entry in blueprint.unit_entries
    ) else 0.0
    score = force_disposition_bonus + bladeguard_bonus + grenade_launcher_bonus
    return {
        "score": score,
        "utility_decomposition": {
            "score": score,
            "force_disposition_bonus": force_disposition_bonus,
            "bladeguard_bonus": bladeguard_bonus,
            "grenade_launcher_bonus": grenade_launcher_bonus,
        },
        "evaluation_summary": {
            "force_disposition": blueprint.force_disposition,
        },
    }


def _heuristic_bundle_payload(bundle_id: str) -> dict[str, object]:
    return {
        "policy_bundle_schema_id": "policy_bundle_schema:v1",
        "policy_bundle_id": bundle_id,
        "controller_type": "headless_self_play",
        "rules_bundle_scope": {
            "match_mode": "exact",
            "ids": ["rules_bundle:test_bundle"],
        },
        "descriptor_bundle_scope": {
            "match_mode": "exact",
            "ids": ["descriptor_bundle:test_bundle"],
        },
        "event_policy_scope": {
            "match_mode": "exact",
            "ids": ["event_policy:chapter_approved_10e_singles_v1"],
        },
        "components": {
            "candidate_ranker": {
                "resolver_kind": "heuristic",
                "resolver_ref": "heuristic:headless_candidate_ranker:v1",
            },
            "matchup_evaluator": {
                "resolver_kind": "heuristic",
                "resolver_ref": "heuristic:capability_matchup:v1",
            },
            "playbook_selector": {
                "resolver_kind": "heuristic",
                "resolver_ref": "heuristic:identity_playbook:v1",
            },
        },
        "fallbacks": {
            "playbook_selector": ["heuristic:identity_playbook_fallback:v1"]
        },
        "required_feature_schema_ids": ["feature_schema:roster_matchup_v1"],
        "required_capability_schema_ids": ["capability_schema:build_capability_v1"],
        "created_from_commit": "0123456789abcdef0123456789abcdef01234567",
    }


def test_search_returns_only_validator_approved_blueprints_and_report_traces(
    waha_helper: WahaHelper,
) -> None:
    actions = [
        SelectWarlordAction(entry_id="entry_captain"),
        ChangeWargearChoiceAction(
            entry_id="entry_intercessors",
            wargear=("Astartes grenade launcher",),
        ),
        AssignEnhancementAction(
            EnhancementAssignment(
                assignment_id="enh_invalid",
                enhancement_name="Artificer Armour",
                target_entry_id="entry_intercessors",
                detachment_selection_id="det_gladius",
            )
        ),
        AddUnitEntryAction(
            RosterEntry(
                entry_id="captain_2",
                name="Captain",
                count=1,
                detachment_selection_id="det_gladius",
            )
        ),
        AddUnitEntryAction(
            RosterEntry(
                entry_id="captain_3",
                name="Captain",
                count=1,
                detachment_selection_id="det_gladius",
            )
        ),
        AddUnitEntryAction(
            RosterEntry(
                entry_id="captain_4",
                name="Captain",
                count=1,
                detachment_selection_id="det_gladius",
            )
        ),
    ]

    report = search_rosters(
        _seed_blueprint(),
        waha_helper=waha_helper,
        evaluator=_scoring_evaluator,
        action_provider=actions,
        config=RosterSearchConfig(
            strategy="beam",
            max_iterations=3,
            beam_width=6,
            top_k=4,
            random_seed=11,
        ),
    )

    assert report.top_candidates
    assert report.rejected_candidate_count > 0
    assert report.metadata["validation_contract"]["warlord_validation"] is True
    assert report.metadata["validation_contract"]["wargear_option_validation"] is True
    assert report.top_candidates[0].edit_trace
    assert "score" in report.top_candidates[0].utility_decomposition
    for candidate in report.top_candidates:
        legality = validate_blueprint_runtime_legality(
            candidate.army_blueprint,
            waha_helper=waha_helper,
        )
        assert legality.is_valid is True


def test_search_is_reproducible_under_fixed_seed_for_evolutionary_strategy(
    waha_helper: WahaHelper,
) -> None:
    actions = [
        SelectWarlordAction(entry_id="entry_captain"),
        ChangeWargearChoiceAction(
            entry_id="entry_intercessors",
            wargear=("Astartes grenade launcher",),
        ),
        MutateForceDispositionAction(
            force_disposition="Siege",
            allowed_force_dispositions=("Assault", "Siege"),
        ),
        AddUnitEntryAction(
            RosterEntry(
                entry_id="entry_bladeguard",
                name="Bladeguard Veteran Squad",
                count=3,
                detachment_selection_id="det_gladius",
            )
        ),
    ]

    config = RosterSearchConfig(
        strategy="evolutionary",
        max_iterations=2,
        population_size=2,
        mutations_per_parent=2,
        top_k=3,
        random_seed=19,
    )

    first = search_rosters(
        _seed_blueprint(),
        waha_helper=waha_helper,
        evaluator=_scoring_evaluator,
        action_provider=actions,
        config=config,
    )
    second = search_rosters(
        _seed_blueprint(),
        waha_helper=waha_helper,
        evaluator=_scoring_evaluator,
        action_provider=actions,
        config=config,
    )

    assert first.to_dict() == second.to_dict()


def test_search_local_strategy_keeps_single_parent_frontier(
    waha_helper: WahaHelper,
) -> None:
    actions = [
        MutateForceDispositionAction(
            force_disposition="Siege",
            allowed_force_dispositions=("Assault", "Siege"),
        ),
        AddUnitEntryAction(
            RosterEntry(
                entry_id="entry_bladeguard",
                name="Bladeguard Veteran Squad",
                count=3,
                detachment_selection_id="det_gladius",
            )
        ),
        ChangeWargearChoiceAction(
            entry_id="entry_intercessors",
            wargear=("Astartes grenade launcher",),
        ),
    ]

    report = search_rosters(
        _seed_blueprint(),
        waha_helper=waha_helper,
        evaluator=_local_path_scoring_evaluator,
        action_provider=actions,
        config=RosterSearchConfig(
            strategy="local",
            max_iterations=2,
            top_k=4,
            random_seed=23,
        ),
    )

    assert report.strategy == "local"
    assert [iteration.frontier_size for iteration in report.iterations] == [1, 1]
    assert report.iterations[0].candidate_count == 3
    assert report.iterations[1].candidate_count == 2
    assert [step["kind"] for step in report.top_candidates[0].edit_trace] == [
        "mutate_force_disposition",
        "add_unit_entry",
    ]
    assert report.top_candidates[0].army_blueprint.force_disposition == "Siege"
    assert any(
        entry.entry_id == "entry_bladeguard"
        for entry in report.top_candidates[0].army_blueprint.unit_entries
    )


def test_search_force_disposition_repair_respects_event_policy_lock_mode(
    waha_helper: WahaHelper,
) -> None:
    seed = _seed_blueprint()
    seed.force_disposition = None
    seed.allowed_force_dispositions = ["Siege", "Assault"]
    actions = [
        MutateForceDispositionAction(
            force_disposition=None,
            allowed_force_dispositions=("Siege", "Assault"),
        )
    ]

    flexible_report = search_rosters(
        seed,
        waha_helper=waha_helper,
        evaluator=_local_path_scoring_evaluator,
        action_provider=actions,
        config=RosterSearchConfig(strategy="local", max_iterations=1, top_k=2, random_seed=31),
        event_policy=chapter_approved_10e_event_policy(),
    )
    locked_report = search_rosters(
        seed,
        waha_helper=waha_helper,
        evaluator=_local_path_scoring_evaluator,
        action_provider=actions,
        config=RosterSearchConfig(strategy="local", max_iterations=1, top_k=2, random_seed=31),
        event_policy=preview_new40k_event_policy(),
    )

    assert flexible_report.seed_blueprint.force_disposition is None
    assert locked_report.seed_blueprint.force_disposition == "Siege"
    assert all(candidate.army_blueprint.force_disposition is None for candidate in flexible_report.top_candidates)
    assert all(candidate.army_blueprint.force_disposition == "Siege" for candidate in locked_report.top_candidates)


def test_heuristic_roster_evaluator_works_with_framework_free_policy_bundle(
    tmp_path: Path,
    waha_helper: WahaHelper,
) -> None:
    models_root = tmp_path / "models"
    bundle_path = ArtifactManifestStore(models_root).bundle_manifest_path("policy_bundle:heuristic_search_v1")
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(
        json.dumps(_heuristic_bundle_payload("policy_bundle:heuristic_search_v1"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    event_policy = chapter_approved_10e_event_policy()
    field_distribution = TournamentFieldDistribution(
        rules_bundle_id="rules_bundle:test_bundle",
        event_policy_id=event_policy.event_policy_id,
        terrain_layout_pack_id="terrain_pack:test",
        opponent_slices=(
            OpponentSlice(
                slice_id="slice:space_marines",
                weight=1.0,
                label="Space Marines",
                faction="Space Marines",
            ),
        ),
        mission_distribution=(WeightedChoice(choice_id="mission:test", weight=1.0),),
        deployment_distribution=(WeightedChoice(choice_id="deployment:test", weight=1.0),),
        terrain_distribution=(WeightedChoice(choice_id="terrain:test", weight=1.0),),
    )

    evaluator = HeuristicRosterEvaluator(
        waha_helper=waha_helper,
        policy_bundle_source=str(bundle_path),
        event_policy=event_policy,
        field_distribution=field_distribution,
        models_root=str(models_root),
    )

    result = evaluator.evaluate(_seed_blueprint())

    assert isinstance(result["score"], float)
    assert "policy_bundle_id" in result["evaluation_summary"]
    assert result["evaluation_summary"]["policy_bundle_id"] == "policy_bundle:heuristic_search_v1"
