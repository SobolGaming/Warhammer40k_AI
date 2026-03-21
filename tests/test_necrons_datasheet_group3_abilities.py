import unittest
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        objective_control=1,
        model_count=1,
    ):
        self.name = name
        self.faction_data = {"name": "Necrons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        model_count = max(1, int(model_count or 1))
        model_label = "Test Model" if model_count == 1 else "Test Models"
        self.datasheets_unit_composition = [{"description": f"{model_count} {model_label}"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": str(int(objective_control)),
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


def _make_unit(
    name,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    objective_control=1,
    model_count=1,
    quantity=None,
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        objective_control=objective_control,
        model_count=model_count,
    )
    return Unit(datasheet, quantity=quantity)


class TestNecronsDatasheetGroup3Abilities(unittest.TestCase):
    def test_crimson_harvest_parses_charge_end_mortal_table(self):
        ability = {
            "name": "Crimson Harvest",
            "description": (
                "Each time this model ends a Charge move, select one enemy unit within Engagement Range of this model and "
                "roll one D6: on a 2-5, that unit suffers D3 mortal wounds; on a 6, that unit suffers D3+3 mortal wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Skorpekh Lord", abilities=[ability])
        entries = list(unit.special_rules.get("charge_end_mortal_wounds", []) or [])
        self.assertEqual(len(entries), 1)
        self.assertEqual(str(entries[0].get("kind", "")), "table_d6_2_5_6")

    def test_self_destruction_parses_start_fight_malign_variant(self):
        ability = {
            "name": "Self-destruction",
            "description": (
                "At the start of the Fight phase, if this unit is within Engagement Range of one or more enemy units, "
                "you can select one model in this unit to destroy. If you do, select one enemy unit within Engagement "
                "Range of that model and roll one D6, adding 1 to the result if that unit is a VEHICLE. On a 2-5, that "
                "unit suffers D3 mortal wounds; on a 6+, that unit suffers 3 mortal wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Canoptek Scarab Swarms", abilities=[ability])
        specs = unit.unit_start_fight_phase_malign_sacrifice_specs()
        self.assertEqual(len(specs), 1)
        self.assertTrue(bool(specs[0].get("allow_any_model", False)))
        self.assertEqual(int(specs[0].get("roll_bonus_vs_vehicle", 0)), 1)
        self.assertEqual(str(specs[0].get("roll_low_mortal", "")), "d3")
        self.assertEqual(str(specs[0].get("roll_high_mortal", "")), "3")

    def test_chittering_swarm_reduces_enemy_oc_in_engagement_range_with_minimum_one(self):
        ability = {
            "name": "Chittering swarm",
            "description": (
                "While an enemy unit is within Engagement Range of this unit, subtract 1 from the Objective Control "
                "characteristic of models in that enemy unit (to a minimum of 1). While this unit is within 6\" of one "
                "or more friendly CRYPTEK models, the Objective Control characteristic of models in this unit is 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        scarabs = _make_unit("Canoptek Scarab Swarms", abilities=[ability])
        enemy_high_oc = _make_unit("Enemy High OC", objective_control=2)
        enemy_low_oc = _make_unit("Enemy Low OC", objective_control=1)

        class _Map:
            def get_enemy_units(self, unit):
                if unit is enemy_high_oc or unit is enemy_low_oc:
                    return [scarabs]
                return []

            def get_friendly_units(self, unit):
                if unit is scarabs:
                    return [scarabs]
                if unit is enemy_high_oc:
                    return [enemy_high_oc]
                if unit is enemy_low_oc:
                    return [enemy_low_oc]
                return []

            def is_within_engagement_range(self, unit_a, unit_b):
                return (unit_a is scarabs and (unit_b is enemy_high_oc or unit_b is enemy_low_oc)) or (
                    unit_b is scarabs and (unit_a is enemy_high_oc or unit_a is enemy_low_oc)
                )

        game_map = _Map()
        reduced_high = int(enemy_high_oc.get_effective_model_characteristic(enemy_high_oc.models[0], "objective_control", game_map=game_map))
        reduced_low = int(enemy_low_oc.get_effective_model_characteristic(enemy_low_oc.models[0], "objective_control", game_map=game_map))
        self.assertEqual(reduced_high, 1)
        self.assertEqual(reduced_low, 1)

    def test_chittering_swarm_sets_self_oc_when_near_friendly_cryptek(self):
        ability = {
            "name": "Chittering swarm",
            "description": (
                "While an enemy unit is within Engagement Range of this unit, subtract 1 from the Objective Control "
                "characteristic of models in that enemy unit (to a minimum of 1). While this unit is within 6\" of one "
                "or more friendly CRYPTEK models, the Objective Control characteristic of models in this unit is 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        scarabs = _make_unit("Canoptek Scarab Swarms", abilities=[ability], objective_control=2)
        cryptek = _make_unit("Chronomancer", keywords=["CRYPTEK"])

        class _MapNoCryptek:
            def get_enemy_units(self, unit):
                return []

            def get_friendly_units(self, unit):
                if unit is scarabs:
                    return [scarabs]
                return []

            def is_within_engagement_range(self, _unit_a, _unit_b):
                return False

        class _MapWithCryptek:
            def get_enemy_units(self, unit):
                return []

            def get_friendly_units(self, unit):
                if unit is scarabs:
                    return [scarabs, cryptek]
                return []

            def is_within_engagement_range(self, _unit_a, _unit_b):
                return False

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=False):
            baseline_oc = int(
                scarabs.get_effective_model_characteristic(
                    scarabs.models[0],
                    "objective_control",
                    game_map=_MapNoCryptek(),
                )
            )
        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            boosted_oc = int(
                scarabs.get_effective_model_characteristic(
                    scarabs.models[0],
                    "objective_control",
                    game_map=_MapWithCryptek(),
                )
            )

        self.assertEqual(baseline_oc, 2)
        self.assertEqual(boosted_oc, 1)

    def test_canoptek_swarm_parses_command_phase_targeted_return(self):
        ability = {
            "name": "Canoptek Swarm",
            "description": (
                "In your Command phase, select one friendly Canoptek Scarab Swarm unit within 6\" of this unit. "
                "One destroyed model is returned to that CANOPTEK SCARAB SWARM unit for each SPYDER model in this unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        spyders = _make_unit(
            "Canoptek Spyders",
            abilities=[ability],
            keywords=["CANOPTEK", "SPYDER"],
        )
        specs = spyders.unit_canoptek_swarm_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(str(specs[0].get("target_keyword", "")), "canoptek scarab swarm")
        self.assertEqual(str(specs[0].get("count_keyword", "")), "spyder")
        self.assertEqual(int(specs[0].get("range", 0)), 6)

    def test_canoptek_swarm_queues_target_and_bodyguard_return(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE, DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.decisions import DecisionResult
        from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        ability = {
            "name": "Canoptek Swarm",
            "description": (
                "In your Command phase, select one friendly Canoptek Scarab Swarm unit within 6\" of this unit. "
                "One destroyed model is returned to that CANOPTEK SCARAB SWARM unit for each SPYDER model in this unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        spyders = _make_unit(
            "Canoptek Spyders",
            abilities=[ability],
            keywords=["CANOPTEK", "SPYDER"],
            model_count=2,
            quantity=2,
        )
        scarabs = _make_unit(
            "Canoptek Scarab Swarms",
            keywords=["CANOPTEK", "SCARAB", "SWARM", "CANOPTEK SCARAB SWARM"],
            model_count=2,
            quantity=2,
        )
        enemy = _make_unit("Enemy")
        self.assertEqual(len(spyders.models), 2)

        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        army_one = Army("A1", detachment_type="Test")
        army_two = Army("A2", detachment_type="Test")
        player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
        player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
        game.add_player(player_one)
        game.add_player(player_two)

        army_one.add_unit(spyders)
        army_one.add_unit(scarabs)
        army_two.add_unit(enemy)

        for unit in (spyders, scarabs, enemy):
            unit.deployed = True
            unit.reserve_status = "deployed"

        lost = scarabs.models[0]
        scarabs.remove_model(lost)
        self.assertIn(lost, scarabs.models_lost)

        game.map.units = [spyders, scarabs, enemy]
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        game.rebuild_entity_registry()

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            game._on_phase_start_canoptek_swarm(player=player_one, phase=game.phase)

        pending = list(game.decision_queue.list() or [])
        choose_req = None
        for req in pending:
            if req.decision_type != DECISION_CHOOSE_QUARRY:
                continue
            if str((req.context or {}).get("ability", "") or "") == "canoptek_swarm_target":
                choose_req = req
                break
        self.assertIsNotNone(choose_req)
        ctx = dict(choose_req.context or {})
        self.assertEqual(int(ctx.get("return_count", 0) or 0), 2)

        scarab_id = str(get_entity_id(scarabs) or "")
        target_option = None
        for opt in list(choose_req.options or []):
            if str((opt.payload or {}).get("target_unit_id", "") or "") == scarab_id:
                target_option = opt
                break
        self.assertIsNotNone(target_option)

        result = DecisionResult(
            decision_id=choose_req.decision_id,
            player_id=player_one.id,
            option_id=target_option.option_id,
        )
        _apply_choose_quarry(game, choose_req, result)

        pending_after = list(game.decision_queue.list() or [])
        bodyguard_req = None
        for req in pending_after:
            if req.decision_type != DECISION_ALLOCATE_DAMAGE:
                continue
            req_ctx = dict(req.context or {})
            if str(req_ctx.get("selection_kind", "") or "") != "bodyguard_return":
                continue
            if str(req_ctx.get("leader_unit_id", "") or "") != str(get_entity_id(spyders) or ""):
                continue
            if str(req_ctx.get("bodyguard_unit_id", "") or "") != scarab_id:
                continue
            bodyguard_req = req
            break
        self.assertIsNotNone(bodyguard_req)
        bodyguard_ctx = dict(bodyguard_req.context or {})
        self.assertEqual(int(bodyguard_ctx.get("remaining", 0) or 0), 2)
        self.assertFalse(bool(bodyguard_ctx.get("allow_skip", True)))

    def test_tectonic_reverberations_parses_movement_phase_pinned(self):
        ability = {
            "name": "Tectonic Reverberations",
            "description": (
                "In your Movement phase, you can select one enemy unit within 18\" of and visible to this model. "
                "Until the start of your next Movement phase that enemy unit is pinned. While a unit is pinned, "
                "subtract 2 from that unit's Move characteristic and subtract 2 from Charge rolls made for it."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        geomancer = _make_unit("Geomancer", abilities=[ability])
        specs = geomancer.model_movement_phase_pinned_specs(geomancer.models[0])
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("range", 0) or 0), 18)
        self.assertEqual(int(specs[0].get("move_penalty", 0) or 0), -2)
        self.assertEqual(int(specs[0].get("charge_penalty", 0) or 0), -2)
        self.assertEqual(str(specs[0].get("expires_phase", "") or ""), "MOVEMENT_PHASE")

    def test_tectonic_reverberations_queues_choice_applies_and_cleans_up(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        ability = {
            "name": "Tectonic Reverberations",
            "description": (
                "In your Movement phase, you can select one enemy unit within 18\" of and visible to this model. "
                "Until the start of your next Movement phase that enemy unit is pinned. While a unit is pinned, "
                "subtract 2 from that unit's Move characteristic and subtract 2 from Charge rolls made for it."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        geomancer = _make_unit("Geomancer", abilities=[ability], keywords=["NECRONS", "INFANTRY", "CHARACTER"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"])

        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        army_one = Army("A1", detachment_type="Test")
        army_two = Army("A2", detachment_type="Test")
        player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
        player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
        game.add_player(player_one)
        game.add_player(player_two)
        army_one.add_unit(geomancer)
        army_two.add_unit(enemy)

        geomancer.deployed = True
        geomancer.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"
        geomancer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        geomancer._has_line_of_sight_to_target = lambda _model, _target, _map: True
        game.map.units = [geomancer, enemy]
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0
        game.rebuild_entity_registry()

        game._on_phase_end_movement_phase_pinned(player=player_one, phase=game.phase)

        choose_req = None
        for req in list(game.decision_queue.list() or []):
            if req.decision_type != DECISION_CHOOSE_QUARRY:
                continue
            if str((req.context or {}).get("ability", "") or "") != "post_shoot_pinned":
                continue
            choose_req = req
            break
        self.assertIsNotNone(choose_req)
        ctx = dict(choose_req.context or {})
        self.assertEqual(str(ctx.get("expires_phase", "") or ""), "MOVEMENT_PHASE")
        self.assertEqual(int(ctx.get("move_penalty", 0) or 0), -2)
        self.assertEqual(int(ctx.get("charge_penalty", 0) or 0), -2)

        enemy_id = str(get_entity_id(enemy) or "")
        target_option = None
        for option in list(choose_req.options or []):
            if str((option.payload or {}).get("target_unit_id", "") or "") == enemy_id:
                target_option = option
                break
        self.assertIsNotNone(target_option)

        resolve_decision_command(
            game,
            choose_req,
            target_option.option_id,
            player_id=player_one.id,
        )

        sr = dict(getattr(enemy, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("pinned_active", False)))
        self.assertEqual(int(sr.get("pinned_move_penalty", 0) or 0), -2)
        self.assertEqual(int(sr.get("pinned_charge_penalty", 0) or 0), -2)
        self.assertEqual(str(sr.get("pinned_expires_phase", "") or ""), "MOVEMENT_PHASE")

        game._on_phase_start_pinned_cleanup(player=player_one, phase=BattleRoundPhases.MOVEMENT_PHASE)
        cleared = dict(getattr(enemy, "special_rules", {}) or {})
        self.assertFalse(bool(cleared.get("pinned_active", False)))
        self.assertNotIn("pinned_move_penalty", cleared)
        self.assertNotIn("pinned_charge_penalty", cleared)

    def test_gravitic_pulse_parses_start_opponent_movement_phase_spec(self):
        ability = {
            "name": "Gravitic Pulse",
            "description": (
                "At the start of your opponent's Movement phase, select one enemy unit within 18\" of and visible to this "
                "model. Until the end of the turn, halve the Move characteristic of models in that unit and halve Advance "
                "and Charge rolls made for that unit. If that unit can FLY, until the start of your next Movement phase, "
                "roll one D6 each time that unit ends any type of move: on a 4+, that unit suffers D3 mortal wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        obelisk = _make_unit("Obelisk", abilities=[ability], keywords=["NECRONS", "VEHICLE", "FLY"])
        specs = obelisk.model_start_opponent_movement_phase_gravitic_pulse_specs(obelisk.models[0])
        self.assertEqual(len(specs), 1)
        spec = dict(specs[0] or {})
        self.assertEqual(int(spec.get("range", 0) or 0), 18)
        self.assertTrue(bool(spec.get("optional", False)))
        self.assertTrue(bool(spec.get("requires_visibility", False)))
        self.assertTrue(bool(spec.get("half_move_characteristic", False)))
        self.assertTrue(bool(spec.get("half_advance_roll", False)))
        self.assertTrue(bool(spec.get("half_charge_roll", False)))
        self.assertEqual(int(spec.get("fly_mortal_threshold", 0) or 0), 4)
        self.assertEqual(str(spec.get("fly_mortal_wounds", "") or "").upper(), "D3")
        self.assertEqual(str(spec.get("fly_mortal_expires_phase", "") or ""), "MOVEMENT_PHASE")

    def test_gravitic_pulse_queues_applies_roll_halving_triggers_fly_mortals_and_cleans_up(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        ability = {
            "name": "Gravitic Pulse",
            "description": (
                "At the start of your opponent's Movement phase, select one enemy unit within 18\" of and visible to this "
                "model. Until the end of the turn, halve the Move characteristic of models in that unit and halve Advance "
                "and Charge rolls made for that unit. If that unit can FLY, until the start of your next Movement phase, "
                "roll one D6 each time that unit ends any type of move: on a 4+, that unit suffers D3 mortal wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        obelisk = _make_unit("Obelisk", abilities=[ability], keywords=["NECRONS", "VEHICLE", "FLY"])
        enemy_fly = _make_unit("Enemy Fly", keywords=["INFANTRY", "FLY"], model_count=2, quantity=2)
        enemy_ground = _make_unit("Enemy Ground", keywords=["INFANTRY"], model_count=2, quantity=2)

        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        army_one = Army("A1", detachment_type="Test")
        army_two = Army("A2", detachment_type="Test")
        player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
        player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
        game.add_player(player_one)
        game.add_player(player_two)
        army_one.add_unit(obelisk)
        army_two.add_unit(enemy_fly)
        army_two.add_unit(enemy_ground)

        for unit in (obelisk, enemy_fly, enemy_ground):
            unit.deployed = True
            unit.reserve_status = "deployed"

        obelisk.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy_fly.models[0].set_location(12.0, 0.0, 0.0, 0.0)
        enemy_ground.models[0].set_location(10.0, 3.0, 0.0, 0.0)
        obelisk._has_line_of_sight_to_target = lambda _model, _target, _game_map: True
        game.map.units = [obelisk, enemy_fly, enemy_ground]
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 1
        game.turn = 3
        game.rebuild_entity_registry()

        game._on_phase_start_opponent_movement_phase_gravitic_pulse(player=player_two, phase=game.phase)

        choose_req = None
        for req in list(game.decision_queue.list() or []):
            if req.decision_type != DECISION_CHOOSE_QUARRY:
                continue
            if str((req.context or {}).get("ability", "") or "") != "gravitic_pulse_target":
                continue
            choose_req = req
            break
        self.assertIsNotNone(choose_req)

        target_id = str(get_entity_id(enemy_fly) or "")
        target_option = None
        for option in list(choose_req.options or []):
            if str((option.payload or {}).get("target_unit_id", "") or "") == target_id:
                target_option = option
                break
        self.assertIsNotNone(target_option)

        decision_result = resolve_decision_command(
            game,
            choose_req,
            target_option.option_id,
            player_id=player_one.id,
        )
        self.assertTrue(bool(getattr(decision_result, "ok", False)))

        active = dict(getattr(enemy_fly, "special_rules", {}) or {})
        self.assertTrue(bool(active.get("necrons_gravitic_pulse_active", False)))
        self.assertEqual(str(active.get("necrons_gravitic_pulse_turn_owner", "") or ""), player_two.id)
        self.assertEqual(int(active.get("necrons_gravitic_pulse_turn", 0) or 0), 3)
        self.assertEqual(int(active.get("necrons_gravitic_pulse_stacks", 0) or 0), 1)
        self.assertTrue(bool(active.get("necrons_gravitic_pulse_half_advance_roll", False)))
        self.assertTrue(bool(active.get("necrons_gravitic_pulse_half_charge_roll", False)))
        self.assertTrue(bool(active.get("necrons_gravitic_pulse_fly_mortal_active", False)))
        self.assertEqual(str(active.get("necrons_gravitic_pulse_fly_mortal_source_owner", "") or ""), player_one.id)

        move_after = int(
            enemy_fly.get_effective_model_characteristic(
                enemy_fly.models[0],
                "movement",
                game_map=game.map,
            )
        )
        self.assertEqual(move_after, 3)
        self.assertEqual(int(enemy_fly._apply_advance_roll_modifiers(5)), 3)
        self.assertEqual(int(game._apply_charge_modifiers(enemy_fly, 7, target_unit=obelisk)), 4)
        self.assertEqual(int(game.get_max_charge_distance(enemy_fly, target_unit=obelisk)), 6)

        mortal_calls = []

        def _capture_mortals(target, amount, game_map=None, **_kwargs):
            mortal_calls.append((target, int(amount)))

        enemy_fly._apply_mortal_wounds_to_unit = _capture_mortals
        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4, 2]):
            game._on_unit_move_ended_gravitic_pulse(unit=enemy_fly, action="move")
        self.assertEqual(len(mortal_calls), 1)
        self.assertIs(mortal_calls[0][0], enemy_fly)
        self.assertEqual(int(mortal_calls[0][1]), 2)

        game.current_player_index = 0
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game._on_phase_start_gravitic_pulse_cleanup(player=player_one, phase=game.phase)

        cleared = dict(getattr(enemy_fly, "special_rules", {}) or {})
        self.assertFalse(bool(cleared.get("necrons_gravitic_pulse_active", False)))
        self.assertFalse(bool(cleared.get("necrons_gravitic_pulse_fly_mortal_active", False)))
        restored_move = int(
            enemy_fly.get_effective_model_characteristic(
                enemy_fly.models[0],
                "movement",
                game_map=game.map,
            )
        )
        self.assertEqual(restored_move, 6)

    def test_eternity_gate_parses_reinforcements_setup_spec(self):
        ability = {
            "name": "Eternity Gate",
            "description": (
                "In the Reinforcements step of your Movement phase, you can select one NECRONS INFANTRY unit from your "
                "army either in Reserves or on the battlefield. If that unit is on the battlefield, remove that unit "
                "from the battlefield and place it into Reserves. Set up that unit wholly within 6\" of this model and "
                "not within Engagement Range of any enemy models. That unit cannot declare a charge this turn."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Monolith", abilities=[ability], keywords=["NECRONS", "VEHICLE"])
        specs = unit.unit_eternity_gate_specs()
        self.assertEqual(len(specs), 1)
        spec = dict(specs[0] or {})
        self.assertEqual(int(spec.get("range", 0) or 0), 6)
        self.assertTrue(bool(spec.get("allow_target_in_reserves", False)))
        self.assertTrue(bool(spec.get("allow_target_on_battlefield", False)))
        self.assertTrue(bool(spec.get("no_charge_this_turn", False)))

    def test_eternity_gate_queues_target_and_constrains_arrival(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT, DECISION_SELECT_UNIT
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        ability = {
            "name": "Eternity Gate",
            "description": (
                "In the Reinforcements step of your Movement phase, you can select one NECRONS INFANTRY unit from your "
                "army either in Reserves or on the battlefield. If that unit is on the battlefield, remove that unit "
                "from the battlefield and place it into Reserves. Set up that unit wholly within 6\" of this model and "
                "not within Engagement Range of any enemy models. That unit cannot declare a charge this turn."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        monolith = _make_unit("Monolith", abilities=[ability], keywords=["NECRONS", "VEHICLE"])
        infantry = _make_unit("Necron Warriors", keywords=["NECRONS", "INFANTRY"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"])

        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        army_one = Army("A1", detachment_type="Test")
        army_two = Army("A2", detachment_type="Test")
        player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
        player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
        game.add_player(player_one)
        game.add_player(player_two)

        army_one.add_unit(monolith)
        army_one.add_unit(infantry)
        army_two.add_unit(enemy)

        monolith.deployed = True
        monolith.reserve_status = "deployed"
        infantry.deployed = True
        infantry.reserve_status = "reserves"
        enemy.deployed = True
        enemy.reserve_status = "deployed"

        monolith.models[0].set_location(20.0, 20.0, 0.0, 0.0)
        enemy.models[0].set_location(28.0, 20.0, 0.0, 0.0)
        game.map.units = [monolith, enemy]
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0
        game.turn = 2
        game.rebuild_entity_registry()

        game.process_player_reserves_arrivals(player_one)

        choose_req = None
        for req in list(game.decision_queue.list() or []):
            if req.decision_type != DECISION_CHOOSE_QUARRY:
                continue
            if str((req.context or {}).get("ability", "") or "") != "eternity_gate_target":
                continue
            choose_req = req
            break
        self.assertIsNotNone(choose_req)

        infantry_id = str(get_entity_id(infantry) or "")
        target_option = None
        for option in list(choose_req.options or []):
            if str((option.payload or {}).get("target_unit_id", "") or "") == infantry_id:
                target_option = option
                break
        self.assertIsNotNone(target_option)

        selected = resolve_decision_command(
            game,
            choose_req,
            target_option.option_id,
            player_id=player_one.id,
        )
        self.assertTrue(bool(getattr(selected, "ok", False)))

        select_req = None
        for req in list(game.decision_queue.list() or []):
            if req.decision_type != DECISION_SELECT_UNIT:
                continue
            ctx = dict(req.context or {})
            if str(ctx.get("phase_step", "") or "") != "REINFORCEMENTS":
                continue
            if infantry_id not in list(ctx.get("allowed_unit_ids", []) or []):
                continue
            select_req = req
            break
        self.assertIsNotNone(select_req)

        select_option = None
        for option in list(select_req.options or []):
            if str((option.payload or {}).get("unit_id", "") or "") != infantry_id:
                continue
            select_option = option
            break
        self.assertIsNotNone(select_option)
        selected_reinforcement = resolve_decision_command(
            game,
            select_req,
            select_option.option_id,
            player_id=player_one.id,
            result_payload={"unit_id": infantry_id},
        )
        self.assertTrue(bool(getattr(selected_reinforcement, "ok", False)))

        move_req = None
        for req in list(game.decision_queue.list() or []):
            if req.decision_type != DECISION_MOVE_UNIT:
                continue
            ctx = dict(req.context or {})
            if str(ctx.get("placement_kind", "") or "") != "reserves_arrival":
                continue
            if str(ctx.get("unit_id", "") or "") != infantry_id:
                continue
            if str(ctx.get("reserves_arrival_source_ability", "") or "") != "eternity_gate":
                continue
            move_req = req
            break
        self.assertIsNotNone(move_req)
        move_ctx = dict(move_req.context or {})
        self.assertEqual(str(move_ctx.get("reserves_arrival_anchor_unit_id", "") or ""), str(get_entity_id(monolith) or ""))
        self.assertTrue(bool(move_ctx.get("reserves_arrival_anchor_wholly_within", False)))
        self.assertTrue(bool(move_ctx.get("reserves_arrival_require_not_engagement", False)))
        self.assertEqual(float(move_ctx.get("reserves_arrival_min_enemy_distance_override", 9.0)), 0.0)

        confirm_option = list(move_req.options or [None])[0]
        self.assertIsNotNone(confirm_option)

        model_id = str(get_entity_id(infantry.models[0]) or "")
        too_far = resolve_decision_command(
            game,
            move_req,
            confirm_option.option_id,
            result_payload={
                "model_positions": [
                    {"model_id": model_id, "position": [27.5, 20.0, 0.0], "facing": 0.0},
                ]
            },
            player_id=player_one.id,
        )
        self.assertFalse(bool(getattr(too_far, "ok", False)))

        legal_near_enemy = resolve_decision_command(
            game,
            move_req,
            confirm_option.option_id,
            result_payload={
                "model_positions": [
                    {"model_id": model_id, "position": [24.0, 20.0, 0.0], "facing": 0.0},
                ]
            },
            player_id=player_one.id,
        )
        self.assertTrue(bool(getattr(legal_near_enemy, "ok", False)))
        self.assertEqual(str(getattr(infantry, "reserve_status", "") or ""), "deployed")
        self.assertTrue(bool(getattr(infantry, "arrived_from_reserves_this_turn", False)))
        sr = dict(getattr(infantry, "special_rules", {}) or {})
        self.assertEqual(str(sr.get("eternity_gate_no_charge_turn_owner", "") or ""), player_one.id)
        self.assertEqual(int(sr.get("eternity_gate_no_charge_turn", 0) or 0), 2)

    def test_infectious_murder_madness_aura_grants_conditional_sustained_hits(self):
        from types import SimpleNamespace

        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Infectious Murder-madness (Aura)",
            "description": (
                "While a friendly NECRONS unit (excluding Monster and Titanic units) is within 6\" of this model, each time a model "
                "in that unit makes an attack, if that model has the Destroyer Cult keyword or that enemy unit is the "
                "closest eligible target, that attack has the [SUSTAINED HITS 1] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        nekrosor = _make_unit("Nekrosor Ammentar", abilities=[ability], keywords=["NECRONS", "CHARACTER", "INFANTRY"])
        necron_unit = _make_unit("Necron Unit", keywords=["NECRONS", "INFANTRY"])
        destroyer_unit = _make_unit("Destroyer Unit", keywords=["NECRONS", "INFANTRY", "DESTROYER CULT"])
        monster_unit = _make_unit("Monster Unit", keywords=["NECRONS", "MONSTER"])
        titanic_unit = _make_unit("Titanic Unit", keywords=["NECRONS", "TITANIC"])
        close_enemy = _make_unit("Close Enemy", keywords=["INFANTRY"])
        far_enemy = _make_unit("Far Enemy", keywords=["INFANTRY"])

        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        army_one = Army("A1", detachment_type="Test")
        army_two = Army("A2", detachment_type="Test")
        player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
        player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
        game.add_player(player_one)
        game.add_player(player_two)

        for unit in (nekrosor, necron_unit, destroyer_unit, monster_unit, titanic_unit):
            army_one.add_unit(unit)
        for unit in (close_enemy, far_enemy):
            army_two.add_unit(unit)

        for unit in (nekrosor, necron_unit, destroyer_unit, monster_unit, titanic_unit, close_enemy, far_enemy):
            unit.deployed = True
            unit.reserve_status = "deployed"

        nekrosor.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        necron_unit.models[0].set_location(3.0, 0.0, 0.0, 0.0)
        destroyer_unit.models[0].set_location(4.0, 0.0, 0.0, 0.0)
        monster_unit.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        titanic_unit.models[0].set_location(5.5, 0.0, 0.0, 0.0)
        close_enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        far_enemy.models[0].set_location(18.0, 0.0, 0.0, 0.0)
        game.map.units = [nekrosor, necron_unit, destroyer_unit, monster_unit, titanic_unit, close_enemy, far_enemy]
        game.current_player_index = 0
        game.rebuild_entity_registry()

        parent = SimpleNamespace(name="Test Carbine", is_melee=lambda: False, is_ranged=lambda: True)
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

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            closest_attack = {"_aura_attack_mods": SimpleNamespace(hit=0, hit_reasons=())}
            profile._hit_target_with_tracking(close_enemy, necron_unit.models[0], closest_attack, log_roll=False)
            self.assertEqual(int(closest_attack.get("sustained_hit", 0) or 0), 1)

            far_attack = {"_aura_attack_mods": SimpleNamespace(hit=0, hit_reasons=())}
            profile._hit_target_with_tracking(far_enemy, necron_unit.models[0], far_attack, log_roll=False)
            self.assertEqual(int(far_attack.get("sustained_hit", 0) or 0), 0)

            destroyer_attack = {"_aura_attack_mods": SimpleNamespace(hit=0, hit_reasons=())}
            profile._hit_target_with_tracking(far_enemy, destroyer_unit.models[0], destroyer_attack, log_roll=False)
            self.assertEqual(int(destroyer_attack.get("sustained_hit", 0) or 0), 1)

            monster_attack = {"_aura_attack_mods": SimpleNamespace(hit=0, hit_reasons=())}
            profile._hit_target_with_tracking(close_enemy, monster_unit.models[0], monster_attack, log_roll=False)
            self.assertEqual(int(monster_attack.get("sustained_hit", 0) or 0), 0)

            titanic_attack = {"_aura_attack_mods": SimpleNamespace(hit=0, hit_reasons=())}
            profile._hit_target_with_tracking(close_enemy, titanic_unit.models[0], titanic_attack, log_roll=False)
            self.assertEqual(int(titanic_attack.get("sustained_hit", 0) or 0), 0)

    def test_prophet_of_destruction_queues_target_and_applies_wound_reroll_ones_until_phase_end(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        ability = {
            "name": "Prophet of Destruction",
            "description": (
                "Each time this model destroys an enemy unit, select one other friendly Destroyer Cult unit within 9\" "
                "of it. Until the end of the phase, each time a model in that unit makes an attack, re-roll a Wound roll of 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        nekrosor = _make_unit(
            "Nekrosor Ammentar",
            abilities=[ability],
            keywords=["NECRONS", "DESTROYER CULT", "CHARACTER", "INFANTRY"],
        )
        candidate_one = _make_unit("Destroyer One", keywords=["NECRONS", "DESTROYER CULT", "INFANTRY"])
        candidate_two = _make_unit("Destroyer Two", keywords=["NECRONS", "DESTROYER CULT", "INFANTRY"])
        destroyed_enemy = _make_unit("Destroyed Enemy", keywords=["INFANTRY"])
        target_enemy = _make_unit("Target Enemy", keywords=["INFANTRY"])

        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        army_one = Army("A1", detachment_type="Test")
        army_two = Army("A2", detachment_type="Test")
        player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
        player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
        game.add_player(player_one)
        game.add_player(player_two)

        for unit in (nekrosor, candidate_one, candidate_two):
            army_one.add_unit(unit)
        for unit in (destroyed_enemy, target_enemy):
            army_two.add_unit(unit)

        for unit in (nekrosor, candidate_one, candidate_two, destroyed_enemy, target_enemy):
            unit.deployed = True
            unit.reserve_status = "deployed"

        nekrosor.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        candidate_one.models[0].set_location(6.0, 0.0, 0.0, 0.0)
        candidate_two.models[0].set_location(8.0, 0.0, 0.0, 0.0)
        destroyed_enemy.models[0].set_location(12.0, 0.0, 0.0, 0.0)
        target_enemy.models[0].set_location(16.0, 0.0, 0.0, 0.0)

        game.map.units = [nekrosor, candidate_one, candidate_two, destroyed_enemy, target_enemy]
        game.current_player_index = 0
        game.turn = 2
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.rebuild_entity_registry()

        game._on_unit_destroyed_rules(
            unit=destroyed_enemy,
            destroyed_by_unit=nekrosor,
            destroyed_by_model=nekrosor.models[0],
        )

        choose_req = None
        for req in list(game.decision_queue.list() or []):
            if req.decision_type != DECISION_CHOOSE_QUARRY:
                continue
            if str((req.context or {}).get("ability", "") or "") != "prophet_of_destruction_target":
                continue
            choose_req = req
            break
        self.assertIsNotNone(choose_req)

        candidate_id = str(get_entity_id(candidate_one) or "")
        option = None
        for entry in list(choose_req.options or []):
            if str((entry.payload or {}).get("target_unit_id", "") or "") == candidate_id:
                option = entry
                break
        self.assertIsNotNone(option)

        decision_result = resolve_decision_command(
            game,
            choose_req,
            option.option_id,
            player_id=player_one.id,
        )
        self.assertTrue(bool(getattr(decision_result, "ok", False)))

        active_mods = candidate_one.get_unit_wound_reroll_modifiers("ranged", target=target_enemy)
        self.assertTrue(bool(active_mods.get("reroll_wound_ones", False)))
        self.assertTrue(
            any(
                "Prophet of Destruction" in str(reason)
                for reason in list(active_mods.get("reroll_wound_reasons", ()) or [])
            )
        )

        game.phase = BattleRoundPhases.COMMAND_PHASE
        expired_mods = candidate_one.get_unit_wound_reroll_modifiers("ranged", target=target_enemy)
        self.assertFalse(bool(expired_mods.get("reroll_wound_ones", False)))
        remaining_sr = dict(getattr(candidate_one, "special_rules", {}) or {})
        self.assertNotIn("necrons_prophet_of_destruction_active", remaining_sr)

    def test_living_lightning_parses_dice_pool_mortals(self):
        ability = {
            "name": "Living Lightning",
            "description": (
                "In your Shooting phase, select one enemy unit within 18\" of and visible to this model (excluding units "
                "with the Lone Operative ability that are not part of an Attached unit and are not within 12\" of this "
                "model) and roll four D6: for each 4+, that enemy unit suffers 1 mortal wound."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Plasmancer", abilities=[ability])
        specs = unit.model_start_shooting_phase_eater_plague_specs(unit.models[0])
        self.assertEqual(len(specs), 1)
        self.assertEqual(str(specs[0].get("roll_mode", "")), "dice_pool_threshold")
        self.assertEqual(int(specs[0].get("dice_count", 0)), 4)
        self.assertEqual(int(specs[0].get("threshold", 0)), 4)
        self.assertEqual(str(specs[0].get("mortal_per_success", "")), "1")

    def test_matter_absorption_parses_vehicle_mortals_and_heal(self):
        ability = {
            "name": "Matter Absorption",
            "description": (
                "At the start of your Shooting phase, select one enemy VEHICLE unit within 12\" of this model and roll "
                "one D6: on a 2+, that enemy unit suffers D3 mortal wounds and this model regains up to that many lost wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("C'tan Shard of the Void Dragon", abilities=[ability])
        specs = unit.model_start_shooting_phase_corrupt_machine_spirits_specs(unit.models[0])
        self.assertEqual(len(specs), 1)
        self.assertEqual(str(specs[0].get("roll_mode", "")), "single_threshold")
        self.assertEqual(int(specs[0].get("threshold", 0)), 2)
        self.assertEqual(str(specs[0].get("mortal_on_success", "")), "d3")
        self.assertTrue(bool(specs[0].get("heal_self_on_success", False)))

    def test_malevolent_arcing_parses_thundershock(self):
        ability = {
            "name": "Malevolent Arcing",
            "description": (
                "In your Shooting phase, each time you select a target for this model's twin tesla destructor, roll one D6 "
                "for the target unit and one D6 for every other enemy unit within 3\" of the target unit. On a 5+, the unit "
                "being rolled for is struck by arcing energies; after resolving all of this model's attacks against the target "
                "unit, each unit struck by arcing energies suffers D3 mortal wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Annihilation Barge", abilities=[ability])
        specs = unit.unit_thundershock_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("range", 0)), 3)
        self.assertEqual(int(specs[0].get("threshold", 0)), 5)
        self.assertEqual(str(specs[0].get("mortal_wounds", "")), "d3")

    def test_overwhelming_obliteration_grants_devastating_wounds_when_stationary(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        ability = {
            "name": "Overwhelming Obliteration",
            "description": (
                "In your Movement phase, if this model Remains Stationary, until the end of the turn, "
                "its doomsday cannon has the [DEVASTATING WOUNDS] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Doomsday Ark", abilities=[ability])
        target = _make_unit("Target")

        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        army_one = Army("A1", detachment_type="Test")
        army_two = Army("A2", detachment_type="Test")
        player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
        player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
        game.add_player(player_one)
        game.add_player(player_two)

        army_one.add_unit(attacker)
        army_two.add_unit(target)
        game.current_player_index = 0
        attacker.round_state.remained_stationary_this_round = True

        bonuses = attacker.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=attacker.models[0],
            weapon_name="Doomsday Cannon",
            target=target,
        )
        self.assertTrue(bool(bonuses.get("devastating_wounds", False)))

    def test_the_stars_are_right_parses_start_fight_phase_multiplier_spec(self):
        ability = {
            "name": "The Stars Are Right",
            "description": (
                "Once per battle, at the start of the Fight phase, this model can use this ability. If it does, until the "
                "end of the phase, triple the Attacks and Strength characteristics of this model's Staff of Tomorrow and "
                "every successful Wound roll made for this model's attacks scores a Critical Wound."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        orikan = _make_unit("Orikan The Diviner", abilities=[ability], keywords=["NECRONS", "CHARACTER", "INFANTRY"])
        specs = orikan.model_start_fight_phase_weapon_triple_attacks_strength_crit_wound_specs(orikan.models[0])
        self.assertEqual(len(specs), 1)
        spec = dict(specs[0] or {})
        self.assertEqual(str(spec.get("weapon_name", "") or "").lower(), "staff of tomorrow")
        self.assertEqual(int(spec.get("attacks_multiplier", 0) or 0), 3)
        self.assertEqual(int(spec.get("strength_multiplier", 0) or 0), 3)
        self.assertEqual(int(spec.get("crit_wound_threshold", 0) or 0), 2)
        self.assertTrue(bool(spec.get("crit_all_attacks", False)))

    def test_the_stars_are_right_queues_applies_and_cleans_up(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
        from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.units.wargear import Wargear
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command

        ability = {
            "name": "The Stars Are Right",
            "description": (
                "Once per battle, at the start of the Fight phase, this model can use this ability. If it does, until the "
                "end of the phase, triple the Attacks and Strength characteristics of this model's Staff of Tomorrow and "
                "every successful Wound roll made for this model's attacks scores a Critical Wound."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        orikan = _make_unit("Orikan The Diviner", abilities=[ability], keywords=["NECRONS", "CHARACTER", "INFANTRY"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"])

        # Explicit Staff profile so the multiplier can resolve base Attacks/Strength.
        orikan.models[0].add_wargear(
            Wargear(
                {
                    "name": "Staff of Tomorrow",
                    "type": "Melee",
                    "range": "Melee",
                    "A": "2",
                    "BS_WS": "3",
                    "S": "4",
                    "AP": "-3",
                    "D": "D3",
                    "description": "devastating wounds",
                }
            )
        )

        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        army_one = Army("A1", detachment_type="Test")
        army_two = Army("A2", detachment_type="Test")
        player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
        player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
        game.add_player(player_one)
        game.add_player(player_two)
        army_one.add_unit(orikan)
        army_two.add_unit(enemy)

        for unit in (orikan, enemy):
            unit.deployed = True
            unit.reserve_status = "deployed"

        game.map.units = [orikan, enemy]
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.turn = 2
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(player=player_one, phase=game.phase)
        request = None
        for req in list(game.decision_queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
                continue
            if str((req.context or {}).get("ability", "") or "") != "stars_are_right":
                continue
            request = req
            break
        self.assertIsNotNone(request)

        yes_option_id = ""
        for option in list(request.options or []):
            if bool((option.payload or {}).get("choice", False)):
                yes_option_id = str(option.option_id or "")
                break
        self.assertTrue(bool(yes_option_id))

        result = resolve_decision_command(game, request, yes_option_id, player_id=player_one.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        model = orikan.models[0]
        once_key = str((request.context or {}).get("buff_key", "") or "")
        self.assertTrue(bool(once_key))
        self.assertTrue(bool(model.has_used_once_per_battle(once_key)))

        attacks_override, _attacks_source = model.get_temporary_weapon_attacks_override("Staff of Tomorrow")
        self.assertEqual(int(attacks_override or 0), 6)
        strength_bonus, _strength_reasons = model.get_temporary_weapon_strength_bonus("Staff of Tomorrow")
        self.assertEqual(int(strength_bonus or 0), 8)
        crit_threshold, _crit_reasons = model.get_temporary_weapon_crit_wound_threshold("Staff of Tomorrow")
        self.assertEqual(int(crit_threshold or 0), 2)

        game._on_phase_end_cleanup(player=player_one, phase=BattleRoundPhases.FIGHT_PHASE)
        attacks_after, _ = model.get_temporary_weapon_attacks_override("Staff of Tomorrow")
        strength_after, _ = model.get_temporary_weapon_strength_bonus("Staff of Tomorrow")
        crit_after, _ = model.get_temporary_weapon_crit_wound_threshold("Staff of Tomorrow")
        self.assertEqual(int(attacks_after or 0), 0)
        self.assertEqual(int(strength_after or 0), 0)
        self.assertEqual(int(crit_after or 0), 0)

    def test_malign_sacrifice_roll_handler_uses_vehicle_bonus_profile(self):
        from warhammer40k_ai.engine.roll_handlers import handle_malign_sacrifice_roll
        from warhammer40k_ai.engine.dice_rolls import DiceRollState

        class _MockUnit:
            def __init__(self, name, *, is_vehicle=False):
                self.name = name
                self._is_vehicle = bool(is_vehicle)
                self._applied = []

            def has_any_keyword(self, kw):
                return self._is_vehicle and str(kw or "").upper() == "VEHICLE"

            def _apply_mortal_wounds_to_unit(self, target, amount, game_map=None):
                self._applied.append((target.name, int(amount)))

            def get_parent_army(self):
                class _Army:
                    player = None

                return _Army()

        class _MockModel:
            def __init__(self):
                self.dead = False
                self.name = "Scarab Base"

            def die(self, game_map=None):
                self.dead = True

        source = _MockUnit("Scarab Swarms")
        target = _MockUnit("Enemy Vehicle", is_vehicle=True)
        model = _MockModel()

        class _Game:
            map = None

            def resolve_unit_by_id(self, uid):
                if uid == "source":
                    return source
                if uid == "target":
                    return target
                return None

            def resolve_model_by_id(self, mid):
                if mid == "model":
                    return model
                return None

        state = DiceRollState(
            roll_id=1,
            player_id="p",
            spec={
                "source_unit_id": "source",
                "target_unit_id": "target",
                "model_id": "model",
                "ability_name": "Self-destruction",
                "roll_bonus_vs_vehicle": 1,
                "roll_low_min": 2,
                "roll_low_max": 5,
                "roll_low_mortal": "d3",
                "roll_high_threshold": 6,
                "roll_high_mortal": "3",
                "destroy_selected_model": True,
            },
            status="resolved",
            dice=[{"id": "d1", "value": 5, "faces": 6}],
            total=5,
        )
        with (
            patch(
                "warhammer40k_ai.engine.roll_handlers._get_unit",
                side_effect=lambda _game, uid: source if uid == "source" else target if uid == "target" else None,
            ),
            patch(
                "warhammer40k_ai.engine.roll_handlers._get_model",
                side_effect=lambda _game, mid: model if mid == "model" else None,
            ),
        ):
            result = handle_malign_sacrifice_roll(_Game(), state)
        self.assertEqual(int(result or 0), 3)
        self.assertEqual(source._applied, [("Enemy Vehicle", 3)])
        self.assertTrue(bool(model.dead))


if __name__ == "__main__":
    unittest.main()
