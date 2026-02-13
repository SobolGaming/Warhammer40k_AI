from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
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


def create_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    ds = MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords)
    unit = Unit(ds)
    unit.deployed = True
    return unit


def make_profile(*, range_val: str, is_ranged: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Pulse Rifle" if is_ranged else "Combat Blade",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": str(range_val),
        "A": "1",
        "BS_WS": "4",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_tau_army(detachment_type: str) -> Army:
    army = Army("T'au Empire", detachment_type)
    army.faction_id = "TAU"
    army.player = SimpleNamespace(game=SimpleNamespace(turn=1))
    return army


def test_superior_craftsmanship_adds_six_inches_to_ranged_weapons():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="24", is_ranged=True)

    assert profile._effective_range_max(attacker) == 30


def test_superior_craftsmanship_does_not_modify_melee_weapons():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="2", is_ranged=False)

    assert profile._effective_range_max(attacker) == 2


def test_superior_craftsmanship_requires_experimental_prototype_cadre_detachment():
    army = _build_tau_army("Kauyon")
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="24", is_ranged=True)

    assert profile._effective_range_max(attacker) == 24


def test_superior_craftsmanship_requires_tau_empire_model_keyword():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Mercenary Squad",
        keywords=["INFANTRY"],
        faction_keywords=["KROOT"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="24", is_ranged=True)

    assert profile._effective_range_max(attacker) == 24
