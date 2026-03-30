from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_handlers.movement import _validate_move_unit
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        keywords=None,
        model_count: int = 1,
        wounds: str = "4",
        toughness: str = "5",
        movement: str = "6",
        base_size: str = "32mm",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(movement),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Leagues of Votann",
    faction_keywords=None,
    keywords=None,
    model_count: int = 1,
    wounds: str = "4",
    toughness: str = "5",
    movement: str = "6",
    base_size: str = "32mm",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords or ["LEAGUES OF VOTANN"],
            keywords=keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
            movement=movement,
            base_size=base_size,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    lov_army = Army("Leagues of Votann", "Hearthfyre Arsenal")
    lov_army.faction_id = "LOV"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Votann", control=PlayerControl.LOCAL, army=lov_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 12
    p2.command_points = 12
    lov_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    _inject_hearthfyre_stratagems(p1)
    p1.stratagems.enable_event_subscriptions()
    return game, p1, p2, lov_army, enemy_army


def _inject_hearthfyre_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(s, "name", "") or ""): s
        for s in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        ("000010452007", "COGITATED NEED", 1, "Opponent's turn", "Movement phase", "Hearthfyre Arsenal - Strategic Ploy Stratagem"),
        ("000010452004", "DELAYED-FIRE ROUNDS", 1, "Your turn", "Shooting phase", "Hearthfyre Arsenal - Wargear Stratagem"),
        ("000010452003", "FIRST CONCERN", 1, "Your turn", "Shooting phase", "Hearthfyre Arsenal - Strategic Ploy Stratagem"),
        ("000010452006", "PREVENTATIVE PURGE", 1, "Opponent's turn", "Movement phase", "Hearthfyre Arsenal - Strategic Ploy Stratagem"),
        ("000010452002", "UNWAVERING ACCURACY", 2, "Your turn", "Shooting phase", "Hearthfyre Arsenal - Battle Tactic Stratagem"),
        ("000010452005", "WALL OF STEEL", 1, "Your turn", "Charge phase", "Hearthfyre Arsenal - Battle Tactic Stratagem"),
    )
    for sid, name, cp, turn, phase, stype in specs:
        if _norm_name(name) in existing:
            continue
        player.stratagems.available.append(
            Stratagem(
                id=sid,
                name=name,
                type=stype,
                description="",
                cp_cost=int(cp),
                turn=turn,
                phase=phase,
                detachment="Hearthfyre Arsenal",
                faction_id="LOV",
            )
        )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.current_player_idx = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _norm_name(name: str) -> str:
    text = str(name or "").strip().upper()
    return (
        text.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2019", "'")
    )


def _pending_by_name(stratagems, name: str):
    wanted = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(reaction.get("stratagem", "")) == wanted:
            return reaction
    return None


def _queued_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if getattr(request, "decision_type", None) == decision_type:
            return request
    return None


def _add_objective(game: Game, x: float, y: float, *, name: str = "Objective") -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    objective = Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _g: False,
        location=point,
    )
    game.map.objectives = list(getattr(game.map, "objectives", []) or []) + [objective]
    game.rebuild_entity_registry()
    return objective


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


def _ranged_profile(*, strength: int = 5, ap: int = 0):
    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _move_result(request, unit: Unit, destination: tuple[float, float, float]) -> DecisionResult:
    confirm = list(getattr(request, "options", []) or [])[0]
    model = unit.models[0]
    return DecisionResult(
        decision_id=request.decision_id,
        player_id=str(getattr(request, "player_id", "") or ""),
        option_id=confirm.option_id,
        payload={
            "model_positions": [
                {
                    "model_id": get_entity_id(model),
                    "position": [float(destination[0]), float(destination[1]), float(destination[2])],
                    "facing": 0.0,
                }
            ]
        },
    )


