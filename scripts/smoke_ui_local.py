#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import os
import sys
import warnings
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
    module="pygame.pkgdata",
)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pygame

from scripts.main import initialize_game
from warhammer40k_ai.UI.game_ui import GameView
from warhammer40k_ai.UI.human_interface import HumanUIInterface
from warhammer40k_ai.UI.session_presentation_orchestrator import SessionPresentationOrchestrator
from warhammer40k_ai.engine.local_runtime import LocalAuthoritativeRuntime


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Boot the local pygame UI path with SDL's dummy video driver and fail on crashes.",
    )
    parser.add_argument("--player1-army", default="army_lists/chaos_test.txt")
    parser.add_argument("--player2-army", default="army_lists/aeldari_test.txt")
    parser.add_argument("--frames", type=int, default=3, help="Number of frames to draw after setup.")
    parser.add_argument(
        "--log",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="WARNING",
    )
    return parser


def _setup_logging(log_level: str) -> None:
    logging.basicConfig(level=logging._nameToLevel[log_level], format="%(message)s")


def _assert_army_file_exists(path_value: str) -> None:
    path = Path(path_value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Army file not found: {path}")


def _execute_setup_to_manual_deployment_boundary(game_proxy, runtime: LocalAuthoritativeRuntime) -> str:
    max_steps = 20
    steps = 0
    while game_proxy.is_in_setup_phase():
        if steps >= max_steps:
            phase = game_proxy.get_current_setup_phase()
            raise RuntimeError(f"Setup smoke exceeded {max_steps} steps at {phase}.")
        steps += 1

        if runtime.is_driver_managed_setup_phase():
            runtime.run_setup_autosteps()
            continue

        current_phase = game_proxy.get_current_setup_phase()
        phase_name = str(getattr(current_phase, "name", "") or "")
        if phase_name == "DEPLOY_ARMIES":
            game_proxy.execute_current_setup_phase(manual_phases=True)
            return "manual_deployment_boundary"

        game_proxy.execute_current_setup_phase()
        setup_complete = game_proxy.advance_setup_phase()
        if setup_complete:
            return "setup_complete"

    return "setup_complete"


def _assert_deployment_plans_created(game) -> None:
    for player in list(getattr(game, "players", []) or []):
        player_id = str(getattr(player, "id", "") or "")
        if not player_id:
            raise RuntimeError("Cannot build deployment plan for player without id.")
        plan = game.get_or_create_deployment_plan(player_id)
        plan_id = str(getattr(plan, "plan_id", "") or "")
        if not plan_id:
            raise RuntimeError(f"Deployment plan for {player_id} did not expose a plan_id.")


def _draw_frames(game_view: GameView, frame_count: int) -> None:
    clock = pygame.time.Clock()
    for _ in range(max(1, int(frame_count))):
        game_view.draw()
        pygame.display.flip()
        clock.tick(60)


def _dispatch_smoke_event(screen: pygame.Surface, game_view: GameView, event: pygame.event.Event) -> pygame.Surface:
    if event.type == pygame.VIDEORESIZE:
        new_size = (int(event.w), int(event.h))
        screen = pygame.display.set_mode(new_size, pygame.RESIZABLE)
        game_view.screen = screen
        game_view.resize_layout(new_size[0], new_size[1])
        return screen

    handled = bool(game_view.handle_pygame_event(event))
    if not handled and event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        game_view.close_unit_details()
    return screen


def _exercise_basic_events(screen: pygame.Surface, game_view: GameView) -> pygame.Surface:
    width, height = screen.get_size()
    resize_width = max(800, int(width) - 64)
    resize_height = max(600, int(height) - 64)
    events = [
        pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}),
        pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE}),
        pygame.event.Event(
            pygame.VIDEORESIZE,
            {"w": resize_width, "h": resize_height, "size": (resize_width, resize_height)},
        ),
    ]
    for event in events:
        pygame.event.post(event)
    for event in pygame.event.get():
        screen = _dispatch_smoke_event(screen, game_view, event)
    return screen


def main() -> int:
    args = _build_parser().parse_args()
    _setup_logging(str(args.log_level))
    _assert_army_file_exists(str(args.player1_army))
    _assert_army_file_exists(str(args.player2_army))

    pygame.init()
    try:
        screen, game, game_map, player1, player2 = initialize_game(
            str(args.player1_army),
            str(args.player2_army),
        )
        runtime = LocalAuthoritativeRuntime(
            game,
            player1_army_file=str(args.player1_army),
            player2_army_file=str(args.player2_army),
            manual_phases=True,
        )
        runtime.register_local_player_facade("local_player1", player1.id)
        runtime.register_local_player_facade("local_player2", player2.id)

        ui_interface = HumanUIInterface(screen.get_width(), screen.get_height())
        game_view = GameView(screen, None, runtime.game_proxy, game_map, player1, player2, ui_interface)
        presentation_orchestrator = SessionPresentationOrchestrator(stream_id="local:smoke")
        presentation_orchestrator.bind_game_view(game_view)
        presentation_orchestrator.publish_game_loaded(
            game=runtime.game_proxy,
            game_map=game_map,
            players=[player1, player2],
        )

        boundary = _execute_setup_to_manual_deployment_boundary(runtime.game_proxy, runtime)
        _assert_deployment_plans_created(game)
        game_view.refresh_roster_panes()
        game_view.update_roster_pane_titles()
        presentation_orchestrator.publish_game_loaded(
            game=runtime.game_proxy,
            game_map=game_map,
            players=[player1, player2],
        )

        _draw_frames(game_view, int(args.frames))
        screen = _exercise_basic_events(screen, game_view)
        game_view.screen = screen
        _draw_frames(game_view, 1)

        print(
            "local_ui_smoke=ok "
            f"boundary={boundary} "
            f"frames={max(1, int(args.frames)) + 1} "
            f"video_driver={pygame.display.get_driver()}"
        )
        return 0
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
