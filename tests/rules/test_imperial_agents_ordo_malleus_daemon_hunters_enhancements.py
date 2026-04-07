import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
from warhammer40k_ai.engine.decision_handlers.movement import _evaluate_reserves_arrival_positions
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.aura_effects import get_enemy_aura_leadership_characteristic_penalty
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="Imperial Agents",
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
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
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, faction_name="Imperial Agents", keywords=None, faction_keywords=None, abilities=None):
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    ia_army = Army.with_detachment("Imperial Agents", "Ordo Malleus Daemon Hunters")
    ia_army.faction_id = "AOI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    ia_player.command_points = 5
    enemy_player.command_points = 5
    return game, ia_player, enemy_player, ia_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _model_positions_for(unit: Unit, position: tuple[float, float, float]) -> list[dict]:
    model_id = str(get_entity_id(unit.models[0]) or "")
    return [
        {
            "model_id": model_id,
            "position": [float(position[0]), float(position[1]), float(position[2])],
            "facing": 0.0,
        }
    ]


def _apply_ordo_malleus_enhancement(
    unit: Unit,
    *,
    enhancement_id: str,
    name: str,
    description: str,
) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="AOI",
        detachment="Ordo Malleus Daemon Hunters",
        detachment_id="000000894",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _rapid_ingress_test_stratagem(*, cp_cost: int = 1) -> Stratagem:
    return Stratagem(
        id="test_rapid_ingress",
        name="Rapid Ingress",
        type="Core - Strategic Ploy Stratagem",
        description="",
        cp_cost=int(cp_cost),
        turn="Opponent's turn",
        phase="Movement phase",
        detachment="",
        faction_id="CORE",
    )


def _make_extra_model(name: str, parent_unit: Unit) -> Model:
    template = parent_unit.models[0]
    model = Model(
        name=str(name),
        movement=int(getattr(template, "movement", getattr(template, "_movement", 6)) or 6),
        toughness=int(getattr(template, "toughness", getattr(template, "_toughness", 4)) or 4),
        save=int(getattr(template, "save", getattr(template, "_save", 3)) or 3),
        wounds=int(getattr(template, "wounds", getattr(template, "_wounds", 3)) or 3),
        leadership=int(getattr(template, "leadership", getattr(template, "_leadership", 7)) or 7),
        objective_control=int(
            getattr(template, "objective_control", getattr(template, "_objective_control", 1)) or 1
        ),
        model_base=template.model_base,
        inv_save=int(getattr(template, "_inv_save", 7) or 7),
        inv_save_condition=getattr(template, "_inv_save_condition", None),
        keywords=list(getattr(template, "keywords", []) or []),
        faction_keywords=list(getattr(template, "faction_keywords", []) or []),
    )
    model.parent_unit = parent_unit
    return model


class _AuraMap:
    def __init__(self, *, enemy_units):
        self._enemy_units = list(enemy_units or [])

    def get_enemy_units(self, _unit):
        return list(self._enemy_units)


def _find_battleshock_clear_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "start_any_phase_clear_battleshock"
    ]


def _choose_option_by_payload_field(game: Game, request, *, player_id: str, field: str, value: str) -> None:
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get(field, "") or "") == str(value or "")
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    if not bool(getattr(result, "ok", False)):
        raise AssertionError(f"Failed to resolve decision for {field}={value}")


