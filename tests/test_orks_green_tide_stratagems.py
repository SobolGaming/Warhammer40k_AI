from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: str = "2",
    ):
        slug = str(name or "unit").lower().replace(" ", "_")
        self.id = f"mock_{slug}"
        self.name = name
        faction_kw = [str(keyword).upper() for keyword in list(faction_keywords or [])]
        self.faction_data = {"name": "Orks" if "ORKS" in faction_kw else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None, model_count: int = 1, wounds: str = "2") -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army("Orks", "Green Tide")
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ork_player = Player("Orks", control=PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)

    ork_player.command_points = 10
    enemy_player.command_points = 10
    ork_army.configure_rule_managers(force=True)
    ork_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, ork_player, enemy_player, ork_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def test_come_on_ladz_returns_up_to_d3_plus_2_destroyed_boyz_models():
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_game()
    boyz = _make_unit(
        "Boyz Mob",
        keywords=["INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=6,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(boyz)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)

    removed = list(boyz.models[:3])
    for model in removed:
        boyz.remove_model(model)
    assert len(list(getattr(boyz, "models_lost", []) or [])) == 3

    _set_phase(game, ork_player, "COMMAND_PHASE", 0)
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=2):
        ok = ork_player.stratagems.use("COME ON LADZ!", unit=boyz, phase_name="Command phase")

    assert ok
    assert int(ork_player.command_points or 0) == 9
    assert len(list(getattr(boyz, "models_lost", []) or [])) == 0
    assert len(list(getattr(boyz, "models", []) or [])) == 6


def test_come_on_ladz_excludes_character_models():
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_game()
    boyz = _make_unit(
        "Boyz",
        keywords=["INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=5,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(boyz)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, boyz, 20.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)

    removed_normal = boyz.models[0]
    removed_character = boyz.models[1]
    boyz.remove_model(removed_normal)
    boyz.remove_model(removed_character)
    removed_character.keywords.append("CHARACTER")

    _set_phase(game, ork_player, "COMMAND_PHASE", 0)
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=3):
        ok = ork_player.stratagems.use("COME ON LADZ!", unit=boyz, phase_name="Command phase")

    assert ok
    assert int(ork_player.command_points or 0) == 9
    assert len(list(getattr(boyz, "models", []) or [])) == 4
    assert removed_character in list(getattr(boyz, "models_lost", []) or [])


def test_come_on_ladz_requires_boyz_keyword():
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_game()
    nobz = _make_unit(
        "Nobz",
        keywords=["INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
        model_count=4,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(nobz)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, nobz, 30.0, 10.0)
    _deploy_unit(game, enemy, 40.0, 10.0)

    removed = nobz.models[0]
    nobz.remove_model(removed)
    _set_phase(game, ork_player, "COMMAND_PHASE", 0)

    blocked = ork_player.stratagems.use("COME ON LADZ!", unit=nobz, phase_name="Command phase")
    assert not blocked
    assert int(ork_player.command_points or 0) == 10


def test_come_on_ladz_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000008882005")
    assert descriptor is not None
    assert descriptor.name == "COME ON LADZ!"
    assert descriptor.effect == "return_destroyed_models"
    assert str(descriptor.effect_params.get("return_roll", "")).upper() == "D3+2"
    assert bool(descriptor.effect_params.get("exclude_character", False)) is True

    by_name = get_stratagem_tool_descriptor(name="COME ON LADZ!")
    assert by_name is not None
    assert by_name.stratagem_id == "000008882005"
