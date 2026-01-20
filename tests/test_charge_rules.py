from warhammer40k_ai.engine.game import Game, Battlefield
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, move: str = "6", cost: int = 100, base_size: str = "32mm"):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": cost}]
        self.datasheets_models = [{
            "M": move, "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def make_unit(name: str, *, keywords=None, faction: str = "A") -> Unit:
    unit = Unit(MockDatasheet(name, keywords=keywords))
    unit.deployed = True
    unit.faction = faction
    return unit


def attach_to_game(game_map: Map, units_a, units_b):
    game = Game(Battlefield(width=60, height=44))
    game.map = game_map
    p1 = Player("P1", PlayerControl.LOCAL, None)
    p2 = Player("P2", PlayerControl.REMOTE, None)
    game.add_player(p1)
    game.add_player(p2)
    a1 = Army("Army1", "Det1")
    a2 = Army("Army2", "Det2")
    p1.set_army(a1)
    p2.set_army(a2)
    for u in units_a:
        a1.add_unit(u)
    for u in units_b:
        a2.add_unit(u)
    game_map.units = list(units_a) + list(units_b)
    return game, p1, p2


def test_cannot_declare_charge_when_engaged_with_any_enemy():
    game_map = Map(width=60, height=44)
    charger = make_unit("Charger")
    engaged = make_unit("Engaged", faction="B")
    target = make_unit("Target", faction="B")
    game, _p1, _p2 = attach_to_game(game_map, [charger], [engaged, target])

    charger.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    engaged.models[0].set_location(11.0, 10.0, 0.0, 0.0)
    target.models[0].set_location(20.0, 10.0, 0.0, 0.0)

    assert charger.can_declare_charge_against(target, game) is False


def test_charge_declare_records_multiple_targets():
    game_map = Map(width=60, height=44)
    charger = make_unit("Charger")
    t1 = make_unit("Target 1", faction="B")
    t2 = make_unit("Target 2", faction="B")
    game, _p1, _p2 = attach_to_game(game_map, [charger], [t1, t2])

    charger.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    t1.models[0].set_location(18.0, 10.0, 0.0, 0.0)
    t2.models[0].set_location(19.0, 10.0, 0.0, 0.0)

    declared = game.declare_charge(charger, [t1, t2])
    assert declared is not None
    t1_id = get_entity_id(t1)
    t2_id = get_entity_id(t2)
    charger_id = get_entity_id(charger)
    assert set(declared.get("target_unit_ids", [])) == {t1_id, t2_id}
    assert charger.round_state.charge_target_ids == {t1_id, t2_id}
    assert charger_id in game.phase_charge_targets.get(t1_id, set())
    assert charger_id in game.phase_charge_targets.get(t2_id, set())


def test_charge_end_state_blocks_non_targets():
    game_map = Map(width=60, height=44)
    charger = make_unit("Charger")
    target = make_unit("Target", faction="B")
    other = make_unit("Other", faction="B")
    game, _p1, _p2 = attach_to_game(game_map, [charger], [target, other])

    charger.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    target.models[0].set_location(11.0, 10.0, 0.0, 0.0)
    other.models[0].set_location(11.0, 11.0, 0.0, 0.0)

    assert game_map.is_within_engagement_range(charger, target) is True
    assert game_map.is_within_engagement_range(charger, other) is True

    ok, reason = charger.validate_charge_end_state([target], game_map)
    assert ok is False
    assert "non-target" in reason.lower()
