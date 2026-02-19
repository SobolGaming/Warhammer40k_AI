import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


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
                "W": "1",
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


def test_troupe_gains_battleline_and_oc_two_in_ghosts_of_the_webway():
    army = _build_aeldari_army("Ghosts of the Webway")
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


def test_troupe_not_modified_outside_ghosts_of_the_webway():
    army = _build_aeldari_army("Warhost")
    troupe = _make_unit(
        "Troupe",
        keywords=["INFANTRY", "TROUPE", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
        objective_control=1,
    )

    army.add_unit(troupe)

    assert not troupe.is_battleline
    for model in list(troupe.models or []):
        assert int(getattr(model, "_base_objective_control", 0) or 0) == 1
        assert int(getattr(model, "_objective_control", 0) or 0) == 1


def test_acrobatic_onslaught_allows_harlequins_charge_move_through_enemy_models():
    army = _build_aeldari_army("Ghosts of the Webway")
    harlequins = _make_unit(
        "Skyweavers",
        keywords=["MOUNTED", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    non_harlequins = _make_unit(
        "Guardian Defenders",
        keywords=["INFANTRY"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    army.add_unit(harlequins)
    army.add_unit(non_harlequins)

    harlequin_rules = get_validation_rules(MovementType.CHARGE, moving_unit=harlequins)
    assert bool(harlequin_rules.get("can_move_through_enemy_models"))
    assert bool(harlequin_rules.get("ignore_enemy_models_blocking"))

    non_harlequin_rules = get_validation_rules(MovementType.CHARGE, moving_unit=non_harlequins)
    assert not bool(non_harlequin_rules.get("can_move_through_enemy_models"))


def test_troupe_counts_as_battleline_for_unit_limit_validation():
    army = _build_aeldari_army("Ghosts of the Webway")
    for index in range(4):
        unit = _make_unit(
            f"Troupe {index + 1}",
            keywords=["INFANTRY", "TROUPE", "HARLEQUINS"],
            faction_keywords=["AELDARI", "HARLEQUINS"],
            objective_control=1,
        )
        unit.name = "Troupe"
        army.add_unit(unit)

    army.validate_unit_limits()


def test_travelling_players_unique_cap_override_is_three_per_named_unit():
    army = _build_aeldari_army("Ghosts of the Webway")
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
