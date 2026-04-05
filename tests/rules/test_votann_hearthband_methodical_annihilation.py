import pytest
from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        save: str = "4",
    ):
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": str(save),
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


def create_unit(name: str, x: float, y: float, *, keywords=None, faction_keywords=None) -> Unit:
    ds = MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords)
    unit = Unit(ds)
    for m in unit.models:
        m.set_location(x, y, 0.0, 0.0)
    unit.deployed = True
    return unit


def attach_to_armies(game_map: Map, units_a, units_b):
    army_a = Army("Army A", "Hearthband")
    army_a.faction_id = "LOV"
    army_b = Army("Army B", "Other")
    army_b.faction_id = "ENEMY"
    game = SimpleNamespace(map=game_map, turn=1)
    army_a.player = SimpleNamespace(game=game)
    army_b.player = SimpleNamespace(game=game)
    for u in units_a:
        army_a.add_unit(u)
    for u in units_b:
        army_b.add_unit(u)
    game_map.units = units_a + units_b
    return army_a, army_b, game


def make_ranged_profile(*, ap: str = "0") -> WargearProfile:
    parent = SimpleNamespace(
        name="Ion Blaster",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "3",
        "S": "4",
        "AP": str(ap),
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def test_methodical_annihilation_reroll_wound_ones_when_closest(monkeypatch):
    import warhammer40k_ai.units.wargear as wargear_mod

    game_map = Map(width=48, height=72)
    attacker = create_unit(
        "Hearthkyn Warriors",
        10.0,
        10.0,
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    target_close = create_unit("Target A", 20.0, 10.0)
    target_far = create_unit("Target B", 30.0, 10.0)
    attach_to_armies(game_map, [attacker], [target_close, target_far])

    profile = make_ranged_profile()

    # Force reroll to a 4 after rolling a 1.
    monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 4)
    attack_instance = {}
    wound_result = profile._wound_target_with_tracking(
        target_close,
        attacker.models[0],
        attack_instance,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )

    assert wound_result.get("reroll_of_one") == 1
    assert wound_result.get("roll") == 4
    assert any("Methodical Annihilation" in m for m in wound_result.get("special_effects", []))

    attack_instance = {}
    wound_result_far = profile._wound_target_with_tracking(
        target_far,
        attacker.models[0],
        attack_instance,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )

    assert wound_result_far.get("reroll_of_one") is None
    assert wound_result_far.get("roll") == 1


def test_methodical_annihilation_ap_bonus_for_kahl():
    game_map = Map(width=48, height=72)
    attacker = create_unit(
        "Kahl",
        10.0,
        10.0,
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    target = create_unit("Target", 20.0, 10.0)
    attach_to_armies(game_map, [attacker], [target])

    profile = make_ranged_profile(ap="0")
    ap_val = profile.get_effective_ap(attacker.models[0], target)
    assert ap_val == -1


def test_methodical_annihilation_ap_bonus_ignores_keywords_only():
    game_map = Map(width=48, height=72)
    attacker = create_unit(
        "Hearthkyn Warriors",
        10.0,
        10.0,
        keywords=["Kahl"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    target = create_unit("Target", 20.0, 10.0)
    attach_to_armies(game_map, [attacker], [target])

    profile = make_ranged_profile(ap="0")
    ap_val = profile.get_effective_ap(attacker.models[0], target)
    assert ap_val == 0


def test_methodical_annihilation_no_ap_bonus_for_other_units():
    game_map = Map(width=48, height=72)
    attacker = create_unit(
        "Hearthkyn Warriors",
        10.0,
        10.0,
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    target = create_unit("Target", 20.0, 10.0)
    attach_to_armies(game_map, [attacker], [target])

    profile = make_ranged_profile(ap="0")
    ap_val = profile.get_effective_ap(attacker.models[0], target)
    assert ap_val == 0
