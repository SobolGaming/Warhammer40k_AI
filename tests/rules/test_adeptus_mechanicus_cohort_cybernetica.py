from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Adeptus Mechanicus"}
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
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def test_cyber_psalm_programming_grants_legio_cybernetica_move_and_oc():
    army = Army("Adeptus Mechanicus", detachment_type="Cohort Cybernetica")
    army.faction_id = "ADM"
    legio_unit = _make_unit(
        "Kastelan Robots",
        keywords=["LEGIO CYBERNETICA", "VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army.add_unit(legio_unit)

    model = legio_unit.models[0]
    assert legio_unit.get_effective_model_characteristic(model, "movement") == 8
    assert legio_unit.get_effective_model_characteristic(model, "objective_control") == 2


def test_cyber_psalm_programming_does_not_apply_to_non_legio_units():
    army = Army("Adeptus Mechanicus", detachment_type="Cohort Cybernetica")
    army.faction_id = "ADM"
    skitarii = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army.add_unit(skitarii)

    model = skitarii.models[0]
    assert skitarii.get_effective_model_characteristic(model, "movement") == 6
    assert skitarii.get_effective_model_characteristic(model, "objective_control") == 1


def test_cyber_psalm_programming_oc_bonus_is_disabled_while_battle_shocked():
    army = Army("Adeptus Mechanicus", detachment_type="Cohort Cybernetica")
    army.faction_id = "ADM"
    legio_unit = _make_unit(
        "Kastelan Robots",
        keywords=["LEGIO CYBERNETICA", "VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army.add_unit(legio_unit)
    model = legio_unit.models[0]

    mgr = army.adeptus_mechanicus_detachments
    assert mgr is not None
    bonus, source = mgr.cyber_psalm_programming_objective_control_bonus(model, unit=legio_unit)
    assert bonus == 1
    assert source == "Cyber-Psalm Programming"

    legio_unit.status_effects = [BattleShockEffect(current_turn=1)]
    bonus_bs, _source_bs = mgr.cyber_psalm_programming_objective_control_bonus(model, unit=legio_unit)
    assert bonus_bs == 0
    assert legio_unit.get_effective_model_characteristic(model, "movement") == 8


def test_cyber_psalm_programming_uses_attached_root_for_leader_models():
    army = Army("Adeptus Mechanicus", detachment_type="Cohort Cybernetica")
    army.faction_id = "ADM"
    legio_bodyguard = _make_unit(
        "Kastelan Robots",
        keywords=["LEGIO CYBERNETICA", "VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    tech_priest = _make_unit(
        "Tech-priest Dominus",
        keywords=["INFANTRY", "CHARACTER", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army.add_unit(legio_bodyguard)
    army.add_unit(tech_priest)
    _attach_leader(legio_bodyguard, tech_priest)

    leader_model = tech_priest.models[0]
    assert tech_priest.get_effective_model_characteristic(leader_model, "movement") == 8
    assert tech_priest.get_effective_model_characteristic(leader_model, "objective_control") == 2