class TestHearthfyreArsenalStratagems(unittest.TestCase):
    def test_hearthfyre_stratagem_descriptors_registered(self):
        expected = {
            "000010452007": ("Cogitated Need", "reactive_move_toward_closest_objective_marker"),
            "000010452004": ("Delayed-Fire Rounds", "apply_move_triggered_mortal_wounds_until_owner_next_shooting_phase"),
            "000010452003": ("First Concern", "post_shoot_normal_move_if_remained_stationary"),
            "000010452006": ("Preventative Purge", "reactive_shooting_at_falling_back_enemy_with_hit_penalty"),
            "000010452002": ("Unwavering Accuracy", "ignore_ballistic_hit_wound_and_ap_modifiers_for_ranged_attacks"),
            "000010452005": ("Wall of Steel", "charge_end_mortal_wounds_with_optional_extra_dice"),
        }
        for stratagem_id, (expected_name, expected_effect) in expected.items():
            by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
            by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
            self.assertIsNotNone(by_id)
            self.assertIsNotNone(by_name)
            self.assertEqual(str(by_id.name or ""), expected_name)
            self.assertEqual(str(by_name.name or ""), expected_name)
            self.assertEqual(str(by_id.effect or ""), expected_effect)

    def test_unwavering_accuracy_ignores_negative_ranged_modifiers_until_phase_end(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        thunderkyn = _make_unit(
            "Brôkhyr Thunderkyn",
            keywords=["INFANTRY", "BRÔKHYR", "THUNDERKYN"],
            model_count=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            toughness="5",
        )
        lov_army.add_unit(thunderkyn)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, thunderkyn, 10.0, 10.0)
        _deploy_unit(game, enemy, 16.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "UNWAVERING ACCURACY")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("UNWAVERING ACCURACY", unit=thunderkyn, dequeue=True)
        self.assertTrue(ok)

        thunderkyn.special_rules["pain_suppressed_active"] = True
        enemy.special_rules["defensive_wound_mods"] = [
            {"value": 1, "attack_type": "ranged", "expires_phase": "SHOOTING_PHASE", "source": "Test Wound Penalty"}
        ]
        enemy.special_rules["armour_of_contempt_ap_worsen"] = {str(get_entity_id(thunderkyn) or ""): 1}

        profile = _ranged_profile(strength=5, ap=-1)
        hit = profile._hit_target_with_tracking(
            enemy,
            thunderkyn.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        wound = profile._wound_target_with_tracking(
            enemy,
            thunderkyn.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertEqual(int(hit.get("final_needed", 0) or 0), 3)
        self.assertFalse(any("SUPPRESSED" in str(mod).upper() for mod in list(hit.get("modifiers", []) or [])))
        self.assertEqual(int(wound.get("final_needed", 0) or 0), 4)
        self.assertFalse(any("TEST WOUND PENALTY" in str(mod).upper() for mod in list(wound.get("modifiers", []) or [])))
        self.assertEqual(int(profile.get_effective_ap(thunderkyn.models[0], enemy) or 0), -1)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        self.assertNotIn("hearthfyre_unwavering_accuracy_active", dict(thunderkyn.special_rules or {}))

    def test_first_concern_queues_post_shoot_move_for_stationary_hearthfyre_unit(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        evaluator = _make_unit(
            "Arkanyst Evaluator",
            keywords=["INFANTRY", "ARKANYST EVALUATOR"],
            movement="7",
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(evaluator)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, evaluator, 10.0, 10.0)
        _deploy_unit(game, enemy, 16.0, 10.0)
        evaluator.round_state.remained_stationary_this_round = True
        evaluator.round_state.shot_this_round = True
        game.rebuild_entity_registry()

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=evaluator, hits_by_target={enemy: [1]})

        pending = _pending_by_name(p1.stratagems, "FIRST CONCERN")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("FIRST CONCERN", unit=evaluator, dequeue=True)
        self.assertTrue(ok)

        request = _queued_request(game, DECISION_MOVE_UNIT)
        self.assertIsNotNone(request)
        context = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(context.get("reactive_move_kind", "") or ""), "hearthfyre_first_concern")
        self.assertEqual(int(context.get("max_distance", 0) or 0), 7)

    def test_delayed_fire_rounds_marks_hit_enemy_applies_mortal_wounds_and_clears_next_shooting_phase(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        shooter = _make_unit(
            "Arkanyst Evaluator",
            keywords=["INFANTRY", "ARKANYST EVALUATOR"],
        )
        enemy = _make_unit(
            "Enemy Squad",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            model_count=3,
        )
        lov_army.add_unit(shooter)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, shooter, 10.0, 10.0)
        _deploy_unit(game, enemy, 16.0, 10.0)
        shooter.round_state.shot_this_round = True
        game.rebuild_entity_registry()

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=shooter, hits_by_target={enemy: [1]})
        pending = _pending_by_name(p1.stratagems, "DELAYED-FIRE ROUNDS")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("DELAYED-FIRE ROUNDS", unit=shooter, enemy_unit=enemy, dequeue=True)
        self.assertTrue(ok)
        self.assertTrue(bool(enemy.special_rules.get("hearthfyre_delayed_fire_rounds_active")))

        shooter._apply_mortal_wounds_to_unit = Mock()
        with patch("warhammer40k_ai.rules.stratagems_votann.dice_module.get_roll", side_effect=[1, 2, 1]):
            game.event_system.publish("unit_move_ended", unit=enemy, action="move")

        shooter._apply_mortal_wounds_to_unit.assert_called_once()
        args, kwargs = shooter._apply_mortal_wounds_to_unit.call_args
        self.assertIs(args[0], enemy)
        self.assertEqual(int(args[1] or 0), 2)
        self.assertIs(kwargs.get("game_map"), game.map)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        self.assertNotIn("hearthfyre_delayed_fire_rounds_active", dict(enemy.special_rules or {}))

    def test_preventative_purge_queues_forced_reactive_shooting_with_temporary_hit_penalty(self):
        game, p1, p2, lov_army, enemy_army = _build_game()
        thunderkyn = _make_unit(
            "Brôkhyr Thunderkyn",
            keywords=["INFANTRY", "BRÔKHYR", "THUNDERKYN"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(thunderkyn)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, thunderkyn, 10.0, 10.0)
        _deploy_unit(game, enemy, 16.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p2, "MOVEMENT_PHASE", 1)
        game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")
        pending = _pending_by_name(p1.stratagems, "PREVENTATIVE PURGE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("PREVENTATIVE PURGE", unit=thunderkyn, enemy_unit=enemy, dequeue=True)
        self.assertTrue(ok)
        self.assertTrue(bool(thunderkyn.special_rules.get("hearthfyre_preventative_purge_active")))

        request = _queued_request(game, DECISION_DECLARE_SHOTS)
        self.assertIsNotNone(request)
        context = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(context.get("force_target_unit_id", "") or ""), str(get_entity_id(enemy) or ""))

        hit = _ranged_profile()._hit_target_with_tracking(
            enemy,
            thunderkyn.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(int(hit.get("final_needed", 0) or 0), 4)
        self.assertTrue(any("PREVENTATIVE PURGE" in str(mod).upper() for mod in list(hit.get("modifiers", []) or [])))

        game.event_system.publish("unit_shooting_resolved", attacker_unit=thunderkyn, hits_by_target={enemy: [1]})
        self.assertNotIn("hearthfyre_preventative_purge_active", dict(thunderkyn.special_rules or {}))

    def test_wall_of_steel_inflicts_capped_mortal_wounds_with_optional_yield_points(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        steeljacks = _make_unit(
            "Ironkin Steeljacks",
            keywords=["INFANTRY", "IRONKIN", "STEELJACKS"],
            model_count=5,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(steeljacks)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, steeljacks, 10.0, 10.0)
        _deploy_unit(game, enemy, 24.0, 10.0)
        steeljacks.round_state.charged_this_round = True
        game.map.is_within_engagement_range = lambda _a, _b: True
        lov_army.prioritised_efficiency.add_yield_points(2, game=game)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "CHARGE_PHASE", 0)
        game.event_system.publish("unit_move_ended", unit=steeljacks, action="charge")
        pending = _pending_by_name(p1.stratagems, "WALL OF STEEL")
        self.assertIsNotNone(pending)

        steeljacks._apply_mortal_wounds_to_unit = Mock()
        with patch("warhammer40k_ai.rules.stratagems_votann.dice_module.get_roll", side_effect=[4, 4, 4, 4, 1, 4, 4]):
            ok = p1.stratagems.use(
                "WALL OF STEEL",
                unit=steeljacks,
                enemy_unit=enemy,
                spend_yield_points=True,
                dequeue=True,
            )

        self.assertTrue(ok)
        self.assertEqual(int(lov_army.prioritised_efficiency.yield_points or 0), 0)
        steeljacks._apply_mortal_wounds_to_unit.assert_called_once()
        args, kwargs = steeljacks._apply_mortal_wounds_to_unit.call_args
        self.assertIs(args[0], enemy)
        self.assertEqual(int(args[1] or 0), 6)
        self.assertIs(kwargs.get("game_map"), game.map)

    def test_cogitated_need_queues_objective_locked_move_and_validator_rejects_non_closing_path(self):
        game, p1, p2, lov_army, _enemy_army = _build_game()
        steeljacks = _make_unit(
            "Ironkin Steeljacks",
            keywords=["INFANTRY", "IRONKIN", "STEELJACKS"],
            movement="6",
        )
        lov_army.add_unit(steeljacks)
        _deploy_unit(game, steeljacks, 10.0, 10.0)
        close_objective = _add_objective(game, 18.0, 10.0, name="Close Objective")
        _add_objective(game, 30.0, 10.0, name="Far Objective")
        game.rebuild_entity_registry()

        _set_phase(game, p2, "MOVEMENT_PHASE", 1)
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "COGITATED NEED")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("COGITATED NEED", unit=steeljacks, dequeue=True)
        self.assertTrue(ok)

        request = _queued_request(game, DECISION_MOVE_UNIT)
        self.assertIsNotNone(request)
        context = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(context.get("reactive_move_kind", "") or ""), "hearthfyre_cogitated_need")
        self.assertEqual(
            str(context.get("hearthfyre_cogitated_need_objective_id", "") or ""),
            str(get_entity_id(close_objective) or ""),
        )

        errors = _validate_move_unit(game, request, _move_result(request, steeljacks, (11.0, 10.0, 0.0)))
        self.assertTrue(errors)
        self.assertIn("cogitated need", str(errors[0]).lower())


if __name__ == "__main__":
    unittest.main()
