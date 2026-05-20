#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from warhammer40k_ai.engine.decision_requests import build_select_next_deploy_unit_request
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.local_runtime import LocalAuthoritativeRuntime
from warhammer40k_ai.engine.snapshot import load_game_snapshot, snapshot_game
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.game_context import game_context


PLAN_ID_KEYS = {
    "general_plan_id",
    "deployment_order_bundle_id",
    "prebattle_order_bundle_id",
    "deployment_plan_id",
    "battle_round_plan_id",
    "commander_order_bundle_id",
}

FULL_PLAN_KEYS = {
    "general_plan",
    "deployment_order_bundle",
    "prebattle_order_bundle",
    "deployment_plan",
    "battle_round_plan",
    "commander_order_bundle",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build compiled plan context, snapshot it, JSON round-trip it, and reload it.",
    )
    parser.add_argument("--player1-army", default="army_lists/chaos_test.txt")
    parser.add_argument("--player2-army", default="army_lists/aeldari_test.txt")
    return parser


def _resolve_army_path(path_value: str) -> str:
    path = Path(path_value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Army file not found: {path}")
    return str(path)


def _build_runtime(player1_army: str, player2_army: str) -> LocalAuthoritativeRuntime:
    player1 = Player("Player 1", control=PlayerControl.LOCAL)
    player2 = Player("Player 2", control=PlayerControl.LOCAL)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player1, player2])
    game.auto_resolve_dice_rolls = False
    runtime = LocalAuthoritativeRuntime(
        game,
        player1_army_file=player1_army,
        player2_army_file=player2_army,
        manual_phases=True,
    )
    runtime.register_local_player_facade("local_player1", player1.id)
    runtime.register_local_player_facade("local_player2", player2.id)
    return runtime


def _execute_setup_to_deployment(runtime: LocalAuthoritativeRuntime) -> None:
    game_proxy = runtime.game_proxy
    max_steps = 20
    steps = 0
    while game_proxy.is_in_setup_phase():
        if steps >= max_steps:
            phase = game_proxy.get_current_setup_phase()
            raise RuntimeError(f"Snapshot smoke exceeded {max_steps} setup steps at {phase}.")
        steps += 1

        if runtime.is_driver_managed_setup_phase():
            with game_context(runtime.game):
                runtime.run_setup_autosteps()
            continue

        phase = game_proxy.get_current_setup_phase()
        phase_name = str(getattr(phase, "name", "") or "")
        with game_context(runtime.game):
            if phase_name == "DEPLOY_ARMIES":
                game_proxy.execute_current_setup_phase(manual_phases=True)
                return
            game_proxy.execute_current_setup_phase()
            game_proxy.advance_setup_phase()

    raise RuntimeError("Snapshot smoke completed setup before reaching DEPLOY_ARMIES.")


def _deployable_units_for_player(player: object) -> list[object]:
    army = player.get_army() if player is not None else None
    units = list(getattr(army, "units", []) or []) if army is not None else []
    deployable: list[object] = []
    for unit in units:
        if unit is None:
            continue
        if bool(getattr(unit, "deployed", False)):
            continue
        if bool(getattr(unit, "is_attached_leader", False)):
            continue
        if bool(getattr(unit, "is_joined_support", False)):
            continue
        if bool(getattr(unit, "is_embarked", False)) or getattr(unit, "embarked_in", None) is not None:
            continue
        reserve_status = str(getattr(unit, "reserve_status", "") or "").strip().lower()
        if reserve_status in {"reserves", "strategic_reserves", "embarked"}:
            continue
        deployable.append(unit)
    deployable.sort(key=lambda unit: str(get_entity_id(unit) or ""))
    return deployable


