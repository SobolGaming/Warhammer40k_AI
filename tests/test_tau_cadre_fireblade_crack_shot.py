from __future__ import annotations

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _make_tau_unit(name: str) -> Unit:
    datasheet = _WAHA.get_datasheet(name, faction_id="TAU")
    assert datasheet is not None
    unit = Unit(datasheet)
    unit.deployed = True
    return unit


def _first_ranged_profile(unit: Unit):
    model = unit.models[0]
    for wargear in list(getattr(model, "wargear", []) or []):
        if wargear.is_ranged():
            return next(iter(wargear.profiles.values()))
    raise AssertionError(f"Expected a ranged weapon profile on {unit.name}.")


def test_cadre_fireblade_crack_shot_sets_ap_to_minus_three_on_critical_wound():
    attacker = _make_tau_unit("Cadre Fireblade")
    defender = _make_tau_unit("Breacher Team")
    profile = _first_ranged_profile(attacker)
    target_model = defender.models[0]

    save_result = profile._save_with_tracking(
        target_model,
        {
            "attacker_model": attacker.models[0],
            "attacker_unit": attacker,
            "target_unit": defender,
            "crit_wound": True,
        },
        ap=0,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert int(save_result.get("final_save", 0) or 0) == 7
    assert any(
        "Crack Shot" in str(effect) and "-3" in str(effect)
        for effect in list(save_result.get("special_effects", []) or [])
    )


def test_cadre_fireblade_crack_shot_does_not_apply_without_critical_wound():
    attacker = _make_tau_unit("Cadre Fireblade")
    defender = _make_tau_unit("Breacher Team")
    profile = _first_ranged_profile(attacker)
    target_model = defender.models[0]

    save_result = profile._save_with_tracking(
        target_model,
        {
            "attacker_model": attacker.models[0],
            "attacker_unit": attacker,
            "target_unit": defender,
            "crit_wound": False,
        },
        ap=0,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert int(save_result.get("final_save", 0) or 0) == 4
    assert not any(
        "Crack Shot" in str(effect)
        for effect in list(save_result.get("special_effects", []) or [])
    )
