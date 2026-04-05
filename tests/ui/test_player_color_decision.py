import asyncio

from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PLAYER_COLOR
from warhammer40k_ai.engine.decision_requests import (
    PLAYER_COLOR_HUE_STEP_DEGREES,
    build_player_color_selection_requests,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.UI.decision_ui_utils import option_id_for_hue_degrees
from warhammer40k_ai.UI.player_colors import get_zone_fill_rgba
from warhammer40k_ai.network.server import NetworkServer
from warhammer40k_ai.roster.player import DEFAULT_PLAYER_UI_COLOR_PALETTE, Player, PlayerControl
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


def _build_game():
    player1 = Player("Player One", control=PlayerControl.LOCAL)
    player2 = Player("Player Two", control=PlayerControl.LOCAL)
    game = Game(Battlefield(width=60, height=44), players=[player1, player2])
    return game, player1, player2


def test_players_receive_deterministic_default_ui_colors():
    _, player1, player2 = _build_game()
    assert player1.get_ui_color_rgb() == DEFAULT_PLAYER_UI_COLOR_PALETTE[0]
    assert player2.get_ui_color_rgb() == DEFAULT_PLAYER_UI_COLOR_PALETTE[1]
    assert player1.ui_color_selected is False
    assert player2.ui_color_selected is False


def test_player_color_request_builder_is_deterministic():
    game, player1, player2 = _build_game()
    requests_a = build_player_color_selection_requests(game, [player2, player1], queue_requests=False)
    requests_b = build_player_color_selection_requests(game, [player1, player2], queue_requests=False)

    assert [r.player_id for r in requests_a] == [r.player_id for r in requests_b]
    assert all(r.decision_type == DECISION_CHOOSE_PLAYER_COLOR for r in requests_a)

    expected_count = 360 // PLAYER_COLOR_HUE_STEP_DEGREES
    for req_a, req_b in zip(requests_a, requests_b):
        assert req_a.context.get("selection_kind") == "player_color"
        assert req_a.context.get("hue_step_degrees") == PLAYER_COLOR_HUE_STEP_DEGREES
        assert len(req_a.options) == expected_count
        action_ids_a = [str(opt.payload.get("action_id", "")) for opt in req_a.options]
        action_ids_b = [str(opt.payload.get("action_id", "")) for opt in req_b.options]
        assert action_ids_a == action_ids_b
        assert len(action_ids_a) == len(set(action_ids_a))
        assert list(req_a.candidates) == sorted(req_a.candidates, key=lambda c: str(c.action_id))


def test_player_color_requests_are_deduped_and_apply_updates_player_state():
    game, player1, _ = _build_game()
    game._apply_player_color_declarations()
    pending = [req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_CHOOSE_PLAYER_COLOR]
    assert len(pending) == 2

    # Re-applying declarations should not enqueue duplicates.
    game._apply_player_color_declarations()
    pending_again = [req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_CHOOSE_PLAYER_COLOR]
    assert len(pending_again) == 2

    request = next(req for req in pending_again if str(req.player_id) == str(player1.id))
    chosen = request.options[5]
    cmd_result = resolve_decision_command(game, request, chosen.option_id, player_id=player1.id)
    assert bool(getattr(cmd_result, "ok", False))
    assert player1.ui_color_selected is True
    assert player1.get_ui_color_rgb() == tuple(chosen.payload["rgb"])
    assert int(player1.ui_color_hue_degrees) == int(chosen.payload["hue_degrees"])


def test_player_color_validation_rejects_out_of_range_rgb():
    game, player1, _ = _build_game()
    bad_option = DecisionOption.create(
        "Bad Color",
        payload={
            "player_id": player1.id,
            "rgb": [300, 10, 10],
            "hue_degrees": 0,
        },
    )
    request = DecisionRequest.create(
        DECISION_CHOOSE_PLAYER_COLOR,
        "Pick a color.",
        player_id=player1.id,
        options=[bad_option],
        context={"player_id": player1.id, "selection_kind": "player_color"},
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player1.id,
        option_id=bad_option.option_id,
        payload={},
    )
    apply_result = dispatch_decision(game, request, result)
    assert apply_result.ok is False
    assert "out of range" in " ".join(apply_result.errors).lower()


def test_network_server_formation_queue_includes_player_color_decisions():
    game, player1, player2 = _build_game()
    server = NetworkServer(host="127.0.0.1", port=0, cert_path=None, key_path=None)
    server._game = game

    created = asyncio.run(server._queue_formation_decisions())
    created_player_ids = {
        str(getattr(req, "context", {}).get("player_id", "") or "")
        for req in created
        if req.decision_type == DECISION_CHOOSE_PLAYER_COLOR
    }
    assert created_player_ids == {str(player1.id), str(player2.id)}

    pending = [req for req in server._pending_formation_decisions() if req.decision_type == DECISION_CHOOSE_PLAYER_COLOR]
    pending_player_ids = {str(getattr(req, "context", {}).get("player_id", "") or "") for req in pending}
    assert pending_player_ids == {str(player1.id), str(player2.id)}


def test_option_id_for_hue_degrees_matches_color_payload_hue():
    game, player1, _ = _build_game()
    requests = build_player_color_selection_requests(game, [player1], queue_requests=False)
    assert requests
    request = requests[0]
    selected_option = request.options[4]
    hue = int(selected_option.payload["hue_degrees"])

    assert option_id_for_hue_degrees(request, hue) == selected_option.option_id
    assert option_id_for_hue_degrees(request, hue + 360) == selected_option.option_id
    assert option_id_for_hue_degrees(request, hue + 1) == ""


def test_zone_fill_color_uses_player_selected_rgb():
    _, player1, _ = _build_game()
    player1.set_ui_color([12, 34, 56], hue_degrees=15, selected=True, source="selected")
    assert get_zone_fill_rgba(player1) == (12, 34, 56, 96)


def test_sync_deployment_zones_rekeys_by_attacker_defender_assignment():
    game, player1, player2 = _build_game()
    defender_zone = {"zone_type": "defender", "name": "Defender Zone"}
    attacker_zone = {"zone_type": "attacker", "name": "Attacker Zone"}

    game.deployment_zones = {
        str(player1.id): defender_zone,
        str(player2.id): attacker_zone,
    }
    game.attacker_index = 0
    game.defender_index = 1

    game.sync_deployment_zones_to_attacker_defender()

    assert game.deployment_zones[str(player2.id)]["zone_type"] == "defender"
    assert game.deployment_zones[str(player1.id)]["zone_type"] == "attacker"
