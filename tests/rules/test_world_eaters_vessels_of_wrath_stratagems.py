import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        wounds="4",
        transport="",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": wounds,
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = transport


def _make_unit(name, *, keywords=None, faction_keywords=None, wounds="4", transport=""):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        wounds=wounds,
        transport=transport,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("World Eaters", "Vessels of Wrath")
    army1.faction_id = "WE"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    game.turn = 1
    p1.command_points = 6
    p2.command_points = 6
    return game, p1, p2, army1, army2


def _place_unit(game, unit, x, y):
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


class _MeleeWargear:
    name = "Test Chainblade"

    @staticmethod
    def is_melee():
        return True

    @staticmethod
    def is_ranged():
        return False


class _RangedWargear:
    name = "Test Rifle"

    @staticmethod
    def is_melee():
        return False

    @staticmethod
    def is_ranged():
        return True


def _melee_profile(strength="5", ap="0"):
    from warhammer40k_ai.units.wargear import WargearProfile

    return WargearProfile(
        "Test Chainblade",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": str(ap),
            "D": "1",
            "description": "",
        },
        parent_wargear=_MeleeWargear(),
    )


def _ranged_profile(strength="3", ap="0"):
    from warhammer40k_ai.units.wargear import WargearProfile

    return WargearProfile(
        "Test Rifle",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": str(ap),
            "D": "1",
            "description": "",
        },
        parent_wargear=_RangedWargear(),
    )


def _add_test_objective(game, x=0.0, y=0.0, radius=3.0):
    from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint

    obj = Objective(
        name="Objective",
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _g: False,
        location=ObjectivePoint(float(x), float(y), 0.0, control_radius=float(radius)),
    )
    game.map.objectives.append(obj)
    return obj


