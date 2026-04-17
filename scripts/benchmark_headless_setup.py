#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from shapely.geometry import Point

from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.engine.headless_setup_benchmark import run_setup_only_headless_benchmark


class _ApplyResult:
    def __init__(self, ok: bool) -> None:
        self.ok = bool(ok)


class _BenchmarkBase:
    has_circular_base = True

    def __init__(self, x: float, y: float, radius: float = 0.5) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = 0.0
        self._radius = float(radius)

    def get_radius(self) -> float:
        return float(self._radius)

    def get_longest_radius(self) -> float:
        return float(self._radius)

    def get_base_shape(self):
        return Point(float(self.x), float(self.y)).buffer(float(self._radius))


class _BenchmarkModel:
    def __init__(self, model_id: str, *, x: float, y: float, radius: float = 0.5) -> None:
        self.id = model_id
        self._id = model_id
        self.model_base = _BenchmarkBase(x=float(x), y=float(y), radius=float(radius))
        self.is_alive = True

    def get_location(self) -> tuple[float, float, float, float]:
        return (float(self.model_base.x), float(self.model_base.y), float(self.model_base.z), 0.0)

    def set_location(self, x: float, y: float, z: float, facing: float = 0.0) -> None:
        self.model_base.x = float(x)
        self.model_base.y = float(y)
        self.model_base.z = float(z)
        self.model_base.facing = float(facing)


class _BenchmarkPlayer:
    def __init__(self, player_id: str) -> None:
        self.id = player_id
        self.army = None


class _BenchmarkArmy:
    def __init__(self, player: _BenchmarkPlayer, units: list[object]) -> None:
        self.player = player
        self.units = list(units)


class _BenchmarkUnit:
    def __init__(
        self,
        unit_id: str,
        *,
        player: _BenchmarkPlayer,
        reserve_status: str,
        strategic: bool,
        x: float = 0.0,
        y: float = 0.0,
        radius: float = 0.5,
    ) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = unit_id
        self.reserve_status = reserve_status
        self.deployed = reserve_status == "deployed"
        self.embarked_in = None
        self.is_embarked = False
        self.models = [_BenchmarkModel(f"{unit_id}:model", x=x, y=y, radius=radius)]
        self._player = player
        self._strategic = bool(strategic)

    def get_parent_army(self):
        return self._player.army

    def get_attached_unit_root(self):
        return self

    def is_alive(self) -> bool:
        return True

    def is_in_reserves(self) -> bool:
        return str(self.reserve_status or "").strip().lower() != "deployed"

    def is_in_strategic_reserves(self) -> bool:
        return bool(self._strategic)

    def has_deep_strike(self) -> bool:
        return not bool(self._strategic)

    def calculate_model_positions(
        self,
        x: float,
        y: float,
        _game_map: object,
        *,
        avoid_friendly_units: bool = False,
        boundary_repulsors: object | None = None,
        search_context: object | None = None,
    ) -> list[tuple[float, float, float, float]]:
        del avoid_friendly_units, boundary_repulsors, search_context
        return [(float(x), float(y), 0.0, 0.0)]


class _BenchmarkGame:
    def __init__(self, *, width: float, height: float, arriving: _BenchmarkUnit, enemies: list[_BenchmarkUnit], success_xy: tuple[float, float]) -> None:
        self.is_authoritative = True
        self.battlefield = SimpleNamespace(width=float(width), height=float(height))
        self.map = SimpleNamespace(width=float(width), height=float(height))
        self.commands: list[object] = []
        self.turn = 2
        self.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        self.ruleset_bundle = None
        self._success_xy = (float(success_xy[0]), float(success_xy[1]))
        arriving_player = arriving.get_parent_army().player
        enemy_players = [enemy.get_parent_army().player for enemy in list(enemies or [])]
        self.players = [arriving_player, *enemy_players]

    def _resolve_unit_by_id(self, unit_id: str):
        for player in list(self.players or []):
            for unit in list(getattr(getattr(player, "army", None), "units", []) or []):
                if str(getattr(unit, "id", "")) == str(unit_id):
                    return unit
        return None

    def get_boundary_repulsors(self, _unit, context: str = ""):
        del context
        return []

    def apply_command(self, command):
        self.commands.append(command)
        payload = dict(command.payload or {})
        result_payload = dict(payload.get("result_payload", {}) or {})
        model_positions = list(result_payload.get("model_positions", []) or [])
        if not model_positions:
            return _ApplyResult(False)
        pos = list(model_positions[0].get("position", []) or [])
        if len(pos) < 2:
            return _ApplyResult(False)
        x = float(pos[0])
        y = float(pos[1])
        return _ApplyResult(ok=(abs(x - self._success_xy[0]) < 1e-6 and abs(y - self._success_xy[1]) < 1e-6))


