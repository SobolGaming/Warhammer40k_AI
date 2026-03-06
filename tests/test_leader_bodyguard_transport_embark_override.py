from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


class _DummyPlayer:
    def __init__(self, name: str = "P1"):
        self.name = name
        self.id = name
        self.game = None


class _DummyDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        attached_to=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "TestFaction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = []
        self.datasheets_models_cost = []
        self.datasheets_wargear = []
        self.datasheets_options = []
        self.datasheets_abilities = []
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.transport = ""
        self.damaged_w = ""
        self.damaged_description = ""
        self.abilities_override = list(abilities or [])


class _TestUnit(Unit):
    def _parse_unit_composition(self, _data):
        return {"TestModel": 1}

    def _create_models(self, _datasheet, quantity=None):
        class _M:
            is_alive = True
            wounds = 1
            _base_wounds = 1
            name = "M"
            leadership = 7
            objective_control = 1
            movement = 6
            toughness = 4
            save = 3
            inv_save = None
            _pending_placement = False
            abilities = []
            wargear = []
            optional_wargear = []
            keywords = []
            faction_keywords = []

        n = 1 if quantity is None else int(quantity)
        return [_M() for _ in range(n)]

    def _parse_models_cost(self, _data):
        return {1: 100}

    def _parse_wargear(self, _datasheet):
        return []

    def _parse_wargear_options(self, _datasheet):
        return

    def _parse_abilities(self, datasheet):
        return list(getattr(datasheet, "abilities_override", []) or [])

    def add_wargear(self):
        return


def _make_army(units):
    army = Army(faction="Test", detachment_type="Test", points_limit=2000)
    army.player = _DummyPlayer()
    army.units = list(units)
    for unit in army.units:
        unit.parent_army = army
    return army


def _authority_of_the_inquisition() -> Ability:
    return Ability(
        "Authority of the Inquisition",
        "",
        "While this model is leading a unit, it can embark within any TRANSPORT that its Bodyguard unit can embark within.",
        "",
        "",
    )


def _make_transport() -> _TestUnit:
    transport = _TestUnit(
        _DummyDatasheet(
            "Transport",
            "TR1",
            keywords=["Transport", "Vehicle"],
            faction_keywords=["IMPERIUM"],
        )
    )
    transport.transport_capacity = 6
    return transport


def test_leading_embark_override_ignores_leader_keyword_exclusions():
    bodyguard = _TestUnit(
        _DummyDatasheet(
            "Bodyguard",
            "BG1",
            keywords=["Infantry"],
            faction_keywords=["IMPERIUM"],
        )
    )
    leader = _TestUnit(
        _DummyDatasheet(
            "Leader",
            "LD1",
            abilities=[_authority_of_the_inquisition()],
            keywords=["Character", "Infantry", "Terminator"],
            faction_keywords=["IMPERIUM"],
            attached_to=["BG1"],
        )
    )
    transport = _make_transport()
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = {"Terminator"}

    _make_army([bodyguard, leader, transport])

    assert transport.can_transport(bodyguard) is True
    leader.attach_to_unit(bodyguard)
    assert transport.can_transport(bodyguard) is True


def test_leading_embark_override_still_requires_bodyguard_transport_eligibility():
    bodyguard = _TestUnit(
        _DummyDatasheet(
            "Bodyguard",
            "BG1",
            keywords=["Infantry"],
            faction_keywords=["IMPERIUM"],
        )
    )
    leader = _TestUnit(
        _DummyDatasheet(
            "Leader",
            "LD1",
            abilities=[_authority_of_the_inquisition()],
            keywords=["Character", "Infantry", "Adeptus Astartes"],
            faction_keywords=["IMPERIUM"],
            attached_to=["BG1"],
        )
    )
    transport = _make_transport()
    transport.transport_required_keywords = {"Adeptus Astartes", "Infantry"}
    transport.transport_excluded_keywords = set()

    _make_army([bodyguard, leader, transport])

    leader.attach_to_unit(bodyguard)
    assert transport.can_transport(bodyguard) is False


def test_excluded_leader_keyword_blocks_embark_without_override():
    bodyguard = _TestUnit(
        _DummyDatasheet(
            "Bodyguard",
            "BG1",
            keywords=["Infantry"],
            faction_keywords=["IMPERIUM"],
        )
    )
    leader = _TestUnit(
        _DummyDatasheet(
            "Leader",
            "LD1",
            abilities=[
                Ability(
                    "Senior Officer",
                    "",
                    "While this model is leading a unit, ranged weapons equipped by models in that unit have the [SUSTAINED HITS 1] ability.",
                    "",
                    "",
                )
            ],
            keywords=["Character", "Infantry", "Terminator"],
            faction_keywords=["IMPERIUM"],
            attached_to=["BG1"],
        )
    )
    transport = _make_transport()
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = {"Terminator"}

    _make_army([bodyguard, leader, transport])

    assert transport.can_transport(bodyguard) is True
    leader.attach_to_unit(bodyguard)
    assert transport.can_transport(bodyguard) is False
