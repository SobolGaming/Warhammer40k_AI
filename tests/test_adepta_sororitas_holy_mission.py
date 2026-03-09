from warhammer40k_ai.units.unit import Unit


HOLY_MISSION_TEXT = (
    'If this model is attached to a DOMINION SQUAD during the Declare Battle Formations step, '
    'it gains the Scouts 6" ability. '
    'If this model is attached to a SISTERS NOVITIATE SQUAD during the Declare Battle Formations step, '
    "it gains the Infiltrators ability."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Adepta Sororitas"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "3",
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
        ),
        quantity=1,
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_priest() -> Unit:
    priest = _make_unit(
        "Ministorum Priest",
        abilities=[
            {
                "name": "Holy Mission",
                "description": HOLY_MISSION_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "INFANTRY", "MINISTORUM PRIEST"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    priest.can_be_attached_to = ["Dominion Squad", "Sisters Novitiate Squad", "Battle Sisters Squad"]
    return priest


def _attach(leader: Unit, bodyguard: Unit) -> None:
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    leader._invalidate_ability_cache()
    bodyguard._invalidate_ability_cache()


def test_holy_mission_unattached_priest_has_no_scouts_or_infiltrators():
    priest = _make_priest()

    assert priest.has_infiltrate() is False
    assert priest.has_scout() == (False, 0.0)


def test_holy_mission_attached_to_dominion_grants_scouts_only():
    priest = _make_priest()
    bodyguard = _make_unit("Dominion Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    _attach(priest, bodyguard)

    assert priest.has_infiltrate() is False
    assert priest.has_scout() == (True, 6.0)


def test_holy_mission_attached_to_sisters_novitiate_grants_infiltrators_only():
    priest = _make_priest()
    bodyguard = _make_unit("Sisters Novitiate Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    _attach(priest, bodyguard)

    assert priest.has_infiltrate() is True
    assert priest.has_scout() == (False, 0.0)


def test_holy_mission_attached_to_other_bodyguard_grants_neither_bonus():
    priest = _make_priest()
    bodyguard = _make_unit("Battle Sisters Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    _attach(priest, bodyguard)

    assert priest.has_infiltrate() is False
    assert priest.has_scout() == (False, 0.0)
