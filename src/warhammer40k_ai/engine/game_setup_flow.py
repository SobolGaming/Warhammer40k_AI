from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from typing import TYPE_CHECKING

from .command_kinds import CMD_ADVANCE_SETUP_PHASE, CMD_EXECUTE_SETUP_PHASE
from .commands import GameCommand
from .game_phase_flow import complete_setup_and_start_battle_round
from .phase import SetupPhase

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .decisions import DecisionRequest


class PregameStepId(str, Enum):
    MUSTER_ARMIES = "muster_armies"
    DETERMINE_MISSION = "determine_mission"
    DETERMINE_DEPLOYMENT = "determine_deployment"
    OPTIONAL_TWIST = "optional_twist"
    CREATE_BATTLEFIELD = "create_battlefield"
    DETERMINE_ATTACKER_AND_DEFENDER = "determine_attacker_and_defender"
    SELECT_SECONDARY_MISSIONS = "select_secondary_missions"
    DECLARE_BATTLE_FORMATIONS = "declare_battle_formations"
    DEPLOY_ARMIES = "deploy_armies"
    REDEPLOY_UNITS = "redeploy_units"
    DETERMINE_FIRST_TURN_ORDER = "determine_first_turn_order"
    RESOLVE_PREBATTLE_RULES = "resolve_prebattle_rules"


@dataclass(frozen=True)
class PregameStepDefinition:
    step_id: PregameStepId
    label: str
    setup_phase: SetupPhase | None
    provisional: bool = False
    notes: str | None = None


@dataclass(frozen=True)
class PregameStepState:
    definition: PregameStepDefinition
    status: str
    detail: str | None = None


@dataclass(frozen=True)
class PregameFlowState:
    current_step_id: PregameStepId | None
    current_setup_phase: SetupPhase | None
    setup_complete: bool
    steps: tuple[PregameStepState, ...]


_SETUP_PHASE_SEQUENCE: tuple[SetupPhase, ...] = (
    SetupPhase.MUSTER_ARMIES,
    SetupPhase.SELECT_MISSION_OBJECTIVES,
    SetupPhase.CREATE_BATTLEFIELD,
    SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER,
    SetupPhase.DECLARE_BATTLE_FORMATIONS,
    SetupPhase.DEPLOY_ARMIES,
    SetupPhase.REDEPLOY_UNITS,
    SetupPhase.DETERMINE_FIRST_TURN_ORDER,
    SetupPhase.RESOLVE_PREBATTLE_RULES,
)

_PREGAME_STEPS: tuple[PregameStepDefinition, ...] = (
    PregameStepDefinition(PregameStepId.MUSTER_ARMIES, "Muster armies", SetupPhase.MUSTER_ARMIES),
    PregameStepDefinition(PregameStepId.DETERMINE_MISSION, "Determine mission", SetupPhase.SELECT_MISSION_OBJECTIVES),
    PregameStepDefinition(
        PregameStepId.DETERMINE_DEPLOYMENT,
        "Determine deployment",
        SetupPhase.SELECT_MISSION_OBJECTIVES,
        provisional=True,
        notes="Derived from the currently selected mission combination until PR-006 rewrites mission compilation.",
    ),
    PregameStepDefinition(
        PregameStepId.OPTIONAL_TWIST,
        "Optional Twist",
        SetupPhase.SELECT_MISSION_OBJECTIVES,
        provisional=True,
        notes="Explicit placeholder only; preview-era twist content remains stubbed until final mission-pack data lands.",
    ),
    PregameStepDefinition(PregameStepId.CREATE_BATTLEFIELD, "Create battlefield", SetupPhase.CREATE_BATTLEFIELD),
    PregameStepDefinition(
        PregameStepId.DETERMINE_ATTACKER_AND_DEFENDER,
        "Determine attacker and defender",
        SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER,
    ),
    PregameStepDefinition(
        PregameStepId.SELECT_SECONDARY_MISSIONS,
        "Select secondary missions",
        SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER,
        provisional=True,
        notes="Current deck-draw secondary handling stays deferred until the Command phase; the setup step is represented explicitly as a stub.",
    ),
    PregameStepDefinition(
        PregameStepId.DECLARE_BATTLE_FORMATIONS,
        "Declare battle formations",
        SetupPhase.DECLARE_BATTLE_FORMATIONS,
        notes="Legacy compatibility tail retained until the mission/deployment rewrite lands.",
    ),
    PregameStepDefinition(PregameStepId.DEPLOY_ARMIES, "Deploy armies", SetupPhase.DEPLOY_ARMIES),
    PregameStepDefinition(PregameStepId.REDEPLOY_UNITS, "Redeploy units", SetupPhase.REDEPLOY_UNITS),
    PregameStepDefinition(
        PregameStepId.DETERMINE_FIRST_TURN_ORDER,
        "Determine first turn order",
        SetupPhase.DETERMINE_FIRST_TURN_ORDER,
    ),
    PregameStepDefinition(
        PregameStepId.RESOLVE_PREBATTLE_RULES,
        "Resolve prebattle rules",
        SetupPhase.RESOLVE_PREBATTLE_RULES,
    ),
)

