from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
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
                "M": "7",
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


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
    unit.embarked_in = None
    return unit


def _build_aeldari_army(detachment: str) -> Army:
    army = Army("Aeldari", detachment)
    army.faction_id = "AE"
    return army


def test_yriels_own_allows_aeldari_charge_after_advance():
    army = _build_aeldari_army("Eldritch Raiders")
    unit = _make_unit(
        "Aeldari Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["AELDARI"],
    )
    army.add_unit(unit)

    assert unit.can_charge_after_advance() is True


def test_yriels_own_does_not_apply_outside_eldritch_raiders():
    army = _build_aeldari_army("Warhost")
    unit = _make_unit(
        "Aeldari Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["AELDARI"],
    )
    army.add_unit(unit)

    assert unit.can_charge_after_advance() is False


def test_yriels_own_reroll_advance_applies_to_named_unit_types():
    army = _build_aeldari_army("Eldritch Raiders")
    anhrathe = _make_unit(
        "Corsairs",
        keywords=["INFANTRY", "ANHRATHE"],
        faction_keywords=["AELDARI"],
    )
    rangers = _make_unit(
        "Rangers",
        keywords=["INFANTRY", "RANGERS"],
        faction_keywords=["AELDARI"],
    )
    shroud_runners = _make_unit(
        "Shroud Runners",
        keywords=["MOUNTED", "SHROUD RUNNERS"],
        faction_keywords=["AELDARI"],
    )
    guardian = _make_unit(
        "Guardian Defenders",
        keywords=["INFANTRY"],
        faction_keywords=["AELDARI"],
    )

    army.add_unit(anhrathe)
    army.add_unit(rangers)
    army.add_unit(shroud_runners)
    army.add_unit(guardian)

    assert anhrathe.can_reroll_advance_roll() is True
    assert rangers.can_reroll_advance_roll() is True
    assert shroud_runners.can_reroll_advance_roll() is True
    assert guardian.can_reroll_advance_roll() is False


def test_yriels_own_reroll_advance_not_active_outside_eldritch_raiders():
    army = _build_aeldari_army("Warhost")
    anhrathe = _make_unit(
        "Corsairs",
        keywords=["INFANTRY", "ANHRATHE"],
        faction_keywords=["AELDARI"],
    )
    rangers = _make_unit(
        "Rangers",
        keywords=["INFANTRY", "RANGERS"],
        faction_keywords=["AELDARI"],
    )
    shroud_runners = _make_unit(
        "Shroud Runners",
        keywords=["MOUNTED", "SHROUD RUNNERS"],
        faction_keywords=["AELDARI"],
    )

    army.add_unit(anhrathe)
    army.add_unit(rangers)
    army.add_unit(shroud_runners)

    assert anhrathe.can_reroll_advance_roll() is False
    assert rangers.can_reroll_advance_roll() is False
    assert shroud_runners.can_reroll_advance_roll() is False
