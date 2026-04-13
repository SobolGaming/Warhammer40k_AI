from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import StratagemManager
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str | None = None,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: str = "4",
        datasheet_abilities=None,
    ) -> None:
        self.id = str(datasheet_id or f"ds_{name.lower().replace(' ', '_')}")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "5",
                "Sv": "2",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(datasheet_abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str | None = None,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: str = "4",
    datasheet_abilities=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            datasheet_abilities=datasheet_abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army.with_detachment("Chaos Space Marines", "Warpstrike Champions")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", control=PlayerControl.LOCAL, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.turn = 1
    return game, csm_army, enemy_army, csm_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="CSM",
        detachment="Warpstrike Champions",
        points=20,
        description=str(enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if bearer_id and str(get_entity_id(model) or "") == bearer_id:
            return model
    return list(getattr(unit, "models", []) or [None])[0]


def _other_model(unit: Unit):
    bearer = _bearer_model(unit)
    for model in list(getattr(unit, "models", []) or []):
        if model is not bearer:
            return model
    return None


def _make_profile(*, weapon_type: str, strength: str = "4", attacks: str = "2", damage: str = "1"):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if str(weapon_type).lower() == "melee" else "Ranged",
            "range": "Melee" if str(weapon_type).lower() == "melee" else "24",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _deep_strike_ability():
    return {
        "name": "Deep Strike",
        "description": "Deep Strike",
        "type": "Core",
        "parameter": "",
    }


def _blank_attack_result(profile, attacker_model, target_unit) -> AttackResult:
    return AttackResult(
        weapon_name=str(getattr(profile.parent_wargear, "name", "") or "Weapon"),
        attacker_name=str(getattr(attacker_model, "name", "") or "Attacker"),
        target_unit_name=str(getattr(target_unit, "name", "") or "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(getattr(profile, "attacks", "") or ""),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def test_warpstrike_champions_enhancement_descriptors_registered():
    expected = {
        "000010739002": ("Infernal Fulgurite", "rapid_ingress_zero_cp_with_repeat_bypass"),
        "000010739003": ("Eye of the Warp", "charge_reroll_on_setup_turn"),
        "000010739004": ("Akshur's Binding Runes", "strategic_reserves_setup_round_bonus_for_deep_strike"),
        "000010739005": (
            "Tzagulla",
            "bearer_melee_and_ranged_attacks_strength_ap_bonus_with_setup_turn_damage_bonus",
        ),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_infernal_fulgurite_allows_rapid_ingress_for_zero_cp_once_per_battle():
    game, csm_army, _enemy_army, csm_player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Chaos Terminator Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(bearer)
    bearer.deployed = False
    bearer.reserve_status = "reserves"
    bearer._started_in_reserves = True
    _apply_enhancement(bearer, enhancement_id="000010739002", enhancement_name="Infernal Fulgurite")

    strat = SimpleNamespace(name="Rapid Ingress", cp_cost=1)
    preview = csm_player.preview_stratagem_cp_cost(
        strat,
        target_unit=bearer,
        assume_optional_discounts=True,
    )
    assert int(preview.get("cost", -1)) == 0
    assert any("Infernal Fulgurite" in str(reason) for reason in list(preview.get("reasons", []) or []))

    csm_player.set_next_optional_decision("INFERNAL_FULGURITE_RAPID_INGRESS", True)
    first = csm_player.apply_stratagem_cp_cost(strat, target_unit=bearer)
    assert int(first.get("cost", -1)) == 0
    assert bool(first.get("infernal_fulgurite_use", False))

    second_preview = csm_player.preview_stratagem_cp_cost(
        strat,
        target_unit=bearer,
        assume_optional_discounts=True,
    )
    assert int(second_preview.get("cost", -1)) == 1


def test_infernal_fulgurite_repeat_bypass_allows_second_rapid_ingress_target():
    game, csm_army, _enemy_army, csm_player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Chaos Terminator Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    other = _make_unit(
        "Mutilators",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(bearer)
    csm_army.add_unit(other)
    bearer.deployed = False
    bearer.reserve_status = "reserves"
    bearer._started_in_reserves = True
    other.deployed = False
    other.reserve_status = "reserves"
    other._started_in_reserves = True
    _apply_enhancement(bearer, enhancement_id="000010739002", enhancement_name="Infernal Fulgurite")

    manager = StratagemManager(csm_player)
    manager._used_stratagems_this_phase.add("RAPID INGRESS")
    manager._record_rapid_ingress_use(other)

    assert bool(manager._rapid_ingress_repeat_allowed(target_unit=bearer))
    assert not bool(manager._rapid_ingress_repeat_allowed(target_unit=other))


def test_eye_of_the_warp_rerolls_charge_on_setup_turn_only_while_bearer_alive():
    game, csm_army, _enemy_army, _csm_player, _enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Chaos Terminator Lord",
        keywords=["HERETIC ASTARTES", "CHARACTER", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
        datasheet_abilities=[_deep_strike_ability()],
    )
    csm_army.add_unit(bearer_unit)
    _apply_enhancement(bearer_unit, enhancement_id="000010739003", enhancement_name="Eye of the Warp")

    assert not bool(bearer_unit.can_reroll_charge_roll(game=game))

    bearer_unit.round_state.reinforced_this_round = True
    assert bool(bearer_unit.can_reroll_charge_roll(game=game))

    bearer = _bearer_model(bearer_unit)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    assert not bool(bearer_unit.can_reroll_charge_roll(game=game))


def test_akshurs_binding_runes_allows_turn_one_arrival_only_while_bearer_alive():
    game, csm_army, _enemy_army, csm_player, _enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Chaos Terminator Lord",
        keywords=["HERETIC ASTARTES", "CHARACTER", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
        datasheet_abilities=[_deep_strike_ability()],
    )
    bearer_unit.deployed = False
    bearer_unit.reserve_status = "strategic_reserves"
    bearer_unit._started_in_reserves = True
    csm_army.add_unit(bearer_unit)
    _apply_enhancement(
        bearer_unit,
        enhancement_id="000010739004",
        enhancement_name="Akshur's Binding Runes",
    )

    game.turn = 1
    game.current_player_index = 0
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")

    assert bearer_unit.can_arrive_from_reserves(1)

    bearer = _bearer_model(bearer_unit)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    assert not bearer_unit.can_arrive_from_reserves(1)


def test_tzagulla_applies_bearer_only_ranged_and_melee_bonuses_with_setup_turn_damage_bonus():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Chaos Terminator Lord",
        keywords=["HERETIC ASTARTES", "CHARACTER", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
        datasheet_abilities=[_deep_strike_ability()],
    )
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="10",
    )
    csm_army.add_unit(bearer_unit)
    enemy_army.add_unit(target)
    game.map.units = [bearer_unit, target]
    game.rebuild_entity_registry()

    _apply_enhancement(bearer_unit, enhancement_id="000010739005", enhancement_name="Tzagulla")
    bearer = _bearer_model(bearer_unit)
    other = _other_model(bearer_unit)
    assert bearer is not None
    assert other is not None

    ranged_profile = _make_profile(weapon_type="ranged", strength="4", attacks="2", damage="1")
    melee_profile = _make_profile(weapon_type="melee", strength="4", attacks="2", damage="1")

    bearer_ranged_count = ranged_profile._resolve_attack_count(
        target,
        bearer,
        _blank_attack_result(ranged_profile, bearer, target),
        publish_roll_event=False,
    )
    other_ranged_count = ranged_profile._resolve_attack_count(
        target,
        other,
        _blank_attack_result(ranged_profile, other, target),
        publish_roll_event=False,
    )
    assert int(bearer_ranged_count.num_attacks) == 3
    assert int(other_ranged_count.num_attacks) == 2

    bearer_melee_count = melee_profile._resolve_attack_count(
        target,
        bearer,
        _blank_attack_result(melee_profile, bearer, target),
        publish_roll_event=False,
    )
    other_melee_count = melee_profile._resolve_attack_count(
        target,
        other,
        _blank_attack_result(melee_profile, other, target),
        publish_roll_event=False,
    )
    assert int(bearer_melee_count.num_attacks) == 3
    assert int(other_melee_count.num_attacks) == 2

    bearer_ranged_wound = ranged_profile._wound_target_with_tracking(target, bearer, {}, roll_value=4, log_roll=False)
    other_ranged_wound = ranged_profile._wound_target_with_tracking(target, other, {}, roll_value=4, log_roll=False)
    assert any("+1S from Enhancement bearer (ranged)" in str(mod) for mod in list(bearer_ranged_wound.get("modifiers", []) or []))
    assert not any("+1S from Enhancement bearer (ranged)" in str(mod) for mod in list(other_ranged_wound.get("modifiers", []) or []))

    assert int(ranged_profile.get_effective_ap(bearer, target)) == -1
    assert int(ranged_profile.get_effective_ap(other, target)) == 0
    assert int(melee_profile.get_effective_ap(bearer, target)) == -1
    assert int(melee_profile.get_effective_ap(other, target)) == 0

    bearer_unit.arrived_from_reserves_this_turn = False
    ranged_damage = ranged_profile._damage_target_with_tracking(target.models[0], bearer, {}, allow_rerolls=False)
    melee_damage = melee_profile._damage_target_with_tracking(target.models[0], bearer, {}, allow_rerolls=False)
    assert int(ranged_damage.get("damage_rolled", 0) or 0) == 1
    assert int(melee_damage.get("damage_rolled", 0) or 0) == 1

    bearer_unit.arrived_from_reserves_this_turn = True
    ranged_damage_after_setup = ranged_profile._damage_target_with_tracking(target.models[0], bearer, {}, allow_rerolls=False)
    melee_damage_after_setup = melee_profile._damage_target_with_tracking(target.models[0], bearer, {}, allow_rerolls=False)
    assert int(ranged_damage_after_setup.get("damage_applied", 0) or 0) == 2
    assert int(melee_damage_after_setup.get("damage_applied", 0) or 0) == 2
    assert any("Tzagulla +1D" in str(effect) for effect in list(ranged_damage_after_setup.get("special_effects", []) or []))
    assert any("Tzagulla +1D" in str(effect) for effect in list(melee_damage_after_setup.get("special_effects", []) or []))


def test_warpstrike_champions_support_matrix_classifies_enhancements_supported():
    import scripts.generate_ability_support_matrix as gsm

    expected = {
        "000010739002": "Infernal Fulgurite",
        "000010739003": "Eye of the Warp",
        "000010739004": "Akshur's Binding Runes",
        "000010739005": "Tzagulla",
    }
    for enhancement_id, name in expected.items():
        status, notes = gsm._enhancement_support(name, enhancement_id, name)
        assert status == "Supported"
        assert str(name).split()[0] in notes
