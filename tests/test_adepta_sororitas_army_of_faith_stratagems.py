from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Adepta Sororitas"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army_as = Army("Adepta Sororitas", "Army of Faith")
    army_as.faction_id = "AS"
    army_enemy = Army("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("AS", control=PlayerControl.LOCAL, army=army_as)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 5
    p2.command_points = 5
    army_as.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, army_as, army_enemy


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


def test_angelic_descent_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000009038007")
    assert desc is not None
    assert desc.name == "Angelic Descent"
    assert desc.effect == "enter_strategic_reserves"
    assert int(desc.cp_cost or 0) == 1


def test_angelic_descent_queues_at_opponent_fight_phase_end_and_enters_strategic_reserves():
    game, p1, p2, army_as, army_enemy = _build_game()
    seraphim = _make_unit(
        "Seraphim Squad",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_as.add_unit(seraphim)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, seraphim, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(p1.stratagems, "ANGELIC DESCENT")
    assert pending is not None

    ok = p1.stratagems.use(
        "ANGELIC DESCENT",
        unit=seraphim,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4
    assert str(getattr(seraphim, "reserve_status", "") or "") == "strategic_reserves"
    assert seraphim not in list(getattr(game.map, "units", []) or [])
