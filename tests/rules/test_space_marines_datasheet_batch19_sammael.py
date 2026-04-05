from __future__ import annotations

from types import MethodType, SimpleNamespace

import pytest

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
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
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.turn = 1
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    try:
        leader.attach_to_unit(bodyguard)
    except Exception:
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
    for unit in (bodyguard, leader):
        invalidate = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()
    bodyguard._refresh_bearer_unit_common_modifiers()


def test_sammael_grand_master_of_the_ravenwing_grants_advance_shoot_and_charge_without_bonus_by_default() -> None:
    game, sm_army, _enemy_army = _build_game()
    outriders = _actual_unit("Outrider Squad", datasheet_id="000002712")
    sammael = _actual_unit("Sammael", datasheet_id="000002291")
    sm_army.add_unit(outriders)
    sm_army.add_unit(sammael)
    _attach_leader(outriders, sammael)

    assert outriders.has_advance_and_shoot() is True
    assert outriders.has_advance_and_charge() is True
    assert "Grand Master of the Ravenwing" not in {
        source for _value, source in list(outriders._collect_advance_roll_modifiers() or [])
    }
    assert "Grand Master of the Ravenwing" not in {
        source for _value, source in list(game.get_charge_roll_modifiers(outriders, target_unit=None) or [])
    }


def test_sammael_grand_master_of_the_ravenwing_adds_bonus_when_another_source_already_grants_eligibility() -> None:
    game, sm_army, _enemy_army = _build_game()
    outriders = _actual_unit("Outrider Squad", datasheet_id="000002712")
    sammael = _actual_unit("Sammael", datasheet_id="000002291")
    sm_army.add_unit(outriders)
    sm_army.add_unit(sammael)
    _attach_leader(outriders, sammael)

    outriders.possible_abilities.append(
        SimpleNamespace(
            name="Test Blitz",
            description="This unit is eligible to shoot and declare a charge in a turn in which it Advanced.",
        )
    )
    invalidate = getattr(outriders, "_invalidate_ability_cache", None)
    if callable(invalidate):
        invalidate()
    outriders._refresh_bearer_unit_common_modifiers()

    assert outriders.has_advance_and_shoot() is True
    assert outriders.has_advance_and_charge() is True
    assert ("Grand Master of the Ravenwing" in {
        source for _value, source in list(outriders._collect_advance_roll_modifiers() or [])
    })
    assert ("Grand Master of the Ravenwing" in {
        source for _value, source in list(game.get_charge_roll_modifiers(outriders, target_unit=None) or [])
    })


@pytest.mark.parametrize(("battleshocked", "expected_modifier"), [(False, 0), (True, -1)])
def test_sammael_cut_off_their_escape_forces_desperate_escape_tests(
    battleshocked: bool,
    expected_modifier: int,
) -> None:
    sammael = _actual_unit("Sammael", datasheet_id="000002291")
    enemy = _actual_unit("Outrider Squad", datasheet_id="000002712")
    sammael.parent_army = object()
    enemy.parent_army = object()
    _deploy(enemy, 10.0, 10.0)
    _deploy(sammael, 10.6, 10.0)
    if battleshocked:
        enemy.apply_status_effect(BattleShockEffect(1))

    game_map = Map(60, 44)
    game_map.units = [enemy, sammael]

    called = {"count": 0, "modifier": None}

    def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
        called["count"] += 1
        called["modifier"] = roll_modifier
        return 0

    enemy.take_desperate_escape_test = MethodType(_fake, enemy)

    result = enemy.fall_back((14.0, 10.0, 0.0), [], game_map)

    assert result is True
    assert called["count"] == 1
    assert int(called["modifier"] or 0) == expected_modifier
