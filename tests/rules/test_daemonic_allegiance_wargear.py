import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, ability_desc: str):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "6",
                "Sv": "3",
                "W": "10",
                "Ld": "7",
                "OC": "3",
                "base_size": "90mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = [
            {
                "name": "Torrent of burning blood",
                "type": "Ranged",
                "range": "12",
                "A": "D6",
                "BS_WS": "3+",
                "S": "6",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            {
                "name": "Warp gaze",
                "type": "Ranged",
                "range": "24",
                "A": "2",
                "BS_WS": "3+",
                "S": "8",
                "AP": "-2",
                "D": "D3",
                "description": "",
            },
            {
                "name": "Phlegm bombardment",
                "type": "Ranged",
                "range": "36",
                "A": "D6",
                "BS_WS": "3+",
                "S": "9",
                "AP": "-2",
                "D": "D3",
                "description": "",
            },
            {
                "name": "Scream of despair",
                "type": "Ranged",
                "range": "18",
                "A": "3",
                "BS_WS": "3+",
                "S": "7",
                "AP": "-1",
                "D": "2",
                "description": "",
            },
        ]
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": "Daemonic Allegiance",
                "description": ability_desc,
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit():
    ability_desc = (
        "When you select this model to include in your army, you must select one of the keywords below. "
        "Until the end of the battle, this model has that keyword and the additional wargear stated for that keyword below: "
        "KHORNE - This model is additionally equipped with: torrent of burning blood "
        "TZEENTCH - This model is additionally equipped with: warp gaze "
        "NURGLE - This model is additionally equipped with: phlegm bombardment "
        "SLAANESH - This model is additionally equipped with: scream of despair"
    )
    datasheet = _MockDatasheet("Soul Grinder", ability_desc=ability_desc)
    return Unit(datasheet)


def test_daemonic_allegiance_parses_options():
    unit = _make_unit()
    options = unit.get_daemonic_allegiance_options()
    assert options == [
        ("KHORNE", "Torrent of burning blood"),
        ("TZEENTCH", "Warp gaze"),
        ("NURGLE", "Phlegm bombardment"),
        ("SLAANESH", "Scream of despair"),
    ]


def test_daemonic_allegiance_applies_keyword_and_wargear():
    unit = _make_unit()
    unit.daemonic_allegiance = "KHORNE"
    applied = unit.apply_daemonic_allegiance_selection()
    assert applied is True
    assert "KHORNE" in unit.keywords
    assert any(wg.name == "Torrent of burning blood" for wg in unit.models[0].wargear)


def test_daemonic_allegiance_invalidates_cached_wargear_rule_answers():
    ability_desc = (
        "When you select this model to include in your army, you must select one of the keywords below. "
        "Until the end of the battle, this model has that keyword and the additional wargear stated for that keyword below: "
        "KHORNE - This model is additionally equipped with: brass standard "
        "TZEENTCH - This model is additionally equipped with: changeling sigil "
        "NURGLE - This model is additionally equipped with: rot icon "
        "SLAANESH - This model is additionally equipped with: swift icon"
    )
    datasheet = _MockDatasheet("Soul Grinder", ability_desc=ability_desc)
    datasheet.datasheets_unit_composition = [{"description": "2 Test Models"}]
    datasheet.datasheets_models_cost = [{"description": "2 models", "cost": 100}]
    datasheet.datasheets_abilities.append(
        {
            "name": "Swift Icon",
            "description": 'The bearer has a Move characteristic of 12".',
            "type": "Wargear",
            "parameter": "",
        }
    )
    unit = Unit(datasheet)
    model = unit.models[0]

    assert unit.get_model_move_characteristic_override(model) == (None, None)

    unit.daemonic_allegiance = "SLAANESH"
    assert unit.apply_daemonic_allegiance_selection() is True

    assert unit.get_model_move_characteristic_override(model) == (12, "Swift Icon")


def test_daemonic_allegiance_requires_selection():
    unit = _make_unit()
    army = Army.with_detachment("Chaos Daemons", "Daemonic Incursion", points_limit=2000)
    army.faction_id = "CD"
    army.add_unit(unit)
    with pytest.raises(ArmyValidationError):
        army.validate_daemonic_allegiances()