_PHASE_TO_STEP_INDEX: dict[SetupPhase, int] = {
    SetupPhase.MUSTER_ARMIES: 0,
    SetupPhase.SELECT_MISSION_OBJECTIVES: 1,
    SetupPhase.CREATE_BATTLEFIELD: 4,
    SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER: 5,
    SetupPhase.DECLARE_BATTLE_FORMATIONS: 7,
    SetupPhase.DEPLOY_ARMIES: 8,
    SetupPhase.REDEPLOY_UNITS: 9,
    SetupPhase.DETERMINE_FIRST_TURN_ORDER: 10,
    SetupPhase.RESOLVE_PREBATTLE_RULES: 11,
}

_DRIVER_MANAGED_SETUP_PHASES = {
    SetupPhase.MUSTER_ARMIES,
    SetupPhase.SELECT_MISSION_OBJECTIVES,
    SetupPhase.CREATE_BATTLEFIELD,
    SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER,
}


def setup_phase_sequence() -> tuple[SetupPhase, ...]:
    return _SETUP_PHASE_SEQUENCE


def pregame_step_definitions() -> tuple[PregameStepDefinition, ...]:
    return _PREGAME_STEPS


def driver_managed_setup_phases() -> set[SetupPhase]:
    return set(_DRIVER_MANAGED_SETUP_PHASES)


def is_in_setup_phase(game) -> bool:
    """Check if we're still in the setup phase."""
    return not game.setup_complete


def get_current_setup_phase(game) -> SetupPhase:
    """Get the current setup phase."""
    return game.setup_phase


def _derived_preview_steps_status(game, *, current_step_index: int) -> dict[PregameStepId, tuple[str, str | None]]:
    selected_mission = dict(getattr(game, "selected_mission_info", {}) or {})
    has_selected_mission = bool(selected_mission)
    secondary_mode = str(getattr(game, "secondary_mission_mode", "") or "").strip()
    statuses: dict[PregameStepId, tuple[str, str | None]] = {}

    if current_step_index <= 1:
        if current_step_index == 1:
            statuses[PregameStepId.DETERMINE_DEPLOYMENT] = ("pending", "Waiting for mission selection to establish deployment.")
            statuses[PregameStepId.OPTIONAL_TWIST] = ("pending", "Twist handling remains provisional until mission data is finalized.")
        else:
            statuses[PregameStepId.DETERMINE_DEPLOYMENT] = ("pending", None)
            statuses[PregameStepId.OPTIONAL_TWIST] = ("pending", None)
    else:
        deployment_name = str(selected_mission.get("deployment", "") or "").strip()
        if has_selected_mission and deployment_name:
            statuses[PregameStepId.DETERMINE_DEPLOYMENT] = (
                "completed",
                f"Derived from selected mission combination as deployment '{deployment_name}'.",
            )
        else:
            statuses[PregameStepId.DETERMINE_DEPLOYMENT] = (
                "stubbed",
                "No explicit deployment-definition selection is stored yet; current runtime derives it from the mission combination.",
            )
        statuses[PregameStepId.OPTIONAL_TWIST] = (
            "stubbed",
            "No twist content is applied yet; the step remains an explicit placeholder.",
        )

    if current_step_index <= 5:
        statuses[PregameStepId.SELECT_SECONDARY_MISSIONS] = ("pending", None)
    else:
        detail = "Secondary selection remains deferred to command-phase deck draw."
        if secondary_mode:
            detail = f"Secondary selection mode placeholder recorded as '{secondary_mode}'."
        statuses[PregameStepId.SELECT_SECONDARY_MISSIONS] = ("stubbed", detail)
    return statuses


def build_pregame_flow_state(game) -> PregameFlowState:
    current_phase = getattr(game, "setup_phase", None)
    if bool(getattr(game, "setup_complete", False)):
        step_states = tuple(
            PregameStepState(
                definition=definition,
                status="completed",
                detail=definition.notes,
            )
            for definition in _PREGAME_STEPS
        )
        return PregameFlowState(
            current_step_id=None,
            current_setup_phase=current_phase,
            setup_complete=True,
            steps=step_states,
        )

    current_step_index = _PHASE_TO_STEP_INDEX.get(current_phase, 0)
    derived_statuses = _derived_preview_steps_status(game, current_step_index=current_step_index)
    step_states: list[PregameStepState] = []
    current_step_id: PregameStepId | None = None
    for idx, definition in enumerate(_PREGAME_STEPS):
        if definition.step_id in derived_statuses:
            status, detail = derived_statuses[definition.step_id]
        elif idx < current_step_index:
            status = "completed"
            detail = definition.notes
        elif idx == current_step_index:
            status = "current"
            detail = definition.notes
            current_step_id = definition.step_id
        else:
            status = "pending"
            detail = definition.notes
        if status == "current":
            current_step_id = definition.step_id
        step_states.append(PregameStepState(definition=definition, status=status, detail=detail))
    return PregameFlowState(
        current_step_id=current_step_id,
        current_setup_phase=current_phase,
        setup_complete=False,
        steps=tuple(step_states),
    )