def _force_compiled_plans(game: Game) -> dict[str, dict[str, str]]:
    summary: dict[str, dict[str, str]] = {}
    for player in list(getattr(game, "players", []) or []):
        player_id = str(getattr(player, "id", "") or "")
        if not player_id:
            raise RuntimeError("Cannot compile plans for a player without an id.")
        general_plan = game.get_or_create_general_plan(player_id)
        deployment_orders = game.get_or_create_deployment_order_bundle(player_id)
        prebattle_orders = game.get_or_create_prebattle_order_bundle(player_id)
        deployment_plan = game.get_or_create_deployment_plan(player_id)
        battle_round_plan = game.get_or_create_battle_round_plan(player_id)
        battle_metadata = dict(getattr(battle_round_plan, "metadata", {}) or {})
        commander_bundle = dict(battle_metadata.get("commander_order_bundle", {}) or {})
        commander_bundle_id = str(
            battle_metadata.get("commander_order_bundle_id")
            or commander_bundle.get("order_bundle_id")
            or ""
        )
        ids = {
            "general_plan_id": str(getattr(general_plan, "plan_id", "") or ""),
            "deployment_order_bundle_id": str(getattr(deployment_orders, "order_bundle_id", "") or ""),
            "prebattle_order_bundle_id": str(getattr(prebattle_orders, "order_bundle_id", "") or ""),
            "deployment_plan_id": str(getattr(deployment_plan, "plan_id", "") or ""),
            "battle_round_plan_id": str(getattr(battle_round_plan, "plan_id", "") or ""),
            "commander_order_bundle_id": commander_bundle_id,
        }
        missing = [key for key, value in ids.items() if not value]
        if missing:
            raise RuntimeError(f"Compiled plan ids missing for player {player_id}: {missing}")
        summary[player_id] = ids
    return summary


def _queue_plan_context_decision(game: Game):
    phase = game.get_current_setup_phase()
    if str(getattr(phase, "name", "") or "") != "DEPLOY_ARMIES":
        raise RuntimeError(f"Snapshot smoke expected DEPLOY_ARMIES, got {phase}.")
    player = game.get_current_deployment_player()
    if player is None:
        raise RuntimeError("Snapshot smoke could not determine current deployment player.")
    deployable = _deployable_units_for_player(player)
    if not deployable:
        raise RuntimeError("Snapshot smoke found no deployable units.")
    deployment_zones = getattr(game, "deployment_zones", {}) or {}
    deployment_zone = deployment_zones.get(getattr(player, "id", None)) if isinstance(deployment_zones, dict) else None
    already_deployed = [
        unit
        for unit in list(getattr(player.get_army(), "units", []) or [])
        if bool(getattr(unit, "deployed", False))
    ]
    request = build_select_next_deploy_unit_request(
        game,
        player,
        deployable,
        deployment_zone=deployment_zone if isinstance(deployment_zone, dict) else None,
        already_deployed_units=already_deployed,
        extra_context={
            "decision_owner": "snapshot_plan_smoke",
            "include_full_general_plan": True,
            "include_full_deployment_order_bundle": True,
            "include_full_prebattle_order_bundle": True,
            "include_full_deployment_plan": True,
            "include_full_battle_round_plan": True,
            "include_full_commander_order_bundle": True,
        },
        queue_requests=True,
    )
    if request is None:
        raise RuntimeError("Snapshot smoke did not create a deployment plan context request.")
    missing_ids = sorted(key for key in PLAN_ID_KEYS if not request.context.get(key))
    missing_payloads = sorted(key for key in FULL_PLAN_KEYS if key not in request.context)
    if missing_ids or missing_payloads:
        raise RuntimeError(
            "Compiled plan context did not attach all expected keys: "
            f"missing_ids={missing_ids}; missing_payloads={missing_payloads}"
        )
    return request


def main() -> int:
    args = _build_parser().parse_args()
    player1_army = _resolve_army_path(str(args.player1_army))
    player2_army = _resolve_army_path(str(args.player2_army))
    runtime = _build_runtime(player1_army, player2_army)
    game = runtime.game

    _execute_setup_to_deployment(runtime)
    plan_ids = _force_compiled_plans(game)
    _queue_plan_context_decision(game)
    first_snapshot = snapshot_game(game)
    encoded = json.dumps(first_snapshot, sort_keys=True)
    loaded = load_game_snapshot(json.loads(encoded))
    second_snapshot = snapshot_game(loaded)
    reencoded = json.dumps(second_snapshot, sort_keys=True)

    print(
        "snapshot_plan_smoke=ok "
        f"players={len(plan_ids)} "
        f"decisions={len(first_snapshot.get('decisions', []) or [])} "
        f"snapshot_bytes={len(encoded)} "
        f"resnapshot_bytes={len(reencoded)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
