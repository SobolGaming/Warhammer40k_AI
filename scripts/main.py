#!/usr/bin/env python3
"""
Warhammer 40,000 gameplay runner (local UI only).

This script runs the interactive UI loop and supports manual phase advancement.
"""

import argparse
import logging
import os
import sys
from typing import Tuple

# Suppress pygame initialization messages before importing pygame
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.engine.deployment import HumanDeploymentDecisionMaker


def setup_logging() -> logging.Logger:
    """Configure logging for UI play."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
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
    pygame.init()
    from warhammer40k_ai.UI.game_ui import (
        ROSTER_PANE_WIDTH,
        STRATAGEM_PANE_WIDTH,
        BATTLEFIELD_WIDTH,
        BATTLEFIELD_HEIGHT,
        INFO_PANE_HEIGHT,
        TILE_SIZE,
    )

    # Calculate desired window size
    desired_width = BATTLEFIELD_WIDTH + 2 * (ROSTER_PANE_WIDTH + STRATAGEM_PANE_WIDTH)
    TOP_PANE_HEIGHT = int(2 * TILE_SIZE)
    desired_height = BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT + TOP_PANE_HEIGHT

    # Create the window at full desired size first, then determine which display it actually landed on.
    screen = pygame.display.set_mode((desired_width, desired_height), pygame.RESIZABLE)
    pygame.display.set_caption("Warhammer 40,000 Battlefield")

    def _get_target_display_size_for_window() -> Tuple[int, int]:
        """Best-effort: return (w,h) of the display containing the window."""
        info = pygame.display.Info()
        fallback_w, fallback_h = int(info.current_w), int(info.current_h)

        try:
            if hasattr(pygame.display, "get_window_position"):
                wx, wy = pygame.display.get_window_position()
            else:
                return fallback_w, fallback_h

            if hasattr(pygame.display, "get_num_displays") and hasattr(pygame.display, "get_display_bounds"):
                num = int(pygame.display.get_num_displays())
                cx = int(wx + desired_width // 2)
                cy = int(wy + desired_height // 2)
                for i in range(num):
                    bx, by, bw, bh = pygame.display.get_display_bounds(i)
                    if bx <= cx < bx + bw and by <= cy < by + bh:
                        return int(bw), int(bh)
        except Exception:
            pass

        try:
            if hasattr(pygame.display, "get_desktop_sizes"):
                desktop_sizes = pygame.display.get_desktop_sizes()
                if desktop_sizes:
                    best_w, best_h = max(desktop_sizes, key=lambda s: int(s[0]) * int(s[1]))
                    return int(best_w), int(best_h)
        except Exception:
            pass

        return fallback_w, fallback_h

    monitor_width, monitor_height = _get_target_display_size_for_window()

    margin_w = 100
    margin_h = 150
    if sys.platform == "darwin":
        margin_w = 40
        margin_h = 60

    usable_width = max(1, monitor_width - margin_w)
    usable_height = max(1, monitor_height - margin_h)
    scale_factor = min(1.0, usable_width / desired_width, usable_height / desired_height)

    if (desired_width <= monitor_width and desired_height <= monitor_height) and scale_factor < 1.0:
        scale_factor = 1.0

    if os.environ.get("WH_UI_DISPLAY_DEBUG", "").strip():
        try:
            info = pygame.display.Info()
            print(
                f"Display debug: desired={desired_width}x{desired_height} "
                f"info={int(info.current_w)}x{int(info.current_h)} "
                f"chosen_display={monitor_width}x{monitor_height} "
                f"usable={usable_width}x{usable_height} "
                f"scale={scale_factor:.2f}"
            )
        except Exception:
            pass

    if scale_factor < 1.0:
        actual_width = int(desired_width * scale_factor)
        actual_height = int(desired_height * scale_factor)
        print(
            f"Scaling window to fit display: {desired_width}x{desired_height} -> "
            f"{actual_width}x{actual_height} (scale: {scale_factor:.2f})"
        )
        screen = pygame.display.set_mode((actual_width, actual_height), pygame.RESIZABLE)
    else:
        print(f"Using full size window: {desired_width}x{desired_height}")

    pygame.display.set_caption("Warhammer 40,000 Battlefield")

    player1 = Player("Player 1", control=PlayerControl.LOCAL, army=None)
    player2 = Player("Player 2", control=PlayerControl.LOCAL, army=None)

    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield, [player1, player2])

    game_map = Map(*game.get_battlefield_size())
    game.map = game_map

    game.army_files = {
        "player1": player1_army_file,
        "player2": player2_army_file,
    }

    return screen, game, game_map, player1, player2


def execute_setup_phases(game: Game, player_configs: dict, ui_interface) -> None:
    """Execute all setup phases automatically."""
    setup_kwargs = {
        "player1_army_file": player_configs.get("player1_army_file"),
        "player2_army_file": player_configs.get("player2_army_file"),
    }

    while game.is_in_setup_phase():
        current_phase = game.get_current_setup_phase()

        if current_phase.name == "DEPLOY_ARMIES":
            decision_makers = {
                player.name: HumanDeploymentDecisionMaker(ui_interface=ui_interface)
                for player in game.players
            }
            setup_kwargs["decision_makers"] = decision_makers

        game.execute_current_setup_phase(**setup_kwargs)
        setup_complete = game.advance_setup_phase()
        if setup_complete:
            break


def execute_human_turn(game: Game, player: Player, ui_interface=None) -> None:
    """Execute a local player's turn."""
    if game.is_fight_phase():
        print(f"{player.name} fight phase - use UI to select units and fight")
        return
    if game.is_command_phase():
        game.start_command_phase()
        game.next_phase()
        return
    game.next_phase()


