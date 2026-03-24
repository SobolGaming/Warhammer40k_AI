from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pygame

import warhammer40k_ai.UI.game_ui as game_ui_mod
from warhammer40k_ai.UI.game_ui import GameView


def _load_replay_viewer_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "replay_viewer.py"
    spec = importlib.util.spec_from_file_location("test_replay_viewer_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load replay_viewer.py module spec.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_game_view_draw_invokes_post_draw_callback_before_display_update(monkeypatch) -> None:
    call_order: list[str] = []

    monkeypatch.setattr(game_ui_mod, "draw_stratagem_panes", lambda _self: None)
    monkeypatch.setattr(game_ui_mod, "draw_battlefield", lambda *args, **kwargs: None)
    monkeypatch.setattr(game_ui_mod, "draw_deployment_zones", lambda *args, **kwargs: None)
    monkeypatch.setattr(game_ui_mod, "draw_objective", lambda *args, **kwargs: None)
    monkeypatch.setattr(game_ui_mod, "draw_units", lambda *args, **kwargs: None)
    monkeypatch.setattr(game_ui_mod, "draw_top_status_pane", lambda *args, **kwargs: None)
    monkeypatch.setattr(game_ui_mod, "draw_bottom_logs_pane", lambda *args, **kwargs: None)
    monkeypatch.setattr(game_ui_mod, "draw_weapon_ranges", lambda *args, **kwargs: None)
    monkeypatch.setattr(game_ui_mod.pygame.mouse, "get_pos", lambda: (0, 0))
    monkeypatch.setattr(game_ui_mod.pygame.display, "update", lambda *args, **kwargs: call_order.append("update"))

    screen = pygame.Surface((800, 600))

    class _Pane:
        def draw(self, *_args, **_kwargs) -> None:
            return None

    class _DialogManager:
        def draw(self, *_args, **_kwargs) -> None:
            return None

    class _PopupOverlays:
        def set_screen(self, *_args, **_kwargs) -> None:
            return None

    class _Player:
        def get_army(self):
            return SimpleNamespace(units=[])

    game = SimpleNamespace(
        deployment_zones=[],
        map=SimpleNamespace(terrain_features=[], objectives=[], units=[]),
        get_current_player=lambda: _Player(),
    )

    view = SimpleNamespace(
        screen=screen,
        phase_manager=SimpleNamespace(update=lambda: None, get_current_handler=lambda: None),
        left_roster_pane=_Pane(),
        right_roster_pane=_Pane(),
        scaled_battlefield_width=600,
        scaled_battlefield_height=500,
        zoom_level=1.0,
        offset_x=0.0,
        offset_y=0.0,
        game=game,
        game_map=game.map,
        battlefield_left=0,
        player1=None,
        player2=None,
        _draw_cult_ambush_markers=lambda _surface: None,
        individual_model_movement_dialog=SimpleNamespace(
            visible=False,
            unit=None,
            selected_model_index=None,
            movement_type="",
        ),
        selected_unit=None,
        selected_weapon_profile=None,
        detailed_unit=None,
        rule_detail_panel=None,
        draw_move_path=lambda _unit: None,
        ui_interface=SimpleNamespace(update=lambda _screen: None),
        developer_menu_dialog=SimpleNamespace(visible=False, draw=lambda _screen: None),
        dialog_manager=_DialogManager(),
        popup_overlays=_PopupOverlays(),
        _mission_popup=None,
        _vp_history_popup=None,
        _cp_history_popup=None,
        post_draw_callback=lambda _screen: call_order.append("callback"),
    )

    GameView.draw(view)

    assert call_order == ["callback", "update"]


def test_overlay_lines_use_prebattle_label_when_setup_is_incomplete() -> None:
    replay_viewer = _load_replay_viewer_module()
    fake_reader = SimpleNamespace(
        get_step=lambda _idx: SimpleNamespace(
            chosen_option_id="opt-1",
            phase="COMMAND_PHASE",
            turn_id=1,
            decision_type="ATTACH_LEADER",
            actor_player_id="player-1",
            controller_kind="human_local",
            chosen_action_id="action-1",
            wall_clock_ms=5,
            time_budget_ms=None,
        ),
        get_request_payload=lambda _idx: {
            "prompt": "Attach leader Jain Zar",
            "options": [
                {
                    "option_id": "opt-1",
                    "label": "Howling Banshees",
                    "payload": {"action_id": "action-1"},
                }
            ],
        },
        get_decision_record=lambda _idx: {"outcome": {"immediate_deltas": {}}},
        get_events_for_decision=lambda _idx: [{"type": "decision_requested"}],
    )

    lines = replay_viewer._overlay_lines(
        fake_reader,
        {"session_id": "selfplay:000000"},
        "/tmp/replay.sqlite3",
        5,
        220,
        SimpleNamespace(setup_complete=False, setup_phase=SimpleNamespace(name="DECLARE_BATTLE_FORMATIONS")),
    )

    assert ("DECLARE_BATTLE_FORMATIONS | pre-battle | ATTACH_LEADER", replay_viewer.OVERLAY_TEXT) in lines
    assert ("COMMAND_PHASE | turn 1 | ATTACH_LEADER", replay_viewer.OVERLAY_TEXT) not in lines


def test_replay_viewer_uses_game_view_post_draw_callback_without_extra_flip(monkeypatch) -> None:
    replay_viewer = _load_replay_viewer_module()
    overlay_draws: list[tuple[object, list[tuple[str, tuple[int, int, int]]]]] = []
    display_state = {"flip_calls": 0, "captions": []}

    class _FakeScreen:
        def get_width(self) -> int:
            return 1280

        def get_height(self) -> int:
            return 720

    screen = _FakeScreen()

    class _FakeDisplay:
        @staticmethod
        def set_mode(_size, _flags=None):
            return screen

        @staticmethod
        def set_caption(title: str) -> None:
            display_state["captions"].append(title)

        @staticmethod
        def flip() -> None:
            display_state["flip_calls"] += 1

    class _FakeClock:
        def tick(self, _fps: int) -> None:
            return None

    fake_pygame = SimpleNamespace(
        QUIT=1,
        VIDEORESIZE=2,
        KEYDOWN=3,
        K_ESCAPE=27,
        RESIZABLE=0,
        event=SimpleNamespace(get=lambda: [SimpleNamespace(type=1)]),
        display=_FakeDisplay(),
        time=SimpleNamespace(Clock=lambda: _FakeClock()),
        quit=lambda: None,
        Surface=object,
    )

    created_view: dict[str, object] = {}

    class _FakeGameView:
        def __init__(self, screen, _env, _game, _game_map, _player1, _player2, _ui_interface=None):
            self.screen = screen
            self.post_draw_callback = None
            created_view["instance"] = self

        def set_game(self, *_args, **_kwargs) -> None:
            return None

        def resize_layout(self, *_args, **_kwargs) -> None:
            return None

        def handle_pygame_event(self, _event) -> bool:
            return False

        def draw(self) -> None:
            if callable(self.post_draw_callback):
                self.post_draw_callback(self.screen)

    fake_reader = SimpleNamespace(
        metadata=lambda: {"session_id": "selfplay:000000"},
        decision_count=lambda: 5,
    )

    monkeypatch.setattr(replay_viewer, "pygame", fake_pygame)
    monkeypatch.setattr(
        replay_viewer,
        "_parse_args",
        lambda: SimpleNamespace(replay_path="", session_id="selfplay:000000", replay_dir="data", decision_idx=0),
    )
    monkeypatch.setattr(replay_viewer, "_load_reader", lambda _args: (fake_reader, "/tmp/replay.sqlite3"))
    monkeypatch.setattr(replay_viewer, "_load_game_for_index", lambda _reader, _idx: SimpleNamespace(map=None))
    monkeypatch.setattr(replay_viewer, "_resolve_players", lambda _game: ("p1", "p2"))
    monkeypatch.setattr(replay_viewer, "create_pygame_screen", lambda title: screen)
    monkeypatch.setattr(replay_viewer, "HumanUIInterface", lambda width, height: SimpleNamespace(screen_width=width, screen_height=height))
    monkeypatch.setattr(replay_viewer, "GameView", _FakeGameView)
    monkeypatch.setattr(
        replay_viewer,
        "_overlay_lines",
        lambda *_args, **_kwargs: [("Controls", (1, 2, 3))],
    )
    monkeypatch.setattr(
        replay_viewer,
        "_draw_overlay",
        lambda surface, lines: overlay_draws.append((surface, list(lines))),
    )

    assert replay_viewer.main() == 0
    assert created_view["instance"].post_draw_callback is not None
    assert overlay_draws == [(screen, [("Controls", (1, 2, 3))])]
    assert display_state["flip_calls"] == 0
