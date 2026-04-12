from __future__ import annotations

import pytest

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


@pytest.mark.parametrize(
    "faction_id,datasheet_id,expected_abilities",
    [
        ("CSM", "000000969", {"Deadly Demise", "Dark Pacts", "Scuttling Walker", "Daemonforge"}),
        ("TS", "000001030", {"Deadly Demise", "Feel No Pain", "Scuttling Walker", "Destroyer of Futures"}),
    ],
)
def test_current_defiler_datasheets_match_latest_json(faction_id: str, datasheet_id: str, expected_abilities: set[str]) -> None:
    datasheet = _WAHA.get_datasheet("Defiler", datasheet_id=datasheet_id, faction_id=faction_id)
    assert datasheet is not None

    unit = Unit(datasheet)
    model = unit.models[0]

    assert int(model.movement or 0) == 12
    assert int(model.toughness or 0) == 11
    assert int(model.wounds or 0) == 18
    assert int(model.leadership or 0) == 6
    assert int(model.objective_control or 0) == 5
    assert int(model.save or 0) == 3
    assert int((model.inv_save or (0, ""))[0] or 0) == 5

    wargear_names = [str(getattr(wargear, "name", "") or "") for wargear in list(getattr(model, "wargear", []) or [])]
    assert wargear_names == [
        "Hades battle cannon",
        "Excruciator cannon",
        "Excruciator cannon",
        "Heavy missile launcher",
        "Heavy baleflamer",
        "Shearing claws",
    ]

    ability_names = {str(getattr(ability, "name", "") or "") for ability in list(getattr(unit, "possible_abilities", []) or [])}
    assert expected_abilities.issubset(ability_names)

    has_deadly_demise, damage_dice = unit.has_deadly_demise()
    assert has_deadly_demise is True
    assert damage_dice is not None
    assert int(getattr(damage_dice, "number", 0) or 0) == 1
    assert int(getattr(damage_dice, "die_faces", 0) or 0) == 6