class TestWorldEatersVesselsOfWrathStratagems(unittest.TestCase):
    def test_aspire_to_infamy_applies_non_character_melee_strength_and_ap(self):
        game, p1, _p2, army1, army2 = _build_game()
        berzerkers = _make_unit(
            "Khorne Berzerkers",
            keywords=["INFANTRY", "BERZERKERS", "KHORNE"],
            faction_keywords=["WORLD EATERS"],
        )
        character = _make_unit(
            "Master of Executions",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(berzerkers)
        army1.add_unit(character)
        army2.add_unit(enemy)
        _place_unit(game, berzerkers, 10.0, 10.0)
        _place_unit(game, character, 12.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("ASPIRE TO INFAMY", unit=berzerkers, phase_name="Fight phase")
        self.assertTrue(ok)

        profile = _melee_profile()
        attacker = berzerkers.models[0]
        ap_non_character = profile.get_effective_ap(attacker, enemy)
        wound_non_character = profile._wound_target_with_tracking(enemy, attacker, {})

        self.assertEqual(ap_non_character, -1)
        self.assertTrue(any("Aspire to Infamy" in str(m) for m in list(wound_non_character.get("modifiers", []) or [])))

        character_attacker = character.models[0]
        ap_character = profile.get_effective_ap(character_attacker, enemy)
        wound_character = profile._wound_target_with_tracking(enemy, character_attacker, {})
        self.assertEqual(ap_character, 0)
        self.assertFalse(any("Aspire to Infamy" in str(m) for m in list(wound_character.get("modifiers", []) or [])))

    def test_overshadowed_by_none_adds_full_wound_reroll_vs_monster(self):
        game, p1, _p2, army1, army2 = _build_game()
        infantry = _make_unit(
            "Eightbound",
            keywords=["INFANTRY", "EIGHTBOUND"],
            faction_keywords=["WORLD EATERS"],
        )
        monster = _make_unit("Enemy Monster", keywords=["MONSTER"], faction_keywords=["ENEMY"], wounds="8")
        army1.add_unit(infantry)
        army2.add_unit(monster)
        _place_unit(game, infantry, 10.0, 10.0)
        _place_unit(game, monster, 14.0, 10.0)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("OVERSHADOWED BY NONE", unit=infantry, phase_name="Fight phase")
        self.assertTrue(ok)

        profile = _melee_profile(strength="4")
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
            wound = profile._wound_target_with_tracking(monster, infantry.models[0], {}, roll_value=1)
        self.assertEqual(int(wound.get("reroll", 0) or 0), 5)
        self.assertIn("Overshadowed by None", list(wound.get("reroll_full_reasons", []) or []))

    def test_brazen_contempt_queues_and_applies_vessel_override(self):
        game, p1, p2, army1, army2 = _build_game()
        target = _make_unit(
            "Eightbound",
            keywords=["INFANTRY", "EIGHTBOUND"],
            faction_keywords=["WORLD EATERS"],
        )
        shooter = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(target)
        army2.add_unit(shooter)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, shooter, 18.0, 10.0)
        target.models[0].keywords.append("Vessel of Wrath")

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)
        game.event_system.publish("shooting_targets_selected", attacking_unit=shooter, target_units=[target])

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "BRAZEN CONTEMPT" for r in pending))

        ok = p1.stratagems.use("BRAZEN CONTEMPT", unit=target, attacking_unit=shooter, phase_name="Shooting phase")
        self.assertTrue(ok)

        profile = _ranged_profile(strength="3")
        wound = profile._wound_target_with_tracking(target, shooter.models[0], {}, roll_value=4)
        self.assertTrue(any("Brazen Contempt" in str(m) for m in list(wound.get("modifiers", []) or [])))

    def test_gory_dedication_queues_on_phase_end_and_sets_sticky_control(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit("Eightbound", keywords=["INFANTRY"], faction_keywords=["WORLD EATERS"])
        enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)

        objective = _add_test_objective(game, x=10.0, y=10.0, radius=3.0)
        ox = float(getattr(objective.location, "x", 10.0) or 10.0)
        oy = float(getattr(objective.location, "y", 10.0) or 10.0)
        _place_unit(game, unit, ox, oy)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        game.event_system.publish(
            "model_destroyed",
            attacker_unit=unit,
            target_unit=enemy,
            target_model=enemy.models[0],
            weapon_profile=_melee_profile(),
        )
        game.event_system.publish("phase_end", player=p1, phase=phase)

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "GORY DEDICATION" for r in pending))

        ok = p1.stratagems.use(
            "GORY DEDICATION",
            unit=unit,
            objective=objective,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertIs(objective.location.sticky_controller, p1)
        self.assertEqual(str(getattr(objective.location, "sticky_source", "") or ""), "gory_dedication")

    def test_meet_force_with_force_queues_and_creates_blood_surge_move(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT

        game, p1, p2, army1, army2 = _build_game()
        target = _make_unit(
            "Eightbound",
            keywords=["INFANTRY", "EIGHTBOUND"],
            faction_keywords=["WORLD EATERS"],
            wounds="4",
        )
        shooter = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(target)
        army2.add_unit(shooter)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, shooter, 18.0, 10.0)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)
        game.event_system.publish("shooting_targets_selected", attacking_unit=shooter, target_units=[target])

        target.models[0].wounds = max(0, int(target.models[0].wounds or 0) - 1)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=shooter, hits_by_target={target: 1})

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "MEET FORCE WITH FORCE" for r in pending))

        ok = p1.stratagems.use(
            "MEET FORCE WITH FORCE",
            unit=target,
            enemy_unit=shooter,
            phase_name="Shooting phase",
            max_distance=5,
        )
        self.assertTrue(ok)

        pending_moves = [
            req
            for req in list(game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_MOVE_UNIT
        ]
        self.assertTrue(pending_moves)
        ctx = dict(getattr(pending_moves[0], "context", {}) or {})
        self.assertEqual(ctx.get("movement_type"), "blood_surge")
        self.assertEqual(ctx.get("reactive_move_kind"), "meet_force_with_force")
        self.assertEqual(int(ctx.get("max_distance", 0) or 0), 5)

    def test_punish_the_craven_queues_and_marks_fallback_penalty(self):
        game, p1, p2, army1, army2 = _build_game()
        target = _make_unit(
            "Eightbound",
            keywords=["INFANTRY", "EIGHTBOUND"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(target)
        army2.add_unit(enemy)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        target.models[0].keywords.append("Vessel of Wrath")

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)
        game.event_system.publish("unit_move_started", unit=enemy, action="fall_back")

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "PUNISH THE CRAVEN" for r in pending))

        ok = p1.stratagems.use(
            "PUNISH THE CRAVEN",
            unit=target,
            enemy_unit=enemy,
            phase_name="Movement phase",
        )
        self.assertTrue(ok)

        sr = target.special_rules
        self.assertTrue(sr.get("enemy_fallback_desperate_escape"))
        self.assertEqual(int(sr.get("enemy_fallback_desperate_escape_penalty", 0) or 0), 1)
        self.assertEqual(str(sr.get("enemy_fallback_desperate_escape_target_enemy_id", "") or ""), str(enemy._id))


if __name__ == "__main__":
    unittest.main()
