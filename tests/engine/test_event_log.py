from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import ObjectivePoint
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.command_kinds import CMD_NEXT_PHASE
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine import event_log as event_log_mod
from warhammer40k_ai.engine.event_log import (
    _HISTORY_PRESERVE_ID_KEYS,
    _is_id_key,
    _normalize_ids,
    DeterministicEventLog,
    GameEvent,
)
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.engine.replay import prepare_replay
from warhammer40k_ai.engine.snapshot import load_game_snapshot, snapshot_game
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility import dice as dice_mod
from warhammer40k_ai.utility.game_context import game_context
from warhammer40k_ai.utility.reroll_tracker import prepare_reroll_event


class _Entity:
    def __init__(self, entity_id: str, name: str = ""):
        self.id = entity_id
        self.name = name


class _ExpensiveRepr:
    def __repr__(self):
        raise AssertionError("event logging should not format payload reprs")


def test_event_publish_info_log_does_not_repr_payload(monkeypatch):
    from warhammer40k_ai.engine.event import system as event_system_module

    calls = []
    monkeypatch.setattr(event_system_module.logger, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(event_system_module.logger, "info", lambda *args, **_kwargs: calls.append(args))

    EventSystem().publish("model_destroyed_before_removal", model=_ExpensiveRepr())

    assert calls == [("Event publish: %s -> keys=%s", "model_destroyed_before_removal", ["model"])]


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
    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    game.event_system.publish("unit_move_started", unit=unit, action="pile_in")
    game.event_system.publish("unit_move_ended", unit=unit, action="pile_in")

    started = [e for e in game.event_log.events if e.event_type == "unit_move_started"]
    ended = [e for e in game.event_log.events if e.event_type == "unit_move_ended"]
    assert started
    assert ended
    assert started[-1].payload["action"] == "pile_in"
    assert started[-1].payload["phase_name"] == "FIGHT_PHASE"
    payload = ended[-1].payload
    assert payload["unit_id"] == "u1"
    assert payload["action"] == "pile_in"
    assert payload["phase_name"] == "FIGHT_PHASE"
    pos = payload["model_positions"][0]
    assert pos["model_id"] == "m1"
    assert pos["x"] == 1250
    assert pos["y"] == 2500
    assert pos["z"] == 0
    assert pos["facing"] == 5000


def test_unit_activation_boundary_events_logged():
    player = Player("P1", control=PlayerControl.LOCAL)
    unit = SimpleNamespace(id="u1")
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.turn = 2
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")

    game.event_system.publish(
        "unit_activation_started",
        unit=unit,
        player=player,
        phase_name="SHOOTING_PHASE",
        phase_step="SHOOT_UNITS",
        selection_purpose="ACTIVATE_SHOOTING_UNIT",
        battle_round=2,
    )
    game.event_system.publish(
        "unit_activation_ended",
        unit=unit,
        player=player,
        phase_name="SHOOTING_PHASE",
        phase_step="SHOOT_UNITS",
        selection_purpose="ACTIVATE_SHOOTING_UNIT",
        battle_round=2,
    )

    started = [e for e in game.event_log.events if e.event_type == "unit_activation_started"]
    ended = [e for e in game.event_log.events if e.event_type == "unit_activation_ended"]
    assert started[-1].payload["unit_id"] == "u1"
    assert started[-1].payload["player_id"] == player.id
    assert started[-1].payload["phase_name"] == "SHOOTING_PHASE"
    assert started[-1].payload["phase_step"] == "SHOOT_UNITS"
    assert started[-1].payload["selection_purpose"] == "ACTIVATE_SHOOTING_UNIT"
    assert started[-1].payload["battle_round"] == 2
    assert ended[-1].payload["unit_id"] == "u1"


def test_unit_move_ended_event_logs_attached_unit_models():
    bodyguard_model = SimpleNamespace(id="m1", get_location=lambda: (1.0, 2.0, 0.0, 0.0))
    leader_model = SimpleNamespace(id="m2", get_location=lambda: (3.0, 4.0, 0.0, 0.25))
    leader = SimpleNamespace(id="leader", models=[leader_model])
    unit = SimpleNamespace(id="unit", models=[bodyguard_model])
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_members = lambda: [unit, leader]
    leader.get_attached_unit_root = lambda: unit
    leader.get_attached_unit_members = lambda: [unit, leader]
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1

    game.event_system.publish("unit_move_ended", unit=unit, action="advance")

    ended = [e for e in game.event_log.events if e.event_type == "unit_move_ended"]
    assert ended
    positions = ended[-1].payload["model_positions"]
    assert {entry["model_id"] for entry in positions} == {"m1", "m2"}
    assert len(positions) == 2


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


def test_destroy_events_include_coherency_removal_context():
    attacker_model = SimpleNamespace(id="am1")
    attacker_unit = SimpleNamespace(id="au1")
    weapon_profile = SimpleNamespace(id="wp1", name="Test Blade")
    target_unit = SimpleNamespace(id="tu1")
    target_model = SimpleNamespace(
        id="tm1",
        _removal_reason="post_casualty_coherency",
        _removal_decision_id="decision-1",
        _coherency_root_unit_id="tu-root",
        _coherency_caused_by_destroyed_model_id="tm0",
        _coherency_damage_source="Allocate wound",
        _coherency_failure_reason="post_casualty",
        _coherency_causal_attacker_unit=attacker_unit,
        _coherency_causal_attacker_model=attacker_model,
        _coherency_causal_weapon_profile=weapon_profile,
    )

    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    game.event_system.publish("model_destroyed_before_removal", unit=target_unit, model=target_model)
    game.event_system.publish("unit_destroyed", unit=target_unit, last_model=target_model)

    model_events = [e for e in game.event_log.events if e.event_type == "model_destroyed_before_removal"]
    unit_events = [e for e in game.event_log.events if e.event_type == "unit_destroyed"]
    assert model_events
    assert unit_events
    for payload in (model_events[-1].payload, unit_events[-1].payload):
        assert payload["removal_reason"] == "post_casualty_coherency"
        assert payload["source_decision_id"] == "decision-1"
        assert payload["coherency_root_unit_id"] == "tu-root"
        assert payload["coherency_caused_by_destroyed_model_id"] == "tm0"
        assert payload["coherency_failure_reason"] == "post_casualty"
        assert payload["causal_attacker_unit_id"] == "au1"
        assert payload["causal_attacker_model_id"] == "am1"
        assert payload["causal_weapon_profile_id"] == "wp1"
        assert payload["causal_weapon_profile_name"] == "Test Blade"


def test_removal_context_payload_does_not_compare_model_like_values_to_none():
    class _ModelLike:
        id = "model:attacker"

        def __eq__(self, other):
            if other is None:
                raise AttributeError("'NoneType' object has no attribute 'id'")
            return getattr(other, "id", None) == self.id

    model = SimpleNamespace(id="model:victim", _coherency_causal_attacker_model=_ModelLike())
    log = DeterministicEventLog()

    payload = log._removal_context_payload(model)

    assert payload["causal_attacker_model_id"] == "model:attacker"


def test_charge_move_failed_event_logged():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    unit = SimpleNamespace(id="charger")

    game.event_system.publish(
        "charge_move_failed",
        unit=unit,
        target_unit_ids=["target-a", "target-b"],
        reason="charge_roll_insufficient_by_distance",
        roll_id=37,
        max_distance=7,
        charge_roll=7,
        declaration_range_limit=12,
        minimum_target_distance=9.2,
        maximum_target_distance=10.5,
        required_charge_distance_estimate=9.5,
        within_declaration_range=True,
        failure_stage="charge_roll_distance",
        solver_failure_reason="no_legal_charge_move",
        target_distances=[
            {
                "target_unit_id": "target-a",
                "distance": 9.2,
                "within_declaration_range": True,
                "required_charge_distance_estimate": 8.2,
            },
            {
                "target_unit_id": "target-b",
                "distance": 10.5,
                "within_declaration_range": True,
                "required_charge_distance_estimate": 9.5,
            },
        ],
        movement_type="charge",
    )

    events = [e for e in game.event_log.events if e.event_type == "charge_move_failed"]
    assert events
    payload = events[-1].payload
    assert payload["unit_id"] == "charger"
    assert payload["target_unit_ids"] == ["target-a", "target-b"]
    assert payload["reason"] == "charge_roll_insufficient_by_distance"
    assert payload["roll_id"] == 37
    assert payload["max_distance"] == 7.0
    assert payload["charge_roll"] == 7.0
    assert payload["declaration_range_limit"] == 12.0
    assert payload["minimum_target_distance"] == 9.2
    assert payload["maximum_target_distance"] == 10.5
    assert payload["required_charge_distance_estimate"] == 9.5
    assert payload["within_declaration_range"] is True
    assert payload["failure_stage"] == "charge_roll_distance"
    assert payload["solver_failure_reason"] == "no_legal_charge_move"
    assert payload["target_distances"][0]["target_unit_id"] == "target-a"
    assert payload["movement_type"] == "charge"


def test_blood_tithe_events_logged():
    player = Player("P1", control=PlayerControl.LOCAL)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.turn = 1
    attacker = SimpleNamespace(id="attacker")
    target = SimpleNamespace(id="target")
    ability = SimpleNamespace(key="ENRAGED_ABJURATION", name="Enraged Abjuration", cost=2)

    game.event_system.publish(
        "blood_tithe_points_gained",
        player=player,
        amount=1,
        total=2,
        attacker_unit=attacker,
        target_unit=target,
        roll=5,
    )
    game.event_system.publish(
        "blood_tithe_activated",
        player=player,
        ability=ability,
        total=0,
    )
    game.event_system.publish(
        "blood_tithe_updated",
        player=player,
        total=0,
        active=["Enraged Abjuration"],
    )

    gained = [event for event in game.event_log.events if event.event_type == "blood_tithe_points_gained"]
    activated = [event for event in game.event_log.events if event.event_type == "blood_tithe_activated"]
    updated = [event for event in game.event_log.events if event.event_type == "blood_tithe_updated"]
    assert gained[-1].payload["player_id"] == player.id
    assert gained[-1].payload["attacker_unit_id"] == "attacker"
    assert gained[-1].payload["target_unit_id"] == "target"
    assert gained[-1].payload["roll"] == 5
    assert activated[-1].payload["ability_key"] == "ENRAGED_ABJURATION"
    assert activated[-1].payload["cost"] == 2
    assert updated[-1].payload["active"] == ["Enraged Abjuration"]


def test_skipped_charge_move_application_logs_failed_charge_move():
    from warhammer40k_ai.engine.decision_handlers.movement import _apply_move_unit
    from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
    from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult

    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    unit = SimpleNamespace(id="charger", models=[])
    target = SimpleNamespace(id="target", models=[])
    game.entity_registry.register(unit, kind="unit")
    game.entity_registry.register(target, kind="unit")
    game.map.get_distance_between_units = lambda _unit, _target: 9.5
    skip_option = DecisionOption.create(
        "Skip",
        payload={"unit_id": "charger", "movement_type": "charge", "action": "skip"},
    )
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Charge move",
        options=[skip_option],
        context={
            "unit_id": "charger",
            "movement_type": "charge",
            "target_unit_ids": ["target"],
            "roll_id": 37,
            "max_distance": 7,
            "allow_skip": True,
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=None,
        option_id=skip_option.option_id,
        payload={"failure_reason": "no_legal_charge_move"},
    )

    _apply_move_unit(game, request, result)

    events = [e for e in game.event_log.events if e.event_type == "charge_move_failed"]
    assert events
    payload = events[-1].payload
    assert payload["unit_id"] == "charger"
    assert payload["target_unit_ids"] == ["target"]
    assert payload["reason"] == "charge_roll_insufficient_by_distance"
    assert payload["roll_id"] == 37
    assert payload["solver_failure_reason"] == "no_legal_charge_move"
    assert payload["max_distance"] == 7.0
    assert payload["charge_roll"] == 7.0
    assert payload["within_declaration_range"] is True
    assert payload["failure_stage"] == "charge_roll_distance"
    assert payload["minimum_target_distance"] == 9.5
    assert payload["required_charge_distance_estimate"] == 8.5
    assert payload["target_distances"] == [
        {
            "distance": 9.5,
            "required_charge_distance_estimate": 8.5,
            "target_unit_id": "target",
            "within_declaration_range": True,
        }
    ]


def test_resolve_coherency_application_stamps_removal_context():
    from warhammer40k_ai.engine.decision_handlers.movement import _apply_resolve_coherency
    from warhammer40k_ai.engine.decision_kinds import DECISION_RESOLVE_COHERENCY
    from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult

    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    game.map.game = game
    attacker_unit = SimpleNamespace(id="attacker-unit")
    attacker_model = SimpleNamespace(id="attacker-model")
    weapon_profile = SimpleNamespace(id="weapon-profile", name="Test Rifle")

    class _CoherencyModel:
        def __init__(self):
            self.id = "coherency-model"
            self.wounds = 1
            self.is_alive = True
            self.parent_unit = None

        def die(self, *, game_map=None):
            self.is_alive = False
            game_map.game.event_system.publish("model_destroyed_before_removal", unit=self.parent_unit, model=self)

    model = _CoherencyModel()
    unit = SimpleNamespace(
        id="coherency-unit",
        models=[model],
        _last_destroyed_by_unit=attacker_unit,
        _last_destroyed_by_model=attacker_model,
        _last_destroyed_by_weapon_profile=weapon_profile,
    )
    model.parent_unit = unit
    game.entity_registry.register(unit, kind="unit")
    game.entity_registry.register(model, kind="model")
    option = DecisionOption.create("Remove model", payload={"unit_id": unit.id})
    request = DecisionRequest.create(
        DECISION_RESOLVE_COHERENCY,
        "Resolve coherency",
        options=[option],
        context={
            "unit_id": unit.id,
            "destroyed_model_id": "initial-casualty",
            "damage_source": "Allocate wound",
            "coherency_failure_reason": "post_casualty",
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=None,
        option_id=option.option_id,
        payload={"model_ids": [model.id]},
    )

    _apply_resolve_coherency(game, request, result)

    events = [e for e in game.event_log.events if e.event_type == "model_destroyed_before_removal"]
    assert events
    payload = events[-1].payload
    assert payload["removal_reason"] == "post_casualty_coherency"
    assert payload["source_decision_id"] == request.decision_id
    assert payload["coherency_root_unit_id"] == "coherency-unit"
    assert payload["coherency_caused_by_destroyed_model_id"] == "initial-casualty"
    assert payload["coherency_damage_source"] == "Allocate wound"
    assert payload["causal_attacker_unit_id"] == "attacker-unit"
    assert payload["causal_attacker_model_id"] == "attacker-model"
    assert payload["causal_weapon_profile_id"] == "weapon-profile"


def test_combat_diagnostic_events_logged():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    attacker_unit = _Entity("attacker-unit", "Attacker")
    attacker_model = _Entity("attacker-model", "Attacker Model")
    target_unit = _Entity("target-unit", "Target")
    target_model = _Entity("target-model", "Target Model")
    weapon_profile = _Entity("weapon-profile", "Test Rifle")

    game.event_system.publish(
        "model_damage_resolved",
        attacker_model=attacker_model,
        attacker_unit=attacker_unit,
        target_model=target_model,
        target_unit=target_unit,
        weapon_profile=weapon_profile,
        damage_source="attack",
        attack_type="shooting",
        requested_damage=3,
        applied_damage=2,
        prevented_damage=1,
        wounds_before=4,
        wounds_after=2,
        model_destroyed=False,
        is_mortal=False,
    )
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=attacker_unit,
        declared_targets=[target_unit],
        successful_attacks=3,
        declaration_count=2,
        hits_by_target={target_unit: 2},
        hit_models_by_target={target_unit: {attacker_model}},
        hit_models_by_target_weapon={target_unit: {"test rifle": {attacker_model}}},
        hit_models_by_target_psychic={},
        killing_models_by_target={},
        damage_by_target={target_unit: 2},
        damage_by_target_while_engaged={},
        executed_declarations=[
            {
                "target_unit_id": target_unit.id,
                "weapon_profile_id": weapon_profile.id,
                "weapon_profile_name": weapon_profile.name,
                "model_count": 1,
                "attacks_executed": 3,
                "reason": "executed",
            }
        ],
        skipped_declarations=[
            {
                "target_unit_id": target_unit.id,
                "weapon_profile_id": weapon_profile.id,
                "weapon_profile_name": weapon_profile.name,
                "model_count": 1,
                "reason": "out_of_range",
            }
        ],
    )
    game.event_system.publish(
        "fight_attacks_resolved",
        unit=attacker_unit,
        target_unit=target_unit,
        successful_attacks=1,
        declaration_count=1,
        hits_by_target={target_unit: 1},
        hit_models_by_target={target_unit: {attacker_model}},
        hit_models_by_target_psychic={},
        killing_models_by_target={},
        damage_by_target={target_unit: 2},
        executed_declarations=[{"model_id": attacker_model.id, "attacks_executed": 1, "reason": "executed"}],
        skipped_declarations=[],
    )

    damage_event = [e for e in game.event_log.events if e.event_type == "model_damage_resolved"][-1]
    shooting_event = [e for e in game.event_log.events if e.event_type == "unit_shooting_resolved"][-1]
    fight_event = [e for e in game.event_log.events if e.event_type == "fight_attacks_resolved"][-1]

    assert damage_event.payload["target_model_id"] == target_model.id
    assert damage_event.payload["applied_damage"] == 2
    assert shooting_event.payload["declared_target_unit_ids"] == [target_unit.id]
    assert shooting_event.payload["hits_by_target"] == {target_unit.id: 2}
    assert shooting_event.payload["hit_models_by_target_weapon"] == {target_unit.id: {"test rifle": [attacker_model.id]}}
    assert shooting_event.payload["executed_declarations"][0]["attacks_executed"] == 3
    assert shooting_event.payload["skipped_declarations"][0]["reason"] == "out_of_range"
    assert fight_event.payload["damage_by_target"] == {target_unit.id: 2}
    assert fight_event.payload["successful_attacks"] == 1


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


def test_event_log_prunes_old_events_when_limit_reached():
    log = DeterministicEventLog(max_events=3)
    for idx in range(5):
        log.record("test_event", payload={"idx": idx}, validate_payload=False)

    assert len(log.events) == 3
    assert [int(event.event_id) for event in log.events] == [3, 4, 5]
    assert log.dropped_through_event_id == 2


def test_history_id_key_classifier_caches_exact_suffix_and_event_id_exception():
    _is_id_key.cache_clear()

    assert _is_id_key("player_id") is True
    assert _is_id_key("actor_id") is True
    assert _is_id_key("target_unit_id") is True
    assert _is_id_key("model_ids") is True
    assert _is_id_key("event_id") is False
    assert _is_id_key(None) is False

    before = _is_id_key.cache_info()
    assert _is_id_key("player_id") is True
    after = _is_id_key.cache_info()
    assert after.hits == before.hits + 1


def test_history_normalization_preserves_action_ids():
    normalized = _normalize_ids(
        {
            "decision_id": "decision-raw",
            "unit_id": "unit-raw",
            "action_id": "move:unit-raw:advance",
            "chosen_action_id": "chosen:unit-raw",
            "action_ids": ["action:a", "action:b"],
        },
        {},
        preserve_keys=_HISTORY_PRESERVE_ID_KEYS,
    )

    assert normalized["decision_id"] == "id_1"
    assert normalized["unit_id"] == "id_2"
    assert normalized["action_id"] == "move:unit-raw:advance"
    assert normalized["chosen_action_id"] == "chosen:unit-raw"
    assert normalized["action_ids"] == ["action:a", "action:b"]


def test_history_fast_hash_matches_after_record_and_from_payload():
    log = DeterministicEventLog()
    log.record(
        "decision_requested",
        actor_id="player:a",
        payload={"decision_id": "decision:a", "player_id": "player:a", "unit_id": "unit:a"},
        validate_payload=False,
    )
    log.record(
        "decision_resolved",
        actor_id="player:a",
        payload={"decision_id": "decision:a", "player_id": "player:a", "chosen_action_id": "action:a"},
        validate_payload=False,
    )

    expected = log.compute_history_hash()
    restored = DeterministicEventLog.from_payload(log.serialize_events(), mode="record")
    replay = DeterministicEventLog.from_payload(log.serialize_events(), mode="replay")
    replay.consume("decision_requested")
    replay.consume("decision_resolved")

    assert restored.compute_history_hash() == expected
    assert replay.compute_history_hash() == expected


def test_history_fast_hash_normalizes_raw_entity_ids_across_streams():
    def build_log(player_id: str, decision_id: str, unit_id: str, model_id: str) -> DeterministicEventLog:
        log = DeterministicEventLog()
        log.record(
            "decision_resolved",
            actor_id=player_id,
            payload={
                "decision_id": decision_id,
                "player_id": player_id,
                "unit_id": unit_id,
                "model_ids": [model_id],
                "payload": {"target_model_id": model_id},
            },
            validate_payload=False,
        )
        return log

    first = build_log("player:a", "decision:a", "unit:a", "model:a")
    second = build_log("player:b", "decision:b", "unit:b", "model:b")

    assert first.compute_history_hash(normalize_ids=True) == second.compute_history_hash(normalize_ids=True)
    assert first.compute_history_hash(normalize_ids=False) != second.compute_history_hash(normalize_ids=False)


def test_history_fast_hash_preserves_action_ids_as_hash_inputs():
    def build_log(action_id: str, chosen_action_id: str) -> DeterministicEventLog:
        log = DeterministicEventLog()
        log.record(
            "decision_resolved",
            actor_id="player:a",
            payload={
                "decision_id": "decision:a",
                "player_id": "player:a",
                "action_id": action_id,
                "chosen_action_id": chosen_action_id,
            },
            validate_payload=False,
        )
        return log

    baseline = build_log("move:unit:a", "candidate:a")
    same_entity_ids = build_log("move:unit:a", "candidate:a")
    different_action = build_log("move:unit:b", "candidate:a")
    different_chosen = build_log("move:unit:a", "candidate:b")

    assert baseline.compute_history_hash() == same_entity_ids.compute_history_hash()
    assert baseline.compute_history_hash() != different_action.compute_history_hash()
    assert baseline.compute_history_hash() != different_chosen.compute_history_hash()


def test_history_fast_hash_preserves_event_id_as_hash_input():
    event_payload = {"decision_id": "decision:a", "player_id": "player:a"}
    event_one = GameEvent(event_id=1, event_type="decision_resolved", actor_id="player:a", payload=event_payload)
    event_two = GameEvent(event_id=2, event_type="decision_resolved", actor_id="player:a", payload=event_payload)
    first = DeterministicEventLog(events=[event_one])
    second = DeterministicEventLog(events=[event_two])

    assert first.compute_history_hash() != second.compute_history_hash()


def test_history_fast_hash_is_neutral_to_automatic_pruning():
    pruned = DeterministicEventLog(max_events=3)
    retained = DeterministicEventLog(max_events=0)
    for idx in range(8):
        payload = {"idx": idx, "decision_id": f"decision:{idx}", "unit_id": f"unit:{idx % 2}"}
        pruned.record("decision_resolved", payload=payload, validate_payload=False)
        retained.record("decision_resolved", payload=payload, validate_payload=False)

    assert len(pruned.events) == 3
    assert pruned.dropped_through_event_id == 5
    assert len(retained.events) == 8
    assert retained.dropped_through_event_id == 0
    assert pruned.compute_history_hash() == retained.compute_history_hash()
    assert pruned.compute_history_hash_legacy() != retained.compute_history_hash_legacy()


def test_replay_history_fast_hash_uses_prefix_table_without_rebuild_on_consume():
    log = DeterministicEventLog()
    for idx in range(3):
        log.record("test_event", payload={"idx": idx, "unit_id": f"unit:{idx}"}, validate_payload=False)
    replay = DeterministicEventLog.from_payload(log.serialize_events(), mode="replay")
    prefix_table = replay._history_prefix_normalized
    prefix_count = replay._history_prefix_event_count

    hashes = [replay.compute_history_hash()]
    replay.consume("test_event")
    hashes.append(replay.compute_history_hash())
    replay.consume("test_event")
    hashes.append(replay.compute_history_hash())

    assert len(set(hashes)) == 3
    assert replay._history_prefix_normalized is prefix_table
    assert replay._history_prefix_event_count == prefix_count == 3


def test_append_only_record_mode_does_not_renormalize_old_events(monkeypatch):
    log = DeterministicEventLog()
    log.record("test_event", payload={"unit_id": "unit:old"}, validate_payload=False)
    normalized_event_ids: list[int] = []
    original_normalize = event_log_mod._normalize_ids

    def spy_normalize(value, *args, **kwargs):
        if isinstance(value, dict) and "event_id" in value and "type" in value:
            normalized_event_ids.append(int(value["event_id"]))
        return original_normalize(value, *args, **kwargs)

    monkeypatch.setattr(event_log_mod, "_normalize_ids", spy_normalize)

    log.record("test_event", payload={"unit_id": "unit:new"}, validate_payload=False)
    log.compute_history_hash()

    assert normalized_event_ids == [2]
