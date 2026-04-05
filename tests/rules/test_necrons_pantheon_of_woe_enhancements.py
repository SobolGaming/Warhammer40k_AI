from __future__ import annotations

import unittest

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 12,
        leadership: int = 7,
        abilities=None,
        base_size: str = "60mm",
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["NECRONS"] if faction_name == "Necrons" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "11",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": "4",
                "base_size": base_size,
                "inv_sv": "4",
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


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    wounds: int = 12,
    leadership: int = 7,
    abilities=None,
    base_size: str = "60mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            leadership=leadership,
            abilities=abilities,
            base_size=base_size,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    necron_army = Army("Necrons", "Pantheon of Woe")
    necron_army.faction_id = "NEC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    necron_player = Player("Necrons", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[necron_player, enemy_player])
    game.turn = 1
    return game, necron_army, enemy_army, necron_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="NEC",
        detachment="Pantheon of Woe",
        points=10,
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _bearer_model(unit: Unit):
    getter = getattr(unit, "_get_enhancement_bearer_model", None)
    if callable(getter):
        bearer = getter()
        if bearer is not None:
            return bearer
    models = list(getattr(unit, "models", []) or [])
    return models[0] if models else None


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _resolve_yes(game: Game, request, player: Player) -> None:
    option_id = None
    for opt in list(request.options or []):
        if bool((opt.payload or {}).get("choice", False)):
            option_id = opt.option_id
            break
    if option_id is None:
        raise AssertionError("Yes option not found")
    result = resolve_decision_command(game, request, option_id, player_id=player.id)
    if not bool(getattr(result, "ok", False)):
        raise AssertionError("Yes/No decision did not resolve successfully")


class _ChargeMap:
    def __init__(self, enemy_unit: Unit):
        self._enemy_unit = enemy_unit

    def get_enemy_units(self, _unit):
        return [self._enemy_unit]

    def get_distance_between_units(self, _a, _b):
        return 6.0

    def is_path_blocked(self, _a, _b):
        return False

    def is_within_engagement_range(self, _a, _b):
        return False