def _make_attack_result(profile: WargearProfile, attacker, target_unit: Unit) -> AttackResult:
    return AttackResult(
        weapon_name=profile.name,
        attacker_name=getattr(attacker, "name", "Attacker"),
        target_unit_name=getattr(target_unit, "name", "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(profile.attacks),
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


def _melee_profile(*, attacks: int = 3, skill: int = 3, strength: int = 4, ap: int = 0, damage: int = 1) -> WargearProfile:
    return WargearProfile(
        "Test Blade",
        {
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False),
    )


def _ranged_profile(*, attacks: int = 2, skill: int = 3, strength: int = 4, ap: int = 0, damage: int = 1) -> WargearProfile:
    return WargearProfile(
        "Test Gun",
        {
            "range": "24",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True),
    )


class TestImperialAgentsOrdoMalleusEnhancements(unittest.TestCase):
    def test_ordo_malleus_enhancement_descriptors_registered(self):
        daemon_slayer = get_enhancement_tool_descriptor(enhancement_id="000009134002")
        self.assertIsNotNone(daemon_slayer)
        self.assertEqual(daemon_slayer.name, "Daemon Slayer")
        self.assertEqual(int(daemon_slayer.effect_params.get("bearer_melee_attacks_bonus", 0) or 0), 1)
        self.assertEqual(str(daemon_slayer.effect_params.get("anti_keyword", "") or ""), "DAEMON")
        self.assertEqual(int(daemon_slayer.effect_params.get("anti_value", 0) or 0), 3)

        formidable_resolve = get_enhancement_tool_descriptor(enhancement_id="000009134003")
        self.assertIsNotNone(formidable_resolve)
        self.assertEqual(formidable_resolve.name, "Formidable Resolve")
        self.assertEqual(int(formidable_resolve.effect_params.get("leadership_improvement", 0) or 0), 1)
        self.assertEqual(int(formidable_resolve.effect_params.get("wounds_bonus", 0) or 0), 1)
        self.assertEqual(str(formidable_resolve.effect_params.get("keyword_phrase", "") or ""), "IMPERIUM")

        gift = get_enhancement_tool_descriptor(enhancement_id="000009134004")
        self.assertIsNotNone(gift)
        self.assertEqual(gift.name, "Gift of the Prescient")
        self.assertEqual(tuple(gift.effect_params.get("stratagem_names", ()) or ()), ("RAPID INGRESS",))
        self.assertEqual(
            tuple(gift.effect_params.get("required_target_unit_name_patterns", ()) or ()),
            ("GREY KNIGHTS TERMINATOR SQUAD",),
        )
        self.assertEqual(float(gift.effect_params.get("deep_strike_min_distance", 0.0) or 0.0), 3.0)

        grimoire = get_enhancement_tool_descriptor(enhancement_id="000009134005")
        self.assertIsNotNone(grimoire)
        self.assertEqual(grimoire.name, "Grimoire of True Names (Aura)")
        self.assertEqual(float(grimoire.effect_params.get("range", 0.0) or 0.0), 9.0)
        self.assertEqual(int(grimoire.effect_params.get("leadership_penalty", 0) or 0), 1)
        self.assertEqual(
            tuple(grimoire.effect_params.get("required_target_keywords", ()) or ()),
            ("DAEMON",),
        )

    def test_daemon_slayer_applies_bearer_only_melee_attack_bonus_and_anti_daemon(self):
        _game, _ia_player, _enemy_player, ia_army, enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Ordo Malleus Inquisitor",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        bearer_unit.models.append(_make_extra_model("Inquisitorial Aide", bearer_unit))
        daemon_target = _make_unit(
            "Daemon Pack",
            faction_name="Enemy",
            keywords=["INFANTRY", "DAEMON"],
            faction_keywords=["CHAOS", "DAEMON", "ENEMY"],
        )
        ia_army.add_unit(bearer_unit)
        enemy_army.add_unit(daemon_target)

        _apply_ordo_malleus_enhancement(
            bearer_unit,
            enhancement_id="000009134002",
            name="Daemon Slayer",
            description=(
                "Add 1 to the Attacks characteristic of the bearer's melee weapons, and those weapons have the "
                "[ANTI-DAEMON 3+] ability."
            ),
        )

        bearer_id = str(bearer_unit.special_rules.get("enhancement_bearer_model_id", "") or "")
        bearer_model = next(
            model
            for model in list(bearer_unit.models or [])
            if str(getattr(model, "id", getattr(model, "_id", "")) or "") == bearer_id
        )
        non_bearer_model = next(model for model in list(bearer_unit.models or []) if model is not bearer_model)

        melee_profile = _melee_profile(attacks=3)
        bearer_result = _make_attack_result(melee_profile, bearer_model, daemon_target)
        bearer_attacks = melee_profile._resolve_attack_count(
            daemon_target,
            bearer_model,
            bearer_result,
            publish_roll_event=False,
        )
        other_result = _make_attack_result(melee_profile, non_bearer_model, daemon_target)
        other_attacks = melee_profile._resolve_attack_count(
            daemon_target,
            non_bearer_model,
            other_result,
            publish_roll_event=False,
        )
        self.assertEqual(int(bearer_attacks.num_attacks), 4)
        self.assertEqual(int(other_attacks.num_attacks), 3)

        bearer_melee = bearer_unit.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=bearer_model,
            weapon_name="Force Blade",
        )
        anti_specs = {tuple(spec) for spec in list(bearer_melee.get("anti_specs") or [])}
        self.assertIn(("DAEMON", 3), anti_specs)

        other_melee = bearer_unit.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=non_bearer_model,
            weapon_name="Close Combat Weapon",
        )
        self.assertEqual(list(other_melee.get("anti_specs") or []), [])

    def test_formidable_resolve_improves_bearer_stats_and_clears_battleshock_once(self):
        game, ia_player, _enemy_player, ia_army, _enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Ordo Malleus Inquisitor",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        target_unit = _make_unit(
            "Imperial Breachers",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(bearer_unit)
        ia_army.add_unit(target_unit)
        _place_unit(game, bearer_unit, 8.0, 8.0)
        _place_unit(game, target_unit, 14.0, 8.0)

        _apply_ordo_malleus_enhancement(
            bearer_unit,
            enhancement_id="000009134003",
            name="Formidable Resolve",
            description=(
                "Improve the bearer's Leadership and Wounds characteristics by 1. Once per battle, at the start of any "
                "phase, you can select one friendly Battle-shocked unit within 12\" of the bearer. That unit is no longer "
                "Battle-shocked."
            ),
        )

        bearer_model = bearer_unit.models[0]
        self.assertEqual(int(bearer_model.leadership or 0), 6)
        self.assertEqual(int(bearer_model.wounds or 0), 4)

        target_unit.apply_status_effect(BattleShockEffect(current_turn=game.turn))
        self.assertTrue(bool(target_unit.is_battle_shocked()))

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game._on_phase_start_optional_abilities(player=ia_player, phase=game.phase)
        requests = _find_battleshock_clear_requests(game)
        self.assertEqual(len(requests), 1)
        request = requests[0]

        _choose_option_by_payload_field(
            game,
            request,
            player_id=ia_player.id,
            field="unit_id",
            value=str(get_entity_id(target_unit) or ""),
        )
        self.assertFalse(bool(target_unit.is_battle_shocked()))

        ability_key = str((request.context or {}).get("ability_key", "") or "")
        self.assertTrue(bool(bearer_unit.has_used_unit_once_per_battle(ability_key)))

        target_unit.apply_status_effect(BattleShockEffect(current_turn=game.turn))
        game._on_phase_start_optional_abilities(player=ia_player, phase=game.phase)
        self.assertEqual(_find_battleshock_clear_requests(game), [])

    def test_grimoire_of_true_names_aura_applies_leadership_hit_and_wound_penalties(self):
        army = Army.with_detachment("Imperial Agents", "Ordo Malleus Daemon Hunters")
        army.faction_id = "AOI"
        source = _make_unit(
            "Ordo Malleus Inquisitor",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        leadership_target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army.add_unit(source)
        _apply_ordo_malleus_enhancement(
            source,
            enhancement_id="000009134005",
            name="Grimoire of True Names (Aura)",
            description=(
                "While an enemy unit is within 9\" of the bearer, worsen the Leadership characteristic of models in that "
                "unit by 1. In addition, while an enemy DAEMON unit is within 9\" of the bearer, each time a model in that "
                "DAEMON unit makes an attack, subtract 1 from the Hit roll and subtract 1 from the Wound roll."
            ),
        )

        game_map = _AuraMap(enemy_units=[source])
        with patch("warhammer40k_ai.utility.aura_effects._iter_possible_abilities", return_value=[]):
            with patch("warhammer40k_ai.utility.aura_effects.model_within_range_of_unit", return_value=True):
                self.assertEqual(get_enemy_aura_leadership_characteristic_penalty(leadership_target, game_map=game_map), 1)
            with patch("warhammer40k_ai.utility.aura_effects.model_within_range_of_unit", return_value=False):
                self.assertEqual(get_enemy_aura_leadership_characteristic_penalty(leadership_target, game_map=game_map), 0)

        game, _ia_player, _enemy_player, ia_army, enemy_army = _build_game()
        source = _make_unit(
            "Ordo Malleus Inquisitor",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        defended_unit = _make_unit(
            "Imperial Breachers",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        daemon_attacker = _make_unit(
            "Daemon Pack",
            faction_name="Enemy",
            keywords=["INFANTRY", "DAEMON"],
            faction_keywords=["CHAOS", "DAEMON", "ENEMY"],
        )
        ia_army.add_unit(source)
        ia_army.add_unit(defended_unit)
        enemy_army.add_unit(daemon_attacker)
        _place_unit(game, source, 8.0, 8.0)
        _place_unit(game, defended_unit, 14.0, 8.0)
        _place_unit(game, daemon_attacker, 16.0, 12.0)

        _apply_ordo_malleus_enhancement(
            source,
            enhancement_id="000009134005",
            name="Grimoire of True Names (Aura)",
            description=(
                "While an enemy unit is within 9\" of the bearer, worsen the Leadership characteristic of models in that "
                "unit by 1. In addition, while an enemy DAEMON unit is within 9\" of the bearer, each time a model in that "
                "DAEMON unit makes an attack, subtract 1 from the Hit roll and subtract 1 from the Wound roll."
            ),
        )

        ranged_profile = _ranged_profile(skill=3, strength=4)
        hit_result = ranged_profile._hit_target_with_tracking(
            defended_unit,
            daemon_attacker.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(int(hit_result["needed"]), 3)
        self.assertEqual(int(hit_result["final_needed"]), 4)
        self.assertTrue(any("Grimoire of True Names" in str(entry) for entry in list(hit_result.get("modifiers") or [])))

        wound_result = ranged_profile._wound_target_with_tracking(
            defended_unit,
            daemon_attacker.models[0],
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(int(wound_result["needed"]), 4)
        self.assertEqual(int(wound_result["final_needed"]), 5)
        self.assertTrue(any("Grimoire of True Names" in str(entry) for entry in list(wound_result.get("modifiers") or [])))

        for model in list(daemon_attacker.models or []):
            model.set_location(30.0, 8.0, 0.0, 0.0)

        far_hit = ranged_profile._hit_target_with_tracking(
            defended_unit,
            daemon_attacker.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(int(far_hit["needed"]), 3)
        self.assertEqual(int(far_hit["final_needed"]), 3)

        far_wound = ranged_profile._wound_target_with_tracking(
            defended_unit,
            daemon_attacker.models[0],
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(int(far_wound["needed"]), 4)
        self.assertEqual(int(far_wound["final_needed"]), 4)

    def test_gift_of_the_prescient_applies_zero_cp_once_per_battle_and_requires_gk_terminator_target(self):
        game, ia_player, _enemy_player, ia_army, _enemy_army = _build_game()
        bearer = _make_unit(
            "Ordo Malleus Inquisitor",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        gk_terminators = _make_unit(
            "Grey Knights Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR", "GREY KNIGHTS"],
            faction_keywords=["IMPERIUM", "GREY KNIGHTS"],
        )
        other_target = _make_unit(
            "Imperial Navy Breachers",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(bearer)
        ia_army.add_unit(gk_terminators)
        ia_army.add_unit(other_target)
        _place_unit(game, bearer, 8.0, 8.0)
        _place_unit(game, other_target, 10.0, 8.0)
        gk_terminators.deployed = False
        gk_terminators.reserve_status = "reserves"

        _apply_ordo_malleus_enhancement(
            bearer,
            enhancement_id="000009134004",
            name="Gift of the Prescient",
            description=(
                "Once per battle, if the bearer is on the battlefield, you can use the Rapid Ingress Stratagem for 0CP. "
                "When doing so, you must target a GREY KNIGHTS TERMINATOR SQUAD unit from your army, and when using that "
                "Stratagem, that unit can be set up anywhere on the battlefield that is more than 3\" away from all enemy units."
            ),
        )

        rapid_ingress = _rapid_ingress_test_stratagem(cp_cost=1)

        non_eligible_preview = ia_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=other_target)
        self.assertEqual(int(non_eligible_preview.get("cost", -1)), 1)

        preview = ia_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=gk_terminators)
        self.assertEqual(int(preview.get("cost", -1)), 0)
        self.assertTrue(any("Gift of the Prescient" in str(r) for r in list(preview.get("reasons", []) or [])))

        first = ia_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=gk_terminators)
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertTrue(bool(first.get("gift_of_the_prescient_use", False)))
        self.assertEqual(float(first.get("gift_of_the_prescient_deep_strike_min_distance", 0.0) or 0.0), 3.0)
        self.assertTrue(bool(bearer.has_used_unit_once_per_battle("gift_of_the_prescient_rapid_ingress")))

        second = ia_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=gk_terminators)
        self.assertEqual(int(second.get("cost", -1)), 1)
        self.assertFalse(bool(second.get("gift_of_the_prescient_use", False)))

    def test_gift_of_the_prescient_allows_rapid_ingress_setup_more_than_three_from_enemy(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        bearer = _make_unit(
            "Inquisitor Lord",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        gk_terminators = _make_unit(
            "Grey Knights Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR", "GREY KNIGHTS"],
            faction_keywords=["IMPERIUM", "GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(bearer)
        ia_army.add_unit(gk_terminators)
        enemy_army.add_unit(enemy)

        _place_unit(game, bearer, 8.0, 8.0)
        _place_unit(game, enemy, 28.0, 20.0)

        gk_terminators.deployed = False
        gk_terminators.reserve_status = "reserves"
        gk_terminators._started_in_reserves = True
        gk_terminators.special_rules["bearer_unit_deep_strike"] = True

        _apply_ordo_malleus_enhancement(
            bearer,
            enhancement_id="000009134004",
            name="Gift of the Prescient",
            description=(
                "Once per battle, if the bearer is on the battlefield, you can use the Rapid Ingress Stratagem for 0CP. "
                "When doing so, you must target a GREY KNIGHTS TERMINATOR SQUAD unit from your army, and when using that "
                "Stratagem, that unit can be set up anywhere on the battlefield that is more than 3\" away from all enemy units."
            ),
        )

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 1  # Opponent's turn
        ia_player.command_points = 0
        enemy_player.command_points = 5

        near_enemy_position = (21.0, 20.0, 0.0)
        evaluation_before = _evaluate_reserves_arrival_positions(
            game,
            gk_terminators,
            _model_positions_for(gk_terminators, near_enemy_position),
        )
        self.assertTrue(bool(list(evaluation_before.get("errors") or [])))

        used = ia_player.stratagems.use(
            "RAPID INGRESS",
            unit=gk_terminators,
            phase_name="Movement phase",
            position=near_enemy_position,
        )
        self.assertTrue(bool(used))
        self.assertEqual(int(ia_player.command_points or 0), 0)
        self.assertTrue(bool(gk_terminators.deployed))
        self.assertEqual(str(gk_terminators.reserve_status or ""), "deployed")
        self.assertNotIn("gift_of_the_prescient_deep_strike_min_distance", gk_terminators.special_rules)


if __name__ == "__main__":
    unittest.main()
