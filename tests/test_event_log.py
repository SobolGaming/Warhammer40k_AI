from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import ObjectivePoint
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.command_kinds import CMD_NEXT_PHASE
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.event_log import DeterministicEventLog
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.engine.replay import prepare_replay
from warhammer40k_ai.engine.snapshot import load_game_snapshot, snapshot_game
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility import dice as dice_mod
from warhammer40k_ai.utility.game_context import game_context
from warhammer40k_ai.utility.reroll_tracker import prepare_reroll_event


def test_dice_roll_replay_from_event_log():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    game.random_source.seed(123)
    with game_context(game):
        rolls = [dice_mod.get_dice_roll(6) for _ in range(5)]

    events = game.event_log.serialize_events()
    dice_events = [e for e in events if e.get("type") == "dice_roll"]
    assert [e["payload"]["value"] for e in dice_events] == rolls

    replay_game = Game(Battlefield(width=60, height=44), players=[])
    replay_game.random_source.seed(123)
    replay_game.event_log.detach()
    replay_log = DeterministicEventLog.from_payload(events, mode="replay")
    replay_log.attach(replay_game)
    replay_game.event_log = replay_log
    with game_context(replay_game):
        replay_rolls = [dice_mod.get_dice_roll(6) for _ in range(5)]
    assert replay_rolls == rolls


def test_snapshot_persists_event_log():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    with game_context(game):
        _ = dice_mod.get_dice_roll(6)
    snapshot = snapshot_game(game)
    assert "events" in snapshot
    assert len(snapshot["events"]) == len(game.event_log.events)

    loaded = load_game_snapshot(snapshot)
    assert len(loaded.event_log.events) == len(game.event_log.events)
    assert loaded.event_log.events[0].event_type == game.event_log.events[0].event_type


def test_roll_made_event_logged():
    player = Player("P1", control=PlayerControl.LOCAL)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.turn = 1
    game.event_system.publish(
        "roll_made",
        player=player,
        unit=None,
        roll_type="test",
        value=4,
        dice=[4],
        reroll_locked=False,
        roll_id=11,
    )
    events = [e for e in game.event_log.events if e.event_type == "roll_made"]
    assert events
    last = events[-1]
    assert last.payload["player_id"] == player.id
    assert last.payload["roll_type"] == "test"
    assert last.payload["value"] == 4


def test_roll_reroll_event_logged():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    roll_id, reroll_cb, _locked = prepare_reroll_event(game, lambda: 5)
    result = reroll_cb()
    assert result == 5
    events = [e for e in game.event_log.events if e.event_type == "roll_rerolled"]
    assert events
    last = events[-1]
    assert last.payload["roll_id"] == roll_id
    assert last.payload["result"] == 5


def test_unit_move_events_logged():
    model = SimpleNamespace(id="m1", get_location=lambda: (1.25, 2.5, 0.0, 0.5))
    unit = SimpleNamespace(id="u1", models=[model])
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    game.event_system.publish("unit_move_started", unit=unit, action="move")
    game.event_system.publish("unit_move_ended", unit=unit, action="move")

    started = [e for e in game.event_log.events if e.event_type == "unit_move_started"]
    ended = [e for e in game.event_log.events if e.event_type == "unit_move_ended"]
    assert started
    assert ended
    payload = ended[-1].payload
    assert payload["unit_id"] == "u1"
    assert payload["action"] == "move"
    pos = payload["model_positions"][0]
    assert pos["model_id"] == "m1"
    assert pos["x"] == 1250
    assert pos["y"] == 2500
    assert pos["z"] == 0
    assert pos["facing"] == 5000


def test_destroy_events_logged():
    attacker_model = SimpleNamespace(id="am1")
    attacker_unit = SimpleNamespace(id="au1")
    target_model = SimpleNamespace(id="tm1")
    target_unit = SimpleNamespace(id="tu1")
    weapon_profile = SimpleNamespace(id="wp1", name="Test Blade")

    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    game.event_system.publish(
        "model_destroyed",
        attacker_model=attacker_model,
        attacker_unit=attacker_unit,
        target_model=target_model,
        target_unit=target_unit,
        weapon_profile=weapon_profile,
        is_mortal=True,
    )
    game.event_system.publish(
        "unit_destroyed",
        unit=target_unit,
        last_model=target_model,
        destroyed_by_unit=attacker_unit,
        destroyed_by_model=attacker_model,
        destroyed_by_weapon_profile=weapon_profile,
    )

    model_events = [e for e in game.event_log.events if e.event_type == "model_destroyed"]
    unit_events = [e for e in game.event_log.events if e.event_type == "unit_destroyed"]
    assert model_events
    assert unit_events
    model_payload = model_events[-1].payload
    unit_payload = unit_events[-1].payload
    assert model_payload["attacker_unit_id"] == "au1"
    assert model_payload["target_unit_id"] == "tu1"
    assert model_payload["weapon_profile_id"] == "wp1"
    assert model_payload["weapon_profile_name"] == "Test Blade"
    assert model_payload["is_mortal"] is True
    assert unit_payload["unit_id"] == "tu1"
    assert unit_payload["destroyed_by_unit_id"] == "au1"
    assert unit_payload["weapon_profile_id"] == "wp1"


