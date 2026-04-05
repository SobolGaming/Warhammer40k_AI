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
        save: str = "2",
        toughness: str = "5",
    ):
        self.name = name
        self.faction_data = {"name": "Adeptus Custodes"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": str(save),
                "W": "3",
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def create_unit(
    name: str,
    x: float,
    y: float,
    *,
    keywords=None,
    faction_keywords=None,
    toughness: str = "5",
) -> Unit:
    ds = MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    unit = Unit(ds)
    for model in unit.models:
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True
    return unit


def attach_to_armies(game_map: Map, units_a, units_b):
    army_a = Army("Adeptus Custodes", "Lions of the Emperor")
    army_a.faction_id = "AC"
    army_b = Army("Enemy", "Other")
    army_b.faction_id = "ENEMY"
    game = SimpleNamespace(map=game_map, turn=1)
    army_a.player = SimpleNamespace(game=game)
    army_b.player = SimpleNamespace(game=game)
    for unit in units_a:
        army_a.add_unit(unit)
    for unit in units_b:
        army_b.add_unit(unit)
    game_map.units = list(units_a) + list(units_b)
    return army_a, army_b, game


def make_profile(*, bs: str = "4", strength: str = "4") -> WargearProfile:
    parent = SimpleNamespace(
        name="Guardian Spear",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": str(bs),
        "S": str(strength),
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def test_against_all_odds_applies_when_isolated():
    game_map = Map(width=48, height=72)
    attacker = create_unit(
        "Custodian Guard",
        10.0,
        10.0,
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    target = create_unit("Target", 20.0, 10.0, faction_keywords=["ENEMY"], toughness="4")
    attach_to_armies(game_map, [attacker], [target])

    profile = make_profile(bs="4", strength="4")
    attack_ctx = {"_aura_attack_mods": _aura_stub()}
    hit_result = profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        dict(attack_ctx),
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result["hit"] is True
    assert any("Against All Odds" in m for m in hit_result.get("modifiers", []))

    wound_result = profile._wound_target_with_tracking(
        target,
        attacker.models[0],
        dict(attack_ctx),
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result["wound"] is True
    assert any("Against All Odds" in m for m in wound_result.get("modifiers", []))


def test_against_all_odds_blocked_by_nearby_friendly_unit():
    game_map = Map(width=48, height=72)
    attacker = create_unit(
        "Custodian Guard",
        10.0,
        10.0,
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    nearby = create_unit(
        "Custodian Guard",
        14.0,
        10.0,
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    target = create_unit("Target", 20.0, 10.0, faction_keywords=["ENEMY"], toughness="4")
    attach_to_armies(game_map, [attacker, nearby], [target])

    profile = make_profile(bs="4", strength="4")
    hit_result = profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result["hit"] is False
    assert not any("Against All Odds" in m for m in hit_result.get("modifiers", []))

    wound_result = profile._wound_target_with_tracking(
        target,
        attacker.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result["wound"] is False
    assert not any("Against All Odds" in m for m in wound_result.get("modifiers", []))


def test_against_all_odds_does_not_apply_to_vehicles():
    game_map = Map(width=48, height=72)
    vehicle = create_unit(
        "Caladius Grav-tank",
        10.0,
        10.0,
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    target = create_unit("Target", 20.0, 10.0, faction_keywords=["ENEMY"], toughness="4")
    attach_to_armies(game_map, [vehicle], [target])

    profile = make_profile(bs="4", strength="4")
    hit_result = profile._hit_target_with_tracking(
        target,
        vehicle.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result["hit"] is False
    assert not any("Against All Odds" in m for m in hit_result.get("modifiers", []))
