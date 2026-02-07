import pytest

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_EXAMPLE
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.mission_cards import MarkedForDeathSecondary, TakeAndHoldPrimary
from warhammer40k_ai.engine.missions import CutoutType, DeploymentZone, DeploymentZoneType, ZoneCutout
from warhammer40k_ai.engine.phase import BattleRoundPhases, SetupPhase
from warhammer40k_ai.engine.snapshot import ANGLE_SCALE, POSITION_SCALE, load_game_snapshot, snapshot_game
from warhammer40k_ai.roster.army import Army, parse_army_list
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit, UnitRoundState
from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp
from warhammer40k_ai.waha_helper import WahaHelper


pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def waha_helper():
    return WahaHelper()


def _build_game(waha_helper):
    datasheet_one = waha_helper.get_full_datasheet_info_by_name("Bloodletters")
    datasheet_two = waha_helper.get_full_datasheet_info_by_name("Servitor Battleclade")
    assert datasheet_one is not None
    assert datasheet_two is not None

    unit_one = Unit(datasheet_one)
    unit_two = Unit(datasheet_two)

    army_one = Army(faction=unit_one.faction, detachment_type="")
    army_two = Army(faction=unit_two.faction, detachment_type="")
    unit_one.parent_army = army_one
    unit_two.parent_army = army_two
    army_one.units.append(unit_one)
    army_two.units.append(unit_two)
    army_one.warlord = unit_one

    player_one = Player("Player One", control=PlayerControl.LOCAL, army=army_one)
    player_two = Player("Player Two", control=PlayerControl.LOCAL, army=army_two)

    game = Game(Battlefield(width=60, height=44), players=[player_one, player_two])
    game.map.units = [unit_one, unit_two]
    return game, unit_one, unit_two, player_one, player_two


