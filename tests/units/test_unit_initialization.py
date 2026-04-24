import pytest

from warhammer40k_ai.units.unit import Unit, UnitInitializationError


class _MalformedCompositionDatasheet:
    name = "Malformed Unit"
    faction_data = {"name": "Test Faction"}
    keywords = []
    faction_keywords = []
    datasheets_unit_composition = [object()]
    datasheets_models_cost = []
    datasheets_models = []
    datasheets_wargear = []
    datasheets_options = []
    datasheets_abilities = []
    loadout = ""


def test_malformed_unit_composition_raises_initialization_error():
    with pytest.raises(UnitInitializationError, match="Failed to parse unit composition"):
        Unit(_MalformedCompositionDatasheet())
