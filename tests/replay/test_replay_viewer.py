from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pygame

import warhammer40k_ai.UI.game_ui as game_ui_mod
import warhammer40k_ai.UI.layout.hud_layout as hud_layout_mod
from warhammer40k_ai.UI.game_ui import GameView


def _load_replay_viewer_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "replay_viewer.py"
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

    assert ("setup phase: DECLARE_BATTLE_FORMATIONS", replay_viewer.OVERLAY_TEXT) in lines
    assert ("decision type: ATTACH_LEADER", replay_viewer.OVERLAY_TEXT) in lines
    assert ("phase: COMMAND_PHASE | turn 1", replay_viewer.OVERLAY_TEXT) not in lines


def test_overlay_lines_show_actor_player_slot_and_replay_army_label() -> None:
    replay_viewer = _load_replay_viewer_module()
    fake_reader = SimpleNamespace(
        get_step=lambda _idx: SimpleNamespace(
            chosen_option_id="opt-1",
            phase="COMMAND_PHASE",
            turn_id=1,
            decision_type="DECLARE_RESERVES",
            actor_player_id="player-2",
            controller_kind="human_remote",
            chosen_action_id="action-1",
            wall_clock_ms=5,
            time_budget_ms=150,
        ),
        get_request_payload=lambda _idx: {
            "prompt": "Allocate reserves for this army.",
            "options": [
                {
                    "option_id": "opt-1",
                    "label": "Teacher allocation",
                    "payload": {"action_id": "action-1"},
                }
            ],
        },
        get_decision_record=lambda _idx: {"outcome": {"immediate_deltas": {}}},
        get_events_for_decision=lambda _idx: [{"type": "decision_requested"}],
    )
    game = SimpleNamespace(
        setup_complete=False,
        setup_phase=SimpleNamespace(name="DECLARE_BATTLE_FORMATIONS"),
        players=[
            SimpleNamespace(id="player-1", name="Player 1"),
            SimpleNamespace(id="player-2", name="Player 2"),
        ],
    )

    lines = replay_viewer._overlay_lines(
        fake_reader,
        {"label": "WE_Daemonkin_2000_vs_Aeldari_Warhost_2000"},
        "/tmp/replay.sqlite3",
        21,
        1285,
        game,
    )

    assert ("actor: Player 2 - Aeldari_Warhost_2000", replay_viewer.OVERLAY_TEXT) in lines
    assert ("controller: human_remote | id player-2", replay_viewer.OVERLAY_MUTED) in lines


def test_load_reader_resolves_filesystem_safe_session_path(monkeypatch, tmp_path) -> None:
    replay_viewer = _load_replay_viewer_module()
    fake_reader = object()

    monkeypatch.setattr(replay_viewer, "load_session_replay_reader", lambda _session_id, base_dir=None: fake_reader)

    reader, resolved = replay_viewer._load_reader(
        SimpleNamespace(replay_path="", session_id="selfplay:000000", replay_dir=str(tmp_path))
    )

    assert reader is fake_reader
    assert resolved == str(tmp_path.resolve() / "selfplay~3A000000" / "replay.sqlite3")


