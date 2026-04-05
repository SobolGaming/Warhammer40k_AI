from __future__ import annotations

import copy

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.candidate_semantics import SEMANTIC_NUMERIC_KEYS
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ALLOCATE_MELEE_TARGETS,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_CHARGE,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
    DECISION_USE_GILDED_CHAMPION,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.relabel import (
    CHOSEN_ACTION_STATUS_INVALID_UNDER_TARGET_BUNDLE,
    CHOSEN_ACTION_STATUS_LEGAL_SEMANTICALLY_COMPARABLE,
    CHOSEN_ACTION_STATUS_LEGAL_VALUE_CHANGED,
    RELABEL_STATUS_INVALID_UNDER_TARGET_BUNDLE,
    RELABEL_STATUS_LEGAL_SEMANTICALLY_COMPARABLE,
    RELABEL_STATUS_LEGAL_VALUE_CHANGED,
    relabel_decision_record,
)
from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.roster.player import Player


def _build_record() -> dict:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )
    game.request_decision(request)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True
    return dict(game.decision_record_store.records[-1])


def _target_bundle_with_suffix(suffix: str) -> RulesetBundle:
    return RulesetBundle.from_values(
        core_rules_id=f"core_{suffix}",
        rules_commentary_id=f"commentary_{suffix}",
        mission_pack_id=f"mission_{suffix}",
        terrain_pack_id=f"terrain_{suffix}",
        dataslate_id=f"dataslate_{suffix}",
        points_id=f"points_{suffix}",
        faction_pack_id=f"faction_{suffix}",
        detachment_pack_id=f"detachment_{suffix}",
    )


def test_relabel_marks_legal_value_changed_when_bundle_changes() -> None:
    record = _build_record()
    target_bundle = _target_bundle_with_suffix("new")

    relabeled = relabel_decision_record(record, target_rules_bundle=target_bundle)

    assert relabeled["relabel_rules_bundle"] == target_bundle.to_dict()
    assert relabeled["relabel_rules_bundle_id"] == target_bundle.rules_bundle_id
    assert relabeled["relabel_status"] == RELABEL_STATUS_LEGAL_VALUE_CHANGED
    assert relabeled["chosen_action_status_under_relabel"] == CHOSEN_ACTION_STATUS_LEGAL_VALUE_CHANGED

    for candidate in list(relabeled.get("candidates", []) or []):
        metadata = dict(candidate.get("metadata", {}) or {})
        assert "projected_score_delta_next_window" in metadata
        assert "projected_control_delta" in metadata
        provenance = list(metadata.get("rules_provenance_refs", []) or [])
        assert target_bundle.rules_bundle_id in provenance


def test_relabel_marks_semantically_comparable_when_bundle_is_same() -> None:
    record = _build_record()
    target_bundle = RulesetBundle.from_dict(dict(record.get("rules_bundle", {}) or {}))

    relabeled = relabel_decision_record(record, target_rules_bundle=target_bundle)

    assert relabeled["relabel_status"] == RELABEL_STATUS_LEGAL_SEMANTICALLY_COMPARABLE
    assert relabeled["chosen_action_status_under_relabel"] == CHOSEN_ACTION_STATUS_LEGAL_SEMANTICALLY_COMPARABLE


def test_relabel_marks_invalid_when_chosen_action_missing() -> None:
    record = _build_record()
    record["chosen_action_id"] = "missing_action_id"
    target_bundle = _target_bundle_with_suffix("new")

    relabeled = relabel_decision_record(record, target_rules_bundle=target_bundle)

    assert relabeled["relabel_status"] == RELABEL_STATUS_INVALID_UNDER_TARGET_BUNDLE
    assert relabeled["chosen_action_status_under_relabel"] == CHOSEN_ACTION_STATUS_INVALID_UNDER_TARGET_BUNDLE
    mapping = dict(relabeled.get("relabel_candidate_map", {}) or {})
    assert "missing_action_id" in mapping


def _semantic_record(decision_type: str, params: dict, metadata: dict | None = None) -> dict:
    source_bundle = _target_bundle_with_suffix("source")
    return {
        "decision_type": decision_type,
        "rules_bundle": source_bundle.to_dict(),
        "rules_bundle_id": source_bundle.rules_bundle_id,
        "candidates": [
            {
                "action_id": f"{decision_type}:candidate",
                "params": dict(params),
                "metadata": dict(metadata or {}),
            }
        ],
        "mask": [True],
        "chosen_action_id": f"{decision_type}:candidate",
        "valid": True,
        "phase": "MOVEMENT",
        "descriptor_ids": {
            "mission_descriptor_id": "mission_descriptor:test",
            "objective_descriptor_ids": ["objective_descriptor:test"],
            "terrain_descriptor_ids": ["terrain_descriptor:test"],
            "deployment_descriptor_id": "deployment_descriptor:test",
            "army_build_descriptor_id": "army_build_descriptor:test",
            "tool_descriptor_ids": ["tool_descriptor:stratagem:test"],
        },
        "omniscient_state": {},
    }


def test_relabel_semantic_metadata_value_shift_for_required_decision_classes() -> None:
    target_bundle = _target_bundle_with_suffix("target")
    records = [
        _semantic_record(
            DECISION_MOVE_UNIT,
            {
                "action": "confirm",
                "unit_id": "unit_1",
                "movement_type": "move",
            },
            metadata={
                "candidate_kind": "move",
                "threat_score": 0.2,
            },
        ),
        _semantic_record(
            DECISION_DECLARE_SHOTS,
            {
                "action": "declare",
                "unit_id": "unit_1",
                "target_unit_ids": ["target_1", "target_2"],
                "declared_shots": [{"weapon_id": "weapon_1", "shots": 4}],
            },
        ),
        _semantic_record(
            DECISION_DECLARE_CHARGE,
            {
                "action": "declare",
                "unit_id": "unit_1",
                "target_unit_ids": ["target_1"],
                "charge_distance": 8,
            },
        ),
        _semantic_record(
            DECISION_ALLOCATE_MELEE_TARGETS,
            {
                "action": "allocate",
                "attack_declarations": [
                    {
                        "model_id": "model_1",
                        "wargear_id": "wargear_1",
                        "profile_name": "talons",
                        "target_unit_id": "target_1",
                        "attacks_override": 5,
                    }
                ],
            },
        ),
        _semantic_record(
            DECISION_USE_GILDED_CHAMPION,
            {
                "action": "use",
                "model_id": "model_1",
                "ability_key": "precision_cut",
                "ability_name": "Precision Strike",
                "cp_cost": 1,
            },
            metadata={"semantic_tags": ["damage_spike"]},
        ),
    ]

    for record in records:
        source_metadata = copy.deepcopy(record["candidates"][0]["metadata"])
        relabeled = relabel_decision_record(record, target_rules_bundle=target_bundle)
        metadata = dict(relabeled["candidates"][0]["metadata"] or {})

        assert metadata.get("relabel_generated") is True
        assert target_bundle.rules_bundle_id in list(metadata.get("rules_provenance_refs", []) or [])
        assert relabeled["relabel_status"] == RELABEL_STATUS_LEGAL_VALUE_CHANGED
        assert relabeled["chosen_action_status_under_relabel"] == CHOSEN_ACTION_STATUS_LEGAL_VALUE_CHANGED

        assert any(
            float(metadata.get(key, 0.0)) != float(source_metadata.get(key, 0.0))
            for key in SEMANTIC_NUMERIC_KEYS
        )
