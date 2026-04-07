from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str,
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        movement: str = "5",
        toughness: str = "5",
        wounds: str = "4",
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = list(attached_to or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": movement,
                "T": toughness,
                "Sv": "4",
                "W": wounds,
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Orks",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    movement: str = "5",
    toughness: str = "5",
    wounds: str = "4",
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        datasheet_id=datasheet_id,
        faction_name=faction_name,
        model_count=model_count,
        keywords=keywords,
        faction_keywords=faction_keywords,
        attached_to=attached_to,
        movement=movement,
        toughness=toughness,
        wounds=wounds,
    )
    return Unit(datasheet)


def _make_more_dakka_army() -> Army:
    army = Army.with_detachment("Orks", "More Dakka!")
    army.faction_id = "ORK"
    return army


def _make_enemy_army() -> Army:
    army = Army.with_detachment("Enemy", "Other")
    army.faction_id = "ENEMY"
    return army


def _apply_enhancement(army: Army, unit: Unit, enhancement_name: str) -> None:
    enhancement = _WAHA.get_enhancement_by_name(enhancement_name)
    assert enhancement is not None, enhancement_name
    army.add_enhancement(enhancement, unit)


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


def _make_profile(*, name: str, weapon_type: str, attacks: str = "2", strength: str = "5") -> WargearProfile:
    is_ranged = str(weapon_type or "").strip().lower() == "ranged"
    parent = SimpleNamespace(
        name=name,
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    return WargearProfile(
        profile_name=name,
        wargear_data={
            "range": "24" if is_ranged else "Melee",
            "A": str(attacks),
            "BS_WS": "5+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_attached_orks_setup():
    ork_army = _make_more_dakka_army()
    enemy_army = _make_enemy_army()
    bodyguard = _make_unit(
        "Warbikers",
        "orks-more-dakka-bodyguard",
        model_count=3,
        keywords=["MOUNTED", "WARBIKERS"],
        faction_keywords=["ORKS"],
        wounds="2",
    )
    leader = _make_unit(
        "Warboss",
        "orks-more-dakka-leader",
        keywords=["CHARACTER", "INFANTRY", "WARBOSS"],
        faction_keywords=["ORKS"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    unrelated = _make_unit(
        "Deffkoptas",
        "orks-more-dakka-unrelated",
        model_count=3,
        keywords=["MOUNTED", "DEFFKOPTAS"],
        faction_keywords=["ORKS"],
        wounds="2",
    )
    target = _make_unit(
        "Enemy Squad",
        "enemy-more-dakka-target",
        faction_name="Enemy",
        model_count=5,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="1",
    )
    ork_army.add_unit(bodyguard)
    ork_army.add_unit(leader)
    ork_army.add_unit(unrelated)
    enemy_army.add_unit(target)
    leader.attach_to_unit(bodyguard)
    return ork_army, enemy_army, bodyguard, leader, unrelated, target


def test_more_dakka_enhancement_descriptors_registered():
    expected = {
        "000009991002": "Da Gobshot Thunderbuss",
        "000009991003": "Dead Shiny Shootas",
        "000009991004": "Targetin' Squigs",
        "000009991005": "Zog Off and Eat Dakka!",
    }
    for enhancement_id, expected_name in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == expected_name


def test_more_dakka_enhancements_register_shared_local_passive_rules():
    ork_army = _make_more_dakka_army()
    gobshot = _make_unit(
        "Big Mek",
        "orks-gobshot-bearer",
        keywords=["CHARACTER", "INFANTRY", "MEK"],
        faction_keywords=["ORKS"],
    )
    dead_shiny = _make_unit(
        "Flash Git Boss",
        "orks-dead-shiny-bearer",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    squigs = _make_unit(
        "Warboss",
        "orks-targetin-bearer",
        keywords=["CHARACTER", "INFANTRY", "WARBOSS"],
        faction_keywords=["ORKS"],
    )
    zog_off = _make_unit(
        "Boss Nob",
        "orks-zog-off-bearer",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    for unit in (gobshot, dead_shiny, squigs, zog_off):
        ork_army.add_unit(unit)

    _apply_enhancement(ork_army, gobshot, "Da Gobshot Thunderbuss")
    _apply_enhancement(ork_army, dead_shiny, "Dead Shiny Shootas")
    _apply_enhancement(ork_army, squigs, "Targetin' Squigs")
    _apply_enhancement(ork_army, zog_off, "Zog Off and Eat Dakka!")

    gobshot_rules = list(gobshot.special_rules.get("enhancement_weapon_keyword_rules", []) or [])
    assert len(gobshot_rules) == 1
    assert gobshot_rules[0]["target_scope"] == "bearer"
    assert gobshot_rules[0]["attack_type"] == "ranged"
    assert gobshot_rules[0]["keywords"] == ["DEVASTATING WOUNDS", "HAZARDOUS"]
    assert gobshot_rules[0]["source"] == "Da Gobshot Thunderbuss"
    assert gobshot_rules[0]["source_model_id"] == str(gobshot.special_rules.get("enhancement_bearer_model_id", "") or "")

    dead_shiny_rules = list(dead_shiny.special_rules.get("enhancement_weapon_keyword_rules", []) or [])
    assert len(dead_shiny_rules) == 1
    assert dead_shiny_rules[0]["target_scope"] == "bearer_unit"
    assert dead_shiny_rules[0]["attack_type"] == "ranged"
    assert dead_shiny_rules[0]["keywords"] == ["RAPID FIRE 1"]

    squigs_rules = list(squigs.special_rules.get("enhancement_attack_roll_modifier_rules", []) or [])
    assert len(squigs_rules) == 1
    assert squigs_rules[0]["target_scope"] == "bearer_unit"
    assert squigs_rules[0]["attack_type"] == "ranged"
    assert squigs_rules[0]["roll"] == "hit"
    assert int(squigs_rules[0]["modifier"]) == 1

    zog_off_rules = list(zog_off.special_rules.get("enhancement_fall_back_shoot_rules", []) or [])
    assert len(zog_off_rules) == 1
    assert zog_off_rules[0]["target_scope"] == "bearer_unit"
    assert zog_off_rules[0]["attack_type"] == "ranged"
    assert zog_off_rules[0]["source"] == "Zog Off and Eat Dakka!"


def test_da_gobshot_thunderbuss_grants_devastating_wounds_and_hazardous_to_bearer_ranged_weapons_only():
    ork_army, _enemy_army, bodyguard, leader, _unrelated, target = _make_attached_orks_setup()
    _apply_enhancement(ork_army, leader, "Da Gobshot Thunderbuss")

    ranged_profile = _make_profile(name="Kustom Shoota", weapon_type="ranged")
    melee_profile = _make_profile(name="Power Klaw", weapon_type="melee")

    bearer_attack = {"_aura_attack_mods": _aura_stub()}
    ranged_profile._hit_target_with_tracking(
        target,
        leader.models[0],
        bearer_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bearer_attack.get("bonus_devastating_wounds") is True
    assert bearer_attack.get("bonus_hazardous") is True

    bodyguard_attack = {"_aura_attack_mods": _aura_stub()}
    ranged_profile._hit_target_with_tracking(
        target,
        bodyguard.models[0],
        bodyguard_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bodyguard_attack.get("bonus_devastating_wounds")
    assert not bodyguard_attack.get("bonus_hazardous")

    melee_attack = {"_aura_attack_mods": _aura_stub()}
    melee_profile._hit_target_with_tracking(
        target,
        leader.models[0],
        melee_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not melee_attack.get("bonus_devastating_wounds")
    assert not melee_attack.get("bonus_hazardous")


def test_dead_shiny_shootas_grants_rapid_fire_to_bearer_unit_only_and_not_other_units():
    ork_army, _enemy_army, bodyguard, leader, unrelated, target = _make_attached_orks_setup()
    _apply_enhancement(ork_army, leader, "Dead Shiny Shootas")

    ranged_profile = _make_profile(name="Shoota", weapon_type="ranged", attacks="2")
    melee_profile = _make_profile(name="Choppa", weapon_type="melee", attacks="2")

    bodyguard_bonus = bodyguard.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=bodyguard.models[0],
        weapon_profile=ranged_profile,
    )
    assert int(bodyguard_bonus.get("rapid_fire_bonus", 0) or 0) == 1
    assert "Rapid Fire 1 (Dead Shiny Shootas)" in list(bodyguard_bonus.get("sources", ()) or ())

    bearer_bonus = bodyguard.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=leader.models[0],
        weapon_profile=ranged_profile,
    )
    assert int(bearer_bonus.get("rapid_fire_bonus", 0) or 0) == 1

    unrelated_bonus = unrelated.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=unrelated.models[0],
        weapon_profile=ranged_profile,
    )
    assert int(unrelated_bonus.get("rapid_fire_bonus", 0) or 0) == 0

    melee_bonus = bodyguard.get_attack_keyword_bonuses(
        target=target,
        attack_type="melee",
        model=bodyguard.models[0],
        weapon_profile=melee_profile,
    )
    assert int(melee_bonus.get("rapid_fire_bonus", 0) or 0) == 0

    bodyguard_attacks = ranged_profile.preview_attack_count(target, bodyguard.models[0], publish_roll_event=False)
    unrelated_attacks = ranged_profile.preview_attack_count(target, unrelated.models[0], publish_roll_event=False)
    assert int(bodyguard_attacks.num_attacks) == 3
    assert int(unrelated_attacks.num_attacks) == 2


def test_targetin_squigs_grants_plus_one_to_hit_for_bearer_unit_ranged_attacks_only():
    ork_army, _enemy_army, bodyguard, leader, unrelated, target = _make_attached_orks_setup()
    _apply_enhancement(ork_army, leader, "Targetin' Squigs")

    ranged_mods = bodyguard.get_unit_hit_reroll_modifiers(
        "ranged",
        target=target,
        attacker_model=bodyguard.models[0],
    )
    assert int(ranged_mods.get("hit", 0) or 0) == 1
    assert "+1 to hit from Targetin' Squigs" in list(ranged_mods.get("hit_reasons", ()) or ())

    melee_mods = bodyguard.get_unit_hit_reroll_modifiers(
        "melee",
        target=target,
        attacker_model=bodyguard.models[0],
    )
    assert int(melee_mods.get("hit", 0) or 0) == 0
    assert not any("Targetin' Squigs" in str(reason or "") for reason in list(melee_mods.get("hit_reasons", ()) or ()))

    unrelated_mods = unrelated.get_unit_hit_reroll_modifiers(
        "ranged",
        target=target,
        attacker_model=unrelated.models[0],
    )
    assert int(unrelated_mods.get("hit", 0) or 0) == 0

    ranged_profile = _make_profile(name="Shoota", weapon_type="ranged")
    hit_result = ranged_profile._hit_target_with_tracking(
        target,
        bodyguard.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit"))


def test_zog_off_and_eat_dakka_grants_shoot_after_fall_back_to_bearer_unit_only():
    ork_army, _enemy_army, bodyguard, leader, unrelated, target = _make_attached_orks_setup()
    _apply_enhancement(ork_army, leader, "Zog Off and Eat Dakka!")

    ranged_profile = _make_profile(name="Deffgun", weapon_type="ranged")

    assert bodyguard.has_fell_back_and_shoot() is True
    assert bodyguard.can_shoot_after_fall_back(ranged_profile) is True
    assert leader.has_fell_back_and_shoot() is True
    assert leader.can_shoot_after_fall_back(ranged_profile) is True
    assert unrelated.has_fell_back_and_shoot() is False
    assert unrelated.can_shoot_after_fall_back(ranged_profile) is False

    unrelated_bonus = unrelated.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=unrelated.models[0],
        weapon_profile=ranged_profile,
    )
    assert int(unrelated_bonus.get("rapid_fire_bonus", 0) or 0) == 0