def test_snapshot_roundtrip_core_state(waha_helper):
    game, unit_one, unit_two, player_one, player_two = _build_game(waha_helper)

    lost_model = unit_one.models.pop()
    unit_one.models_lost.append(lost_model)

    model = unit_one.models[0]
    model.model_base.set_position(1.125, 2.5, 0.75)
    model.model_base.set_facing(1.2345)
    model.last_move_path = [(0.25, 0.5, 0.0, 0.5)]
    model._temporary_effects = {"linked_unit": unit_two}
    model._once_per_battle_used = {"once"}
    model._shot_via_firing_deck_this_round = True

    unit_one._characteristic_modifiers = {
        "movement": [Modifier(ModifierOp.ADD, 1, source="test")],
    }
    unit_one.round_state = UnitRoundState()
    unit_one.round_state.advanced_this_round = True
    unit_one.round_state.num_lost_models_this_round = 1
    unit_one.round_state.advance_roll = 5

    shock = BattleShockEffect(current_turn=game.turn)
    shock.turn = 3
    shock.phase = 1
    unit_one.status_effects = [shock]

    point = ObjectivePoint(x=10.5, y=20.25, z=0.0, control_radius=3.0)
    point.controlling_player = player_one
    objective = Objective(
        name="Test Objective",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="Test",
        conditions=lambda g: True,
        location=point,
    )
    objective.completed = True
    game.map.objectives = [objective]
    game.objectives = [objective]

    zone = DeploymentZone(
        name="Test Zone",
        zone_type=DeploymentZoneType.DEFENDER,
        vertices=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        cutouts=[ZoneCutout(cutout_type=CutoutType.CIRCLE, center_x=5.0, center_y=5.0, parameters=2.0)],
    )
    game.deployment_zones = {
        player_one.id: {"name": "Defender Zone", "zone_type": "defender", "mission_zones": [zone]},
        player_two.id: {"name": "Attacker Zone", "zone_type": "attacker", "mission_zones": [zone]},
    }
    game.map.deployment_zones = dict(game.deployment_zones)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.setup_phase = SetupPhase.DEPLOY_ARMIES
    game.setup_complete = True
    game.battle_shock_step_active = True
    game.current_player_index = 1
    game.attacker_index = 0
    game.defender_index = 1
    game.deployment_turn_index = 1
    game.first_turn_player_index = 0
    game.battle_round_starting_player_index = 1
    game.deployment_actions = {player_one.id: "deploy", player_two.id: "deploy"}
    game.deployment_skip_turns = {0: 1}
    game.deployment_notice = "Test notice"
    game.waiting_for_deployment_input = True
    game.selected_mission_info = {"name": "Test Mission"}
    game.commands = ["do-thing"]
    game.secondary_mission_mode = "tactical"
    game.in_progress_actions = [{"action": "test", "unit": unit_one}]
    game.completed_actions_this_turn = [{"action": "done", "unit": unit_two}]
    game.destroyed_units_this_turn = [unit_two]
    game.models_destroyed_this_turn = [unit_two.models[0]]
    game.destroyed_units_this_battle_round_by_player = {player_one: 2}
    game.phase_targeted_units = {"shooting": {unit_two.id}}
    game.phase_charge_targets = {"charge": {unit_two.id}}
    game._phoenix_gem_pending = [{"unit": unit_one}]
    game._blood_surge_shooting_snapshot = {unit_one: {unit_two: 3}}
    game._horde_move_shooting_snapshot = {unit_one: {unit_two: 1}}
    game._frenzy_shooting_targets = {unit_one: [unit_two]}
    game._frenzy_fight_targets = {unit_one: [unit_two]}
    game._pain_parasite_shooting_snapshot = {unit_one: {unit_two: 1}}
    game._pain_parasite_fight_snapshot = {unit_one: {unit_two: 2}}
    game.army_muster_requests = {"alpha": unit_one}

    player_one.primary_mission = TakeAndHoldPrimary()
    deck_card = MarkedForDeathSecondary()
    deck_card.alpha_targets = [unit_two]
    deck_card.gamma_target = unit_two
    active_card = MarkedForDeathSecondary()
    active_card.alpha_targets = [unit_two]
    active_card.gamma_target = unit_two
    player_one.secondary_deck = [deck_card]
    player_one.active_secondaries = [active_card]

    req = DecisionRequest.create(
        DECISION_CONFIRM_EXAMPLE,
        prompt="Test decision",
        player_id=player_one.id,
        options=[
            DecisionOption.create("Pick", payload={"target": unit_two}),
            DecisionOption.create("None", payload={}),
        ],
        context={"unit": unit_one},
    )
    game.decision_queue.add(req)

    cmd = GameCommand.create(
        "TEST_COMMAND",
        player_id=player_one.id,
        payload={"unit": unit_one},
        metadata={"model": unit_one.models[0]},
    )
    game.command_queue = [cmd]

    game.random_source.seed(123)
    _ = game.random_source.random()
    snapshot = snapshot_game(game)
    expected_random = game.random_source.random()

    loaded = load_game_snapshot(snapshot)
    loaded_units = {u.id: u for p in loaded.players for u in p.army.units}
    loaded_unit_one = loaded_units[unit_one.id]
    loaded_unit_two = loaded_units[unit_two.id]

    assert loaded.turn == game.turn
    assert loaded.phase == game.phase
    assert loaded.setup_phase == game.setup_phase
    assert loaded.battle_shock_step_active is True
    assert loaded.current_player_index == game.current_player_index
    assert loaded.deployment_skip_turns == game.deployment_skip_turns
    assert loaded.deployment_notice == game.deployment_notice
    assert loaded.waiting_for_deployment_input is True

    assert len(loaded.map.objectives) == 1
    loaded_obj = loaded.map.objectives[0]
    assert loaded_obj.name == "Test Objective"
    assert loaded_obj.completed is True
    assert loaded_obj.location.x == pytest.approx(10.5)
    assert loaded_obj.location.y == pytest.approx(20.25)
    assert loaded_obj.location.controlling_player.id == player_one.id

    loaded_model = loaded_unit_one.models[0]
    assert loaded_model.model_base.x == pytest.approx(1.125)
    assert loaded_model.model_base.y == pytest.approx(2.5)
    assert loaded_model.model_base.z == pytest.approx(0.75)
    assert loaded_model.model_base.facing == pytest.approx(1.2345)
    assert loaded_model.last_move_path[0][0] == pytest.approx(0.25)

    assert loaded_unit_one.round_state.advanced_this_round is True
    assert loaded_unit_one.round_state.num_lost_models_this_round == 1
    assert loaded_unit_one.round_state.advance_roll == 5

    mods = loaded_unit_one._characteristic_modifiers["movement"]
    assert mods[0].op == ModifierOp.ADD
    assert mods[0].value == 1
    assert mods[0].source == "test"

    assert isinstance(loaded_unit_one.status_effects[0], BattleShockEffect)
    assert loaded_unit_one.status_effects[0].turn == 3
    assert loaded_unit_one.status_effects[0].phase == 1

    loaded_player_one = loaded.players[0]
    assert loaded_player_one.primary_mission.name == "Take and Hold"
    assert loaded_player_one.secondary_deck[0].alpha_targets[0].id == loaded_unit_two.id

    loaded_decision = loaded.decision_queue.list()[0]
    assert loaded_decision.decision_id == req.decision_id
    assert loaded_decision.context["unit"].id == loaded_unit_one.id
    assert loaded_decision.options[0].payload["target"].id == loaded_unit_two.id

    loaded_cmd = loaded.command_queue[0]
    assert loaded_cmd.command_id == cmd.command_id
    assert loaded_cmd.payload["unit"].id == loaded_unit_one.id
    assert loaded_cmd.metadata["model"].id == loaded_unit_one.models[0].id

    assert loaded.random_source.random() == pytest.approx(expected_random)
    assert loaded._horde_move_shooting_snapshot[str(loaded_unit_one.id)][str(loaded_unit_two.id)] == 1


def test_snapshot_fixed_point_coordinates(waha_helper):
    game, unit_one, _, _, _ = _build_game(waha_helper)

    model = unit_one.models[0]
    model.model_base.set_position(3.333, 4.444, 0.0)
    model.model_base.set_facing(0.9876)

    snapshot = snapshot_game(game)
    units_by_id = {u["id"]: u for u in snapshot["units"]}
    model_data = next(
        m for m in units_by_id[unit_one.id]["models"] if m["id"] == model.id
    )

    assert model_data["position"]["x"] == int(round(3.333 * POSITION_SCALE))
    assert model_data["position"]["y"] == int(round(4.444 * POSITION_SCALE))
    assert model_data["position"]["facing"] == int(round(0.9876 * ANGLE_SCALE))


def test_snapshot_preserves_army_points_totals(waha_helper):
    army_one = parse_army_list("army_lists/warhammer_app_dump.txt", waha_helper)
    army_two = parse_army_list("army_lists/chaos_daemons_GT2023.txt", waha_helper)
    army_one.validate()
    army_two.validate()
    before_points = [army_one.get_total_points(), army_two.get_total_points()]

    player_one = Player("Player One", control=PlayerControl.LOCAL, army=army_one)
    player_two = Player("Player Two", control=PlayerControl.LOCAL, army=army_two)
    game = Game(Battlefield(width=60, height=44), players=[player_one, player_two])
    game.turn = 1  # snapshots require battle round >= 1

    snapshot = snapshot_game(game)
    loaded = load_game_snapshot(snapshot)
    after_points = [pl.army.get_total_points() for pl in loaded.players]

    assert after_points == before_points
