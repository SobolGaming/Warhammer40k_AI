from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


BROAD_SPECTRUM_TARGETING_AUGURS_TEXT = (
    "Each time a model in this unit makes an attack with an eradication caster that targets a unit "
    "(excluding MONSTER and VEHICLE units), that attack has the [SUSTAINED HITS 1] ability."
)
MONOCULAR_TARGETING_HELMS_TEXT = (
    "Each time a model in this unit makes an attack with a neutron fusil against a MONSTER or VEHICLE unit, "
    "that attack has the [IGNORES COVER] ability."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Adeptus Mechanicus"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": name,
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_ability(name: str, description: str) -> dict:
    return {"name": name, "description": description, "type": "Datasheet", "parameter": ""}


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _test_profile(name: str) -> WargearProfile:
    return WargearProfile(
        "default",
        {
            "range": "24",
            "A": "2",
            "BS_WS": "4+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(
            name=name,
            is_ranged=lambda: True,
            is_melee=lambda: False,
        ),
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


def test_hastarii_exterminators_parser_returns_weapon_excluding_keyword_rule():
    unit = _make_unit(
        "Hastarii Exterminators",
        abilities=[_make_ability("Broad-spectrum Targeting Augurs", BROAD_SPECTRUM_TARGETING_AUGURS_TEXT)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )

    rule = unit.get_weapon_target_excluding_keywords_keyword_bonus_rule(unit.models[0])

    assert isinstance(rule, dict)
    assert str(rule.get("attack_type", "") or "") == "ranged"
    assert list(rule.get("weapon_names", []) or []) == ["eradication caster"]
    assert str(rule.get("keyword", "") or "") == "SUSTAINED HITS 1"
    assert tuple(rule.get("target_exclude_keywords_any", ()) or ()) == ("MONSTER", "VEHICLE")
    assert str(rule.get("source", "") or "") == "Broad-spectrum Targeting Augurs"


def test_hastarii_exterminators_broad_spectrum_targeting_augurs_apply_only_to_eradication_caster_vs_non_vehicle_monster():
    unit = _make_unit(
        "Hastarii Exterminators",
        abilities=[_make_ability("Broad-spectrum Targeting Augurs", BROAD_SPECTRUM_TARGETING_AUGURS_TEXT)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    infantry_target = _make_unit("Infantry Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    vehicle_target = _make_unit("Vehicle Target", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    eradication_caster = _test_profile("Eradication Caster")
    arc_blaster = _test_profile("Arc Blaster")

    infantry_bonus = unit.get_attack_keyword_bonuses(
        target=infantry_target,
        attack_type="ranged",
        model=unit.models[0],
        weapon_profile=eradication_caster,
    )
    vehicle_bonus = unit.get_attack_keyword_bonuses(
        target=vehicle_target,
        attack_type="ranged",
        model=unit.models[0],
        weapon_profile=eradication_caster,
    )
    other_weapon_bonus = unit.get_attack_keyword_bonuses(
        target=infantry_target,
        attack_type="ranged",
        model=unit.models[0],
        weapon_profile=arc_blaster,
    )

    assert int(infantry_bonus.get("sustained_hits_value", 0) or 0) == 1
    assert int(vehicle_bonus.get("sustained_hits_value", 0) or 0) == 0
    assert int(other_weapon_bonus.get("sustained_hits_value", 0) or 0) == 0

    infantry_attack = {"_aura_attack_mods": _aura_stub()}
    eradication_caster._hit_target_with_tracking(
        infantry_target,
        unit.models[0],
        infantry_attack,
        roll_value=6,
        allow_rerolls=False,
    )
    assert int(infantry_attack.get("sustained_hit", 0) or 0) == 1

    vehicle_attack = {"_aura_attack_mods": _aura_stub()}
    eradication_caster._hit_target_with_tracking(
        vehicle_target,
        unit.models[0],
        vehicle_attack,
        roll_value=6,
        allow_rerolls=False,
    )
    assert int(vehicle_attack.get("sustained_hit", 0) or 0) == 0


def test_hastarii_fusiliers_parser_returns_weapon_target_keyword_rule():
    unit = _make_unit(
        "Hastarii Fusiliers",
        abilities=[_make_ability("Monocular Targeting Helms", MONOCULAR_TARGETING_HELMS_TEXT)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )

    rule = unit.get_weapon_target_keywords_keyword_bonus_rule(unit.models[0])

    assert isinstance(rule, dict)
    assert str(rule.get("attack_type", "") or "") == "ranged"
    assert list(rule.get("weapon_names", []) or []) == ["neutron fusil"]
    assert str(rule.get("keyword", "") or "") == "IGNORES COVER"
    assert tuple(rule.get("target_keywords_any", ()) or ()) == ("MONSTER", "VEHICLE")
    assert str(rule.get("source", "") or "") == "Monocular Targeting Helms"


def test_hastarii_fusiliers_monocular_targeting_helms_apply_only_to_neutron_fusil_vs_vehicle_monster():
    unit = _make_unit(
        "Hastarii Fusiliers",
        abilities=[_make_ability("Monocular Targeting Helms", MONOCULAR_TARGETING_HELMS_TEXT)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    infantry_target = _make_unit("Infantry Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    monster_target = _make_unit("Monster Target", keywords=["MONSTER"], faction_keywords=["ENEMY"])
    neutron_fusil = _test_profile("Neutron Fusil")
    phosphor_blaster = _test_profile("Phosphor Blaster")

    infantry_bonus = unit.get_attack_keyword_bonuses(
        target=infantry_target,
        attack_type="ranged",
        model=unit.models[0],
        weapon_profile=neutron_fusil,
    )
    monster_bonus = unit.get_attack_keyword_bonuses(
        target=monster_target,
        attack_type="ranged",
        model=unit.models[0],
        weapon_profile=neutron_fusil,
    )
    other_weapon_bonus = unit.get_attack_keyword_bonuses(
        target=monster_target,
        attack_type="ranged",
        model=unit.models[0],
        weapon_profile=phosphor_blaster,
    )

    assert bool(infantry_bonus.get("ignores_cover", False)) is False
    assert bool(monster_bonus.get("ignores_cover", False)) is True
    assert bool(other_weapon_bonus.get("ignores_cover", False)) is False

    infantry_attack = {"_aura_attack_mods": _aura_stub()}
    neutron_fusil._hit_target_with_tracking(
        infantry_target,
        unit.models[0],
        infantry_attack,
        roll_value=4,
        allow_rerolls=False,
    )
    assert bool(infantry_attack.get("ignores_cover", False)) is False

    monster_attack = {"_aura_attack_mods": _aura_stub()}
    neutron_fusil._hit_target_with_tracking(
        monster_target,
        unit.models[0],
        monster_attack,
        roll_value=4,
        allow_rerolls=False,
    )
    assert bool(monster_attack.get("ignores_cover", False)) is True
