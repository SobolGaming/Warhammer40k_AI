# Network Gameplay Plan (Asyncio WebSockets)

Status: Implemented (transport, lobby, army submission, start flow, spectator gating, reconnect/resync)

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
- WebSocket transport lives in `src/warhammer40k_ai/network/transport.py` and requires `websockets`.
- Shared command channel abstractions live in `src/warhammer40k_ai/engine/command_channel.py`.
- Lobby state + transitions live in `src/warhammer40k_ai/network/lobby.py`.
- Control envelope helpers live in `src/warhammer40k_ai/network/control.py`.
- Server/client orchestration lives in `src/warhammer40k_ai/network/server.py` and `src/warhammer40k_ai/network/client.py`.
- Pygame network client lives in `src/warhammer40k_ai/network/pygame_client.py` (CLI: `client-ui`).
- Deterministic event log and snapshot behavior defined in `docs/NETWORK_SAVELOAD_DESIGN.md`.
- Army list parsing and mustering behavior defined in `docs/ARMY_MUSTERING_SCAFFOLDING.md`.

## Architecture Overview

- Single authoritative server hosts one or more game sessions.
- Clients connect over TLS-secured WebSockets and exchange JSON messages.
- Game state updates flow as: Client Command -> Server validation -> Command broadcast + Event broadcast.
- Runtime fan-out uses channel adapters:
  - `NetworkCommandChannel` for websocket transport.
  - `InProcessCommandChannel` for local/in-process composition.
- Shared HUD projection uses `UI/session_presentation_orchestrator.py` so local and network clients consume the same presentation envelope flow.
- UI action intake routes through shared intent gateways (`engine/player_intent_gateway.py`) before authoritative validation.
- Clients keep a local game state by replaying accepted commands from the server.
- Spectators receive snapshots/events only; commands from spectators are rejected.
- The pygame UI pumps networking each frame via `NetworkGameSession.poll_messages()`, which uses non-blocking queue reads and yields when empty so the background receiver task can enqueue newly arrived messages.

## Transport vs Orchestration Split

- Transport concerns:
  - connection lifecycle, TLS, ping/pong, framing, delivery.
  - implemented by `network/transport.py` + `NetworkCommandChannel`.
- Orchestration concerns:
  - setup progression, decision lifecycle, phase sequencing.
  - implemented by authoritative runtime/server components.
- This split keeps orchestration reusable across local and network runtimes while preserving one authoritative flow.

## Ordering and Idempotency Contract

- Authoritative presentation/event fan-out uses a canonical envelope contract
  (`src/warhammer40k_ai/engine/presentation_envelope.py`).
- Contract fields:
  - `schema_version` (major.minor)
  - `stream_id` (deterministic stream identity)
  - `sequence_id` (monotonic per stream)
  - `payload` (event/update body)
- Compatibility rule:
  - major mismatch = reject/fail-fast
  - minor bump = additive-compatible
- Client application semantics:
  - duplicate `sequence_id` values are idempotent no-ops
  - out-of-order/gap handling triggers resync/rebuild behavior

## Parity Hardening Utilities

- Presentation transcript hydration/reconnect checks use
  `UI/presentation_state_hydrator.py`.
- Shadow/diff cutover comparisons use `scripts/presentation_shadow_diff.py`
  to compare local vs network presentation transcripts by sequence/payload.

## Transport and Security

- Use asyncio WebSockets with an SSLContext for TLS.
- Server CLI inputs: `--host`, `--port`, `--cert`, `--key`.
- Client inputs: `--server`, `--ca-cert`, `--insecure` (dev only, explicit opt-in).
- CLI entrypoint: `python -m warhammer40k_ai.network.cli server|client|client-ui|client-headless`.
- Self-signed test certs live in `tests/fixtures/tls/` for integration tests.
- Each connection receives a session-scoped token for reconnects and role locking.
- Optional join code or password for private sessions.

## Debugging

- To log incoming client messages and how they are processed, set `W40K_NETWORK_LOG=1`.
  - Works for both `client` (headless) and `client-ui` (pygame) clients.
  - Logs appear in the terminal running the client.
  - Additional client-side tags include `transport.recv`, `session.poll`, and `client.game.*.cursor` to show inbound queueing and event cursor advances.

## Headless Controller Client

- `client-headless` is a policy-driven network client mode for remote AI/hybrid games.
- It composes:
  - `NetworkClient` transport/auth.
  - `NetworkGameSession` snapshot/resync mirror.
  - `HeadlessPolicyDecisionController` attached to `NetworkGameProxy`.
- The server remains authoritative; the headless client only submits deterministic command payloads for decisions it controls.

## Message Channels

