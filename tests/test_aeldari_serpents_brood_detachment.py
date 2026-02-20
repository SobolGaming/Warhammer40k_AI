import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
        abilities=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "3",
                "Sv": "4",
                "W": "2",
                "Ld": "6",
                "OC": str(int(objective_control)),
                "base_size": "25mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    objective_control: int = 1,
    with_unique_model_rule: bool = False,
) -> Unit:
    abilities = []
    if with_unique_model_rule:
        abilities.append(
            {
                "name": "Travelling Players",
                "description": "Unless otherwise stated, you cannot include more than one of this model in your army.",
                "type": "Datasheet",
                "parameter": "",
            }
        )
    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        objective_control=objective_control,
        abilities=abilities,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_aeldari_army(detachment: str) -> Army:
    army = Army("Aeldari", detachment)
    army.faction_id = "AE"
    return army


def _make_profile(*, name: str, weapon_type: str):
    weapon = Wargear(
        {
            "name": name,
            "type": weapon_type,
            "range": "24" if str(weapon_type).strip().lower() == "ranged" else "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def test_troupe_gains_battleline_and_oc_two_in_serpents_brood():
    army = _build_aeldari_army("Serpent's Brood")
    troupe = _make_unit(
        "Troupe",
        keywords=["INFANTRY", "TROUPE", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
        objective_control=1,
    )

    army.add_unit(troupe)

    assert troupe.is_battleline
    for model in list(troupe.models or []):
        assert int(getattr(model, "_base_objective_control", 0) or 0) == 2
        assert int(getattr(model, "_objective_control", 0) or 0) == 2


def test_travelling_players_unique_cap_override_is_three_per_named_unit_in_serpents_brood():
    army = _build_aeldari_army("Serpent's Brood")
    for _ in range(3):
        army.add_unit(
            _make_unit(
                "Death Jester",
                keywords=["INFANTRY", "CHARACTER", "HARLEQUINS"],
                faction_keywords=["AELDARI", "HARLEQUINS"],
                with_unique_model_rule=True,
            )
        )
    army.validate_unique_model_restrictions()

    army.add_unit(
        _make_unit(
            "Death Jester",
            keywords=["INFANTRY", "CHARACTER", "HARLEQUINS"],
            faction_keywords=["AELDARI", "HARLEQUINS"],
            with_unique_model_rule=True,
        )
    )
    with pytest.raises(ArmyValidationError):
        army.validate_unique_model_restrictions()


def test_boons_grants_sustained_hits_to_harlequins_mounted_and_vehicle_models():
    army = _build_aeldari_army("Serpent's Brood")
    mounted = _make_unit(
        "Skyweavers",
        keywords=["MOUNTED", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    vehicle = _make_unit(
        "Voidweaver",
        keywords=["VEHICLE", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    non_harlequins = _make_unit(
        "Shining Spears",
        keywords=["MOUNTED"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    army.add_unit(mounted)
    army.add_unit(vehicle)
    army.add_unit(non_harlequins)

    mounted_bonus = mounted.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=mounted.models[0],
        weapon_profile=_make_profile(name="Shuriken cannon", weapon_type="Ranged"),
        weapon_name="Shuriken cannon",
    )
    vehicle_bonus = vehicle.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=vehicle.models[0],
        weapon_profile=_make_profile(name="Prismatic cannon", weapon_type="Ranged"),
        weapon_name="Prismatic cannon",
    )
    non_harlequins_bonus = non_harlequins.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=non_harlequins.models[0],
        weapon_profile=_make_profile(name="Shuriken catapult", weapon_type="Ranged"),
        weapon_name="Shuriken catapult",
    )

    assert int(mounted_bonus.get("sustained_hits_value", 0) or 0) == 1
    assert int(vehicle_bonus.get("sustained_hits_value", 0) or 0) == 1
    assert int(non_harlequins_bonus.get("sustained_hits_value", 0) or 0) == 0


def test_boons_grants_sustained_hits_to_harlequins_unit_that_disembarked():
    army = _build_aeldari_army("Serpent's Brood")
    troupe = _make_unit(
        "Troupe",
        keywords=["INFANTRY", "HARLEQUINS", "TROUPE"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    army.add_unit(troupe)

    troupe.round_state.disembarked_this_round = True
    active_bonus = troupe.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=troupe.models[0],
        weapon_profile=_make_profile(name="Harlequin blade", weapon_type="Melee"),
        weapon_name="Harlequin blade",
    )
    assert int(active_bonus.get("sustained_hits_value", 0) or 0) == 1

    troupe.round_state.disembarked_this_round = False
    inactive_bonus = troupe.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=troupe.models[0],
        weapon_profile=_make_profile(name="Harlequin blade", weapon_type="Melee"),
        weapon_name="Harlequin blade",
    )
    assert int(inactive_bonus.get("sustained_hits_value", 0) or 0) == 0


def test_boons_does_not_apply_outside_serpents_brood():
    army = _build_aeldari_army("Warhost")
    mounted = _make_unit(
        "Skyweavers",
        keywords=["MOUNTED", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    army.add_unit(mounted)

    mounted.round_state.disembarked_this_round = True
    bonus = mounted.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=mounted.models[0],
        weapon_profile=_make_profile(name="Shuriken cannon", weapon_type="Ranged"),
        weapon_name="Shuriken cannon",
    )

    assert int(bonus.get("sustained_hits_value", 0) or 0) == 0