def test_overlay_lines_expand_deployment_move_into_per_model_positions() -> None:
    replay_viewer = _load_replay_viewer_module()
    fake_reader = SimpleNamespace(
        get_step=lambda _idx: SimpleNamespace(
            chosen_option_id="opt-1",
            phase="DEPLOY_ARMIES",
            turn_id=0,
            decision_type="MOVE_UNIT",
            actor_player_id="player-1",
            controller_kind="ai",
            chosen_action_id="action-1",
            wall_clock_ms=8,
            time_budget_ms=None,
        ),
        get_request_payload=lambda _idx: {
            "prompt": "Deploy Howling Banshees",
            "context": {"placement_kind": "deployment", "movement_type": "deploy"},
            "options": [
                {
                    "option_id": "opt-1",
                    "label": "Place at (49.1, 6.5)",
                    "payload": {
                        "action_id": "action-1",
                        "movement_type": "deploy",
                        "model_positions": [
                            {"model_id": "m1", "position": [49.1, 6.5, 0.0], "facing": 90.0},
                            {"model_id": "m2", "position": [50.2, 6.7, 0.0], "facing": 90.0},
                        ],
                    },
                }
            ],
        },
        get_decision_record=lambda _idx: {"outcome": {"immediate_deltas": {}}, "candidates": []},
        get_events_for_decision=lambda _idx: [{"type": "decision_requested"}],
    )

    lines = replay_viewer._overlay_lines(
        fake_reader,
        {"session_id": "selfplay:000000"},
        "/tmp/replay.sqlite3",
        12,
        220,
        SimpleNamespace(setup_complete=False, setup_phase=SimpleNamespace(name="DEPLOY_ARMIES")),
    )

    assert ("chosen placement: 2 models", replay_viewer.OVERLAY_TEXT) in lines
    assert ("1. (49.1, 6.5, 0.0, 90.0)", replay_viewer.OVERLAY_TEXT) in lines
    assert ("2. (50.2, 6.7, 0.0, 90.0)", replay_viewer.OVERLAY_TEXT) in lines
    assert ("chosen option: Place at (49.1, 6.5)", replay_viewer.OVERLAY_TEXT) not in lines


def test_format_roll_line_normalizes_get_roll_reason() -> None:
    replay_viewer = _load_replay_viewer_module()

    line = replay_viewer._format_roll_line({"reason": "get_roll(1D6)", "dice": [4], "value": 4})

    assert line == "Replay roll: 4"


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
        lambda surface, lines, position=None: overlay_draws.append((surface, list(lines))),
    )

    assert replay_viewer.main() == 0
    assert created_view["instance"].post_draw_callback is not None
    assert overlay_draws == [(screen, [("Controls", (1, 2, 3))])]
    assert display_state["flip_calls"] == 0


def test_build_hud_log_overrides_includes_current_decision_roll(monkeypatch) -> None:
    replay_viewer = _load_replay_viewer_module()
    player1 = SimpleNamespace(id="player-1", name="Player 1")
    player2 = SimpleNamespace(id="player-2", name="Player 2")

    monkeypatch.setattr(
        replay_viewer,
        "get_recent_actions",
        lambda player, limit=50: ["existing action"] if player is player1 else ["other action"],
    )
    monkeypatch.setattr(
        replay_viewer,
        "get_recent_dice",
        lambda player, limit=50: ["existing die"] if player is player2 else [],
    )

    fake_reader = SimpleNamespace(
        get_events_for_decision=lambda idx: [
            {
                "type": "roll_made",
                "payload": {
                    "player_id": "player-1",
                    "reason": "Advance roll",
                    "dice": [5],
                    "value": 5,
                },
            }
        ]
        if idx == 7
        else []
    )

    overrides = replay_viewer._build_hud_log_overrides(
        fake_reader,
        7,
        SimpleNamespace(players=[player1, player2]),
    )

    assert overrides["p1_actions"] == ["existing action"]
    assert overrides["p1_dice"] == ["Advance roll: 5"]
    assert overrides["p2_actions"] == ["other action"]
    assert overrides["p2_dice"] == ["existing die"]


