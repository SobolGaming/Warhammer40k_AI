from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


EMANATUS_FORCE_FIELD_TEXT = (
    "While a friendly ADEPTUS MECHANICUS BATTLELINE model is wholly within 6\" of this model, "
    "that BATTLELINE model has a 4+ invulnerable save against ranged attacks."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
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
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_admech_army() -> Army:
    army = Army("Adeptus Mechanicus", detachment_type="Other")
    army.faction_id = "ADM"
    return army


def _build_enemy_army() -> Army:
    army = Army("Enemy", detachment_type="Other")
    army.faction_id = "EN"
    return army


def _make_profile(*, range_val: str, is_ranged: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Gun" if is_ranged else "Test Blade",
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


def _emanatus_force_field_ability():
    return {
        "name": "Emanatus Force Field (Aura)",
        "description": EMANATUS_FORCE_FIELD_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }


def test_emanatus_force_field_grants_invulnerable_save_to_battleline_wholly_within_range():
    admech_army = _build_admech_army()
    source = _make_unit(
        "Onager Dunecrawler",
        abilities=[_emanatus_force_field_ability()],
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(source)
    admech_army.add_unit(target)

    enemy_army = _build_enemy_army()
    enemy = _make_unit("Enemy Squad", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_army.add_unit(enemy)

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(2.0, 0.0, 0.0, 0.0)

    profile = _make_profile(range_val="24", is_ranged=True)
    save_result = profile._save_with_tracking(
        target.models[0],
        {"attacker_model": enemy.models[0], "target_unit": target},
        ap=-3,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert save_result.get("save_type") == "invulnerable"
    assert int(save_result.get("final_save", 0) or 0) == 4
    assert any("Emanatus Force Field" in str(entry) for entry in save_result.get("special_effects", []))


def test_emanatus_force_field_does_not_apply_when_target_is_not_wholly_within_range():
    admech_army = _build_admech_army()
    source = _make_unit(
        "Onager Dunecrawler",
        abilities=[_emanatus_force_field_ability()],
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(source)
    admech_army.add_unit(target)

    enemy_army = _build_enemy_army()
    enemy = _make_unit("Enemy Squad", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_army.add_unit(enemy)

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(10.0, 0.0, 0.0, 0.0)

    profile = _make_profile(range_val="24", is_ranged=True)
    save_result = profile._save_with_tracking(
        target.models[0],
        {"attacker_model": enemy.models[0], "target_unit": target},
        ap=-3,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert save_result.get("save_type") != "invulnerable"
    assert int(save_result.get("final_save", 0) or 0) == 7


def test_emanatus_force_field_does_not_apply_against_melee_attacks():
    admech_army = _build_admech_army()
    source = _make_unit(
        "Onager Dunecrawler",
        abilities=[_emanatus_force_field_ability()],
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(source)
    admech_army.add_unit(target)

    enemy_army = _build_enemy_army()
    enemy = _make_unit("Enemy Squad", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_army.add_unit(enemy)

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(2.0, 0.0, 0.0, 0.0)

    profile = _make_profile(range_val="2", is_ranged=False)
    save_result = profile._save_with_tracking(
        target.models[0],
        {"attacker_model": enemy.models[0], "target_unit": target},
        ap=-3,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert save_result.get("save_type") != "invulnerable"
    assert int(save_result.get("final_save", 0) or 0) == 7
