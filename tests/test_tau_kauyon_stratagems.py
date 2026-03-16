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
        self.faction_data = {"name": "T'au Empire"}
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
    army_tau = Army("T'au Empire", "Kauyon")
    army_tau.faction_id = "TAU"
    army_enemy = Army("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("Tau", control=PlayerControl.LOCAL, army=army_tau)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 5
    p2.command_points = 5
    army_tau.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, army_tau, army_enemy


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


def test_wall_of_mirrors_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008443007")
    assert desc is not None
    assert desc.name == "Wall of Mirrors"
    assert desc.effect == "enter_strategic_reserves"
    assert int(desc.cp_cost or 0) == 1


def test_point_blank_ambush_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008443003")
    assert desc is not None
    assert desc.name == "Point-Blank Ambush"
    assert desc.effect == "conditional_ranged_ap_bonus_within_range"
    assert int(desc.cp_cost or 0) == 1
    assert float(desc.range_in or 0) == 9.0


def test_wall_of_mirrors_queues_at_opponent_fight_phase_end_and_enters_strategic_reserves():
    game, p1, p2, army_tau, army_enemy = _build_game()
    stealth = _make_unit(
        "Stealth Battlesuits",
        keywords=["INFANTRY", "STEALTH"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_tau.add_unit(stealth)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, stealth, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(p1.stratagems, "WALL OF MIRRORS")
    assert pending is not None

    ok = p1.stratagems.use(
        "WALL OF MIRRORS",
        unit=stealth,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4
    assert str(getattr(stealth, "reserve_status", "") or "") == "strategic_reserves"
    assert stealth not in list(getattr(game.map, "units", []) or [])


def test_point_blank_ambush_grants_ap_within_9_in_battle_round_3():
    from warhammer40k_ai.units.wargear import WargearProfile

    game, p1, _p2, army_tau, army_enemy = _build_game()
    game.turn = 3
    breachers = _make_unit(
        "Breacher Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    close_enemy = _make_unit(
        "Close Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    far_enemy = _make_unit(
        "Far Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_tau.add_unit(breachers)
    army_enemy.add_unit(close_enemy)
    army_enemy.add_unit(far_enemy)
    for unit, x, y in (
        (breachers, 0.0, 0.0),
        (close_enemy, 8.0, 0.0),
        (far_enemy, 15.0, 0.0),
    ):
        for model in list(getattr(unit, "models", []) or []):
            model.set_location(float(x), float(y), 0.0, 0.0)
    game.map.units = [breachers, close_enemy, far_enemy]
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    ok = p1.stratagems.use("POINT-BLANK AMBUSH", unit=breachers, phase_name="Shooting phase")
    assert ok
    assert int(p1.command_points or 0) == 4

    parent = SimpleNamespace(name="Pulse Blaster", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "10",
            "A": "1",
            "BS_WS": "3+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )

    assert profile.get_effective_ap(breachers.models[0], close_enemy) == -1
    assert profile.get_effective_ap(breachers.models[0], far_enemy) == 0


def test_point_blank_ambush_rejected_in_battle_round_2():
    game, p1, _p2, army_tau, army_enemy = _build_game()
    game.turn = 2
    breachers = _make_unit(
        "Breacher Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_tau.add_unit(breachers)
    army_enemy.add_unit(enemy)
    for unit, x, y in ((breachers, 0.0, 0.0), (enemy, 8.0, 0.0)):
        for model in list(getattr(unit, "models", []) or []):
            model.set_location(float(x), float(y), 0.0, 0.0)
    game.map.units = [breachers, enemy]
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    before_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use("POINT-BLANK AMBUSH", unit=breachers, phase_name="Shooting phase")
    assert not ok
    assert int(p1.command_points or 0) == before_cp
