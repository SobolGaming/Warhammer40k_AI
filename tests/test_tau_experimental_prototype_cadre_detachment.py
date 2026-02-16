from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "2",
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


def create_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    ds = MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords)
    unit = Unit(ds)
    unit.deployed = True
    return unit


def make_profile(*, range_val: str, is_ranged: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Pulse Rifle" if is_ranged else "Combat Blade",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": str(range_val),
        "A": "1",
        "BS_WS": "4",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def make_named_ranged_profile(
    wargear_name: str,
    *,
    range_val: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
) -> tuple[WargearProfile, object]:
    parent = SimpleNamespace(
        name=str(wargear_name),
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": str(range_val),
        "A": "1",
        "BS_WS": "4",
        "S": str(strength),
        "AP": str(ap),
        "D": str(damage),
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent), parent


def _supernova_launcher_enhancement() -> Enhancement:
    return Enhancement(
        id="000009983002",
        name="Supernova Launcher",
        faction_id="TAU",
        detachment="Experimental Prototype Cadre",
        description=(
            "T'AU EMPIRE model only. Select one airbursting fragmentation projector equipped by the bearer. "
            "Improve the Strength characteristic of that weapon by 3, and improve the Armour Penetration and "
            "Damage characteristics of that weapon by 1."
        ),
    )


def _thermoneutronic_projector_enhancement() -> Enhancement:
    return Enhancement(
        id="000009983003",
        name="Thermoneutronic Projector",
        faction_id="TAU",
        detachment="Experimental Prototype Cadre",
        description=(
            "T'AU EMPIRE model only. Select one T'au flamer equipped by the bearer. Improve the Strength "
            "characteristic of that weapon by 2, and improve the Armour Penetration and Damage characteristics "
            "of that weapon by 1."
        ),
    )


def _plasma_accelerator_rifle_enhancement() -> Enhancement:
    return Enhancement(
        id="000009983004",
        name="Plasma Accelerator Rifle",
        faction_id="TAU",
        detachment="Experimental Prototype Cadre",
        description=(
            "T'AU EMPIRE model only. Select one plasma rifle equipped by the bearer. Improve the Strength "
            "characteristic of that weapon by 2, and improve the Attacks, Armour Penetration and Damage "
            "characteristics of that weapon by 1."
        ),
    )


def _build_tau_army(detachment_type: str) -> Army:
    army = Army("T'au Empire", detachment_type)
    army.faction_id = "TAU"
    army.player = SimpleNamespace(game=SimpleNamespace(turn=1))
    return army


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
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def _attach_ranged_profile(unit: Unit, profile: WargearProfile) -> None:
    model = unit.models[0]
    model.wargear.append(
        SimpleNamespace(
            is_ranged=lambda: True,
            profiles={"default": profile},
        )
    )


def _configure_tau_shooting_game(army: Army, *, battle_round: int):
    game = SimpleNamespace(
        turn=int(battle_round),
        map=None,
        is_shooting_phase=lambda: True,
    )
    player = SimpleNamespace(id="P1", name="Player 1", game=game)
    game.get_current_player = lambda: player
    army.player = player
    return game, player


def test_superior_craftsmanship_adds_six_inches_to_ranged_weapons():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="24", is_ranged=True)

    assert profile._effective_range_max(attacker) == 30


def test_superior_craftsmanship_does_not_modify_melee_weapons():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="2", is_ranged=False)

    assert profile._effective_range_max(attacker) == 2


def test_superior_craftsmanship_requires_experimental_prototype_cadre_detachment():
    army = _build_tau_army("Kauyon")
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="24", is_ranged=True)

    assert profile._effective_range_max(attacker) == 24


def test_superior_craftsmanship_requires_tau_empire_model_keyword():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Mercenary Squad",
        keywords=["INFANTRY"],
        faction_keywords=["KROOT"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="24", is_ranged=True)

    assert profile._effective_range_max(attacker) == 24


def test_killing_blow_grants_assault_for_first_three_rounds():
    army = _build_tau_army("Mont'ka")
    army.player.game.turn = 2
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    profile = make_profile(range_val="24", is_ranged=True)

    assert unit.can_shoot_after_advance(profile) is True


def test_killing_blow_assault_expires_after_third_round():
    army = _build_tau_army("Mont'ka")
    army.player.game.turn = 4
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    profile = make_profile(range_val="24", is_ranged=True)

    assert unit.can_shoot_after_advance(profile) is False


