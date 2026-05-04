from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.combat_timing import (
    CombatEngagementState,
    base_contact_center_distance,
    bind_charge_move_targets,
    build_combat_timing_profile,
    engagement_center_distance,
    engagement_state_for_bases,
    fight_phase_move_steps,
    fight_phase_starting_player,
)
from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.engine import fight_move


class _BaseStub:
    def __init__(self, *, x: float, y: float, radius: float = 0.5, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self._radius = float(radius)
        self.has_circular_base = True

    def get_radius(self) -> float:
        return self._radius


class _ModelStub:
    def __init__(self, model_id: str, base: _BaseStub) -> None:
        self.id = model_id
        self._id = model_id
        self.model_base = base
        self.is_alive = True
        self.parent_unit = None


class _UnitStub:
    def __init__(self, unit_id: str, army: object | None = None) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = unit_id
        self.parent_army = army
        self.round_state = SimpleNamespace(charge_roll=9)

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def is_alive(self) -> bool:
        return True


def _preview_game() -> SimpleNamespace:
    return SimpleNamespace(
        ruleset_bundle=RulesetBundle.from_values(core_rules_id="preview-11e-core"),
    )


def test_build_combat_timing_profile_defaults_to_current_runtime_shape() -> None:
    profile = build_combat_timing_profile()

    assert profile.edition_family == "10e_current"
    assert profile.charge_target_selection_window == "post_roll"
    assert profile.geometry.engagement_range_horizontal == 1.0
    assert profile.geometry.ingress_exclusion_distance == 9.0
    assert profile.fight_order_priority_for_stage("fight_first") == "non_active_player"
    assert profile.pile_in_batch_mode == "per_unit"


def test_build_combat_timing_profile_detects_preview_bundle_context() -> None:
    profile = build_combat_timing_profile(context={"rules_bundle_id": "preview-11e-core"})

    assert profile.edition_family == "11e_preview"
    assert profile.charge_target_selection_window == "post_roll"
    assert profile.geometry.engagement_range_horizontal == 2.0
    assert profile.geometry.can_pass_through_enemy_engagement_range is True
    assert profile.geometry.ingress_exclusion_distance == 8.0
    assert profile.fight_order_priority_for_stage("fight_first") == "active_player"
    assert profile.fight_order_priority_for_stage("remaining_combatants") == "non_active_player"
    assert profile.pile_in_batch_mode == "player_batch"
    assert profile.consolidate_batch_mode == "end_batch"
    assert profile.overrun_enabled is True


def test_build_combat_timing_profile_prefers_explicit_profile_marker_over_token_fallback() -> None:
    profile = build_combat_timing_profile(
        context={
            "rules_bundle_id": "rules_bundle:live_release",
            "version_adapter_boundary": {
                "combat_profile_family": "11e_preview",
            },
        }
    )

    assert profile.edition_family == "11e_preview"
    assert profile.geometry.engagement_range_horizontal == 2.0


def test_build_combat_timing_profile_can_explicitly_force_current_profile() -> None:
    profile = build_combat_timing_profile(
        context={
            "rules_bundle_id": "preview-11e-core",
            "version_adapter_boundary": {
                "combat_profile_family": "10e_current",
            },
        }
    )

    assert profile.edition_family == "10e_current"
    assert profile.geometry.engagement_range_horizontal == 1.0


def test_fight_phase_helpers_use_stage_specific_priority() -> None:
    current_player = SimpleNamespace(name="Current")
    opponent_player = SimpleNamespace(name="Opponent")
    game = _preview_game()

    assert fight_phase_starting_player(game, current_player, opponent_player, stage_name="fight_first") is current_player
    assert (
        fight_phase_starting_player(game, current_player, opponent_player, stage_name="remaining_combatants")
        is opponent_player
    )
    assert fight_phase_move_steps(game) == ("pile_in", "consolidate")


def test_engagement_geometry_supports_two_inch_preview_range_across_wall() -> None:
    base_a = _BaseStub(x=10.0, y=10.0)
    base_b = _BaseStub(x=12.5, y=10.0)

    assert engagement_state_for_bases(base_a, base_b) is CombatEngagementState.UNENGAGED
    assert (
        engagement_state_for_bases(base_a, base_b, context={"rules_bundle_id": "preview-11e-core"})
        is CombatEngagementState.ENGAGED
    )
    assert base_contact_center_distance(0.5, 0.5) == 1.025
    assert engagement_center_distance(0.5, 0.5, context={"rules_bundle_id": "preview-11e-core"}) == 3.0


def test_bind_charge_move_targets_records_charge_resolution_state() -> None:
    legal_target = _UnitStub("enemy-1")
    illegal_target = _UnitStub("enemy-2")
    game = _preview_game()
    game._resolve_unit_by_id = lambda unit_id: {
        "enemy-1": legal_target,
        "enemy-2": illegal_target,
    }.get(unit_id)

    class _ChargingUnit(_UnitStub):
        def can_declare_charge_against(self, target, _game, *, out_of_turn: bool = False) -> bool:
            del _game, out_of_turn
            return target is legal_target

    charging_unit = _ChargingUnit("charger")

    bound = bind_charge_move_targets(game, charging_unit, ["enemy-1", "enemy-2", "enemy-1"])

    assert bound == [legal_target]
    assert charging_unit.round_state.charge_resolution_choice == {
        "choice_kind": "selected_targets",
        "selection_window": "post_roll",
        "declared_target_ids": ["enemy-1", "enemy-2"],
        "reachable_target_ids": ["enemy-1"],
        "chosen_target_ids": ["enemy-1"],
    }
    assert charging_unit.round_state.charge_resolution_outcome == {
        "rules_bundle_id": build_combat_timing_profile(ruleset_bundle=game.ruleset_bundle).rules_bundle_id,
        "edition_family": "11e_preview",
        "roll_total": 9,
        "declared_target_ids": ["enemy-1", "enemy-2"],
        "reachable_target_ids": ["enemy-1"],
        "chosen_target_ids": ["enemy-1"],
        "must_end_engaged_with_all_targets": True,
        "cannot_end_engaged_with_non_targets": True,
        "movement_finish_disallows_enemy_engagement_without_charge": True,
    }


def test_bind_charge_move_targets_can_record_declined_charge_choice() -> None:
    game = _preview_game()
    game._resolve_unit_by_id = lambda _unit_id: None
    charging_unit = _UnitStub("charger")

    bound = bind_charge_move_targets(game, charging_unit, [])

    assert bound == []
    assert charging_unit.round_state.charge_resolution_choice["choice_kind"] == "decline_charge"
    assert charging_unit.round_state.charge_resolution_outcome["chosen_target_ids"] == []


def test_fight_move_base_contact_helper_does_not_pass_map_as_game_context() -> None:
    model = _ModelStub("model-1", _BaseStub(x=10.0, y=10.0))
    model.parent_unit = SimpleNamespace()
    enemy_model = _ModelStub("enemy-model-1", _BaseStub(x=11.0, y=10.0))
    game_map = SimpleNamespace(units=[])

    with patch.object(fight_move, "_enemy_models_for_unit", return_value=[enemy_model]):
        with patch.object(
            fight_move,
            "engagement_state_for_models",
            return_value=CombatEngagementState.BASE_CONTACT,
        ) as patched:
            assert fight_move._model_in_base_contact(model, unit=model.parent_unit, game_map=game_map) is True

    _args, kwargs = patched.call_args
    assert "game" not in kwargs


def test_budgeted_fight_move_planning_uses_snapshot_without_routed_pathing() -> None:
    model = _ModelStub("model-1", _BaseStub(x=4.0, y=5.0, z=0.0))
    unit = _UnitStub("unit-1")
    unit.models = [model]
    model.parent_unit = unit
    game = SimpleNamespace(map=SimpleNamespace())

    with patch.object(fight_move, "plan_model_path", side_effect=AssertionError("routed pathing should not run")):
        planned = fight_move.plan_deterministic_fight_move(
            game,
            unit,
            movement_type="pile_in",
            max_distance=3.0,
            target_unit_ids=[],
            deadline=0.0,
        )

    assert planned == [{"model_id": "model-1", "position": [4.0, 5.0, 0.0], "facing": 0.0}]
