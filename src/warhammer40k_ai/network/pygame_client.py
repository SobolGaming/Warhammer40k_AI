from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import pygame

from ..UI.game_ui import GameView
from ..UI.human_interface import HumanUIInterface
from ..UI.window import create_pygame_screen
from .client import NetworkClient
from .game_session import NetworkGameSession, GameUpdate


def _draw_waiting(screen: pygame.Surface, message: str) -> None:
    screen.fill((12, 12, 12))
    font = pygame.font.SysFont("Arial", 22)
    text = font.render(message, True, (230, 230, 230))
    rect = text.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2))
    screen.blit(text, rect)


async def _await_game_start(session: NetworkGameSession, screen: pygame.Surface) -> None:
    clock = pygame.time.Clock()
    while session.game is None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise SystemExit
        try:
            event = await session.client.next_message(timeout=0.05)
            await session.handle_message(event)
        except asyncio.TimeoutError:
            pass
        _draw_waiting(screen, "Waiting for game start...")
        pygame.display.flip()
        clock.tick(30)


async def run_pygame_network_client(
    *,
    uri: str,
    ca_cert: Optional[str] = None,
    insecure: bool = False,
    display_name: str = "Client",
    join_code: Optional[str] = None,
    reconnect_token: Optional[str] = None,
    role: Optional[str] = None,
    army_file: Optional[str] = None,
    ready: bool = False,
) -> None:
    client = NetworkClient(uri=uri, ca_cert=ca_cert, insecure=insecure)
    await client.connect()
    await client.send_hello(display_name)
    screen = create_pygame_screen()
    session = NetworkGameSession(client, allow_commands=(role != "spectator"))

    async def _wait_control(expected_type: str) -> None:
        while True:
            event = await client.next_message()
            await session.handle_message(event)
            if event.category == "control" and event.message_type == expected_type:
                return event.message

    try:
        hello_msg = await _wait_control("hello")
        hello_payload = hello_msg.get("payload", {}) if isinstance(hello_msg, dict) else {}
        if not hello_payload.get("ok"):
            print(f"Version mismatch: {hello_payload.get('errors', [])}")
            return
        await client.send_auth(join_code=join_code, reconnect_token=reconnect_token)
        await _wait_control("auth")
        session.allow_commands = client.role != "spectator"
        if role:
            await client.send_role_select(role)
            await _wait_control("role_select")
        session.allow_commands = client.role != "spectator"
        if army_file:
            list_text = Path(army_file).read_text(encoding="utf-8")
            await client.send_army_submit(list_text, list_name=Path(army_file).name)
            await _wait_control("army_submit")
        if ready:
            await client.send_ready(True)
            await _wait_control("ready")

        await _await_game_start(session, screen)

        ui_interface = HumanUIInterface(screen.get_width(), screen.get_height())

        game_view: Optional[GameView] = None

        def _refresh_view(update: GameUpdate) -> None:
            nonlocal game_view
            game = update.game_proxy
            players = list(getattr(game, "players", []) or [])
            if len(players) < 2:
                return
            if game_view is None:
                game_view = GameView(screen, None, game, getattr(game, "map", None), players[0], players[1], ui_interface)
            else:
                game_view.set_game(game, getattr(game, "map", None), players[0], players[1])

        session.on_game_loaded = _refresh_view
        if session.game is not None and session.game_proxy is not None:
            _refresh_view(GameUpdate(game=session.game, game_proxy=session.game_proxy))

        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    new_size = (event.w, event.h)
                    screen = pygame.display.set_mode(new_size, pygame.RESIZABLE)
                    if game_view:
                        game_view.resize_layout(new_size[0], new_size[1])
                else:
                    if game_view and game_view.handle_pygame_event(event):
                        continue

            await session.poll_messages()
            await session.flush_outgoing()

            if game_view:
                game_view.draw()
                pygame.display.flip()
            clock.tick(60)
    finally:
        await client.close()
