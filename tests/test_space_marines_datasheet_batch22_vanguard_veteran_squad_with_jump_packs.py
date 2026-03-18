from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))


def test_vanguard_veteran_squad_with_jump_packs_vanguard_assault_grants_lethal_hits_to_melee_weapons_after_charge_move() -> None:
    veterans = _actual_unit("Vanguard Veteran Squad With Jump Packs", datasheet_id="000000147")
    model = veterans.models[0]
    model.wargear = [
        SimpleNamespace(name="Heirloom weapon", is_melee=lambda: True, is_ranged=lambda: False),
        SimpleNamespace(name="Heavy bolt pistol", is_melee=lambda: False, is_ranged=lambda: True),
    ]

    specs = veterans.unit_charge_end_weapon_keyword_bonus_specs()

    assert specs == [
        {
            "weapon": "melee weapons",
            "keyword": "LETHAL HITS",
            "source": "Vanguard Assault",
            "attack_type": "melee",
        }
    ]

    applied = veterans._apply_charge_move_weapon_keyword_bonuses()
    assert applied is True

    melee_bonuses = model.get_temporary_weapon_keyword_bonuses("Heirloom weapon")
    melee_keywords = {str(entry.get("keyword", "")).upper() for entry in melee_bonuses}
    assert "LETHAL HITS" in melee_keywords

    ranged_bonuses = model.get_temporary_weapon_keyword_bonuses("Heavy bolt pistol")
    ranged_keywords = {str(entry.get("keyword", "")).upper() for entry in ranged_bonuses}
    assert "LETHAL HITS" not in ranged_keywords
