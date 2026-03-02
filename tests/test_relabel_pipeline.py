from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
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