class TestNecronsPantheonOfWoeEnhancements(unittest.TestCase):
    def test_pantheon_enhancement_descriptors_registered(self):
        expected = {
            "000010672002": ("Singularity Matrix", "targeted_stratagem_cp_increase"),
            "000010672003": ("Quantum Goad", "charge_after_advance"),
            "000010672004": (
                "Animus Damper",
                "opponent_shooting_phase_select_visible_vehicle_leadership_test_hit_penalty_and_failed_test_wound_penalty",
            ),
            "000010672005": (
                "Reletavistic Tether",
                "deep_strike_and_translocation_six_inch_setup_with_conditional_no_charge",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(descriptor)
            self.assertEqual(str(getattr(descriptor, "name", "") or ""), name)
            self.assertEqual(str(getattr(descriptor, "effect", "") or ""), effect)

    def test_singularity_matrix_increases_targeted_stratagem_cp_within_12_of_bearer(self):
        game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
        source = _make_unit(
            "C'tan Shard of the Deceiver",
            "necron-deceiver",
            keywords=["MONSTER", "CHARACTER"],
            faction_keywords=["NECRONS"],
        )
        enemy = _make_unit(
            "Enemy Squad",
            "enemy-squad",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            wounds=2,
            base_size="32mm",
        )
        necron_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy, 10.0, 0.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010672002",
            name="Singularity Matrix",
            description=(
                "C'tan Shard of the Deceiver model only. This model has the following ability: "
                "Lord of Deceit (Aura): Each time your opponent targets a unit from their army with a Stratagem, "
                "if that unit is within 12\" of this model, increase the cost of that use of that Stratagem by 1CP."
            ),
        )

        specs = list(source.special_rules.get("stratagem_target_cp_increase_aura", []) or [])
        self.assertTrue(specs)
        self.assertEqual(str(specs[0].get("source_model_id", "") or ""), str(get_entity_id(source.models[0]) or ""))

        preview_in = necron_player.preview_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertTrue(bool(preview_in.get("auto")))
        applied_in = necron_player.apply_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertEqual(int(applied_in.get("increase", 0) or 0), 1)

        _set_unit_position(enemy, 20.0, 0.0)
        preview_out = necron_player.preview_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertFalse(bool(preview_out.get("auto")))

    def test_quantum_goad_allows_bearer_unit_to_charge_after_advance_while_bearer_alive(self):
        _game, necron_army, _enemy_army, _necron_player, _enemy_player = _build_game()
        source = _make_unit(
            "C'tan Shard of the Nightbringer",
            "necron-nightbringer",
            keywords=["MONSTER", "CHARACTER"],
            faction_keywords=["NECRONS"],
        )
        necron_army.add_unit(source)
        _apply_enhancement(
            source,
            enhancement_id="000010672003",
            name="Quantum Goad",
            description="C'tan Shard of the Nightbringer model only. This model is eligible to declare a charge in a turn in which it Advanced.",
        )

        source.round_state.advanced_this_round = True
        self.assertTrue(source.can_charge_after_advance())

        bearer = _bearer_model(source)
        self.assertIsNotNone(bearer)
        bearer.take_damage(999)
        self.assertFalse(source.can_charge_after_advance())

    def test_animus_damper_queues_visible_vehicle_targets_only_and_is_optional(self):
        game, necron_army, enemy_army, _necron_player, enemy_player = _build_game()
        source = _make_unit(
            "C'tan Shard of the Void Dragon",
            "necron-void-dragon",
            keywords=["MONSTER", "CHARACTER"],
            faction_keywords=["NECRONS"],
        )
        enemy_vehicle = _make_unit(
            "Enemy Vehicle",
            "enemy-vehicle",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        enemy_infantry = _make_unit(
            "Enemy Infantry",
            "enemy-infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            wounds=2,
            base_size="32mm",
        )
        necron_army.add_unit(source)
        enemy_army.add_unit(enemy_vehicle)
        enemy_army.add_unit(enemy_infantry)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy_vehicle, 8.0, 0.0)
        _set_unit_position(enemy_infantry, 8.0, 2.0)
        source._has_line_of_sight_to_target = lambda _model, _target, _map: True
        game.map.units = [source, enemy_vehicle, enemy_infantry]
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010672004",
            name="Animus Damper",
            description=(
                "C'tan Shard of the Void Dragon model only. Once per turn, at the start of your opponent's Shooting phase, "
                "select one enemy VEHICLE unit visible to the bearer. That unit must take a Leadership test. Until the end "
                "of the phase, each time a model in that unit makes an attack, subtract 1 from the Hit roll and, if that "
                "Leadership test was failed, subtract 1 from the Wound roll as well."
            ),
        )

        game.current_player_index = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_opponent_shooting_phase_disrupt(player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)

        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "opponent_shooting_phase_disrupt"
            and str((req.context or {}).get("ability_name", "") or "") == "Animus Damper"
        ]
        self.assertTrue(pending)
        request = pending[0]
        self.assertTrue(any(str((opt.payload or {}).get("action", "") or "") == "skip" for opt in list(request.options or [])))
        target_ids = {
            str((opt.payload or {}).get("target_unit_id", "") or "")
            for opt in list(request.options or [])
            if (opt.payload or {}).get("target_unit_id")
        }
        self.assertIn(str(get_entity_id(enemy_vehicle) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(enemy_infantry) or ""), target_ids)

    def test_animus_damper_failed_leadership_applies_hit_and_wound_penalties(self):
        game, necron_army, enemy_army, necron_player, enemy_player = _build_game()
        source = _make_unit(
            "C'tan Shard of the Void Dragon",
            "necron-void-dragon",
            keywords=["MONSTER", "CHARACTER"],
            faction_keywords=["NECRONS"],
        )
        pass_target = _make_unit(
            "Pass Vehicle",
            "pass-vehicle",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        fail_target = _make_unit(
            "Fail Vehicle",
            "fail-vehicle",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        necron_army.add_unit(source)
        enemy_army.add_unit(pass_target)
        enemy_army.add_unit(fail_target)
        game.map.units = [source, pass_target, fail_target]
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010672004",
            name="Animus Damper",
            description=(
                "C'tan Shard of the Void Dragon model only. Once per turn, at the start of your opponent's Shooting phase, "
                "select one enemy VEHICLE unit visible to the bearer. That unit must take a Leadership test. Until the end "
                "of the phase, each time a model in that unit makes an attack, subtract 1 from the Hit roll and, if that "
                "Leadership test was failed, subtract 1 from the Wound roll as well."
            ),
        )

        bearer = _bearer_model(source)
        self.assertIsNotNone(bearer)
        pass_target.pass_leadership_check = lambda: True
        fail_target.pass_leadership_check = lambda: False

        game.current_player_index = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        pass_request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Animus Damper",
            player_id=necron_player.id,
            options=[
                DecisionOption.create(
                    "Pass Vehicle",
                    payload={
                        "target_unit_id": str(get_entity_id(pass_target) or ""),
                        "source_unit_id": str(get_entity_id(source) or ""),
                        "model_id": str(get_entity_id(bearer) or ""),
                    },
                )
            ],
            context={
                "ability": "opponent_shooting_phase_disrupt",
                "ability_name": "Animus Damper",
                "ability_key": "ANIMUS_DAMPER",
                "resolution_mode": "leadership_test",
                "required_target_keywords": ["VEHICLE"],
                "apply_wound_penalty_on_failed_leadership_test": True,
            },
        )
        pass_result = DecisionResult(
            decision_id=pass_request.decision_id,
            player_id=necron_player.id,
            option_id=pass_request.options[0].option_id,
        )
        _apply_choose_quarry(game, pass_request, pass_result)
        self.assertTrue(bool(pass_target.special_rules.get("shooting_phase_hit_penalty_active")))
        self.assertFalse(bool(pass_target.special_rules.get("shooting_phase_wound_penalty_active")))

        fail_request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Animus Damper",
            player_id=necron_player.id,
            options=[
                DecisionOption.create(
                    "Fail Vehicle",
                    payload={
                        "target_unit_id": str(get_entity_id(fail_target) or ""),
                        "source_unit_id": str(get_entity_id(source) or ""),
                        "model_id": str(get_entity_id(bearer) or ""),
                    },
                )
            ],
            context={
                "ability": "opponent_shooting_phase_disrupt",
                "ability_name": "Animus Damper",
                "ability_key": "ANIMUS_DAMPER",
                "resolution_mode": "leadership_test",
                "required_target_keywords": ["VEHICLE"],
                "apply_wound_penalty_on_failed_leadership_test": True,
            },
        )
        fail_result = DecisionResult(
            decision_id=fail_request.decision_id,
            player_id=necron_player.id,
            option_id=fail_request.options[0].option_id,
        )
        _apply_choose_quarry(game, fail_request, fail_result)
        self.assertTrue(bool(fail_target.special_rules.get("shooting_phase_hit_penalty_active")))
        self.assertTrue(bool(fail_target.special_rules.get("shooting_phase_wound_penalty_active")))
        self.assertFalse(bool(fail_target.special_rules.get("shooting_phase_ineligible_active")))
        self.assertEqual(str(fail_target.special_rules.get("shooting_phase_wound_penalty_owner", "") or ""), enemy_player.id)

    def test_reletavistic_tether_applies_six_inch_setup_for_deep_strike_and_transdimensional_displacement(self):
        game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
        transdimensional_displacement = {
            "name": "Transdimensional Displacement",
            "description": (
                "Each time this model is selected to Advance, you can remove it from the battlefield and set it up again "
                "anywhere on the battlefield that is more than 9\" horizontally away from all enemy units."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        source = _make_unit(
            "Transcendent C'tan",
            "transcendent-ctan",
            keywords=["MONSTER", "CHARACTER"],
            faction_keywords=["NECRONS"],
            abilities=[transdimensional_displacement],
        )
        enemy = _make_unit(
            "Enemy Unit",
            "enemy-unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            wounds=2,
            base_size="32mm",
        )
        necron_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 30.0, 0.0)
        _set_unit_position(enemy, 8.8, 0.0)
        game.map.units = [source, enemy]
        game.map.is_within_boundary = lambda *_args, **_kwargs: True
        game.map.check_collision_with_obstacles = lambda *_args, **_kwargs: False
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010672005",
            name="Reletavistic Tether",
            description=(
                "Transcendent C'tan model only. In your turn, each time this model is set up on the battlefield using "
                "the Deep Strike or Transdimensional Displacement abilities, it can be set up anywhere on the battlefield "
                "that is more than 6\" horizontally away from all enemy units. When doing so, if this model is set up "
                "within 9\" of one or more enemy units, until the end of the turn, it is not eligible to declare a charge."
            ),
        )

        self.assertEqual(float(source.get_deep_strike_min_distance_override() or 0.0), 6.0)

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0
        game._queue_movement_phase_advance_redeploy(player=necron_player, unit=source)

        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(str(getattr(request, "decision_type", "") or ""), DECISION_CONFIRM_YES_NO)
        self.assertEqual(str((request.context or {}).get("ability", "") or ""), "advance_redeploy")

        _resolve_yes(game, request, necron_player)

        move_request = list(game.decision_queue.list() or [])[0]
        self.assertEqual(str(getattr(move_request, "decision_type", "") or ""), DECISION_MOVE_UNIT)
        move_ctx = dict(getattr(move_request, "context", {}) or {})
        self.assertEqual(int(move_ctx.get("min_enemy_distance_horiz", 0) or 0), 6)
        self.assertEqual(float(move_ctx.get("no_charge_if_within_distance_horiz", 0) or 0), 9.0)

        move_option_id = move_request.options[0].option_id
        result = resolve_decision_command(
            game,
            move_request,
            move_option_id,
            player_id=necron_player.id,
            result_payload={
                "model_positions": [
                    {
                        "model_id": str(get_entity_id(source.models[0]) or ""),
                        "position": [0.0, 0.0, 0.0],
                        "facing": 0.0,
                    }
                ]
            },
        )
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(str(source.special_rules.get("reletavistic_tether_no_charge_turn_owner", "") or ""), necron_player.id)

        game.map = _ChargeMap(enemy)
        self.assertFalse(source.can_declare_charge_against(enemy, game))


if __name__ == "__main__":
    unittest.main()
