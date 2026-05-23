import os
import unittest

from warhammer40k_ai.engine.decision_handlers.movement import _finalize_reserves_arrival_move
from warhammer40k_ai.engine.decision_kinds import DECISION_DISEMBARK
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import MovementAction, Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


DROP_POD_ASSAULT_ABILITY = {
    "name": "Drop Pod Assault",
    "description": (
        "This model must start the battle in Reserves and can be set up in the Reinforcements step of your first, "
        "second or third Movement phase, regardless of any mission rules. Any units embarked within this model must "
        "immediately disembark after it has been set up on the battlefield, and they must be set up more than 9\" away "
        "from all enemy models."
    ),
    "type": "Datasheet",
    "parameter": "",
}

DEPLOYMENT_COMPLETE_ABILITY = {
    "name": "Deployment Complete",
    "description": (
        "Once this unit is set up on the battlefield and all units within it have disembarked, until the end of the "
        "battle, units cannot embark within this TRANSPORT."
    ),
    "type": "Datasheet",
    "parameter": "",
}

COMBAT_DISEMBARKATION_ABILITY = {
    "name": "Combat Disembarkation",
    "description": (
        "Each time a unit disembarks from this model after it has been set up on the battlefield, that unit is still "
        "eligible to declare a charge this turn."
    ),
    "type": "Datasheet",
    "parameter": "",
}

