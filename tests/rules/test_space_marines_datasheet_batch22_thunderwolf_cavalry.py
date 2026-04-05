from __future__ import annotations

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))


def _profile(unit: Unit, wargear_name: str):
    for wargear in list(unit.models[0].wargear or []):
        if str(getattr(wargear, "name", "") or "") == wargear_name:
            return wargear.profiles["default"]
    raise AssertionError(f"Profile for {wargear_name!r} not found")


def test_thunderwolf_cavalry_thunderous_charge_only_buffs_wolf_guard_weapon() -> None:
    cavalry = _actual_unit("Thunderwolf Cavalry", datasheet_id="000000322")
    attacker = cavalry.models[0]
    cavalry.round_state.charged_this_round = True

    wolf_guard = _profile(cavalry, "Wolf Guard weapon")
    claws = _profile(cavalry, "Teeth and claws")

    _strength_bonus, wolf_damage_bonus, _strength_reasons, wolf_damage_reasons = (
        wolf_guard._get_charge_melee_strength_damage_bonus(attacker, {})
    )
    _strength_bonus, claw_damage_bonus, _strength_reasons, claw_damage_reasons = (
        claws._get_charge_melee_strength_damage_bonus(attacker, {})
    )

    assert int(wolf_damage_bonus) == 1
    assert any("Thunderous Charge" in reason for reason in list(wolf_damage_reasons or ()))
    assert int(claw_damage_bonus) == 0
    assert list(claw_damage_reasons or ()) == []


def test_thunderwolf_cavalry_thunderous_charge_requires_charge_move() -> None:
    cavalry = _actual_unit("Thunderwolf Cavalry", datasheet_id="000000322")
    attacker = cavalry.models[0]
    cavalry.round_state.charged_this_round = False

    wolf_guard = _profile(cavalry, "Wolf Guard weapon")
    _strength_bonus, wolf_damage_bonus, _strength_reasons, wolf_damage_reasons = (
        wolf_guard._get_charge_melee_strength_damage_bonus(attacker, {})
    )

    assert int(wolf_damage_bonus) == 0
    assert list(wolf_damage_reasons or ()) == []
