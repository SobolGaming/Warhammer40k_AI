# Network Gameplay Plan (Asyncio WebSockets)

Status: Draft

## Goals

- Provide secure, asyncio-based WebSocket networking for remote clients.
- Run a server-authoritative game with deterministic command/event flow.
- Add a staging area (lobby) where clients choose roles and submit armies.
- Support exactly two players plus any number of spectators.
- Let spectators observe everything but never issue game choices.

## Non-Goals

- Matchmaking or public lobbies.
- Voice or text chat.
- Hidden-information rules (not currently part of 10th edition core flow).

## Dependencies and References

- Network protocol messages exist in `src/warhammer40k_ai/network/messages.py`.
- Command processing + resync helpers exist in `src/warhammer40k_ai/network/protocol.py`.
- Deterministic event log and snapshot behavior defined in `docs/NETWORK_SAVELOAD_DESIGN.md`.
- Army list parsing and mustering behavior defined in `docs/ARMY_MUSTERING_SCAFFOLDING.md`.

## Architecture Overview

- Single authoritative server hosts one or more game sessions.
- Clients connect over TLS-secured WebSockets and exchange JSON messages.
- Game state updates flow as: Client Command -> Server validation -> Event broadcast.
- Spectators receive snapshots/events only; commands from spectators are rejected.

## Transport and Security

- Use asyncio WebSockets with an SSLContext for TLS.
- Server CLI inputs: `--host`, `--port`, `--cert`, `--key`.
- Client inputs: `--server`, `--ca-cert`, `--insecure` (dev only, explicit opt-in).
- Each connection receives a session-scoped token for reconnects and role locking.
- Optional join code or password for private sessions.

## Message Channels

Reuse existing game message envelopes for live gameplay:
- `snapshot`, `command`, `event`, `error`, `resync` (see `network/messages.py`).

Add a control channel for lobby/session management:
- `hello`: protocol version + client metadata.
- `auth`: join code/password + reconnect token (if any).
- `lobby_state`: current players, spectators, readiness, selected armies.
- `role_select`: request Player 1, Player 2, or Spectator.
- `army_submit`: send army list payload (see below).
- `ready`: toggle ready state.
- `start_game`: server-only broadcast when match begins.
- `disconnect`: cleanup or role relinquish.

Control messages should be distinct from game envelopes to keep event logs clean.

## Lobby and Role Model

Lobby state tracks:
- `session_id`
- `player_slots`: {player1, player2} with connection_id, display_name, ready
- `spectators`: list of connection_id + display_name
- `armies`: per-player payload state (none, pending, validated)
- `settings`: mission, board size, optional timers (future)

Role assignment rules:
- Only one client can hold Player 1 or Player 2 at a time.
- Spectators can join any time, even mid-game.
- Reconnect tokens allow a disconnected player to reclaim their slot.
- Spectators can never be promoted after game start unless a player slot is empty.

## Army List Submission

Near-term approach (file-based):
- Clients send `army_submit` with `list_name` and `list_text`.
- Server runs `parse_army_list` and validates points/roster.
- Server stores parsed roster in session state for game start.

Future approach (UI mustering):
- Replace `list_text` with structured roster payload from the mustering UI.
- Keep stable IDs so server rehydrates the same roster deterministically.

## Game Start Flow

1. Both players select roles, submit armies, and mark ready.
2. Server validates rosters and locks lobby state.
3. Server creates `Game`, loads armies, and emits a `snapshot`.
4. Server broadcasts initial events (if any) and enters normal command/event loop.

## In-Game Permissions

- Players can send `command` messages that map to decisions/actions.
- Spectators are read-only: server replies to any `command` with `error`.
- UI for spectators disables all decision prompts but still shows state updates.

## Resync and Reconnect

- Clients track `last_event_id` via `EventStreamCursor`.
- Commands include `client_last_event_id` for sync checks.
- Server replies with `resync` if client is behind or out of range.
- Reconnect uses the session token to restore role and last known event id.

## UI Staging Area (Lobby)

Screen layout:
- Connection panel: server address, status, protocol version.
- Role selector: Player 1, Player 2, Spectator (single-choice).
- Army list panel: select file or paste text (players only).
- Readiness toggle + validation status.
- Start button (server/host only, enabled when both players ready).
- Spectator list with live count.

When implemented, add dialog mappings for any new UI prompts to
`docs/NETWORK_SAVELOAD_DESIGN.md` (for determinism and save/load).

## Spectator UX Requirements

- Live view of phases, actions, and event log.
- Read-only inspection of units, stratagems, and abilities.
- No decision prompts or actionable buttons.

## Testing Plan (pytest)

- Unit tests for lobby state transitions and role assignment rules.
- Protocol tests for control messages and error handling.
- Integration tests with asyncio test server + client loopback.
- TLS handshake tests using a self-signed cert in test fixtures.

## Staged Implementation Plan

1. Transport layer: asyncio server/client, TLS, JSON framing, ping/pong.
   - PR: Add shared transport primitives (JSON framing, message validation) + tests.
   - PR: Add asyncio server with TLS config, connection lifecycle, ping/pong, CLI flags.
   - PR: Add asyncio client with TLS/CA handling, reconnect hooks, ping/pong support.
2. Lobby state + control protocol: role selection, ready states, join tokens.
   - PR: Define lobby state model + pure transition helpers + unit tests.
   - PR: Implement control message handlers (`hello`, `auth`, `role_select`, `ready`, `lobby_state`).
   - PR: Wire lobby events into server transport (broadcasts, error handling).
3. Army list submission and server-side parsing/validation.
   - PR: Add `army_submit` control handling + file/text payload validation.
   - PR: Integrate `parse_army_list` and roster validation with structured errors.
   - PR: Add lobby UI support for list submission + status display.
4. Game start integration: snapshot broadcast + command/event streaming.
   - PR: Start-game gatekeeping (both ready, validated rosters) + lobby lock.
   - PR: Instantiate `Game`, emit initial `snapshot`, begin command/event loop.
   - PR: Add integration tests covering start flow and initial sync.
5. Spectator restrictions and UI gating for read-only mode.
   - PR: Enforce server-side command rejection for spectators + tests.
   - PR: Add UI gating to suppress decision prompts for spectators.
   - PR: Update dialog mapping entries in `docs/NETWORK_SAVELOAD_DESIGN.md`.
6. Reconnect/resync support using existing snapshot/resync helpers.
   - PR: Add session tokens + role reclaim rules + lobby state restore.
   - PR: Add resync flow using `build_resync_message` + cursor tracking.
   - PR: Add integration tests for reconnect and out-of-sync recovery.
7. UI polish + documentation updates, including dialog mapping entries.
   - PR: UX pass on lobby layout, validation feedback, and error messages.
   - PR: Add minimal spectator UX affordances (read-only panels).
   - PR: Refresh docs in `docs/NETWORK_GAMEPLAY.md` and related references.
