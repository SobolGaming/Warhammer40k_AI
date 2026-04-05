from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "4",
                "Sv": "5",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "28mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
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
    return Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))


def _build_army(detachment: str) -> Army:
    army = Army("Tyranids", detachment)
    army.faction_id = "TYR"
    return army


def test_questing_tendrils_charge_eligibility_vanguard_onslaught():
    army = _build_army("Vanguard Onslaught")
    vanguard_invader = _make_unit(
        "Genestealers",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    non_vanguard = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )

    army.add_unit(vanguard_invader)
    army.add_unit(non_vanguard)

    assert vanguard_invader.can_charge_after_fall_back()
    assert non_vanguard.can_charge_after_fall_back()
    assert vanguard_invader.can_charge_after_advance()
    assert not non_vanguard.can_charge_after_advance()


def test_questing_tendrils_not_active_outside_vanguard_onslaught():
    army = _build_army("Invasion Fleet")
    vanguard_invader = _make_unit(
        "Genestealers",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    non_vanguard = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )

    army.add_unit(vanguard_invader)
    army.add_unit(non_vanguard)

    assert not vanguard_invader.can_charge_after_fall_back()
    assert not non_vanguard.can_charge_after_fall_back()
    assert not vanguard_invader.can_charge_after_advance()
    assert not non_vanguard.can_charge_after_advance()