def _request_for_unit(unit: _BenchmarkUnit) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_MOVE_UNIT,
        f"Arrive from Reserves: {unit.name}",
        player_id=str(getattr(unit.get_parent_army().player, "id", "") or ""),
        options=[DecisionOption(option_id="confirm", label="Confirm", payload={"action": "confirm", "action_id": "confirm"})],
        context={"placement_kind": "reserves_arrival", "unit_id": str(unit.id), "allow_skip": False},
    )


def _run_crowded_deep_strike_case(max_reserves_arrival_seconds: float) -> dict[str, Any]:
    arriving_player = _BenchmarkPlayer("player:arriving")
    enemy_player = _BenchmarkPlayer("player:enemy")
    arriving = _BenchmarkUnit(
        "unit:deep_strike",
        player=arriving_player,
        reserve_status="reserves",
        strategic=False,
        radius=0.5,
    )
    enemies = [
        _BenchmarkUnit("enemy:center", player=enemy_player, reserve_status="deployed", strategic=False, x=30.0, y=22.0),
        _BenchmarkUnit("enemy:left", player=enemy_player, reserve_status="deployed", strategic=False, x=15.0, y=11.0),
        _BenchmarkUnit("enemy:right", player=enemy_player, reserve_status="deployed", strategic=False, x=15.0, y=33.0),
    ]
    arriving_player.army = _BenchmarkArmy(arriving_player, [arriving])
    enemy_player.army = _BenchmarkArmy(enemy_player, enemies)
    game = _BenchmarkGame(width=60.0, height=44.0, arriving=arriving, enemies=enemies, success_xy=(45.0, 22.0))
    controller = HeadlessPolicyDecisionController(
        game=None,
        auto_attach=False,
        max_reserves_arrival_seconds=float(max_reserves_arrival_seconds),
    )
    controller.reset_reserves_arrival_search_metrics()
    resolved = controller._try_resolve_reserves_arrival_bruteforce(game, _request_for_unit(arriving))
    metric = controller.get_reserves_arrival_search_metrics()[-1]
    return {
        "case": "crowded_deep_strike",
        "resolved": bool(resolved),
        "metric": metric,
        "summary": {
            "first_valid_source": str(metric.get("first_valid_source", "") or ""),
            "build_calls": int(metric.get("build_calls", 0) or 0),
            "exhaustive_fallback_used": bool(metric.get("exhaustive_fallback_used", False)),
        },
    }


def _run_strategic_edge_case(max_reserves_arrival_seconds: float) -> dict[str, Any]:
    arriving_player = _BenchmarkPlayer("player:arriving")
    enemy_player = _BenchmarkPlayer("player:enemy")
    arriving = _BenchmarkUnit(
        "unit:strategic",
        player=arriving_player,
        reserve_status="strategic_reserves",
        strategic=True,
        radius=0.5,
    )
    enemy = _BenchmarkUnit(
        "enemy:blocker",
        player=enemy_player,
        reserve_status="deployed",
        strategic=False,
        x=30.0,
        y=22.0,
    )
    arriving_player.army = _BenchmarkArmy(arriving_player, [arriving])
    enemy_player.army = _BenchmarkArmy(enemy_player, [enemy])
    preferred_offset = HeadlessPolicyDecisionController(game=None, auto_attach=False)._strategic_edge_offset_preference(arriving)
    success_xy = (0.0, float(preferred_offset))
    game = _BenchmarkGame(width=60.0, height=44.0, arriving=arriving, enemies=[enemy], success_xy=success_xy)
    controller = HeadlessPolicyDecisionController(
        game=None,
        auto_attach=False,
        max_reserves_arrival_seconds=float(max_reserves_arrival_seconds),
    )
    controller.reset_reserves_arrival_search_metrics()
    resolved = controller._try_resolve_reserves_arrival_bruteforce(game, _request_for_unit(arriving))
    metric = controller.get_reserves_arrival_search_metrics()[-1]
    return {
        "case": "strategic_edge",
        "resolved": bool(resolved),
        "metric": metric,
        "summary": {
            "first_valid_source": str(metric.get("first_valid_source", "") or ""),
            "build_calls": int(metric.get("build_calls", 0) or 0),
            "exhaustive_fallback_used": bool(metric.get("exhaustive_fallback_used", False)),
        },
    }