def test_draw_bottom_logs_pane_prefers_hud_log_overrides(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    monkeypatch.setattr(hud_layout_mod, "draw_rule_button", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        hud_layout_mod,
        "draw_scroll_text_box",
        lambda _self, _rect, lines, key, title="Logs": captured.__setitem__(key, list(lines)),
    )
    monkeypatch.setattr(hud_layout_mod, "get_recent_actions", lambda *_args, **_kwargs: ["event action"])
    monkeypatch.setattr(hud_layout_mod, "get_recent_dice", lambda *_args, **_kwargs: ["event die"])

    screen = pygame.Surface((1200, 240))
    player1 = SimpleNamespace(name="Player 1")
    player2 = SimpleNamespace(name="Player 2")
    view = SimpleNamespace(
        screen=screen,
        scaled_info_height=120,
        scaled_battlefield_height=120,
        player1=player1,
        player2=player2,
        hud_log_overrides={
            "p1_actions": ["override p1 action"],
            "p1_dice": ["override p1 die"],
            "p2_dice": ["override p2 die"],
            "p2_actions": ["override p2 action"],
        },
        _ui_hitboxes={},
    )

    hud_layout_mod.draw_bottom_logs_pane(view)

    assert captured == {
        "p1_actions": ["override p1 action"],
        "p1_dice": ["override p1 die"],
        "p2_dice": ["override p2 die"],
        "p2_actions": ["override p2 action"],
    }


def test_overlay_layout_allows_partial_offscreen_dragging() -> None:
    replay_viewer = _load_replay_viewer_module()
    screen = pygame.Surface((1280, 720))

    layout = replay_viewer._overlay_layout(
        screen,
        [("Replay", replay_viewer.OVERLAY_TEXT)] * 4,
        position=(-250, 5000),
    )

    assert layout["x"] >= (replay_viewer.OVERLAY_GRAB_MARGIN - layout["width"])
    assert layout["x"] <= (screen.get_width() - replay_viewer.OVERLAY_GRAB_MARGIN)
    assert layout["y"] >= (replay_viewer.OVERLAY_GRAB_MARGIN - layout["height"])
    assert layout["y"] <= (screen.get_height() - replay_viewer.OVERLAY_GRAB_MARGIN)
    assert layout["x"] < replay_viewer.OVERLAY_MARGIN
    assert layout["y"] > (screen.get_height() - layout["height"] - replay_viewer.OVERLAY_MARGIN)


def test_overlay_layout_defaults_to_fully_visible_panel() -> None:
    replay_viewer = _load_replay_viewer_module()
    screen = pygame.Surface((1280, 720))

    layout = replay_viewer._overlay_layout(
        screen,
        [("Replay", replay_viewer.OVERLAY_TEXT)] * 4,
    )

    assert layout["x"] >= replay_viewer.OVERLAY_MARGIN
    assert layout["y"] >= replay_viewer.OVERLAY_MARGIN
    assert layout["x"] + layout["width"] <= screen.get_width() - replay_viewer.OVERLAY_MARGIN
    assert layout["y"] + layout["height"] <= screen.get_height() - replay_viewer.OVERLAY_MARGIN


def test_overlay_header_hitbox_is_drag_handle() -> None:
    replay_viewer = _load_replay_viewer_module()
    layout = {"x": 100, "y": 80, "width": 320, "height": 240, "header_height": 42}

    assert replay_viewer._point_in_overlay_header(layout, (120, 100)) is True
    assert replay_viewer._point_in_overlay_header(layout, (120, 140)) is False


def test_overlay_body_is_also_drag_handle() -> None:
    replay_viewer = _load_replay_viewer_module()
    layout = {"x": 100, "y": 80, "width": 320, "height": 240, "header_height": 42}

    assert replay_viewer._point_in_overlay_drag_region(layout, (120, 100)) is True
    assert replay_viewer._point_in_overlay_drag_region(layout, (120, 200)) is True
    assert replay_viewer._point_in_overlay_drag_region(layout, (50, 50)) is False


def test_overlay_layout_handles_mocked_font_line_sizes(monkeypatch) -> None:
    replay_viewer = _load_replay_viewer_module()
    screen = pygame.Surface((1280, 720))
    mocked_font = SimpleNamespace(get_linesize=MagicMock(return_value=MagicMock()))

    monkeypatch.setattr(replay_viewer, "_overlay_fonts", lambda: (mocked_font, mocked_font))

    layout = replay_viewer._overlay_layout(
        screen,
        [("Replay", replay_viewer.OVERLAY_TEXT)] * 4,
    )

    assert layout["line_height"] == 19
    assert layout["header_height"] == 38
