from warhammer40k_ai.network.lobby import (
    ArmyState,
    ROLE_SPECTATOR,
    apply_army_state,
    apply_auth,
    apply_ready,
    apply_role_select,
    apply_hello,
    disconnect_connection,
    is_ready_to_start,
    new_lobby_state,
    register_connection,
)


def test_lobby_assign_ready_flow():
    state = new_lobby_state()
    state = register_connection(state, "conn-1")
    state = apply_hello(state, "conn-1", "Alice")

    result = apply_auth(state, "conn-1")
    assert result.ok
    token = result.response.get("token")
    assert token

    result = apply_role_select(result.state, "conn-1", "player1")
    assert result.ok

    result = apply_ready(result.state, "conn-1", True)
    assert result.ok
    state = result.state

    slot = state.players["player1"]
    assert slot.display_name == "Alice"
    assert slot.ready is True


def test_lobby_reconnect_token_reclaims_slot():
    state = new_lobby_state()
    state = register_connection(state, "conn-1")
    result = apply_auth(state, "conn-1")
    token = result.response.get("token")
    result = apply_role_select(result.state, "conn-1", "player1")
    state = disconnect_connection(result.state, "conn-1")

    state = register_connection(state, "conn-2")
    result = apply_auth(state, "conn-2", reconnect_token=token)
    assert result.ok
    state = result.state
    slot = state.players["player1"]
    assert slot.connection_id == "conn-2"


def test_lobby_rejects_taken_slot():
    state = new_lobby_state()
    state = register_connection(state, "conn-1")
    state = register_connection(state, "conn-2")

    result = apply_auth(state, "conn-1")
    state = result.state
    result = apply_role_select(state, "conn-1", "player1")
    state = result.state

    result = apply_auth(state, "conn-2")
    state = result.state
    result = apply_role_select(state, "conn-2", "player1")
    assert not result.ok
    assert "taken" in result.errors[0].lower()


def test_lobby_ready_to_start_requires_armies():
    state = new_lobby_state()
    state = register_connection(state, "conn-1")
    state = register_connection(state, "conn-2")

    result = apply_auth(state, "conn-1")
    state = result.state
    result = apply_role_select(state, "conn-1", "player1")
    state = result.state
    result = apply_auth(state, "conn-2")
    state = result.state
    result = apply_role_select(state, "conn-2", "player2")
    state = result.state

    state = apply_army_state(state, "player1", ArmyState(status="validated"))
    state = apply_army_state(state, "player2", ArmyState(status="validated"))

    result = apply_ready(state, "conn-1", True)
    state = result.state
    result = apply_ready(state, "conn-2", True)
    state = result.state

    assert is_ready_to_start(state)


def test_spectator_role_select():
    state = new_lobby_state()
    state = register_connection(state, "conn-1")
    result = apply_auth(state, "conn-1")
    state = result.state
    result = apply_role_select(state, "conn-1", ROLE_SPECTATOR)
    assert result.ok
    assert result.state.connections["conn-1"].role == ROLE_SPECTATOR
