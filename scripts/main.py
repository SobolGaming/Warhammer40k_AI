#!/usr/bin/env python3
"""
Warhammer 40,000 gameplay runner (local UI only).

This script runs the interactive UI loop and supports manual phase advancement.
"""

import argparse
import logging
import os
from typing import Tuple
logger = logging.getLogger(__name__)

# Suppress pygame initialization messages before importing pygame
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.engine.deployment import HumanDeploymentDecisionMaker
from warhammer40k_ai.engine.local_runtime import LocalAuthoritativeRuntime
from warhammer40k_ai.utility.profiling_controller import ProfilingController
from warhammer40k_ai.utility.profiling_sections import profile_section


def _safe_profile_label(value: str) -> str:
    raw = str(value or "profile").strip() or "profile"
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in raw)
    return cleaned.strip("._") or "profile"


def _dump_profile_artifacts(
    controller: ProfilingController,
    *,
    label: str,
    metadata: dict[str, object],
) -> dict[str, str]:
    controller.disable()
    try:
        txt_path, prof_path = controller.dump(
            label=_safe_profile_label(label),
            write_binary_prof=True,
            metadata=dict(metadata or {}),
        )
    except RuntimeError:
        return {}
    artifacts = {"profile_text": str(txt_path.resolve())}
    if prof_path is not None:
        artifacts["profile_binary"] = str(prof_path.resolve())
    return artifacts


def setup_logging(log_level) -> logging.Logger:
    """Configure logging for UI play."""
    print(f"Setting up logging at level {log_level}")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging._nameToLevel[log_level])

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging._nameToLevel[log_level])
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Suppress noisy modules
    for module in [
        "pygame",
        "warhammer40k_ai.roster.army",
        "warhammer40k_ai.units.unit",
        "warhammer40k_ai.units.model",
        "warhammer40k_ai.engine.game",
        "warhammer40k_ai.battlefield.map",
    ]:
        logging.getLogger(module).setLevel(logging.ERROR)

    return logging.getLogger(__name__)


def initialize_game(
    player1_army_file: str,
    player2_army_file: str,
) -> Tuple[pygame.Surface, Game, Map, Player, Player]:
    """Initialize UI, game, and map."""
    from warhammer40k_ai.UI.window import create_pygame_screen

    screen = create_pygame_screen()

    player1 = Player("Player 1", control=PlayerControl.LOCAL, army=None)
    player2 = Player("Player 2", control=PlayerControl.LOCAL, army=None)

    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield, [player1, player2])

    game_map = Map(*game.get_battlefield_size())
    game.set_map(game_map)

    game.army_files = {
        "player1": player1_army_file,
        "player2": player2_army_file,
    }

    return screen, game, game_map, player1, player2


def execute_setup_phases(game_proxy: Game, player_configs: dict, ui_interface, runtime: LocalAuthoritativeRuntime | None = None) -> None:
    """Execute all setup phases automatically."""
    setup_kwargs = {
        "player1_army_file": player_configs.get("player1_army_file"),
        "player2_army_file": player_configs.get("player2_army_file"),
    }

    lifecycle_game = runtime.game_proxy if runtime is not None else game_proxy

    while lifecycle_game.is_in_setup_phase():
        if runtime is not None and runtime.is_driver_managed_setup_phase():
            runtime.run_setup_autosteps()
            continue

        current_phase = lifecycle_game.get_current_setup_phase()

        if current_phase.name == "DEPLOY_ARMIES":
            decision_makers = {
                player.id: HumanDeploymentDecisionMaker(ui_interface=ui_interface)
                for player in lifecycle_game.players
            }
            setup_kwargs["decision_makers"] = decision_makers

        lifecycle_game.execute_current_setup_phase(**setup_kwargs)
        setup_complete = lifecycle_game.advance_setup_phase()
        if setup_complete:
            break


