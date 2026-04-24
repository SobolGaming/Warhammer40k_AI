from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules, validate_final_position


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
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
                "W": "2",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None, model_count: int = 1) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army.with_detachment("Orks", "Green Tide")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ork_player = Player("Orks", control=PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)

    ork_player.command_points = 10
    enemy_player.command_points = 10
    ork_army.configure_rule_managers(force=True)
    ork_player.stratagems.refresh_available()
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


def test_go_get_em_horde_move_rule_overrides_aircraft_exclusion_and_allows_engagement_range() -> None:
    game, ork_player, enemy_player, ork_army, enemy_army = _build_game()
    boyz = _make_unit(
        "Boyz Mob",
        keywords=["INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=10,
    )
    aircraft = _make_unit("Enemy Aircraft", keywords=["AIRCRAFT"], faction_keywords=["ENEMY"])
    infantry = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(boyz)
    enemy_army.add_unit(aircraft)
    enemy_army.add_unit(infantry)
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, aircraft, 16.0, 10.0)
    _deploy_unit(game, infantry, 28.0, 10.0)
    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)

    boyz.activate_go_get_em_horde_move(game=game, attacker_unit=aircraft, can_reroll_distance=True)

    rule = boyz.get_horde_move_rule(game=game)
    assert rule is not None
    assert rule["source"] == "GO GET 'EM!"
    assert bool(rule["distance_reroll"]) is True
    assert tuple(rule["closest_enemy_unit_exclude_keywords"]) == ()

    reactive_rules = get_validation_rules(MovementType.HORDE_MOVE, moving_unit=boyz)
    reactive_rules["blood_surge_max_distance"] = 5.0
    assert "closest_enemy_unit_exclude_keywords" not in reactive_rules

    valid_reactive = validate_final_position(
        boyz.models[0],
        (15.0, 10.0, 0.0),
        reactive_rules,
        game.map,
    )
    assert bool(valid_reactive.get("valid", False))

    invalid_not_closer = validate_final_position(
        boyz.models[0],
        (10.0, 15.0, 0.0),
        reactive_rules,
        game.map,
    )
    assert not bool(invalid_not_closer.get("valid", False))


def test_roll_horde_move_distance_uses_go_get_em_reroll_provider() -> None:
    game, ork_player, enemy_player, ork_army, enemy_army = _build_game()
    boyz = _make_unit(
        "Boyz Mob",
        keywords=["INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=10,
    )
    attacker = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(boyz)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)

    provider_calls: list[dict] = []
    game.install_decision_providers(roll_reroll_provider=lambda **kwargs: provider_calls.append(dict(kwargs)) or True)
    boyz.activate_go_get_em_horde_move(game=game, attacker_unit=attacker, can_reroll_distance=True)

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[2, 5]):
        distance = game.roll_horde_move_distance(boyz)

    assert distance == 5
    assert provider_calls
    assert provider_calls[0]["roll_type"] == "horde_move"
    assert provider_calls[0]["allow_reroll"] is True
    assert provider_calls[0]["source"] == "GO GET 'EM!"
