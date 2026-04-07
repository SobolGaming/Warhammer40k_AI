from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, model_count: int = 1):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _create_unit(name: str, *, keywords=None, faction_keywords=None, model_count: int = 1) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_profile(*, is_ranged: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Attack Weapon",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": "24" if is_ranged else "2",
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_armies(*, target_unit: Unit, enemy_unit: Unit):
    ork_army = Army.with_detachment("Orks", "Green Tide")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    ork_army.add_unit(target_unit)
    enemy_army.add_unit(enemy_unit)
    Player("Ork Player", control=PlayerControl.LOCAL, army=ork_army)
    Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    return ork_army, enemy_army


def _run_save(*, target_model, attacker_model, target_unit, is_ranged: bool, roll_value: int):
    profile = _make_profile(is_ranged=is_ranged)
    return profile._save_with_tracking(
        target_model,
        {"attacker_model": attacker_model, "target_unit": target_unit},
        ap=-3,
        roll_value=roll_value,
        allow_rerolls=False,
        log_roll=False,
    )


def test_mob_mentality_grants_six_plus_invulnerable_to_boyz_units_with_fewer_than_ten_models():
    boyz = _create_unit("Boyz", keywords=["INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=9)
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    _build_armies(target_unit=boyz, enemy_unit=enemy)

    save_result = _run_save(
        target_model=boyz.models[0],
        attacker_model=enemy.models[0],
        target_unit=boyz,
        is_ranged=True,
        roll_value=6,
    )

    assert save_result.get("save_type") == "invulnerable"
    assert int(save_result.get("final_save", 0) or 0) == 6
    assert any("Mob Mentality" in str(entry) for entry in save_result.get("special_effects", []))


def test_mob_mentality_grants_five_plus_invulnerable_to_boyz_units_with_ten_or_more_models():
    boyz = _create_unit("Boyz", keywords=["INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=10)
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    _build_armies(target_unit=boyz, enemy_unit=enemy)

    save_result = _run_save(
        target_model=boyz.models[0],
        attacker_model=enemy.models[0],
        target_unit=boyz,
        is_ranged=True,
        roll_value=5,
    )

    assert save_result.get("save_type") == "invulnerable"
    assert int(save_result.get("final_save", 0) or 0) == 5
    assert any("Mob Mentality" in str(entry) for entry in save_result.get("special_effects", []))


def test_mob_mentality_does_not_apply_to_non_boyz_units():
    nobz = _create_unit("Nobz", keywords=["INFANTRY", "NOBZ"], faction_keywords=["ORKS"], model_count=10)
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    _build_armies(target_unit=nobz, enemy_unit=enemy)

    save_result = _run_save(
        target_model=nobz.models[0],
        attacker_model=enemy.models[0],
        target_unit=nobz,
        is_ranged=True,
        roll_value=6,
    )

    assert save_result.get("save_type") != "invulnerable"
    assert int(save_result.get("final_save", 0) or 0) == 7
    assert not any("Mob Mentality" in str(entry) for entry in save_result.get("special_effects", []))
