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
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
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
    tyr_army = Army("Tyranids", "Vanguard Onslaught")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    tyr_player.command_points = 5
    enemy_player.command_points = 5
    tyr_army.configure_rule_managers(force=True)
    tyr_player.stratagems.refresh_available()
    return game, tyr_player, enemy_player, tyr_army, enemy_army


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


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def test_invisible_hunter_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008418007")
    assert desc is not None
    assert desc.name == "Invisible Hunter"
    assert desc.effect == "enter_strategic_reserves"
    assert int(desc.cp_cost or 0) == 1


def test_invisible_hunter_queues_and_moves_two_vanguard_invader_units_to_strategic_reserves():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    vanguard_a = _make_unit(
        "Genestealers Alpha",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    vanguard_b = _make_unit(
        "Genestealers Beta",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(vanguard_a)
    tyr_army.add_unit(vanguard_b)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, vanguard_a, 10.0, 10.0)
    _deploy_unit(game, vanguard_b, 14.0, 10.0)
    _deploy_unit(game, enemy, 22.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(tyr_player.stratagems, "INVISIBLE HUNTER")
    assert pending is not None
    assert int(pending.get("max_units", 0) or 0) == 2

    ok = tyr_player.stratagems.use(
        "INVISIBLE HUNTER",
        units=[vanguard_a, vanguard_b],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 4
    assert str(getattr(vanguard_a, "reserve_status", "") or "") == "strategic_reserves"
    assert str(getattr(vanguard_b, "reserve_status", "") or "") == "strategic_reserves"
    assert vanguard_a not in list(getattr(game.map, "units", []) or [])
    assert vanguard_b not in list(getattr(game.map, "units", []) or [])


def test_invisible_hunter_rejects_mixed_vanguard_and_non_vanguard_infantry_selection():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    vanguard = _make_unit(
        "Lictors",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    infantry = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(vanguard)
    tyr_army.add_unit(infantry)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, vanguard, 10.0, 10.0)
    _deploy_unit(game, infantry, 16.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    blocked = tyr_player.stratagems.use(
        "INVISIBLE HUNTER",
        units=[vanguard, infantry],
        phase_name="Fight phase",
    )
    assert not blocked
    assert int(tyr_player.command_points or 0) == 5
    assert str(getattr(vanguard, "reserve_status", "") or "") == "deployed"
    assert str(getattr(infantry, "reserve_status", "") or "") == "deployed"
