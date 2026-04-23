from __future__ import annotations

from collections import Counter

from warhammer40k_ai.roster.army import parse_army_list_text
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper import WahaHelper


def test_configure_models_preserves_required_later_composition_rows() -> None:
    waha = WahaHelper(data_dir="wahapedia_data")
    datasheet = waha.get_full_datasheet_info_by_name("Crusader Squad", faction_id="SM")
    unit = Unit(datasheet)

    unit.configure_models(10, [])

    assert Counter(model.name for model in unit.models) == {
        "Sword Brother": 1,
        "Initiate": 5,
        "Neophyte": 4,
    }


def test_army_parser_maps_singular_model_headings_to_runtime_model_names() -> None:
    roster = """Black Templars Test (150 Points)

Black Templars
Wrathful Procession
Strike Force (150 Points)

BATTLELINE

Crusader Squad (150 Points)
  • 1x Sword Brother
     ◦ 1x Heavy bolt pistol
     ◦ 1x Master-crafted power weapon
  • 5x Initiate
     ◦ 5x Bolt pistol
     ◦ 5x Bolt rifle
     ◦ 5x Close combat weapon
  • 4x Neophyte
     ◦ 4x Astartes chainsword
     ◦ 4x Bolt pistol

Exported with app version: Warhammer40k_AI Roster Synthesizer
"""
    army = parse_army_list_text(roster, WahaHelper(data_dir="wahapedia_data"), list_name="bt_crusader")

    [unit] = army.units
    assert unit.name == "Crusader Squad"
    assert Counter(model.name for model in unit.models) == {
        "Sword Brother": 1,
        "Initiate": 5,
        "Neophyte": 4,
    }
    assert army.get_total_points() == 150
