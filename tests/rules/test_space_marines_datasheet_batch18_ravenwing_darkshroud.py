from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str, faction_id: str = "SM") -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id=faction_id))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    return game, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def test_ravenwing_darkshroud_icon_of_old_caliban_grants_stealth_and_cover() -> None:
    game, sm_army, enemy_army = _build_game()
    darkshroud = _actual_unit("Ravenwing Darkshroud", datasheet_id="000000238")
    target = _actual_unit("Outrider Squad", datasheet_id="000002712")
    attacker = _actual_unit("Outrider Squad", datasheet_id="000002712")
    sm_army.add_unit(darkshroud)
    sm_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _deploy(darkshroud, 10.0, 10.0)
    _deploy(target, 14.0, 10.0)
    _deploy(attacker, 24.0, 10.0)
    game.map.units = [darkshroud, target, attacker]
    game.rebuild_entity_registry()

    ranged_profile = WargearProfile(
        "ranged",
        {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""},
    )
    attack_instance = {"mortal_wound": False}

    with (
        patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True),
        patch("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 1),
    ):
        assert target.has_stealth() is True
        ranged_profile._save_with_tracking(target.models[0], attack_instance, ap=0)

    assert attack_instance.get("benefit_of_cover") is True
    assert "Icon of Old Caliban" in str(attack_instance.get("benefit_of_cover_source", ""))