def execute_human_turn(game_proxy: Game, player: Player, ui_interface=None) -> None:
    """Execute a local player's turn."""
    if game_proxy.is_fight_phase():
        logger.info(f"{player.name} fight phase - use UI to select units and fight")
        return
    if game_proxy.is_command_phase():
        game_proxy.start_command_phase()
        game_proxy.next_phase()
        return
    game_proxy.next_phase()


def run_game_loop(player_configs: dict) -> None:
    """Run the interactive UI game loop."""
    manual_phases = bool(player_configs.get("manual_phases", False))

    screen, game, game_map, player1, player2 = initialize_game(
        player_configs["player1_army_file"],
        player_configs["player2_army_file"],
    )
    runtime = LocalAuthoritativeRuntime(
        game,
        player1_army_file=player_configs["player1_army_file"],
        player2_army_file=player_configs["player2_army_file"],
        manual_phases=bool(player_configs.get("manual_phases", False)),
    )
    runtime.register_local_player_facade("local_player1", player1.id)
    runtime.register_local_player_facade("local_player2", player2.id)
    session_game = runtime.game_proxy

    from warhammer40k_ai.UI.game_ui import GameView
    from warhammer40k_ai.UI.human_interface import HumanUIInterface
    from warhammer40k_ai.UI.session_presentation_orchestrator import SessionPresentationOrchestrator

    screen_width, screen_height = screen.get_size()
    ui_interface = HumanUIInterface(screen_width, screen_height)
    game_view = GameView(screen, None, runtime.game_proxy, game_map, player1, player2, ui_interface)
    presentation_orchestrator = SessionPresentationOrchestrator(stream_id="local:authoritative")
    presentation_orchestrator.bind_game_view(game_view)
    presentation_orchestrator.publish_game_loaded(
        game=runtime.game_proxy,
        game_map=game_map,
        players=[player1, player2],
    )

    running = True
    setup_complete = False
    clock = pygame.time.Clock()

    while running and not session_game.is_game_over():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                new_size = (event.w, event.h)
                screen = pygame.display.set_mode(new_size, pygame.RESIZABLE)
                if game_view:
                    game_view.resize_layout(new_size[0], new_size[1])
            elif game_view and game_view.handle_pygame_event(event):
                continue
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if session_game.is_in_setup_phase():
                        current_phase = session_game.get_current_setup_phase()

                        if (
                            current_phase.name == "DEPLOY_ARMIES"
                            and getattr(session_game, "waiting_for_deployment_input", False)
                        ):
                            session_game.set_waiting_for_deployment_input(False)
                            continue

                        setup_kwargs = {
                            "player1_army_file": player_configs.get("player1_army_file"),
                            "player2_army_file": player_configs.get("player2_army_file"),
                        }

                        if current_phase.name == "DEPLOY_ARMIES":
                            decision_makers = {
                                player.id: HumanDeploymentDecisionMaker(ui_interface=ui_interface)
                                for player in session_game.players
                            }
                            setup_kwargs["decision_makers"] = decision_makers
                            setup_kwargs["manual_phases"] = manual_phases

                        session_game.execute_current_setup_phase(**setup_kwargs)

                        if game_view:
                            if current_phase.name == "MUSTER_ARMIES":
                                game_view.refresh_roster_panes()
                                logger.info("Roster panes updated with army units")
                            elif current_phase.name == "DETERMINE_ATTACKER_AND_DEFENDER":
                                game_view.update_roster_pane_titles()
                                logger.info("Roster pane titles updated with roles")

                        should_advance = True
                        if current_phase.name == "DEPLOY_ARMIES":
                            local_players_deploying = False
                            for player in session_game.players:
                                if player.has_control():
                                    undeployed_units = [
                                        unit
                                        for unit in player.get_army().units
                                        if not unit.deployed
                                        and unit.reserve_status not in ("reserves", "strategic_reserves")
                                    ]
                                    if undeployed_units:
                                        local_players_deploying = True
                                        logger.info(f"{player.name} still has {len(undeployed_units)} units to deploy")
                                        break
                            if local_players_deploying:
                                should_advance = False
                                logger.info("Press SPACE again after all units are deployed")

                        if getattr(session_game, "waiting_for_deployment_input", False):
                            should_advance = False

                        if should_advance:
                            setup_complete = session_game.advance_setup_phase()
                            if setup_complete:
                                logger.info("Setup complete! Battle begins!")
                    elif manual_phases:
                        if session_game.is_command_phase():
                            session_game.start_command_phase()
                            session_game.next_phase()
                        elif session_game.is_fight_phase():
                            pass
                        else:
                            session_game.next_phase()
                elif event.key == pygame.K_ESCAPE:
                    if game_view:
                        game_view.close_unit_details()

        if not manual_phases and not session_game.is_in_setup_phase():
            current_player = session_game.get_current_player()
            execute_human_turn(session_game, current_player, ui_interface)

        if not manual_phases and session_game.is_in_setup_phase() and not setup_complete:
            execute_setup_phases(session_game, player_configs, ui_interface, runtime=runtime)
            setup_complete = True
            if game_view:
                game_view.refresh_roster_panes()
                game_view.update_roster_pane_titles()
                logger.info("UI updated after automatic setup completion")

        if game_view:
            with profile_section("render.frame"):
                game_view.draw()
                pygame.display.flip()
            clock.tick(60)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Warhammer 40,000 UI Gameplay Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--player1-army",
        type=str,
        default="army_lists/chaos_test.txt",
        help="Army list file for Player 1",
    )
    parser.add_argument(
        "--player2-army",
        type=str,
        default="army_lists/aeldari_test.txt",
        help="Army list file for Player 2",
    )
    parser.add_argument(
        "--manual-phases",
        action="store_true",
        help="Require SPACE key to advance phases",
    )
    parser.add_argument(
        "-l",
        "--log",
        dest="log_level",
        help="Set the logging level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable cProfile and section-timer profiling artifacts for the UI run.",
    )
    parser.add_argument(
        "--profile-dir",
        default="profiles",
        help="Directory for profiling artifacts when --profile is enabled.",
    )
    parser.add_argument(
        "--profile-sort",
        default="tottime",
        help="pstats sort key for readable profiling reports.",
    )
    parser.add_argument(
        "--profile-lines",
        type=int,
        default=120,
        help="Number of pstats rows to include in readable profiling reports.",
    )
    parser.add_argument(
        "--profile-label",
        default="",
        help="Optional label prefix for profiling artifact filenames.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    setup_logging(args.log_level)
    profile_controller: ProfilingController | None = None
    if bool(args.profile):
        profile_controller = ProfilingController(
            out_dir=str(args.profile_dir or "profiles"),
            sort_by=str(args.profile_sort or "tottime"),
            lines=max(1, int(args.profile_lines or 120)),
        )
        profile_controller.reset()
        profile_controller.enable()
        logger.info("Launch-time profiling enabled.")

    player_configs = {
        "player1_army_file": args.player1_army,
        "player2_army_file": args.player2_army,
        "manual_phases": args.manual_phases,
    }

    logger.info("Game Configuration:")
    logger.info(f"   Player 1: {player_configs['player1_army_file']}")
    logger.info(f"   Player 2: {player_configs['player2_army_file']}")
    if args.manual_phases:
        logger.info("   Manual Phases: ENABLED")

    try:
        run_game_loop(player_configs)
    except KeyboardInterrupt:
        logger.info("\nGame interrupted by user.")
    except Exception as exc:
        logger.exception(f"An error occurred: {exc}")
        import traceback

        traceback.print_exc()
    finally:
        if profile_controller is not None:
            artifacts = _dump_profile_artifacts(
                profile_controller,
                label=f"{str(args.profile_label or 'main')}_pid{os.getpid()}",
                metadata={
                    "script": "scripts/main.py",
                    "player1_army": str(args.player1_army),
                    "player2_army": str(args.player2_army),
                    "manual_phases": bool(args.manual_phases),
                },
            )
            if artifacts:
                logger.info(
                    "Profiling reports saved to %s and %s.",
                    artifacts.get("profile_text", ""),
                    artifacts.get("profile_binary", ""),
                )


if __name__ == "__main__":
    main()