Reuse existing game message envelopes for live gameplay:
- `snapshot`, `command`, `event`, `error`, `resync` (see `network/messages.py`).
Note: server broadcasts accepted `command` messages so clients can apply them locally.

Add a control channel for lobby/session management:
- `hello`: protocol version + app_version + client metadata (server replies with server_version + ok).
- `auth`: join code/password + reconnect token (if any).
- `lobby_state`: current players, spectators, readiness, selected armies.
- `role_select`: request Player 1, Player 2, or Spectator.
- `army_submit`: send army list payload (see below).
- `ready`: toggle ready state.
- `start_game`: server-only broadcast when match begins.
- `disconnect`: cleanup or role relinquish.

Control messages should be distinct from game envelopes to keep event logs clean.
Control responses include `ok` and (on failure) `errors` in payload.
Server rejects `auth` until a `hello` handshake succeeds with a matching `app_version`.

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

## Setup Phase Automation (Network)

- Server skips `MUSTER_ARMIES` (armies are already validated/loaded from lobby submission).
- Server auto-runs setup phases up to `DECLARE_BATTLE_FORMATIONS`:
  - Randomly selects a Chapter Approved mission combination + layout (deterministic dice).
  - Executes `SELECT_MISSION_OBJECTIVES`, `CREATE_BATTLEFIELD`, and `DETERMINE_ATTACKER_AND_DEFENDER`.
- During `DECLARE_BATTLE_FORMATIONS`, the server queues formation decisions:
  - Attach Leaders, Assign Transports, Allocate Reserves.
  - Nurgle’s Gift plague selection (when applicable).
- Formation decisions are buffered server-side; the server waits for **both** players to resolve them.
  - Once all formation decisions are submitted, the server resyncs all clients to reveal formations simultaneously
    and advances to `DEPLOY_ARMIES`.
- Clients in remote games auto-open formation dialogs; manual SPACE-based setup advancement is ignored.

## In-Game Permissions

- Players can send `command` messages that map to decisions/actions.
- Spectators are read-only: server replies to any `command` with `error`.
- UI for spectators disables all decision prompts but still shows state updates.
- Manual phase-advance shortcuts (e.g., SPACE key) are ignored unless the current player has local control.

## Resync and Reconnect

- Clients track `last_event_id` via `EventStreamCursor`.
- Commands include `client_last_event_id` for sync checks.
- Server replies with `resync` if client is behind or out of range.
- Reconnect uses the session token to restore role and last known event id.

## UI Staging Area (Lobby)

Screen layout:
- Connection panel: server address, status, protocol version, app version.
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

1. Transport layer: asyncio server/client, TLS, JSON framing, ping/pong. (Complete)
   - PR: Add shared transport primitives (JSON framing, message validation) + tests.
   - PR: Add asyncio server with TLS config, connection lifecycle, ping/pong, CLI flags.
   - PR: Add asyncio client with TLS/CA handling, reconnect hooks, ping/pong support.
2. Lobby state + control protocol: role selection, ready states, join tokens. (Complete)
   - PR: Define lobby state model + pure transition helpers + unit tests.
   - PR: Implement control message handlers (`hello`, `auth`, `role_select`, `ready`, `lobby_state`).
   - PR: Wire lobby events into server transport (broadcasts, error handling).
3. Army list submission and server-side parsing/validation. (Complete)
   - PR: Add `army_submit` control handling + file/text payload validation.
   - PR: Integrate `parse_army_list` and roster validation with structured errors.
   - PR: Add lobby UI support for list submission + status display.
4. Game start integration: snapshot broadcast + command/event streaming. (Complete)
   - PR: Start-game gatekeeping (both ready, validated rosters) + lobby lock.
   - PR: Instantiate `Game`, emit initial `snapshot`, begin command/event loop.
   - PR: Add integration tests covering start flow and initial sync.
5. Spectator restrictions and UI gating for read-only mode. (Complete)
   - PR: Enforce server-side command rejection for spectators + tests.
   - PR: Add UI gating to suppress decision prompts for spectators.
   - PR: Update dialog mapping entries in `docs/NETWORK_SAVELOAD_DESIGN.md`.
6. Reconnect/resync support using existing snapshot/resync helpers. (Complete)
   - PR: Add session tokens + role reclaim rules + lobby state restore.
   - PR: Add resync flow using `build_resync_message` + cursor tracking.
   - PR: Add integration tests for reconnect and out-of-sync recovery.
7. UI polish + documentation updates, including dialog mapping entries. (Complete)
   - PR: UX pass on lobby layout, validation feedback, and error messages.
   - PR: Add minimal spectator UX affordances (read-only panels).
   - PR: Refresh docs in `docs/NETWORK_GAMEPLAY.md` and related references.
