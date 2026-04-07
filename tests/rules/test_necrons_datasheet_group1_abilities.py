import unittest
from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Necrons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    return Unit(datasheet)


def _build_game():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army.with_detachment("Necrons", "Det")
    army1.faction_id = "NEC"
    army2 = Army.with_detachment("Enemy", "Det")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


class TestNecronsDatasheetGroup1Abilities(unittest.TestCase):
    def test_chronometron_parses_post_shoot_reactive_move(self):
        ability = {
            "name": "Chronometron",
            "description": (
                "In your Shooting phase, after this model's unit has shot, if it is not within Engagement Range of any enemy "
                "units, that unit can make a Normal move of up to 5\" as if it were your Movement phase. If it does, until "
                "the end of the turn, that unit is not eligible to declare a charge."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Chronomancer", abilities=[ability])
        specs = unit.unit_post_shoot_reactive_move_no_charge_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("range", 0)), 5)
        self.assertTrue(bool(specs[0].get("requires_not_engaged", False)))

    def test_evasion_engrams_parses_post_shoot_reactive_move(self):
        ability = {
            "name": "Evasion Engrams",
            "description": (
                "In your Shooting phase, after this unit has shot, it can make a Normal move of up to 6\". If it does, until "
                "the end of the turn, this unit is not eligible to declare a charge."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Tomb Blades", abilities=[ability])
        specs = unit.unit_post_shoot_reactive_move_no_charge_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("range", 0)), 6)
        self.assertFalse(bool(specs[0].get("requires_not_engaged", True)))

    def test_targeting_relay_parses_post_shoot_no_cover(self):
        ability = {
            "name": "Targeting Relay",
            "description": (
                "In your Shooting phase, each time this model is selected to shoot, after resolving its attacks, select one "
                "enemy unit that was hit by one or more of those attacks. Until the end of the phase, that unit cannot have "
                "the Benefit of Cover."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Triarch Stalker", abilities=[ability])
        specs = unit.unit_post_shoot_no_cover_specs()
        self.assertEqual(len(specs), 1)
        self.assertTrue(bool(specs[0].get("any_weapon", False)))
        self.assertEqual(str(specs[0].get("duration", "")), "phase_end")

    def test_implacable_eradication_grants_full_wound_reroll_on_objective_target(self):
        ability = {
            "name": "Implacable Eradication",
            "description": (
                "Each time a model in this unit makes an attack, re-roll a Wound roll of 1. If the target of that attack is "
                "an enemy unit within range of an objective marker, you can re-roll the Wound roll instead."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        attacker = _make_unit("Immortals", abilities=[ability])
        target = _make_unit("Enemy")
        army1.add_unit(attacker)
        army2.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target]
        game.map.add_objective(
            Objective(
                name="Obj",
                category=ObjectiveCategory.PRIMARY,
                points=0,
                description="",
                conditions=lambda _g: False,
                location=ObjectivePoint(10.0, 0.0, 0.0, control_radius=3.0),
            )
        )

        mods = attacker.get_unit_wound_reroll_modifiers("ranged", target=target)
        self.assertIn(1, tuple(mods.get("reroll_wound_values", ())))
        self.assertTrue(bool(mods.get("reroll_wound_full", False)))

    def test_hard_wired_for_destruction_full_reroll_only_on_enemy_controlled_objective(self):
        from warhammer40k_ai.units import wargear as wargear_mod
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Hard-wired for Destruction",
            "description": (
                "Each time a model in this unit makes a ranged attack that targets the closest eligible enemy unit, re-roll "
                "a Hit roll of 1. If the target of that attack is within range of an objective marker your opponent controls, "
                "you can re-roll the Hit roll instead."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, p2 = _build_game()
        attacker = _make_unit("Lokhust Destroyers", abilities=[ability])
        target = _make_unit("Target")
        other = _make_unit("Other Target")
        army1.add_unit(attacker)
        army2.add_unit(target)
        army2.add_unit(other)

        attacker.deployed = True
        target.deployed = True
        other.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        other.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target, other]

        objective = Objective(
            name="Obj",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=ObjectivePoint(10.0, 0.0, 0.0, control_radius=3.0),
        )
        objective.location.controlling_player = p2
        game.map.add_objective(objective)

        parent = SimpleNamespace(name="Gauss", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        rolls = iter([2, 6, 6, 6, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls, 6)
        try:
            result = profile.attack(target, attacker.models[0], game_map=game.map)
        finally:
            wargear_mod.get_roll = original_roll
        self.assertIsNotNone(result.hit_results[0].get("reroll"))

        objective.location.controlling_player = p1
        rolls = iter([2, 6, 6, 6, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls, 6)
        try:
            result = profile.attack(target, attacker.models[0], game_map=game.map)
        finally:
            wargear_mod.get_roll = original_roll
        self.assertIsNone(result.hit_results[0].get("reroll"))

    def test_driven_by_hatred_full_hit_and_wound_rerolls_vs_below_half(self):
        ability = {
            "name": "Driven by Hatred",
            "description": (
                "Each time this model makes an attack that targets an enemy unit that is Below Half-strength, you can "
                "re-roll the Hit roll and you can re-roll the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Lokhust Lord", abilities=[ability])
        model = attacker.models[0]
        target = _make_unit("Enemy")
        target.is_below_half_strength = lambda: True
        target.is_below_starting_strength = lambda: True

        hit_mods = attacker.get_model_hit_reroll_modifiers(model=model, target=target)
        wound_mods = attacker.get_model_wound_reroll_modifiers(model=model, target=target)
        self.assertTrue(bool(hit_mods.get("reroll_hit_full", False)))
        self.assertTrue(bool(wound_mods.get("reroll_wound_full", False)))

        target.is_below_half_strength = lambda: False
        target.is_below_starting_strength = lambda: False
        hit_mods = attacker.get_model_hit_reroll_modifiers(model=model, target=target)
        wound_mods = attacker.get_model_wound_reroll_modifiers(model=model, target=target)
        self.assertFalse(bool(hit_mods.get("reroll_hit_full", False)))
        self.assertFalse(bool(wound_mods.get("reroll_wound_full", False)))

    def test_whirling_onslaught_charge_upgrades_to_full_hit_reroll(self):
        ability = {
            "name": "Whirling Onslaught",
            "description": (
                "Each time a model in this unit makes a melee attack, re-roll a Hit roll of 1. If this unit made a Charge "
                "move this turn, you can re-roll the Hit roll instead."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Skorpekh Destroyers", abilities=[ability])
        target = _make_unit("Enemy")

        attacker.round_state.charged_this_round = False
        mods = attacker.get_unit_hit_reroll_modifiers("melee", target=target)
        self.assertIn(1, tuple(mods.get("reroll_hit_values", ())))
        self.assertFalse(bool(mods.get("reroll_hit_full", False)))

        attacker.round_state.charged_this_round = True
        mods = attacker.get_unit_hit_reroll_modifiers("melee", target=target)
        self.assertTrue(bool(mods.get("reroll_hit_full", False)))

    def test_plasmacyte_parses_selected_fight_devastating_wounds_spec(self):
        ability = {
            "name": "Plasmacyte",
            "description": (
                "Once per battle for each Plasmacyte this unit has, when this unit is selected to fight, you can use "
                "this ability. If you do, until the end of the phase, melee weapons equipped by models in this unit "
                "have the [DEVASTATING WOUNDS] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Skorpekh Destroyers", abilities=[ability])
        specs = unit.unit_plasmacyte_specs()
        self.assertEqual(len(specs), 1)
        self.assertTrue(bool(specs[0].get("per_plasmacyte", False)))

    def test_sentinel_construct_overwatch_threshold(self):
        ability = {
            "name": "Sentinel Construct",
            "description": (
                "Each time you target this unit with the Fire Overwatch Stratagem, while resolving that Stratagem, "
                "hits are scored on unmodified Hit rolls of 5+."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        unit = _make_unit("Canoptek Doomstalker", abilities=[ability])
        enemy = _make_unit("Enemy")
        army1.add_unit(unit)
        army2.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        self.assertEqual(unit.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game), 5)

    def test_sentinel_construct_overwatch_threshold_when_resolving_wording(self):
        ability = {
            "name": "Sentinel Construct",
            "description": (
                "Each time you target this unit with the Fire Overwatch Stratagem, hits are scored on unmodified Hit "
                "rolls of 5+ when resolving that Stratagem."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        unit = _make_unit("Canoptek Doomstalker", abilities=[ability])
        enemy = _make_unit("Enemy")
        army1.add_unit(unit)
        army2.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        self.assertEqual(unit.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game), 5)

    def test_atavistic_instigation_parses_model_weapon_choice_spec(self):
        ability = {
            "name": "Atavistic Instigation",
            "description": (
                "Each time this model targets an enemy unit with its heavy death ray, your opponent must declare if that unit "
                "will stand firm or duck for cover: - If it stands firm, when resolving ranged attacks against that unit this "
                "phase, a successful unmodified Hit roll of 5+ scores a Critical Hit. - If it ducks for cover, until the start "
                "of your next Shooting phase, each time a model in that unit makes an attack, subtract 1 from the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Doom Scythe", abilities=[ability])
        specs = unit.model_atavistic_instigation_specs(unit.models[0])
        self.assertEqual(len(specs), 1)
        self.assertEqual(str(specs[0].get("weapon_key", "")), "heavy death ray")
        self.assertEqual(int(specs[0].get("stand_firm_crit_hit_threshold", 0)), 5)
        self.assertEqual(int(specs[0].get("duck_hit_roll_penalty", 0)), 1)

    def test_atavistic_instigation_queues_opponent_choice_for_heavy_death_ray_target(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.game import BattleRoundPhases

        ability = {
            "name": "Atavistic Instigation",
            "description": (
                "Each time this model targets an enemy unit with its heavy death ray, your opponent must declare if that unit "
                "will stand firm or duck for cover: - If it stands firm, when resolving ranged attacks against that unit this "
                "phase, a successful unmodified Hit roll of 5+ scores a Critical Hit. - If it ducks for cover, until the start "
                "of your next Shooting phase, each time a model in that unit makes an attack, subtract 1 from the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, p2 = _build_game()
        source = _make_unit("Doom Scythe", abilities=[ability])
        target = _make_unit("Enemy")
        army1.add_unit(source)
        army2.add_unit(target)
        source.deployed = True
        target.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target]
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1
        game.rebuild_entity_registry()

        heavy_profile = SimpleNamespace(parent_wargear=SimpleNamespace(name="heavy death ray"), name="Heavy Profile")
        tesla_profile = SimpleNamespace(parent_wargear=SimpleNamespace(name="tesla destructor"), name="Tesla Profile")
        game._on_shooting_targets_selected_atavistic_instigation(
            attacking_unit=source,
            target_units=[target],
            weapon_declarations=[
                {"weapon_profile": heavy_profile, "target_unit": target, "models": [source.models[0]]},
                {"weapon_profile": tesla_profile, "target_unit": target, "models": [source.models[0]]},
            ],
        )

        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "atavistic_instigation"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.player_id, p2.id)
        choices = {str((opt.payload or {}).get("atavistic_instigation_choice", "") or "") for opt in list(request.options or [])}
        self.assertEqual(choices, {"stand_firm", "duck_for_cover"})
        self.assertNotEqual(p1.id, request.player_id)

    def test_atavistic_instigation_stand_firm_applies_ranged_crit_threshold_this_phase(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command

        ability = {
            "name": "Atavistic Instigation",
            "description": (
                "Each time this model targets an enemy unit with its heavy death ray, your opponent must declare if that unit "
                "will stand firm or duck for cover: - If it stands firm, when resolving ranged attacks against that unit this "
                "phase, a successful unmodified Hit roll of 5+ scores a Critical Hit. - If it ducks for cover, until the start "
                "of your next Shooting phase, each time a model in that unit makes an attack, subtract 1 from the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, p2 = _build_game()
        source = _make_unit("Doom Scythe", abilities=[ability])
        target = _make_unit("Enemy")
        army1.add_unit(source)
        army2.add_unit(target)
        source.deployed = True
        target.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target]
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1
        game.rebuild_entity_registry()

        heavy_profile = SimpleNamespace(parent_wargear=SimpleNamespace(name="heavy death ray"), name="Heavy Profile")
        game._on_shooting_targets_selected_atavistic_instigation(
            attacking_unit=source,
            target_units=[target],
            weapon_declarations=[{"weapon_profile": heavy_profile, "target_unit": target, "models": [source.models[0]]}],
        )
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "atavistic_instigation"
        )
        option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("atavistic_instigation_choice", "")) == "stand_firm"
        )
        result = resolve_decision_command(game, request, option.option_id, player_id=p2.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        sr = getattr(target, "special_rules", {}) or {}
        self.assertTrue(bool(sr.get("atavistic_instigation_stand_firm_active")))
        self.assertEqual(int(sr.get("atavistic_instigation_stand_firm_value", 0)), 5)

        ranged_mods = source.get_unit_hit_reroll_modifiers("ranged", target=target)
        self.assertEqual(int(ranged_mods.get("crit_hit_threshold", 0) or 0), 5)
        melee_mods = source.get_unit_hit_reroll_modifiers("melee", target=target)
        self.assertEqual(int(melee_mods.get("crit_hit_threshold", 0) or 0), 0)

        game._on_phase_end_cleanup(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
        self.assertFalse(bool((target.special_rules or {}).get("atavistic_instigation_stand_firm_active")))

    def test_atavistic_instigation_duck_for_cover_applies_hit_penalty_until_owner_next_shooting(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.units import wargear as wargear_mod
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Atavistic Instigation",
            "description": (
                "Each time this model targets an enemy unit with its heavy death ray, your opponent must declare if that unit "
                "will stand firm or duck for cover: - If it stands firm, when resolving ranged attacks against that unit this "
                "phase, a successful unmodified Hit roll of 5+ scores a Critical Hit. - If it ducks for cover, until the start "
                "of your next Shooting phase, each time a model in that unit makes an attack, subtract 1 from the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, p2 = _build_game()
        source = _make_unit("Doom Scythe", abilities=[ability])
        ducked = _make_unit("Enemy")
        army1.add_unit(source)
        army2.add_unit(ducked)
        source.deployed = True
        ducked.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        ducked.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [source, ducked]
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1
        game.rebuild_entity_registry()

        heavy_profile = SimpleNamespace(parent_wargear=SimpleNamespace(name="heavy death ray"), name="Heavy Profile")
        game._on_shooting_targets_selected_atavistic_instigation(
            attacking_unit=source,
            target_units=[ducked],
            weapon_declarations=[{"weapon_profile": heavy_profile, "target_unit": ducked, "models": [source.models[0]]}],
        )
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "atavistic_instigation"
        )
        option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("atavistic_instigation_choice", "")) == "duck_for_cover"
        )
        result = resolve_decision_command(game, request, option.option_id, player_id=p2.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertTrue(bool((ducked.special_rules or {}).get("atavistic_instigation_duck_active")))

        parent = SimpleNamespace(name="Blaster", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={"range": "24", "A": "1", "BS_WS": "4+", "S": "4", "AP": "0", "D": "1", "description": ""},
            parent_wargear=parent,
        )
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: 4
        try:
            attack_with_penalty = profile.attack(source, ducked.models[0], game_map=game.map)
        finally:
            wargear_mod.get_roll = original_roll
        self.assertEqual(int(attack_with_penalty.hit_results[0].get("final_needed", 0) or 0), 5)

        game._on_phase_start_post_shoot_duration_cleanup(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
        self.assertFalse(bool((ducked.special_rules or {}).get("atavistic_instigation_duck_active")))

        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: 4
        try:
            attack_after_cleanup = profile.attack(source, ducked.models[0], game_map=game.map)
        finally:
            wargear_mod.get_roll = original_roll
        self.assertEqual(int(attack_after_cleanup.hit_results[0].get("final_needed", 0) or 0), 4)

    def test_multi_threat_eliminator_parses_reactive_shoot_rule(self):
        ability = {
            "name": "Multi-threat Eliminator",
            "description": (
                "Once per turn, in your opponent's Shooting phase, when an enemy unit makes a ranged attack that targets a "
                "friendly NECRONS unit within 3\" of a model with this ability, after that enemy unit has shot, one model "
                "with this ability that is within 3\" of that target can shoot as if it were your Shooting phase, but it must "
                "target only that enemy unit when doing so, and can only do so if that enemy unit is an eligible target."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit(
            "Hexmark Destroyer",
            abilities=[ability],
            keywords=["NECRONS", "INFANTRY", "CHARACTER"],
            faction_keywords=["NECRONS"],
        )
        rule = unit.get_guns_blazing_rule()
        self.assertIsNotNone(rule)
        self.assertEqual(str((rule or {}).get("source", "") or ""), "Multi-threat Eliminator")
        self.assertEqual(str((rule or {}).get("friendly_keyword", "") or ""), "NECRONS")
        self.assertEqual(int((rule or {}).get("range", 0) or 0), 3)

    def test_multi_threat_eliminator_queues_reactive_shooting_decision(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        ability = {
            "name": "Multi-threat Eliminator",
            "description": (
                "Once per turn, in your opponent's Shooting phase, when an enemy unit makes a ranged attack that targets a "
                "friendly NECRONS unit within 3\" of a model with this ability, after that enemy unit has shot, one model "
                "with this ability that is within 3\" of that target can shoot as if it were your Shooting phase, but it must "
                "target only that enemy unit when doing so, and can only do so if that enemy unit is an eligible target."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, _p2 = _build_game()
        enemy_attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"])
        friendly_target = _make_unit(
            "Necron Warriors",
            keywords=["NECRONS", "INFANTRY"],
            faction_keywords=["NECRONS"],
        )
        hexmark = _make_unit(
            "Hexmark Destroyer",
            abilities=[ability],
            keywords=["NECRONS", "INFANTRY", "CHARACTER"],
            faction_keywords=["NECRONS"],
        )
        army2.add_unit(enemy_attacker)
        army1.add_unit(friendly_target)
        army1.add_unit(hexmark)
        enemy_attacker.deployed = True
        friendly_target.deployed = True
        hexmark.deployed = True
        enemy_attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        friendly_target.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        hexmark.models[0].set_location(7.0, 0.0, 0.0, 0.0)
        game.map.units = [enemy_attacker, friendly_target, hexmark]
        game.current_player_index = 1
        game.rebuild_entity_registry()
        game._setup_reactive_can_shoot_target = lambda _unit, _target: True

        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=enemy_attacker,
            target_units=[friendly_target],
        )
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=enemy_attacker,
            hits_by_target={friendly_target: 1},
        )

        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_DECLARE_SHOTS)
        self.assertTrue(bool((request.context or {}).get("guns_blazing_flow", False)))
        self.assertEqual(str((request.context or {}).get("guns_blazing_source", "") or ""), "Multi-threat Eliminator")
        self.assertEqual(request.player_id, p1.id)
        self.assertEqual(
            str((request.context or {}).get("force_target_unit_id", "") or ""),
            str(get_entity_id(enemy_attacker) or ""),
        )

    def test_mechanical_augmentation_parses_aura_rule(self):
        ability = {
            "name": "Mechanical Augmentation (Aura)",
            "description": (
                "While a friendly Necrons Battleline unit is within 3\" of this model, each time a model in that unit "
                "makes an attack, improve the Armour Penetration characteristic of that attack by 1, and each time an "
                "attack targets that unit, worsen the Armour Penetration characteristic of that attack by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        szeras = _make_unit(
            "Illuminor Szeras",
            abilities=[ability],
            keywords=["NECRONS", "CHARACTER", "INFANTRY"],
            faction_keywords=["NECRONS"],
        )
        rule = szeras.get_mechanical_augmentation_aura_rule()
        self.assertIsNotNone(rule)
        self.assertEqual(str((rule or {}).get("friendly_keyword_phrase", "") or ""), "NECRONS BATTLELINE")
        self.assertEqual(int((rule or {}).get("base_range", 0) or 0), 3)
        self.assertEqual(int((rule or {}).get("range", 0) or 0), 3)
        self.assertEqual(int((rule or {}).get("attack_ap_bonus", 0) or 0), 1)
        self.assertEqual(int((rule or {}).get("incoming_ap_worsen", 0) or 0), 1)

    def test_mechanical_augmentation_improves_battleline_attack_ap_within_aura(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Mechanical Augmentation (Aura)",
            "description": (
                "While a friendly Necrons Battleline unit is within 3\" of this model, each time a model in that unit "
                "makes an attack, improve the Armour Penetration characteristic of that attack by 1, and each time an "
                "attack targets that unit, worsen the Armour Penetration characteristic of that attack by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        szeras = _make_unit(
            "Illuminor Szeras",
            abilities=[ability],
            keywords=["NECRONS", "CHARACTER", "INFANTRY"],
            faction_keywords=["NECRONS"],
        )
        battleline = _make_unit(
            "Necron Warriors",
            keywords=["NECRONS", "INFANTRY", "BATTLELINE"],
            faction_keywords=["NECRONS"],
        )
        enemy = _make_unit("Enemy")
        army1.add_unit(szeras)
        army1.add_unit(battleline)
        army2.add_unit(enemy)
        szeras.deployed = True
        battleline.deployed = True
        enemy.deployed = True
        szeras.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        battleline.models[0].set_location(2.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [szeras, battleline, enemy]

        parent = SimpleNamespace(name="Gauss Flayer", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={"range": "24", "A": "1", "BS_WS": "4+", "S": "4", "AP": "0", "D": "1", "description": ""},
            parent_wargear=parent,
        )
        self.assertEqual(profile.get_effective_ap(battleline.models[0], enemy), -1)

        battleline.models[0].set_location(6.5, 0.0, 0.0, 0.0)
        self.assertEqual(profile.get_effective_ap(battleline.models[0], enemy), 0)

    def test_mechanical_augmentation_worsens_incoming_ap_against_battleline_within_aura(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Mechanical Augmentation (Aura)",
            "description": (
                "While a friendly Necrons Battleline unit is within 3\" of this model, each time a model in that unit "
                "makes an attack, improve the Armour Penetration characteristic of that attack by 1, and each time an "
                "attack targets that unit, worsen the Armour Penetration characteristic of that attack by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        szeras = _make_unit(
            "Illuminor Szeras",
            abilities=[ability],
            keywords=["NECRONS", "CHARACTER", "INFANTRY"],
            faction_keywords=["NECRONS"],
        )
        battleline = _make_unit(
            "Necron Warriors",
            keywords=["NECRONS", "INFANTRY", "BATTLELINE"],
            faction_keywords=["NECRONS"],
        )
        enemy = _make_unit("Enemy Shooters")
        army1.add_unit(szeras)
        army1.add_unit(battleline)
        army2.add_unit(enemy)
        szeras.deployed = True
        battleline.deployed = True
        enemy.deployed = True
        szeras.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        battleline.models[0].set_location(2.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(14.0, 0.0, 0.0, 0.0)
        game.map.units = [szeras, battleline, enemy]

        parent = SimpleNamespace(name="Enemy Rifle", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={"range": "24", "A": "1", "BS_WS": "4+", "S": "4", "AP": "-2", "D": "1", "description": ""},
            parent_wargear=parent,
        )
        self.assertEqual(profile.get_effective_ap(enemy.models[0], battleline), -1)

        battleline.models[0].set_location(7.5, 0.0, 0.0, 0.0)
        self.assertEqual(profile.get_effective_ap(enemy.models[0], battleline), -2)

    def test_atomic_energy_manipulator_increases_mechanical_augmentation_range_to_max(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases

        mechanical = {
            "name": "Mechanical Augmentation (Aura)",
            "description": (
                "While a friendly Necrons Battleline unit is within 3\" of this model, each time a model in that unit "
                "makes an attack, improve the Armour Penetration characteristic of that attack by 1, and each time an "
                "attack targets that unit, worsen the Armour Penetration characteristic of that attack by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        atomic = {
            "name": "Atomic Energy Manipulator",
            "description": (
                "At the end of the Fight phase, if this model destroyed one or more models this phase, until the end of "
                "the battle, add 3\" to the range of its Mechanical Augmentation ability to a max of 12."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, _p2 = _build_game()
        szeras = _make_unit(
            "Illuminor Szeras",
            abilities=[mechanical, atomic],
            keywords=["NECRONS", "CHARACTER", "INFANTRY"],
            faction_keywords=["NECRONS"],
        )
        enemy = _make_unit("Enemy")
        army1.add_unit(szeras)
        army2.add_unit(enemy)
        szeras.deployed = True
        enemy.deployed = True
        game.map.units = [szeras, enemy]
        game.current_player_index = 0
        game.rebuild_entity_registry()

        melee_profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_melee=lambda: True, is_ranged=lambda: False))
        for turn, expected_range in ((1, 6), (2, 9), (3, 12), (4, 12)):
            game.turn = int(turn)
            game.phase = BattleRoundPhases.FIGHT_PHASE
            game._on_model_destroyed_rules(
                attacker_model=szeras.models[0],
                attacker_unit=szeras,
                target_model=enemy.models[0],
                target_unit=enemy,
                weapon_profile=melee_profile,
            )
            game._on_phase_end_necrons_atomic_energy_manipulator(player=p1, phase=BattleRoundPhases.FIGHT_PHASE)
            rule = szeras.get_mechanical_augmentation_aura_rule() or {}
            self.assertEqual(int(rule.get("range", 0) or 0), int(expected_range))


if __name__ == "__main__":
    unittest.main()