def test_replay_helper_consumes_event_tail():
    player = Player("P1", control=PlayerControl.LOCAL)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.turn = 1
    game.setup_complete = True
    game.phase = BattleRoundPhases.COMMAND_PHASE
    snapshot = snapshot_game(game)

    with game_context(game):
        recorded_roll = dice_mod.get_dice_roll(6)
    cmd = GameCommand.create(CMD_NEXT_PHASE, player_id=player.id)
    game.apply_command(cmd)

    tail = game.event_log.serialize_events()
    replay_game = prepare_replay(snapshot, tail)

    with game_context(replay_game):
        replay_roll = dice_mod.get_dice_roll(6)
    replay_cmd = GameCommand.create(CMD_NEXT_PHASE, player_id=replay_game.get_current_player().id)
    replay_game.apply_command(replay_cmd)
    replay_game.event_log.assert_consumed()

    assert replay_roll == recorded_roll
    assert replay_game.phase == BattleRoundPhases.MOVEMENT_PHASE


def test_vp_awarded_event_logged():
    player = Player("P1", control=PlayerControl.LOCAL)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.turn = 1
    awarded = game.award_vp(player, 5, source="primary", timing="Test")
    assert awarded == 5
    events = [e for e in game.event_log.events if e.event_type == "vp_awarded"]
    assert events
    payload = events[-1].payload
    assert payload["player_id"] == player.id
    assert payload["awarded_vp"] == 5
    assert payload["total_vp"] == 5
    assert payload["source"] == "primary"


def test_phase_events_logged():
    player = Player("P1", control=PlayerControl.LOCAL)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.turn = 1
    game.setup_complete = True
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.next_phase()
    events = [e.event_type for e in game.event_log.events]
    assert "phase_end" in events
    assert "phase_start" in events


def test_objective_control_changed_logged():
    player = Player("P1", control=PlayerControl.LOCAL)
    point = ObjectivePoint(x=1.0, y=2.0, z=0.0, control_radius=3.0)
    point.controlling_player = player
    game_state = SimpleNamespace(players=[player], event_system=EventSystem())
    log = DeterministicEventLog()
    log.attach(game_state)
    point.update_control(game_state)
    events = [e for e in log.events if e.event_type == "objective_control_changed"]
    assert events
    payload = events[-1].payload
    assert payload["objective_id"] == point.id
    assert payload["previous_controller_id"] == player.id
    assert payload["controller_id"] is None


def test_event_log_hash_deterministic_with_seed():
    game1 = Game(Battlefield(width=60, height=44), players=[])
    game1.turn = 1
    game1.random_source.seed(123)
    with game_context(game1):
        _ = [dice_mod.get_dice_roll(6) for _ in range(5)]
    hash1 = game1.event_log.compute_hash()

    game2 = Game(Battlefield(width=60, height=44), players=[])
    game2.turn = 1
    game2.random_source.seed(123)
    with game_context(game2):
        _ = [dice_mod.get_dice_roll(6) for _ in range(5)]
    hash2 = game2.event_log.compute_hash()

    assert hash1 == hash2


def test_replay_produces_identical_end_state():
    player = Player("P1", control=PlayerControl.LOCAL)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.turn = 1
    game.setup_complete = True
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.random_source.seed(42)

    snapshot = snapshot_game(game)

    with game_context(game):
        _ = dice_mod.get_dice_roll(6)
    cmd = GameCommand.create(CMD_NEXT_PHASE, player_id=player.id)
    game.apply_command(cmd)
    end_snapshot = snapshot_game(game)

    tail = game.event_log.serialize_events()
    replay_game = prepare_replay(snapshot, tail)

    with game_context(replay_game):
        _ = dice_mod.get_dice_roll(6)
    replay_cmd = GameCommand.create(CMD_NEXT_PHASE, player_id=replay_game.get_current_player().id)
    replay_game.apply_command(replay_cmd)
    replay_game.event_log.assert_consumed()

    replay_snapshot = snapshot_game(replay_game)
    assert replay_snapshot == end_snapshot
