from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.combat_timing import (
    bind_charge_move_targets,
    build_combat_timing_profile,
    fight_phase_move_steps,
    fight_phase_starting_player,
)


def test_build_combat_timing_profile_defaults_to_current_runtime_shape() -> None:
    profile = build_combat_timing_profile()

    assert profile.edition_family == "10e_current"
    assert profile.charge_target_binding == "post_roll"
    assert profile.fight_stage_start_player == "non_active_player"
    assert profile.disembark_charge_policy == "10e"


def test_build_combat_timing_profile_detects_preview_bundle_context() -> None:
    profile = build_combat_timing_profile(context={"rules_bundle_id": "preview-11e-core"})

    assert profile.edition_family == "11e_preview"
    assert profile.charge_target_binding == "post_roll"
    assert profile.disembark_charge_policy == "preview"


def test_fight_phase_helpers_use_non_active_player_and_standard_move_steps() -> None:
    current_player = SimpleNamespace(name="Current")
    opponent_player = SimpleNamespace(name="Opponent")
    game = SimpleNamespace(ruleset_bundle=None)

    assert fight_phase_starting_player(game, current_player, opponent_player) is opponent_player
    assert fight_phase_move_steps(game) == ("pile_in", "consolidate")


def test_bind_charge_move_targets_applies_post_roll_legality() -> None:
    legal_target = SimpleNamespace(id="enemy-1", is_alive=lambda: True)
    illegal_target = SimpleNamespace(id="enemy-2", is_alive=lambda: True)
    game = SimpleNamespace(
        ruleset_bundle=None,
        _resolve_unit_by_id=lambda unit_id: {
            "enemy-1": legal_target,
            "enemy-2": illegal_target,
        }.get(unit_id),
    )

    class _ChargingUnit:
        def can_declare_charge_against(self, target, _game, *, out_of_turn: bool = False) -> bool:
            del _game, out_of_turn
            return target is legal_target

    bound = bind_charge_move_targets(game, _ChargingUnit(), ["enemy-1", "enemy-2", "enemy-1"])

    assert bound == [legal_target]
