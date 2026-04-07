import unittest

from warhammer40k_ai.engine.decision_handlers.movement import _finalize_reserves_arrival_move
from warhammer40k_ai.engine.decision_kinds import DECISION_DISEMBARK
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import MovementAction, Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


AERIAL_SEEDING_ABILITY = {
    "name": "Aerial Seeding",
    "description": (
        "This model must start the battle in Reserves, but neither it nor any units embarked within it are counted "
        "towards any limits placed on the maximum number of Reserves units you can start the battle with. This model "
        "can be set up in the Reinforcements step of your first, second or third Movement phase, regardless of any "
        "mission rules. Any units embarked within this model must immediately disembark after it has been set up on "
        "the battlefield, and they must be set up more than 9\" away from all enemy models. After this model has been "
        "set up on the battlefield, no units can embark within it."
    ),
    "type": "Datasheet",
    "parameter": "",
}


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        transport_text: str = "",
        base_size: str = "32mm",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["TYRANIDS"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "9",
                "Sv": "3",
                "W": "12",
                "Ld": "7",
                "OC": "1",
                "base_size": str(base_size),
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport_text or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_tyrannocyte() -> Unit:
    return Unit(
        _MockDatasheet(
            "Tyrannocyte",
            keywords=["MONSTER", "TRANSPORT", "DEEP STRIKE"],
            faction_keywords=["TYRANIDS"],
            abilities=[AERIAL_SEEDING_ABILITY],
            transport_text="This model has a transport capacity of 20 TYRANIDS INFANTRY models.",
            base_size="100mm",
        )
    )


def _make_infantry(name: str, *, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=["INFANTRY"],
            faction_keywords=faction_keywords or ["TYRANIDS"],
            abilities=[],
            base_size="32mm",
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    tyr_army = Army.with_detachment("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _aerial_disembark_requests(game: Game):
    requests = []
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_DISEMBARK:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != "drop_pod_assault_disembark":
            continue
        requests.append(req)
    return requests


class TestTyranidsAerialSeeding(unittest.TestCase):
    def test_aerial_seeding_rule_is_detected_and_forces_start_in_reserves(self):
        tyrannocyte = _make_tyrannocyte()
        rule = tyrannocyte.get_drop_pod_assault_rule()
        self.assertIsInstance(rule, dict)
        self.assertEqual(str(rule.get("source", "") or ""), "Aerial Seeding")
        self.assertTrue(bool(rule.get("requires_start_in_reserves", False)))
        self.assertTrue(bool(rule.get("allows_turn_one_arrival", False)))
        self.assertTrue(bool(rule.get("immediate_disembark", False)))
        self.assertTrue(bool(rule.get("no_embark_after_setup", False)))
        self.assertTrue(bool(rule.get("counts_not_towards_reserves_limit", False)))
        self.assertTrue(bool(tyrannocyte.must_start_in_reserves()))

    def test_aerial_seeding_transport_is_exempt_from_reserves_unit_cap(self):
        game, _tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
        tyrannocyte = _make_tyrannocyte()
        passenger = _make_infantry("Termagants")
        unit_a = _make_infantry("Hormagaunts")
        unit_b = _make_infantry("Gargoyles")
        unit_c = _make_infantry("Neurogaunts")

        tyr_army.add_unit(tyrannocyte)
        tyr_army.add_unit(passenger)
        tyr_army.add_unit(unit_a)
        tyr_army.add_unit(unit_b)
        tyr_army.add_unit(unit_c)
        game.rebuild_entity_registry()

        self.assertTrue(bool(tyrannocyte.add_passenger(passenger, game_map=game.map)))
        passenger.round_state.embarked_this_round = False

        decisions = {
            str(get_entity_id(tyrannocyte) or ""): "reserves",
            str(get_entity_id(unit_a) or ""): "reserves",
            str(get_entity_id(unit_b) or ""): "reserves",
            str(get_entity_id(unit_c) or ""): "deploy",
        }

        status = tyr_army.validate_reserves_decisions(decisions)
        self.assertTrue(bool(status.get("valid", False)))
        self.assertEqual(int(status.get("reserve_units", 0) or 0), 2)
        self.assertLessEqual(int(status.get("reserve_units", 0) or 0), int(status["limits"]["max_units"]))

    def test_aerial_seeding_arrival_queues_mandatory_disembark_and_locks_embark(self):
        game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
        tyrannocyte = _make_tyrannocyte()
        passenger = _make_infantry("Tyranid Warriors")
        extra_unit = _make_infantry("Spare Unit")
        tyr_army.add_unit(tyrannocyte)
        tyr_army.add_unit(passenger)
        tyr_army.add_unit(extra_unit)
        game.rebuild_entity_registry()

        self.assertTrue(bool(tyrannocyte.add_passenger(passenger, game_map=game.map)))
        passenger.round_state.embarked_this_round = False
        tyrannocyte.deployed = False
        tyrannocyte.reserve_status = "reserves"
        tyrannocyte._started_in_reserves = True

        tyrannocyte_model_id = str(get_entity_id(tyrannocyte.models[0]) or "")
        _finalize_reserves_arrival_move(
            game,
            tyrannocyte,
            [{"model_id": tyrannocyte_model_id, "position": [20.0, 20.0, 0.0], "facing": 0.0}],
        )

        requests = _aerial_disembark_requests(game)
        self.assertEqual(len(requests), 1)
        req = requests[0]
        ctx = dict(getattr(req, "context", {}) or {})
        self.assertTrue(bool(ctx.get("mandatory_disembark", False)))
        self.assertEqual(str(ctx.get("ability_name", "") or ""), "Aerial Seeding")
        self.assertEqual(float(ctx.get("disembark_min_enemy_horizontal_distance", 0) or 0), 9.0)

        opt = list(getattr(req, "options", []) or [])[0]
        resolved = resolve_decision_command(
            game,
            req,
            opt.option_id,
            result_payload={},
            player_id=tyr_player.id,
        )
        self.assertTrue(bool(getattr(resolved, "ok", False)))
        self.assertIsNone(getattr(passenger, "embarked_in", None))
        self.assertTrue(bool(passenger.round_state.disembarked_this_round))

        transport_sr = dict(getattr(tyrannocyte, "special_rules", {}) or {})
        self.assertTrue(bool(transport_sr.get("drop_pod_embark_locked", False)))
        self.assertEqual(str(transport_sr.get("drop_pod_embark_lock_source", "") or ""), "Aerial Seeding")
        self.assertFalse(bool(tyrannocyte.can_transport(extra_unit)))

    def test_aerial_seeding_disembark_counts_as_normal_move_and_blocks_charge(self):
        game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
        tyrannocyte = _make_tyrannocyte()
        passenger = _make_infantry("Tyranid Warriors")
        enemy = _make_infantry("Enemy Unit", faction_keywords=["ENEMY"])
        tyr_army.add_unit(tyrannocyte)
        tyr_army.add_unit(passenger)
        enemy_army.add_unit(enemy)
        enemy.deployed = True
        enemy.models[0].set_location(35.0, 20.0, 0.0, 0.0)
        game.map.units = [enemy]
        game.rebuild_entity_registry()

        self.assertTrue(bool(tyrannocyte.add_passenger(passenger, game_map=game.map)))
        passenger.round_state.embarked_this_round = False
        tyrannocyte.deployed = False
        tyrannocyte.reserve_status = "reserves"
        tyrannocyte._started_in_reserves = True

        tyrannocyte_model_id = str(get_entity_id(tyrannocyte.models[0]) or "")
        _finalize_reserves_arrival_move(
            game,
            tyrannocyte,
            [{"model_id": tyrannocyte_model_id, "position": [20.0, 20.0, 0.0], "facing": 0.0}],
        )
        requests = _aerial_disembark_requests(game)
        self.assertEqual(len(requests), 1)
        req = requests[0]
        opt = list(getattr(req, "options", []) or [])[0]
        passenger_model_id = str(get_entity_id(passenger.models[0]) or "")
        resolved = resolve_decision_command(
            game,
            req,
            opt.option_id,
            result_payload={"model_positions": [{"model_id": passenger_model_id, "position": [23.0, 20.0, 0.0]}]},
            player_id=tyr_player.id,
        )

        self.assertTrue(bool(getattr(resolved, "ok", False)))
        self.assertTrue(bool(passenger.round_state.disembarked_from_moved_transport))
        self.assertTrue(bool(passenger.round_state.disembarked_cannot_charge))
        self.assertTrue(bool(passenger.round_state.reinforced_this_round))
        self.assertTrue(bool(passenger.arrived_from_reserves_this_turn))
        self.assertEqual(int(getattr(passenger, "reserve_turn_deployed", 0) or 0), int(game.turn))
        self.assertFalse(passenger.can_declare_charge_against(enemy, game))
        self.assertFalse(
            passenger._execute_action(
                MovementAction.MOVE.value,
                (24.0, 20.0, 0.0),
                game.map,
            )
        )


if __name__ == "__main__":
    unittest.main()
