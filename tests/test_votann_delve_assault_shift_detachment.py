from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "4",
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


def _build_army(detachment: str) -> Army:
    army = Army("Leagues of Votann", detachment)
    army.faction_id = "LOV"
    return army


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
    return unit


def test_fury_from_the_delve_grants_battleline_to_cthonian_beserks():
    army = _build_army("Dêlve Assault Shift")
    beserks = _make_unit(
        "Cthonian Beserks",
        keywords=["INFANTRY", "CTHONIAN BESERKS"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )

    army.add_unit(beserks)

    assert beserks.is_battleline


def test_fury_from_the_delve_grants_deep_strike_to_cthonian_beserks():
    army = _build_army("Dêlve Assault Shift")
    beserks = _make_unit(
        "Cthonian Beserks",
        keywords=["INFANTRY", "CTHONIAN BESERKS"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )

    army.add_unit(beserks)

    assert beserks.has_deep_strike()


def test_fury_from_the_delve_not_active_outside_delve_assault_shift():
    army = _build_army("Hearthband")
    beserks = _make_unit(
        "Cthonian Beserks",
        keywords=["INFANTRY", "CTHONIAN BESERKS"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )

    army.add_unit(beserks)

    assert not beserks.is_battleline
    assert not beserks.has_deep_strike()


def test_fury_from_the_delve_does_not_affect_non_beserks_units():
    army = _build_army("Dêlve Assault Shift")
    earthshakers = _make_unit(
        "Cthonian Earthshakers",
        keywords=["INFANTRY", "CTHONIAN"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )

    army.add_unit(earthshakers)

    assert not earthshakers.is_battleline
    assert not earthshakers.has_deep_strike()