DESIGNER_NOTE_ABILITY = {
    "name": "Designer's Note",
    "description": (
        "The highlighted portions of this model are the only parts that are considered to make up its hull. Models "
        "can be set up or end a move on any part of this model that is not highlighted in red. If any models are on "
        "non-highlighted sections of this model when it is destroyed, place those models as close to their original "
        "position as possible, on the battlefield, after removing this model."
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
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS ASTARTES"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "8",
                "Sv": "3",
                "W": "8",
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


def _make_drop_pod(*, with_deployment_complete: bool = True) -> Unit:
    abilities = [DROP_POD_ASSAULT_ABILITY, COMBAT_DISEMBARKATION_ABILITY, DESIGNER_NOTE_ABILITY]
    if with_deployment_complete:
        abilities.append(DEPLOYMENT_COMPLETE_ABILITY)
    return Unit(
        _MockDatasheet(
            "Drop Pod",
            keywords=["VEHICLE", "TRANSPORT"],
            faction_keywords=["ADEPTUS ASTARTES"],
            abilities=abilities,
            transport_text="This model has a transport capacity of 10 ADEPTUS ASTARTES INFANTRY models.",
            base_size="80mm",
        )
    )


def _make_infantry(name: str, *, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=["INFANTRY"],
            faction_keywords=faction_keywords or ["ADEPTUS ASTARTES"],
            abilities=[],
            base_size="32mm",
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("SM", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, sm_player, enemy_player, sm_army, enemy_army


def _place_unit(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _drop_pod_disembark_requests(game: Game):
    requests = []
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_DISEMBARK:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != "drop_pod_assault_disembark":
            continue
        requests.append(req)
    return requests


def _seed_support_maps():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)
    return gsm


class TestDropPodAssaultAndDeploymentComplete(unittest.TestCase):
    def test_drop_pod_assault_forces_start_in_reserves(self):
        pod = _make_drop_pod(with_deployment_complete=True)
        self.assertTrue(bool(pod.must_start_in_reserves()))

    def test_drop_pod_arrival_queues_mandatory_disembark_and_locks_embark_after_resolution(self):
        game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
        pod = _make_drop_pod(with_deployment_complete=True)
        passenger = _make_infantry("Assault Intercessors")
        extra_unit = _make_infantry("Spare Squad")
        sm_army.add_unit(pod)
        sm_army.add_unit(passenger)
        sm_army.add_unit(extra_unit)
        game.rebuild_entity_registry()

        self.assertTrue(bool(pod.add_passenger(passenger, game_map=game.map)))
        passenger.round_state.embarked_this_round = False
        pod.deployed = False
        pod.reserve_status = "reserves"
        pod._started_in_reserves = True

        pod_model_id = str(get_entity_id(pod.models[0]) or "")
        _finalize_reserves_arrival_move(
            game,
            pod,
            [{"model_id": pod_model_id, "position": [20.0, 20.0, 0.0], "facing": 0.0}],
        )

        requests = _drop_pod_disembark_requests(game)
        self.assertEqual(len(requests), 1)
        req = requests[0]
        ctx = dict(getattr(req, "context", {}) or {})
        self.assertTrue(bool(ctx.get("mandatory_disembark", False)))
        self.assertEqual(float(ctx.get("disembark_min_enemy_horizontal_distance", 0) or 0), 9.0)
        self.assertEqual(len(list(getattr(req, "options", []) or [])), 1)

        opt = list(getattr(req, "options", []) or [])[0]
        resolved = resolve_decision_command(
            game,
            req,
            opt.option_id,
            result_payload={},
            player_id=sm_player.id,
        )
        self.assertTrue(bool(getattr(resolved, "ok", False)))
        self.assertIsNone(getattr(passenger, "embarked_in", None))
        self.assertTrue(bool(passenger.round_state.disembarked_this_round))

        transport_sr = dict(getattr(pod, "special_rules", {}) or {})
        self.assertTrue(bool(transport_sr.get("drop_pod_embark_locked", False)))
        self.assertFalse(bool(transport_sr.get("drop_pod_embark_lock_pending", False)))
        self.assertFalse(bool(pod.can_transport(extra_unit)))

    def test_drop_pod_disembark_manual_positions_enforce_nine_inch_enemy_restriction(self):
        game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
        pod = _make_drop_pod(with_deployment_complete=True)
        passenger = _make_infantry("Assault Intercessors")
        enemy = _make_infantry("Enemy Unit", faction_keywords=["ENEMY"])
        sm_army.add_unit(pod)
        sm_army.add_unit(passenger)
        enemy_army.add_unit(enemy)
        _place_unit(enemy, 32.0, 20.0)
        game.map.units = [enemy]
        game.rebuild_entity_registry()

        self.assertTrue(bool(pod.add_passenger(passenger, game_map=game.map)))
        passenger.round_state.embarked_this_round = False
        pod.deployed = False
        pod.reserve_status = "reserves"
        pod._started_in_reserves = True

        pod_model_id = str(get_entity_id(pod.models[0]) or "")
        _finalize_reserves_arrival_move(
            game,
            pod,
            [{"model_id": pod_model_id, "position": [20.0, 20.0, 0.0], "facing": 0.0}],
        )
        requests = _drop_pod_disembark_requests(game)
        self.assertEqual(len(requests), 1)
        req = requests[0]
        opt = list(getattr(req, "options", []) or [])[0]
        passenger_model_id = str(get_entity_id(passenger.models[0]) or "")
        invalid = resolve_decision_command(
            game,
            req,
            opt.option_id,
            result_payload={"model_positions": [{"model_id": passenger_model_id, "position": [23.0, 20.0, 0.0]}]},
            player_id=sm_player.id,
        )
        self.assertFalse(bool(getattr(invalid, "ok", False)))
        self.assertTrue(any("too close" in str(err).lower() for err in list(getattr(invalid, "errors", []) or [])))

    def test_drop_pod_combat_disembarkation_counts_as_normal_move_but_still_allows_charge(self):
        game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
        pod = _make_drop_pod(with_deployment_complete=True)
        passenger = _make_infantry("Assault Intercessors")
        enemy = _make_infantry("Enemy Unit", faction_keywords=["ENEMY"])
        sm_army.add_unit(pod)
        sm_army.add_unit(passenger)
        enemy_army.add_unit(enemy)
        _place_unit(enemy, 35.0, 20.0)
        game.map.units = [enemy]
        game.rebuild_entity_registry()

        self.assertTrue(bool(pod.add_passenger(passenger, game_map=game.map)))
        passenger.round_state.embarked_this_round = False
        pod.deployed = False
        pod.reserve_status = "reserves"
        pod._started_in_reserves = True

        pod_model_id = str(get_entity_id(pod.models[0]) or "")
        _finalize_reserves_arrival_move(
            game,
            pod,
            [{"model_id": pod_model_id, "position": [20.0, 20.0, 0.0], "facing": 0.0}],
        )
        requests = _drop_pod_disembark_requests(game)
        self.assertEqual(len(requests), 1)
        req = requests[0]
        opt = list(getattr(req, "options", []) or [])[0]
        passenger_model_id = str(get_entity_id(passenger.models[0]) or "")
        resolved = resolve_decision_command(
            game,
            req,
            opt.option_id,
            result_payload={"model_positions": [{"model_id": passenger_model_id, "position": [23.0, 20.0, 0.0]}]},
            player_id=sm_player.id,
        )

        self.assertTrue(bool(getattr(resolved, "ok", False)))
        self.assertTrue(bool(passenger.round_state.disembarked_this_round))
        self.assertTrue(bool(passenger.round_state.disembarked_from_moved_transport))
        self.assertFalse(bool(passenger.round_state.disembarked_cannot_charge))
        self.assertTrue(bool(passenger.round_state.reinforced_this_round))
        self.assertTrue(bool(passenger.arrived_from_reserves_this_turn))
        self.assertEqual(int(getattr(passenger, "reserve_turn_deployed", 0) or 0), int(game.turn))
        self.assertTrue(passenger.can_declare_charge_against(enemy, game))
        self.assertFalse(
            passenger._execute_action(
                MovementAction.MOVE.value,
                (24.0, 20.0, 0.0),
                game.map,
            )
        )


def test_support_matrix_classifies_drop_pod_abilities_as_supported():
    gsm = _seed_support_maps()

    status, notes = gsm._classify_ability(
        "Combat Disembarkation",
        COMBAT_DISEMBARKATION_ABILITY["description"],
        faction_id="SM",
    )
    assert status == "Supported"
    assert "transport setup" in str(notes or "").lower()

    status, notes = gsm._classify_ability(
        "Designer's Note",
        DESIGNER_NOTE_ABILITY["description"],
        faction_id="SM",
    )
    assert status == "Supported"
    assert "hull-only" in str(notes or "").lower()


if __name__ == "__main__":
    unittest.main()