def _next_setup_phase(current_phase: SetupPhase) -> SetupPhase | None:
    try:
        idx = _SETUP_PHASE_SEQUENCE.index(current_phase)
    except ValueError:
        raise ValueError(f"Unsupported setup phase: {current_phase}") from None
    next_idx = idx + 1
    if next_idx >= len(_SETUP_PHASE_SEQUENCE):
        return None
    return _SETUP_PHASE_SEQUENCE[next_idx]


def advance_setup_phase_impl(game) -> bool:
    """Advance to the next setup phase. Returns True if setup is complete."""
    if game.setup_complete:
        return True

    next_phase = _next_setup_phase(game.setup_phase)
    if next_phase is None:
        return complete_setup_and_start_battle_round(game)

    game.setup_phase = next_phase
    if game.setup_phase == SetupPhase.SELECT_MISSION_OBJECTIVES and bool(getattr(game, "is_authoritative", True)):
        game.request_mission_selection()
    if game.setup_phase == SetupPhase.RESOLVE_PREBATTLE_RULES:
        game._queue_prebattle_rules_start_requests()
    logger.info("Advanced to setup phase: %s", game.setup_phase.name)
    return False


def advance_setup_phase(game) -> bool:
    """Advance to the next setup phase. Returns True if setup is complete."""
    if game.in_command_context():
        return advance_setup_phase_impl(game)
    player_id = None
    current_player = game.get_current_player()
    if current_player is not None:
        player_id = current_player.id
    cmd = GameCommand.create(CMD_ADVANCE_SETUP_PHASE, player_id=player_id)
    result = game.apply_command(cmd)
    if getattr(result, "ok", False):
        return bool(getattr(result, "value", False))
    return bool(game.setup_complete)


def _execute_setup_phase(game, phase: SetupPhase, **kwargs) -> None:
    if phase == SetupPhase.MUSTER_ARMIES:
        game.execute_muster_armies_phase(kwargs.get("player1_army_file"), kwargs.get("player2_army_file"))
        return
    if phase == SetupPhase.SELECT_MISSION_OBJECTIVES:
        game.execute_select_mission_objectives_phase()
        return
    if phase == SetupPhase.CREATE_BATTLEFIELD:
        game.execute_create_battlefield_phase()
        return
    if phase == SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER:
        game.execute_determine_attacker_defender_phase()
        return
    if phase == SetupPhase.DECLARE_BATTLE_FORMATIONS:
        game.execute_declare_battle_formations_phase()
        return
    if phase == SetupPhase.DEPLOY_ARMIES:
        decision_makers = kwargs.get("decision_makers")
        if decision_makers is None:
            decision_makers = getattr(game, "_pending_setup_decision_makers", None)
        game.execute_deploy_armies_phase(
            manual_phases=kwargs.get("manual_phases", False),
            decision_makers=decision_makers,
        )
        return
    if phase == SetupPhase.REDEPLOY_UNITS:
        game.execute_redeploy_units_phase()
        return
    if phase == SetupPhase.DETERMINE_FIRST_TURN_ORDER:
        game.execute_determine_first_turn_order_phase()
        return
    if phase == SetupPhase.RESOLVE_PREBATTLE_RULES:
        game.execute_resolve_prebattle_rules_phase()


def execute_current_setup_phase_impl(game, **kwargs) -> None:
    """Execute the current setup phase with any necessary parameters."""
    _execute_setup_phase(game, game.setup_phase, **kwargs)


def execute_current_setup_phase(game, **kwargs) -> None:
    """Execute the current setup phase via command dispatch."""
    if game.in_command_context():
        execute_current_setup_phase_impl(game, **kwargs)
        return
    decision_makers = kwargs.get("decision_makers")
    if decision_makers is not None:
        game._pending_setup_decision_makers = decision_makers
    payload = {
        "player1_army_file": kwargs.get("player1_army_file"),
        "player2_army_file": kwargs.get("player2_army_file"),
        "manual_phases": bool(kwargs.get("manual_phases", False)),
    }
    player_id = None
    current_player = game.get_current_player()
    if current_player is not None:
        player_id = current_player.id
    cmd = GameCommand.create(CMD_EXECUTE_SETUP_PHASE, player_id=player_id, payload=payload)
    try:
        game.apply_command(cmd)
    finally:
        if decision_makers is not None:
            game._pending_setup_decision_makers = None
