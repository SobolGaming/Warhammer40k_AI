from __future__ import annotations

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army


def test_whirlwind_pinning_bombardment_parses_as_weapon_gated_post_shoot_battleshock() -> None:
    whirlwind = _actual_unit("Whirlwind", datasheet_id="000002727")

    specs = whirlwind.model_post_shoot_battleshock_specs(whirlwind.models[0])

    assert len(specs) == 1
    spec = specs[0]
    assert bool(spec.get("infantry_only", False)) is True
    assert bool(spec.get("auto_each_target", False)) is True
    assert str(spec.get("source", "") or "") == "Pinning Bombardment"
    assert str(spec.get("require_weapon_key_hit", "") or "") == whirlwind._normalize_keyword_phrase(
        "Whirlwind vengeance launcher"
    )


def test_whirlwind_pinning_bombardment_forces_only_hit_infantry_targets_to_test() -> None:
    game, sm_army, enemy_army = _build_game()

    whirlwind = _actual_unit("Whirlwind", datasheet_id="000002727")
    enemy_infantry = _actual_unit("Intercessor Squad", datasheet_id="000001157")
    enemy_vehicle = _actual_unit("Rhino", datasheet_id="000002723")

    sm_army.add_unit(whirlwind)
    enemy_army.add_unit(enemy_infantry)
    enemy_army.add_unit(enemy_vehicle)
    game.map.units = [whirlwind, enemy_infantry, enemy_vehicle]
    game.rebuild_entity_registry()

    infantry_calls: list[int] = []
    vehicle_calls: list[int] = []
    enemy_infantry.take_battle_shock_test = lambda current_turn=0: infantry_calls.append(int(current_turn))
    enemy_vehicle.take_battle_shock_test = lambda current_turn=0: vehicle_calls.append(int(current_turn))

    attacker_model = whirlwind.models[0]
    weapon_key = whirlwind._normalize_keyword_phrase("Whirlwind vengeance launcher")
    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=whirlwind,
        hits_by_target={enemy_infantry: 1, enemy_vehicle: 1},
        hit_models_by_target={
            enemy_infantry: {attacker_model},
            enemy_vehicle: {attacker_model},
        },
        hit_models_by_target_weapon={
            enemy_infantry: {weapon_key: {attacker_model}},
            enemy_vehicle: {whirlwind._normalize_keyword_phrase("storm bolter"): {attacker_model}},
        },
        killing_models_by_target={},
    )

    assert infantry_calls == [1]
    assert vehicle_calls == []

