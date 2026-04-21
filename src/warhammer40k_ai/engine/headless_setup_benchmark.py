from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from .battlefield import Battlefield, BattlefieldSize
from .deployment_headless import DeterministicDeploymentDecisionMaker
from .game import Game
from .headless_policy_controller import HeadlessPolicyDecisionController
from .local_runtime import LocalAuthoritativeRuntime
from .phase import SetupPhase
from ..roster.player import Player, PlayerControl


def drain_pending_decisions(game: Game, *, max_attempts: int = 4000) -> None:
    queue = getattr(game, "decision_queue", None)
    event_system = getattr(game, "event_system", None)
    if queue is None or event_system is None:
        return
    attempts = 0
    while True:
        request = queue.peek()
        if request is None:
            return
        if attempts >= int(max_attempts):
            raise RuntimeError(
                f"Unable to resolve pending decision after {max_attempts} attempts: "
                f"{getattr(request, 'decision_type', '')}"
            )
        decision_id_before = str(getattr(request, "decision_id", "") or "")
        event_system.publish("decision_requested", request=request, game=game)
        request_after = queue.peek()
        if request_after is None:
            return
        decision_id_after = str(getattr(request_after, "decision_id", "") or "")
        if decision_id_after == decision_id_before:
            raise RuntimeError(
                "Headless policy could not resolve decision "
                f"{decision_id_after} ({getattr(request_after, 'decision_type', '')})."
            )
        attempts += 1


def _annotate_deployment_metrics(metrics: list[dict[str, object]]) -> list[dict[str, object]]:
    annotated: list[dict[str, object]] = []
    for index, metric in enumerate(list(metrics or []), start=1):
        entry = dict(metric or {})
        entry["deployment_order"] = int(index)
        annotated.append(entry)
    return annotated


def _summarize_deployment_metrics(metrics_by_player: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    flat = [
        dict(metric or {})
        for metrics in dict(metrics_by_player or {}).values()
        for metric in list(metrics or [])
    ]
    validate_counts = [int(metric.get("validate_calls", 0) or 0) for metric in flat]
    return {
        "unit_count": int(len(flat)),
        "total_validate_calls": int(sum(validate_counts)),
        "max_validate_calls": int(max(validate_counts) if validate_counts else 0),
        "exhaustive_fallback_count": int(
            sum(1 for metric in flat if bool(metric.get("exhaustive_fallback_used", False)))
        ),
        "first_valid_sources": [
            str(metric.get("first_valid_source", "") or "")
            for metric in flat
            if str(metric.get("first_valid_source", "") or "")
        ],
    }


def _summarize_reserves_metrics(metrics: list[dict[str, object]]) -> dict[str, object]:
    build_calls = [int(metric.get("build_calls", 0) or 0) for metric in list(metrics or [])]
    return {
        "decision_count": int(len(list(metrics or []))),
        "total_build_calls": int(sum(build_calls)),
        "max_build_calls": int(max(build_calls) if build_calls else 0),
        "exhaustive_fallback_count": int(
            sum(1 for metric in list(metrics or []) if bool(metric.get("exhaustive_fallback_used", False)))
        ),
        "first_valid_sources": [
            str(metric.get("first_valid_source", "") or "")
            for metric in list(metrics or [])
            if str(metric.get("first_valid_source", "") or "")
        ],
    }


def _setup_phase_name(game: Game) -> str:
    phase = game.get_current_setup_phase()
    return str(getattr(phase, "name", "") or "UNKNOWN")


def run_setup_only_headless_benchmark(
    *,
    player1_army_file: str,
    player2_army_file: str,
    reserve_policy: str = "forced_only",
    deployment_ranker_model: str | None = None,
    max_reserves_arrival_seconds: float = 10.0,
    max_attempts: int = 4000,
    stop_after_phase: str = "DEPLOY_ARMIES",
) -> dict[str, Any]:
    player1 = Player("Player 1", control=PlayerControl.REMOTE)
    player2 = Player("Player 2", control=PlayerControl.REMOTE)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player1, player2])

    controller = HeadlessPolicyDecisionController(
        game=game,
        auto_attach=True,
        max_reserves_arrival_seconds=float(max_reserves_arrival_seconds),
        reserve_policy=str(reserve_policy or "forced_only"),
    )
    runtime = LocalAuthoritativeRuntime(
        game,
        player1_army_file=str(player1_army_file),
        player2_army_file=str(player2_army_file),
        manual_phases=False,
    )
    session_game = runtime.game_proxy

    makers = {
        player1.id: DeterministicDeploymentDecisionMaker(
            game,
            reserve_policy=str(reserve_policy or "forced_only"),
            ranker_model_path=str(deployment_ranker_model or ""),
        ),
        player2.id: DeterministicDeploymentDecisionMaker(
            game,
            reserve_policy=str(reserve_policy or "forced_only"),
            ranker_model_path=str(deployment_ranker_model or ""),
        ),
    }

    phase_timings: list[dict[str, object]] = []
    stop_after = str(stop_after_phase or "").strip().upper()
    last_completed_phase = ""
    while session_game.is_in_setup_phase():
        phase_name = _setup_phase_name(session_game)
        started = time.perf_counter()
        if runtime.is_driver_managed_setup_phase():
            runtime.run_setup_autosteps()
            drain_pending_decisions(game, max_attempts=max_attempts)
            phase_timings.append(
                {
                    "phase": str(phase_name),
                    "mode": "driver_autostep",
                    "elapsed_ms": int(round((time.perf_counter() - started) * 1000.0)),
                }
            )
            last_completed_phase = str(phase_name)
            continue

        setup_kwargs: dict[str, Any] = {
            "player1_army_file": str(player1_army_file),
            "player2_army_file": str(player2_army_file),
        }
        if session_game.get_current_setup_phase() == SetupPhase.DEPLOY_ARMIES:
            setup_kwargs["decision_makers"] = makers
        session_game.execute_current_setup_phase(**setup_kwargs)
        drain_pending_decisions(game, max_attempts=max_attempts)
        session_game.advance_setup_phase()
        drain_pending_decisions(game, max_attempts=max_attempts)
        phase_timings.append(
            {
                "phase": str(phase_name),
                "mode": "explicit",
                "elapsed_ms": int(round((time.perf_counter() - started) * 1000.0)),
            }
        )
        last_completed_phase = str(phase_name)
        if stop_after and str(phase_name).upper() == stop_after:
            break

    deployment_metrics = {
        str(player_id): _annotate_deployment_metrics(maker.get_deployment_search_metrics())
        for player_id, maker in dict(makers or {}).items()
    }
    reserves_metrics = controller.get_reserves_arrival_search_metrics()
    return {
        "player1_army_file": str(Path(player1_army_file)),
        "player2_army_file": str(Path(player2_army_file)),
        "setup_complete": bool(getattr(session_game, "setup_complete", False)),
        "turn": int(getattr(session_game, "turn", 0) or 0),
        "current_setup_phase": _setup_phase_name(session_game) if session_game.is_in_setup_phase() else "",
        "last_completed_setup_phase": str(last_completed_phase or ""),
        "phase_after_setup": str(getattr(getattr(session_game, "phase", None), "name", "") or ""),
        "stopped_after_phase": str(stop_after or ""),
        "phase_timings": phase_timings,
        "deployment_metrics": deployment_metrics,
        "deployment_summary": _summarize_deployment_metrics(deployment_metrics),
        "reserves_metrics": [dict(metric or {}) for metric in list(reserves_metrics or [])],
        "reserves_summary": _summarize_reserves_metrics(reserves_metrics),
    }
