from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        toughness: int = 4,
        wounds: int = 4,
    ) -> None:
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ENEMY"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))


def _make_target_unit(
    name: str,
    *,
    keywords: list[str],
    toughness: int = 12,
    wounds: int = 10,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=["ENEMY"],
            toughness=toughness,
            wounds=wounds,
        )
    )


def _profile(unit: Unit, wargear_name: str):
    for wargear in list(unit.models[0].wargear or []):
        if str(getattr(wargear, "name", "") or "") == wargear_name:
            return wargear.profiles["default"]
    raise AssertionError(f"Profile for {wargear_name!r} not found")


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def test_tor_garadon_siege_captain_rule_parses_target_keywords_and_bonuses() -> None:
    tor = _actual_unit("Tor Garadon", datasheet_id="000002473")
    attacker = tor.models[0]

    rule = tor.get_model_target_keywords_profile_bonus_rule(attacker)

    assert rule is not None
    assert str(rule.get("attack_type", "")) == "any"
    assert tuple(rule.get("target_keywords_any", ()) or ()) == ("MONSTER", "VEHICLE", "FORTIFICATION")
    assert int(rule.get("strength_bonus", 0) or 0) == 2
    assert int(rule.get("ap_bonus", 0) or 0) == 2
    assert int(rule.get("damage_bonus", 0) or 0) == 2
    assert str(rule.get("source", "")) == "Siege Captain"


def test_tor_garadon_siege_captain_applies_to_ranged_and_melee_profiles_only_vs_matching_targets() -> None:
    tor = _actual_unit("Tor Garadon", datasheet_id="000002473")
    attacker = tor.models[0]
    vehicle_target = _make_target_unit("Vehicle Target", keywords=["VEHICLE"])
    infantry_target = _make_target_unit("Infantry Target", keywords=["INFANTRY"])

    grav_gun = _profile(tor, "Artificer grav-gun")
    hand_of_defiance = _profile(tor, "Hand of Defiance")

    assert grav_gun.get_effective_ap(attacker, vehicle_target) == -3
    assert grav_gun.get_effective_ap(attacker, infantry_target) == -1
    assert hand_of_defiance.get_effective_ap(attacker, vehicle_target) == -4
    assert hand_of_defiance.get_effective_ap(attacker, infantry_target) == -2

    vehicle_wound = hand_of_defiance._wound_target_with_tracking(
        vehicle_target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    infantry_wound = hand_of_defiance._wound_target_with_tracking(
        infantry_target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )

    assert vehicle_wound.get("wound") is True
    assert infantry_wound.get("wound") is False
    assert any("Siege Captain" in reason and "+2S" in reason for reason in list(vehicle_wound.get("modifiers", []) or []))
    assert not any("Siege Captain" in reason for reason in list(infantry_wound.get("modifiers", []) or []))

    vehicle_damage = grav_gun._damage_target_with_tracking(
        vehicle_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    infantry_damage = grav_gun._damage_target_with_tracking(
        infantry_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )

    assert int(vehicle_damage.get("damage_applied", 0) or 0) == 4
    assert int(infantry_damage.get("damage_applied", 0) or 0) == 2
    assert any("Siege Captain +2D" in effect for effect in list(vehicle_damage.get("special_effects", []) or []))
    assert not any("Siege Captain" in effect for effect in list(infantry_damage.get("special_effects", []) or []))
