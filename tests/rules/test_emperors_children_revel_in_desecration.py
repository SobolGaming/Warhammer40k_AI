from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": "Emperor's Children"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["EMPEROR'S CHILDREN"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "10",
                "Sv": "3",
                "W": "14",
                "Ld": "7",
                "OC": "3",
                "base_size": "100mm",
                "inv_sv": "5",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_profile(*, skill: str = "4+") -> WargearProfile:
    parent = SimpleNamespace(name="Excruciator cannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": skill,
            "S": "9",
            "AP": "-1",
            "D": "3",
            "description": "",
        },
        parent_wargear=parent,
    )


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


_REVEL_IN_DESECRATION = (
    "Each time this model makes an attack that targets an enemy unit that is not below Half-strength, "
    "add 1 to the Hit roll."
)


def test_revel_in_desecration_adds_hit_vs_targets_not_below_half_strength(monkeypatch) -> None:
    attacker = _make_unit(
        "Defiler",
        "000004208",
        abilities=[_ability("Revel in Desecration", _REVEL_IN_DESECRATION)],
        keywords=["VEHICLE", "DAEMON"],
    )
    target = _make_unit("Target", "enemy_target")
    target.is_below_half_strength = lambda: False

    monkeypatch.setattr(wargear_mod, "get_roll", lambda _die: 3)

    attack_instance = {"_aura_attack_mods": _aura_stub()}
    result = _make_profile()._hit_target_with_tracking(target, attacker.models[0], attack_instance)

    assert bool(result.get("hit", False)) is True
    assert int(result.get("final_needed", 0) or 0) == 3
    assert any("not below half-strength" in str(reason).lower() for reason in result.get("modifiers", ()))
    model_attack_mods = dict(attack_instance.get("_model_attack_mods", {}) or {})
    assert int(model_attack_mods.get("hit", 0) or 0) == 1
    assert any("not below half-strength" in str(reason).lower() for reason in model_attack_mods.get("hit_reasons", ()))


def test_revel_in_desecration_does_not_add_hit_vs_targets_below_half_strength(monkeypatch) -> None:
    attacker = _make_unit(
        "Defiler",
        "000004208",
        abilities=[_ability("Revel in Desecration", _REVEL_IN_DESECRATION)],
        keywords=["VEHICLE", "DAEMON"],
    )
    target = _make_unit("Target", "enemy_target")
    target.is_below_half_strength = lambda: True

    monkeypatch.setattr(wargear_mod, "get_roll", lambda _die: 3)

    attack_instance = {"_aura_attack_mods": _aura_stub()}
    result = _make_profile()._hit_target_with_tracking(target, attacker.models[0], attack_instance)

    assert bool(result.get("hit", False)) is False
    assert int(result.get("final_needed", 0) or 0) == 4
    assert tuple(result.get("modifiers", ()) or ()) == ()
    model_attack_mods = dict(attack_instance.get("_model_attack_mods", {}) or {})
    assert int(model_attack_mods.get("hit", 0) or 0) == 0
    assert tuple(model_attack_mods.get("hit_reasons", ()) or ()) == ()
