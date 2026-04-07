from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.game_setup_flow import PregameStepId, driver_managed_setup_phases
from warhammer40k_ai.engine.phase import SetupPhase
from warhammer40k_ai.engine.snapshot import load_game_snapshot, snapshot_game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl


def _build_game() -> Game:
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    player_one = Player("Player One", control=PlayerControl.LOCAL, army=Army.with_detachment("Chaos Daemons", "Test"))
    player_two = Player("Player Two", control=PlayerControl.LOCAL, army=Army.with_detachment("Chaos Daemons", "Test"))
    game = Game(battlefield, players=[player_one, player_two])
    game.is_authoritative = True
    return game


def _status_map(game: Game) -> dict[PregameStepId, tuple[str, str | None]]:
    flow = game.get_pregame_flow_state()
    return {
        step.definition.step_id: (step.status, step.detail)
        for step in flow.steps
    }


def test_pregame_flow_starts_with_explicit_preview_sequence() -> None:
    game = _build_game()

    expected_driver_phases = {
        SetupPhase.MUSTER_ARMIES,
        SetupPhase.SELECT_MISSION_OBJECTIVES,
        SetupPhase.CREATE_BATTLEFIELD,
        SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER,
    }
    assert driver_managed_setup_phases() == expected_driver_phases

    flow = game.get_pregame_flow_state()
    statuses = _status_map(game)

    assert flow.current_step_id == PregameStepId.MUSTER_ARMIES
    assert statuses[PregameStepId.MUSTER_ARMIES][0] == "current"
    assert statuses[PregameStepId.DETERMINE_MISSION][0] == "pending"
    assert statuses[PregameStepId.DETERMINE_DEPLOYMENT][0] == "pending"
    assert statuses[PregameStepId.OPTIONAL_TWIST][0] == "pending"
    assert statuses[PregameStepId.SELECT_SECONDARY_MISSIONS][0] == "pending"

    game.setup_phase = SetupPhase.SELECT_MISSION_OBJECTIVES
    flow = game.get_pregame_flow_state()
    statuses = _status_map(game)

    assert flow.current_step_id == PregameStepId.DETERMINE_MISSION
    assert statuses[PregameStepId.MUSTER_ARMIES][0] == "completed"
    assert statuses[PregameStepId.DETERMINE_MISSION][0] == "current"
    assert statuses[PregameStepId.DETERMINE_DEPLOYMENT] == (
        "pending",
        "Waiting for mission selection to establish deployment.",
    )


def test_pregame_flow_marks_preview_deployment_and_secondary_steps_explicitly() -> None:
    game = _build_game()
    game.selected_mission_info = {
        "combination_id": "M",
        "primary": "Take and Hold",
        "deployment": "Crucible of Battle",
        "layout": 1,
    }
    game.secondary_mission_mode = "tactical"
    game.setup_phase = SetupPhase.DECLARE_BATTLE_FORMATIONS

    flow = game.get_pregame_flow_state()
    statuses = _status_map(game)

    assert flow.current_step_id == PregameStepId.DECLARE_BATTLE_FORMATIONS
    assert statuses[PregameStepId.DETERMINE_MISSION][0] == "completed"
    assert statuses[PregameStepId.DETERMINE_DEPLOYMENT] == (
        "completed",
        "Derived from selected mission definition as deployment 'Crucible of Battle'.",
    )
    assert statuses[PregameStepId.OPTIONAL_TWIST] == (
        "stubbed",
        "No explicit twist definition is stored yet; the step remains an explicit placeholder.",
    )
    assert statuses[PregameStepId.SELECT_SECONDARY_MISSIONS] == (
        "stubbed",
        "Secondary selection mode placeholder recorded as 'tactical'.",
    )


def test_snapshot_roundtrip_preserves_explicit_pregame_state() -> None:
    game = _build_game()
    game.setup_phase = SetupPhase.CREATE_BATTLEFIELD
    game.selected_mission_info = {
        "combination_id": "M",
        "primary": "Take and Hold",
        "deployment": "Crucible of Battle",
        "layout": 1,
    }

    loaded = load_game_snapshot(snapshot_game(game))
    flow = loaded.get_pregame_flow_state()
    statuses = {
        step.definition.step_id: step.status
        for step in flow.steps
    }

    assert loaded.setup_phase == SetupPhase.CREATE_BATTLEFIELD
    assert flow.current_step_id == PregameStepId.CREATE_BATTLEFIELD
    assert statuses[PregameStepId.DETERMINE_DEPLOYMENT] == "completed"
    assert statuses[PregameStepId.OPTIONAL_TWIST] == "stubbed"