def _load_json(path: str | None) -> dict[str, Any]:
    if not str(path or "").strip():
        return {}
    return dict(json.loads(Path(path).read_text(encoding="utf-8")) or {})


def _phase_elapsed(report: dict[str, Any], phase_name: str) -> int:
    return int(
        sum(
            int(entry.get("elapsed_ms", 0) or 0)
            for entry in list(report.get("phase_timings", []) or [])
            if str(entry.get("phase", "") or "") == str(phase_name or "")
        )
    )


def _compare_to_baseline(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    if not baseline:
        return {}
    current_setup = dict(current.get("setup_benchmark", {}) or {})
    baseline_setup = dict(baseline.get("setup_benchmark", {}) or {})
    current_deploy_ms = _phase_elapsed(current_setup, "DEPLOY_ARMIES")
    baseline_deploy_ms = _phase_elapsed(baseline_setup, "DEPLOY_ARMIES")
    speedup = None
    if current_deploy_ms > 0 and baseline_deploy_ms > 0:
        speedup = round(float(baseline_deploy_ms) / float(current_deploy_ms), 3)
    return {
        "deploy_armies_elapsed_ms": {
            "before": int(baseline_deploy_ms),
            "after": int(current_deploy_ms),
            "speedup": speedup,
        },
        "total_validate_calls": {
            "before": int(dict(baseline_setup.get("deployment_summary", {}) or {}).get("total_validate_calls", 0) or 0),
            "after": int(dict(current_setup.get("deployment_summary", {}) or {}).get("total_validate_calls", 0) or 0),
        },
        "max_validate_calls": {
            "before": int(dict(baseline_setup.get("deployment_summary", {}) or {}).get("max_validate_calls", 0) or 0),
            "after": int(dict(current_setup.get("deployment_summary", {}) or {}).get("max_validate_calls", 0) or 0),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark headless setup deployment and reserves-arrival search.")
    parser.add_argument("--player1-army", default="army_lists/Aeldari_Warhost_2000.txt")
    parser.add_argument("--player2-army", default="army_lists/WE_Daemonkin_2000.txt")
    parser.add_argument("--reserve-policy", default="forced_only", choices=("forced_only", "balanced"))
    parser.add_argument("--deployment-ranker-model", default="")
    parser.add_argument("--max-reserves-arrival-seconds", type=float, default=10.0)
    parser.add_argument("--baseline-json", default="")
    parser.add_argument("--output", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = {
        "setup_benchmark": run_setup_only_headless_benchmark(
            player1_army_file=str(args.player1_army),
            player2_army_file=str(args.player2_army),
            reserve_policy=str(args.reserve_policy),
            deployment_ranker_model=str(args.deployment_ranker_model or ""),
            max_reserves_arrival_seconds=float(args.max_reserves_arrival_seconds),
        ),
        "reserves_benchmarks": [
            _run_crowded_deep_strike_case(float(args.max_reserves_arrival_seconds)),
            _run_strategic_edge_case(float(args.max_reserves_arrival_seconds)),
        ],
    }
    baseline = _load_json(str(args.baseline_json or ""))
    if baseline:
        result["baseline_comparison"] = _compare_to_baseline(result, baseline)

    encoded = json.dumps(result, indent=2, sort_keys=True)
    output_path = str(args.output or "").strip()
    if output_path:
        Path(output_path).write_text(encoded + "\n", encoding="utf-8")
        print(output_path)
        return
    print(encoded)


if __name__ == "__main__":
    main()
