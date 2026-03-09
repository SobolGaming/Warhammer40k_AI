from warhammer40k_ai.units.unit import Unit


HOLY_VANGUARD_TEXT = (
    "If this unit has a Leader unit attached to it during the Declare Battle Formations step "
    "and this unit starts the battle embarked within a TRANSPORT, that Leader unit gains the Scouts 6\" ability."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        attached_to_names=None,
        keywords=None,
        faction_keywords=None,
    ):
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
        self.attached_to = list(attached_to_names or [])
        self.attached_to_names = list(attached_to_names or [])


def _make_unit(
    name: str,
    *,
    abilities=None,
    attached_to_names=None,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            attached_to_names=attached_to_names,
            keywords=keywords,
            faction_keywords=faction_keywords,
        ),
        quantity=1,
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _prepare_holy_vanguard_pair(*, bodyguard_embarked: bool):
    bodyguard = _make_unit(
        "Dominion Squad",
        abilities=[
            {
                "name": "Holy Vanguard",
                "description": HOLY_VANGUARD_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    leader = _make_unit(
        "Canoness",
        attached_to_names=["Dominion Squad"],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    if not list(getattr(leader, "can_be_attached_to", []) or []):
        leader.can_be_attached_to = ["Dominion Squad"]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    if bodyguard_embarked:
        bodyguard.embarked_in = object()
    leader._apply_attached_unit_bodyguard_leader_scouts(bodyguard)
    return leader


def test_holy_vanguard_does_not_grant_scouts_when_bodyguard_not_embarked():
    leader = _prepare_holy_vanguard_pair(bodyguard_embarked=False)
    has_scout, scout_distance = leader.has_scout()
    assert has_scout is False
    assert float(scout_distance) == 0.0


def test_holy_vanguard_grants_scouts_when_bodyguard_is_embarked():
    leader = _prepare_holy_vanguard_pair(bodyguard_embarked=True)
    has_scout, scout_distance = leader.has_scout()
    assert has_scout is True
    assert float(scout_distance) == 6.0
