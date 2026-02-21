import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        toughness=6,
        movement=6,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
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
        normalized = []
        for ability in list(abilities or []):
            if not isinstance(ability, dict):
                continue
            entry = dict(ability)
            entry.setdefault("type", "")
            entry.setdefault("parameter", "")
            normalized.append(entry)
        self.datasheets_abilities = normalized
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    toughness=6,
    movement=6,
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        abilities=abilities,
        toughness=toughness,
        movement=movement,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Necrons", "Starshatter Arsenal")
    army1.faction_id = "NEC"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 3
    p2.command_points = 3
    return game, p1, p2, army1, army2


class TestNecronsStarshatterStratagems(unittest.TestCase):
    def test_unyielding_forms_requires_strength_gt_toughness(self):
        from warhammer40k_ai.units.wargear import Wargear

        game, p1, p2, army1, army2 = _build_game()
        necron_unit = _make_unit(
            "Ghost Ark",
            keywords=["VEHICLE"],
            faction_keywords=["NECRONS"],
            toughness=6,
        )
        enemy_unit = _make_unit("Enemy Shooters", keywords=["INFANTRY"])
        army1.add_unit(necron_unit)
        army2.add_unit(enemy_unit)

        necron_unit.deployed = True
        enemy_unit.deployed = True
        necron_unit.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        enemy_unit.models[0].set_location(10.0, 5.0, 0.0, 0.0)
        game.map.place_unit(necron_unit)
        game.map.place_unit(enemy_unit)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.current_player_index = 1
        game.phase = phase
        game.event_system.publish("phase_start", player=p2, phase=phase)
        ok = p1.stratagems.use(
            "UNYIELDING FORMS",
            unit=necron_unit,
            attacker_unit=enemy_unit,
            phase_name="Shooting phase",
            candidates=[necron_unit],
        )
        self.assertTrue(ok)

        data_strong = {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "7",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Ranged",
            "name": "Test Gun",
        }
        profile_strong = Wargear(data_strong).profiles["default"]
        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        result = profile_strong._wound_target_with_tracking(necron_unit, enemy_unit.models[0], dict(attack_instance))
        self.assertTrue(any("UNYIELDING FORMS" in m for m in result.get("modifiers", [])))

        data_equal = dict(data_strong)
        data_equal["S"] = "6"
        profile_equal = Wargear(data_equal).profiles["default"]
        result_equal = profile_equal._wound_target_with_tracking(necron_unit, enemy_unit.models[0], dict(attack_instance))
        self.assertFalse(any("UNYIELDING FORMS" in m for m in result_equal.get("modifiers", [])))

    def test_merciless_reclamation_dynamic_objective_check(self):
        from warhammer40k_ai.units.wargear import Wargear
        from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint

        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Doomstalker",
            keywords=["VEHICLE"],
            faction_keywords=["NECRONS"],
        )
        target_near = _make_unit("Target Near", keywords=["INFANTRY"])
        target_far = _make_unit("Target Far", keywords=["INFANTRY"])
        army1.add_unit(attacker)
        army2.add_unit(target_near)
        army2.add_unit(target_far)

        attacker.deployed = True
        target_near.deployed = True
        target_far.deployed = True
        attacker.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        target_near.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        target_far.models[0].set_location(40.0, 40.0, 0.0, 0.0)
        game.map.place_unit(attacker)
        game.map.place_unit(target_near)
        game.map.place_unit(target_far)

        obj_point = ObjectivePoint(10.0, 10.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Test Objective",
            category=ObjectiveCategory.PRIMARY,
            points=5,
            description="Test",
            conditions=lambda _game: True,
            location=obj_point,
        )
        game.map.add_objectives([objective])

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.current_player_index = 0
        game.phase = phase
        game.event_system.publish("phase_start", player=p1, phase=phase)
        ok = p1.stratagems.use("MERCILESS RECLAMATION", unit=attacker, phase_name="Shooting phase")
        self.assertTrue(ok)

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Ranged",
            "name": "Test Gun",
        }
        profile = Wargear(data).profiles["default"]
        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }

        near_result = profile._wound_target_with_tracking(target_near, attacker.models[0], dict(attack_instance))
        self.assertTrue(any("Merciless Reclamation" in m for m in near_result.get("modifiers", [])))

        far_result = profile._wound_target_with_tracking(target_far, attacker.models[0], dict(attack_instance))
        self.assertFalse(any("Merciless Reclamation" in m for m in far_result.get("modifiers", [])))

    def test_dimensional_tunnel_sets_and_clears_move_types(self):
        from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules

        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit(
            "Doomsday Ark",
            keywords=["VEHICLE"],
            faction_keywords=["NECRONS"],
        )
        army1.add_unit(unit)
        unit.deployed = True

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 0
        game.phase = phase
        game.event_system.publish("phase_start", player=p1, phase=phase)
        ok = p1.stratagems.use("DIMENSIONAL TUNNEL", unit=unit, phase_name="Movement phase")
        self.assertTrue(ok)
        sr = unit.special_rules
        self.assertTrue(sr.get("dimensional_tunnel_active"))
        self.assertTrue(set(sr.get("bearer_unit_phase_move_types", [])) >= {"move", "advance", "fall_back"})
        move_rules = get_validation_rules(MovementType.MOVE, moving_unit=unit)
        self.assertTrue(bool(move_rules.get("can_move_through_enemy_models")))
        self.assertTrue(bool(move_rules.get("can_move_through_terrain")))
        self.assertFalse(bool(move_rules.get("cannot_move_within_engagement_range", True)))
        self.assertTrue(bool(move_rules.get("cannot_end_in_engagement_range")))

        game.event_system.publish("phase_end", player=p1, phase=phase)
        sr = unit.special_rules
        self.assertFalse(sr.get("dimensional_tunnel_active", False))
        self.assertNotIn("bearer_unit_phase_move_types", sr)

    def test_chronoshift_fixed_advance_roll(self):
        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit(
            "Ghost Ark",
            keywords=["VEHICLE"],
            faction_keywords=["NECRONS"],
        )
        army1.add_unit(unit)
        unit.deployed = True

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 0
        game.phase = phase
        game.event_system.publish("phase_start", player=p1, phase=phase)
        ok = p1.stratagems.use("CHRONOSHIFT", unit=unit, phase_name="Movement phase")
        self.assertTrue(ok)
        roll = unit.prepare_advance()
        self.assertEqual(roll, 6)
        self.assertEqual(unit.round_state.advance_roll, 6)

    def test_endless_servitude_triggers_reanimation(self):
        from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
        from warhammer40k_ai.utility import dice as dice_module

        game, p1, _p2, army1, _army2 = _build_game()
        abilities = [{"name": "Reanimation Protocols", "description": ""}]
        unit = _make_unit(
            "Warriors",
            keywords=["INFANTRY"],
            faction_keywords=["NECRONS"],
            abilities=abilities,
        )
        army1.add_unit(unit)
        unit.deployed = True
        unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        game.map.place_unit(unit)

        obj_point = ObjectivePoint(10.0, 10.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Test Objective",
            category=ObjectiveCategory.PRIMARY,
            points=5,
            description="Test",
            conditions=lambda _game: True,
            location=obj_point,
        )
        game.map.add_objectives([objective])

        unit.models[0].wounds = 1
        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.current_player_index = 0
        game.phase = phase
        game.event_system.publish("phase_start", player=p1, phase=phase)

        original_roll = dice_module.get_roll
        dice_module.get_roll = lambda _d: 1
        try:
            ok = p1.stratagems.use("ENDLESS SERVITUDE", unit=unit, phase_name="Fight phase")
        finally:
            dice_module.get_roll = original_roll
        self.assertTrue(ok)
        self.assertEqual(unit.models[0].wounds, 2)

    def test_reactive_reposition_queues_move_decision(self):
        from warhammer40k_ai.utility import dice as dice_module
        from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT

        game, p1, p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Immortals",
            keywords=["INFANTRY"],
            faction_keywords=["NECRONS"],
        )
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)

        unit.deployed = True
        enemy.deployed = True
        unit.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 5.0, 0.0, 0.0)
        game.map.place_unit(unit)
        game.map.place_unit(enemy)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.current_player_index = 1
        game.phase = phase
        game.event_system.publish("phase_start", player=p2, phase=phase)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[unit])
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={unit: 1})

        reactions = [r for r in p1.stratagems.get_pending_reactions() if r.get("stratagem") == "REACTIVE REPOSITION"]
        self.assertTrue(reactions)

        original_roll = dice_module.get_roll
        dice_module.get_roll = lambda _d: 4
        try:
            ok = p1.stratagems.use(
                "REACTIVE REPOSITION",
                unit=unit,
                enemy_unit=enemy,
                phase_name="Shooting phase",
                candidates=[unit],
                dequeue=True,
            )
        finally:
            dice_module.get_roll = original_roll
        self.assertTrue(ok)
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_MOVE_UNIT
        ]
        self.assertTrue(pending)
        ctx = dict(getattr(pending[0], "context", {}) or {})
        self.assertEqual(ctx.get("max_distance"), 4)
        self.assertEqual(ctx.get("movement_type"), "reactive")
        self.assertEqual(ctx.get("reactive_move_kind"), "reactive_reposition")


if __name__ == "__main__":
    unittest.main()
