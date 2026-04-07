from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, abilities=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Grey Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _deep_strike_ability() -> dict:
    return {
        "name": "Deep Strike",
        "description": "Deep Strike",
        "type": "Core",
        "parameter": "",
    }


def _make_unit(name: str, *, keywords=None, faction_keywords=None, abilities=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army_gk = Army.with_detachment("Grey Knights", "Augurium Task Force")
    army_gk.faction_id = "GK"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("GK", control=PlayerControl.LOCAL, army=army_gk)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 5
    p2.command_points = 5
    army_gk.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, army_gk, army_enemy


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def test_augurium_stratagem_descriptors_registered():
    redirected = get_stratagem_tool_descriptor(stratagem_id="000010365006")
    assert redirected is not None
    assert redirected.name == "Redirected Strike"
    assert redirected.effect == "enter_strategic_reserves_if_deep_strike"

    mirage = get_stratagem_tool_descriptor(stratagem_id="000010365007")
    assert mirage is not None
    assert mirage.name == "Mirage of Echoes"
    assert float(mirage.range_in or 0.0) == 12.0


def test_redirected_strike_queues_at_command_phase_end_and_enters_strategic_reserves():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    psyker = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        abilities=[_deep_strike_ability()],
    )
    army_gk.add_unit(psyker)
    _deploy_unit(game, psyker, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "COMMAND_PHASE", 0)
    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="COMMAND_PHASE"))
    pending = _pending_by_name(p1.stratagems, "REDIRECTED STRIKE")
    assert pending is not None

    ok = p1.stratagems.use(
        "REDIRECTED STRIKE",
        unit=psyker,
        phase_name="Command phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4
    assert str(getattr(psyker, "reserve_status", "") or "") == "strategic_reserves"
    assert psyker not in list(getattr(game.map, "units", []) or [])


def test_mirage_of_echoes_queues_on_enemy_reinforcement_setup_and_enters_strategic_reserves():
    game, p1, p2, army_gk, army_enemy = _build_game()
    psyker = _make_unit(
        "Purifier Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        abilities=[_deep_strike_ability()],
    )
    enemy = _make_unit(
        "Enemy Reinforcements",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_gk.add_unit(psyker)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, psyker, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_set_up", unit=enemy, set_up_as_reinforcements=True)
    pending = _pending_by_name(p1.stratagems, "MIRAGE OF ECHOES")
    assert pending is not None

    ok = p1.stratagems.use(
        "MIRAGE OF ECHOES",
        unit=psyker,
        enemy_unit=enemy,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4
    assert str(getattr(psyker, "reserve_status", "") or "") == "strategic_reserves"
    assert psyker not in list(getattr(game.map, "units", []) or [])