def test_killing_blow_assault_requires_tau_empire_keyword():
    army = _build_tau_army("Mont'ka")
    army.player.game.turn = 2
    unit = create_unit(
        "Mercenary Squad",
        keywords=["INFANTRY"],
        faction_keywords=["KROOT"],
    )
    army.add_unit(unit)
    profile = make_profile(range_val="24", is_ranged=True)

    assert unit.can_shoot_after_advance(profile) is False


def test_killing_blow_guided_units_gain_lethal_hits_first_three_rounds():
    from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager

    army = _build_tau_army("Mont'ka")
    game, player = _configure_tau_shooting_game(army, battle_round=2)

    attacker_unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    observer_unit = create_unit(
        "Pathfinders",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    target_unit = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(attacker_unit)
    army.add_unit(observer_unit)

    observer_profile = make_profile(range_val="24", is_ranged=True)
    _attach_ranged_profile(observer_unit, observer_profile)

    ftgg = ForTheGreaterGoodManager(army)
    army.for_the_greater_good = ftgg
    assert ftgg.mark_spotted(observer_unit, target_unit, game=game, player=player) is True

    attack_profile = make_profile(range_val="24", is_ranged=True)
    attacker_model = attacker_unit.models[0]
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    hit_result = attack_profile._hit_target_with_tracking(
        target_unit,
        attacker_model,
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert hit_result["hit"] is True
    assert attack_instance.get("lethal_hit") is True
    assert "Lethal Hits" in hit_result.get("special_effects", [])


def test_killing_blow_lethal_hits_do_not_apply_after_third_round():
    from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager

    army = _build_tau_army("Mont'ka")
    game, player = _configure_tau_shooting_game(army, battle_round=4)

    attacker_unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    observer_unit = create_unit(
        "Pathfinders",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    target_unit = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(attacker_unit)
    army.add_unit(observer_unit)

    observer_profile = make_profile(range_val="24", is_ranged=True)
    _attach_ranged_profile(observer_unit, observer_profile)

    ftgg = ForTheGreaterGoodManager(army)
    army.for_the_greater_good = ftgg
    assert ftgg.mark_spotted(observer_unit, target_unit, game=game, player=player) is True

    attack_profile = make_profile(range_val="24", is_ranged=True)
    attacker_model = attacker_unit.models[0]
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    hit_result = attack_profile._hit_target_with_tracking(
        target_unit,
        attacker_model,
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert hit_result["hit"] is True
    assert attack_instance.get("lethal_hit") is not True
    assert "Lethal Hits" not in hit_result.get("special_effects", [])


def test_killing_blow_lethal_hits_require_guided_unit():
    from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager

    army = _build_tau_army("Mont'ka")
    _configure_tau_shooting_game(army, battle_round=2)

    attacker_unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    target_unit = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(attacker_unit)
    army.for_the_greater_good = ForTheGreaterGoodManager(army)

    attack_profile = make_profile(range_val="24", is_ranged=True)
    attacker_model = attacker_unit.models[0]
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    hit_result = attack_profile._hit_target_with_tracking(
        target_unit,
        attacker_model,
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert hit_result["hit"] is True
    assert attack_instance.get("lethal_hit") is not True
    assert "Lethal Hits" not in hit_result.get("special_effects", [])


def test_supernova_launcher_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000009983002")
    assert desc is not None
    assert desc.name == "Supernova Launcher"
    assert desc.effect == "selected_ranged_weapon_strength_ap_damage_bonus"
    assert desc.effect_params.get("weapon_name") == "airbursting fragmentation projector"
    assert int(desc.effect_params.get("strength_bonus", 0) or 0) == 3
    assert int(desc.effect_params.get("ap_bonus", 0) or 0) == 1
    assert int(desc.effect_params.get("damage_bonus", 0) or 0) == 1


def test_supernova_launcher_buffs_selected_airbursting_weapon_only():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    airburst_profile, airburst_wargear = make_named_ranged_profile("Airbursting Fragmentation Projector")
    burst_profile, burst_wargear = make_named_ranged_profile("Burst Cannon")
    attacker.wargear.extend([airburst_wargear, burst_wargear])

    enhancement = _supernova_launcher_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    target_for_wound = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    airburst_wound = airburst_profile._wound_target_with_tracking(
        target_for_wound,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    burst_wound = burst_profile._wound_target_with_tracking(
        target_for_wound,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert airburst_profile.get_effective_ap(attacker, target_for_wound) == -1
    assert burst_profile.get_effective_ap(attacker, target_for_wound) == 0
    assert any("Supernova Launcher" in str(entry) and "+3S" in str(entry) for entry in airburst_wound.get("modifiers", []))
    assert not any("Supernova Launcher" in str(entry) for entry in burst_wound.get("modifiers", []))

    selected_damage_target = create_unit(
        "Selected Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    other_damage_target = create_unit(
        "Other Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    selected_damage = airburst_profile._damage_target_with_tracking(
        selected_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    other_damage = burst_profile._damage_target_with_tracking(
        other_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    assert any("Supernova Launcher +1D" in str(entry) for entry in selected_damage.get("special_effects", []))
    assert not any("Supernova Launcher +1D" in str(entry) for entry in other_damage.get("special_effects", []))


def test_supernova_launcher_selects_single_matching_weapon_instance():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    first_profile, first_wargear = make_named_ranged_profile("Airbursting Fragmentation Projector")
    second_profile, second_wargear = make_named_ranged_profile("Airbursting Fragmentation Projector")
    attacker.wargear.extend([first_wargear, second_wargear])

    enhancement = _supernova_launcher_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    assert bool(unit.special_rules.get("enhancement_supernova_launcher", False))
    assert int(unit.special_rules.get("enhancement_supernova_launcher_weapon_slot_index", -1)) == 0

    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    first_wound = first_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    second_wound = second_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert first_profile.get_effective_ap(attacker, target) == -1
    assert second_profile.get_effective_ap(attacker, target) == 0
    assert any("Supernova Launcher" in str(entry) and "+3S" in str(entry) for entry in first_wound.get("modifiers", []))
    assert not any("Supernova Launcher" in str(entry) for entry in second_wound.get("modifiers", []))


def test_thermoneutronic_projector_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000009983003")
    assert desc is not None
    assert desc.name == "Thermoneutronic Projector"
    assert desc.effect == "selected_ranged_weapon_strength_ap_damage_bonus"
    assert desc.effect_params.get("weapon_name") == "t'au flamer"
    assert int(desc.effect_params.get("strength_bonus", 0) or 0) == 2
    assert int(desc.effect_params.get("ap_bonus", 0) or 0) == 1
    assert int(desc.effect_params.get("damage_bonus", 0) or 0) == 1


def test_thermoneutronic_projector_buffs_selected_tau_flamer_only():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    flamer_profile, flamer_wargear = make_named_ranged_profile("T'au Flamer")
    burst_profile, burst_wargear = make_named_ranged_profile("Burst Cannon")
    attacker.wargear.extend([flamer_wargear, burst_wargear])

    enhancement = _thermoneutronic_projector_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    target_for_wound = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    flamer_wound = flamer_profile._wound_target_with_tracking(
        target_for_wound,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    burst_wound = burst_profile._wound_target_with_tracking(
        target_for_wound,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert flamer_profile.get_effective_ap(attacker, target_for_wound) == -1
    assert burst_profile.get_effective_ap(attacker, target_for_wound) == 0
    assert any(
        "Thermoneutronic Projector" in str(entry) and "+2S" in str(entry)
        for entry in flamer_wound.get("modifiers", [])
    )
    assert not any("Thermoneutronic Projector" in str(entry) for entry in burst_wound.get("modifiers", []))

    selected_damage_target = create_unit(
        "Selected Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    other_damage_target = create_unit(
        "Other Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    selected_damage = flamer_profile._damage_target_with_tracking(
        selected_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    other_damage = burst_profile._damage_target_with_tracking(
        other_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    assert any("Thermoneutronic Projector +1D" in str(entry) for entry in selected_damage.get("special_effects", []))
    assert not any("Thermoneutronic Projector +1D" in str(entry) for entry in other_damage.get("special_effects", []))


def test_thermoneutronic_projector_selects_single_matching_weapon_instance():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    first_profile, first_wargear = make_named_ranged_profile("T'au Flamer")
    second_profile, second_wargear = make_named_ranged_profile("T'au Flamer")
    attacker.wargear.extend([first_wargear, second_wargear])

    enhancement = _thermoneutronic_projector_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    assert bool(unit.special_rules.get("enhancement_thermoneutronic_projector", False))
    assert int(unit.special_rules.get("enhancement_thermoneutronic_projector_weapon_slot_index", -1)) == 0

    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    first_wound = first_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    second_wound = second_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert first_profile.get_effective_ap(attacker, target) == -1
    assert second_profile.get_effective_ap(attacker, target) == 0
    assert any(
        "Thermoneutronic Projector" in str(entry) and "+2S" in str(entry)
        for entry in first_wound.get("modifiers", [])
    )
    assert not any("Thermoneutronic Projector" in str(entry) for entry in second_wound.get("modifiers", []))


def test_plasma_accelerator_rifle_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000009983004")
    assert desc is not None
    assert desc.name == "Plasma Accelerator Rifle"
    assert desc.effect == "selected_ranged_weapon_strength_ap_damage_bonus"
    assert desc.effect_params.get("weapon_name") == "plasma rifle"
    assert int(desc.effect_params.get("strength_bonus", 0) or 0) == 2
    assert int(desc.effect_params.get("attacks_bonus", 0) or 0) == 1
    assert int(desc.effect_params.get("ap_bonus", 0) or 0) == 1
    assert int(desc.effect_params.get("damage_bonus", 0) or 0) == 1


def test_plasma_accelerator_rifle_buffs_selected_plasma_rifle_only():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    plasma_profile, plasma_wargear = make_named_ranged_profile("Plasma Rifle")
    burst_profile, burst_wargear = make_named_ranged_profile("Burst Cannon")
    attacker.wargear.extend([plasma_wargear, burst_wargear])

    enhancement = _plasma_accelerator_rifle_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    plasma_wound = plasma_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    burst_wound = burst_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert plasma_profile.get_effective_ap(attacker, target) == -1
    assert burst_profile.get_effective_ap(attacker, target) == 0
    assert any(
        "Plasma Accelerator Rifle" in str(entry) and "+2S" in str(entry)
        for entry in plasma_wound.get("modifiers", [])
    )
    assert not any("Plasma Accelerator Rifle" in str(entry) for entry in burst_wound.get("modifiers", []))

    selected_attack_count = plasma_profile.preview_attack_count(target, attacker, publish_roll_event=False)
    other_attack_count = burst_profile.preview_attack_count(target, attacker, publish_roll_event=False)
    assert selected_attack_count.num_attacks == 2
    assert other_attack_count.num_attacks == 1
    assert any("Plasma Accelerator Rifle +1A" in str(entry) for entry in selected_attack_count.special_modifiers)
    assert not any("Plasma Accelerator Rifle +1A" in str(entry) for entry in other_attack_count.special_modifiers)

    selected_damage_target = create_unit(
        "Selected Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    other_damage_target = create_unit(
        "Other Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    selected_damage = plasma_profile._damage_target_with_tracking(
        selected_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    other_damage = burst_profile._damage_target_with_tracking(
        other_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    assert any("Plasma Accelerator Rifle +1D" in str(entry) for entry in selected_damage.get("special_effects", []))
    assert not any("Plasma Accelerator Rifle +1D" in str(entry) for entry in other_damage.get("special_effects", []))


def test_plasma_accelerator_rifle_selects_single_matching_weapon_instance():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    first_profile, first_wargear = make_named_ranged_profile("Plasma Rifle")
    second_profile, second_wargear = make_named_ranged_profile("Plasma Rifle")
    attacker.wargear.extend([first_wargear, second_wargear])

    enhancement = _plasma_accelerator_rifle_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    assert bool(unit.special_rules.get("enhancement_plasma_accelerator_rifle", False))
    assert int(unit.special_rules.get("enhancement_plasma_accelerator_rifle_weapon_slot_index", -1)) == 0

    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    first_wound = first_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    second_wound = second_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    first_attack_count = first_profile.preview_attack_count(target, attacker, publish_roll_event=False)
    second_attack_count = second_profile.preview_attack_count(target, attacker, publish_roll_event=False)

    assert first_profile.get_effective_ap(attacker, target) == -1
    assert second_profile.get_effective_ap(attacker, target) == 0
    assert first_attack_count.num_attacks == 2
    assert second_attack_count.num_attacks == 1
    assert any("Plasma Accelerator Rifle +1A" in str(entry) for entry in first_attack_count.special_modifiers)
    assert not any("Plasma Accelerator Rifle +1A" in str(entry) for entry in second_attack_count.special_modifiers)
    assert any(
        "Plasma Accelerator Rifle" in str(entry) and "+2S" in str(entry)
        for entry in first_wound.get("modifiers", [])
    )
    assert not any("Plasma Accelerator Rifle" in str(entry) for entry in second_wound.get("modifiers", []))