def run_game_loop(player_configs: dict) -> None:
    """Run the interactive UI game loop."""
    manual_phases = bool(player_configs.get("manual_phases", False))

    screen, game, game_map, player1, player2 = initialize_game(
        player_configs["player1_army_file"],
        player_configs["player2_army_file"],
    )

    from warhammer40k_ai.UI.game_ui import GameView
    from warhammer40k_ai.UI.human_interface import HumanUIInterface

    screen_width, screen_height = screen.get_size()
    ui_interface = HumanUIInterface(screen_width, screen_height)
    game_view = GameView(screen, None, game, game_map, player1, player2, ui_interface)

    running = True
    setup_complete = False

    while running and not game.is_game_over():
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
                    if game.is_in_setup_phase():
                        current_phase = game.get_current_setup_phase()

                        if (
                            current_phase.name == "DEPLOY_ARMIES"
                            and getattr(game, "waiting_for_deployment_input", False)
                        ):
                            game.waiting_for_deployment_input = False
                            continue

                        setup_kwargs = {
                            "player1_army_file": player_configs.get("player1_army_file"),
                            "player2_army_file": player_configs.get("player2_army_file"),
                        }

                        if current_phase.name == "DEPLOY_ARMIES":
                            decision_makers = {
                                player.name: HumanDeploymentDecisionMaker(ui_interface=ui_interface)
                                for player in game.players
                            }
                            setup_kwargs["decision_makers"] = decision_makers
                            setup_kwargs["manual_phases"] = manual_phases

                        game.execute_current_setup_phase(**setup_kwargs)

                        if game_view:
                            if current_phase.name == "MUSTER_ARMIES":
                                game_view.refresh_roster_panes()
                                print("Roster panes updated with army units")
                            elif current_phase.name == "DETERMINE_ATTACKER_AND_DEFENDER":
                                game_view.update_roster_pane_titles()
                                print("Roster pane titles updated with roles")

                        should_advance = True
                        if current_phase.name == "DEPLOY_ARMIES":
                            local_players_deploying = False
                            for player in game.players:
                                if player.has_control():
                                    undeployed_units = [
                                        unit
                                        for unit in player.get_army().units
                                        if not unit.deployed
                                        and unit.reserve_status not in ("reserves", "strategic_reserves")
                                    ]
                                    if undeployed_units:
                                        local_players_deploying = True
                                        print(f"{player.name} still has {len(undeployed_units)} units to deploy")
                                        break
                            if local_players_deploying:
                                should_advance = False
                                print("Press SPACE again after all units are deployed")

                        if getattr(game, "waiting_for_deployment_input", False):
                            should_advance = False

                        if should_advance:
                            setup_complete = game.advance_setup_phase()
                            if setup_complete:
                                print("Setup complete! Battle begins!")
                    elif manual_phases:
                        current_player = game.get_current_player()
                        if game.is_command_phase():
                            game.start_command_phase()
                            game.next_phase()
                        elif game.is_fight_phase():
                            pass
                        else:
                            game.next_phase()
                elif event.key == pygame.K_ESCAPE:
                    if game_view:
                        game_view.close_unit_details()

        if not manual_phases and not game.is_in_setup_phase():
            current_player = game.get_current_player()
            execute_human_turn(game, current_player, ui_interface)

        if not manual_phases and game.is_in_setup_phase() and not setup_complete:
            execute_setup_phases(game, player_configs, ui_interface)
            setup_complete = True
            if game_view:
                game_view.refresh_roster_panes()
                game_view.update_roster_pane_titles()
                print("UI updated after automatic setup completion")

        if game_view:
            game_view.draw()
            pygame.display.flip()
            pygame.time.Clock().tick(60)


def main() -> None:
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

    args = parser.parse_args()
    setup_logging()

    player_configs = {
        "player1_army_file": args.player1_army,
        "player2_army_file": args.player2_army,
        "manual_phases": args.manual_phases,
    }

    print("Game Configuration:")
    print(f"   Player 1: {player_configs['player1_army_file']}")
    print(f"   Player 2: {player_configs['player2_army_file']}")
    if args.manual_phases:
        print("   Manual Phases: ENABLED")

    try:
        run_game_loop(player_configs)
    except KeyboardInterrupt:
        print("\nGame interrupted by user.")
    except Exception as exc:
        print(f"An error occurred: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
