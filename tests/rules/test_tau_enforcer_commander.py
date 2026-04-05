from __future__ import annotations

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _make_tau_unit(name: str) -> Unit:
    datasheet = _WAHA.get_datasheet(name, faction_id="TAU")
    assert datasheet is not None
    unit = Unit(datasheet)
    unit.deployed = True
    return unit


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def _make_profile(*, ranged: bool, ap: int):
    weapon = Wargear(
        {
            "name": "Test Rifle" if ranged else "Test Blade",
            "type": "Ranged" if ranged else "Melee",
            "range": "24" if ranged else "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def test_enforcer_commander_worsens_ap_of_ranged_attacks_while_leading():
    attacker = _make_tau_unit("Breacher Team")
    bodyguard = _make_tau_unit("Crisis Fireknife Battlesuits")
    leader = _make_tau_unit("Commander In Enforcer Battlesuit")
    _attach_leader(bodyguard, leader)

    bodyguard._parse_against_attack_characteristic_defensive_rules()
    entries = list(bodyguard.special_rules.get("defensive_ap_worsen", []) or [])
    assert any(str(entry.get("source", "")) == "Enforcer Commander" for entry in entries)

    ranged_profile = _make_profile(ranged=True, ap=-2)
    ap_with_leader = ranged_profile.get_effective_ap(attacker.models[0], bodyguard)

    plain_target = _make_tau_unit("Crisis Fireknife Battlesuits")
    plain_target._parse_against_attack_characteristic_defensive_rules()
    ap_without_leader = ranged_profile.get_effective_ap(attacker.models[0], plain_target)

    assert ap_without_leader == -2
    assert ap_with_leader == -1


def test_enforcer_commander_does_not_worsen_ap_of_melee_attacks():
    attacker = _make_tau_unit("Breacher Team")
    bodyguard = _make_tau_unit("Crisis Fireknife Battlesuits")
    leader = _make_tau_unit("Commander In Enforcer Battlesuit")
    _attach_leader(bodyguard, leader)

    bodyguard._parse_against_attack_characteristic_defensive_rules()
    melee_profile = _make_profile(ranged=False, ap=-2)
    ap_with_leader = melee_profile.get_effective_ap(attacker.models[0], bodyguard)

    assert ap_with_leader == -2
