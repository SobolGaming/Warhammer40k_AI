from types import SimpleNamespace

from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.classes.model import Model
from warhammer40k_ai.classes.wargear import WargearProfile
from warhammer40k_ai.utility.model_base import Base, BaseType


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "2",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def build_model(name: str, toughness: int) -> Model:
    return Model(
        name=name,
        movement=6,
        toughness=toughness,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )


def make_kill_team_unit(name: str, model_stats, *, keywords=None):
    abilities = [{"name": "Kill Team", "description": "", "type": "", "parameter": ""}]
    datasheet = MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        abilities=abilities,
    )
    unit = Unit(datasheet)
    models = []
    for model_name, toughness in model_stats:
        model = build_model(model_name, toughness)
        model.parent_unit = unit
        models.append(model)
    unit.models = models
    return unit


def test_kill_team_majority_toughness_tie_uses_highest_and_attack_override():
    target = make_kill_team_unit(
        "Kill Team Target",
        [
            ("Kill Team Veteran", 4),
            ("Kill Team Veteran", 4),
            ("Kill Team Biker", 5),
            ("Kill Team Biker", 5),
        ],
    )
    assert target.get_kill_team_majority_toughness() == 5

    attacker_ds = MockDatasheet("Attacker", faction_keywords=["IMPERIUM"])
    attacker_unit = Unit(attacker_ds)
    attacker_model = build_model("Attacker", 4)
    attacker_model.parent_unit = attacker_unit

    parent_wargear = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent_wargear,
    )

    from warhammer40k_ai.classes import wargear as wargear_mod
    old_get_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _s: 6
    try:
        result = profile.attack(target, attacker_model)
    finally:
        wargear_mod.get_roll = old_get_roll

    assert result.wound_results
    assert result.wound_results[0]["target_toughness"] == 5


def test_kill_team_attached_leader_included_in_majority():
    target = make_kill_team_unit(
        "Kill Team Target",
        [
            ("Kill Team Veteran", 4),
            ("Kill Team Veteran", 5),
        ],
    )
    leader_ds = MockDatasheet("Leader", keywords=["Character"], faction_keywords=["IMPERIUM"])
    leader = Unit(leader_ds)
    leader_model = build_model("Leader", 6)
    leader_model.parent_unit = leader
    leader.models = [leader_model]
    leader.attached_to = target
    target.attached_leaders = [leader]

    assert target.get_kill_team_majority_toughness() == 6


def test_kill_team_transport_slots_double():
    target = make_kill_team_unit(
        "Kill Team Transport",
        [
            ("Kill Team Terminator", 4),
            ("Kill Team Biker", 4),
            ("Kill Team Veteran", 4),
        ],
    )
    assert target.get_transport_slots_required() == 5


def test_kill_team_counts_as_infantry_for_terrain():
    target = make_kill_team_unit(
        "Kill Team Terrain",
        [("Kill Team Veteran", 4)],
        keywords=["Mounted"],
    )
    assert target.counts_as_infantry_for_terrain() is True
    assert target.can_move_through_ruins_walls() is True
