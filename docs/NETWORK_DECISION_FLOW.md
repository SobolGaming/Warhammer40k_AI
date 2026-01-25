# Network Decision Flow (As Implemented)

Status: Current behavior (Jan 2026)

This document describes the **server/client decision flow** as implemented today, including
which steps are **simultaneous** vs **sequential**, and **when the server waits** on player input.
It is intended to complement `docs/NETWORK_GAMEPLAY.md` and the decision mapping list in
`docs/NETWORK_SAVELOAD_DESIGN.md`.

---

## Conventions

- **Server authoritative**: only the server validates and accepts commands.
- **Clients are thin views**: each client runs a local game state by applying server‑accepted commands/events.
- **DecisionRequest → DecisionResult**: UI decisions are serialized as `REQUEST_DECISION` + `RESOLVE_DECISION` commands.
- **Waiting**: “server waits” means it does not advance to the next step until required decisions are resolved.
- **Headless auto-decisions**: in local/headless mode, a server-side agent may auto-resolve dice roll decisions via `RESOLVE_DECISION` (no direct engine bypass).

**Simultaneous vs Sequential**
- **Simultaneous**: both players can decide independently at the same time (e.g., formations).
- **Sequential**: a later step only starts after earlier steps or required decisions complete.

---

## 0) Connect + Lobby (Sequential by message)

1. Client connects (TLS WebSocket).
2. `hello` (includes `app_version`, server validates match) → `auth` → `role_select`.
3. Players send `army_submit`.
4. Players send `ready`.
5. Server validates both rosters and starts the game.

---

## 1) Start Game + Snapshot (Sequential by server)

1. Server broadcasts `start_game` (control) with `session_id`.
2. Server broadcasts a full `snapshot` (game state + event cursor).
3. Clients load the snapshot and enter setup mode.
4. If a client reconnects with `last_event_id`, the server sends a `resync`
   (events since that id); otherwise the server sends a full `snapshot`.

---

## 2) Server-Driven Setup Autosteps (Sequential)

The server automatically advances setup until **DECLARE_BATTLE_FORMATIONS**.

1. MUSTER_ARMIES → server advances immediately once both players are ready.
2. SELECT_MISSION_OBJECTIVES
   - Server rolls a random mission combination + layout (deterministic dice).
   - Server sends `CMD_SELECT_MISSION`, then `CMD_EXECUTE_SETUP_PHASE`,
     then `CMD_ADVANCE_SETUP_PHASE`.
3. CREATE_BATTLEFIELD
   - Server sends `CMD_EXECUTE_SETUP_PHASE`, then `CMD_ADVANCE_SETUP_PHASE`.
4. DETERMINE_ATTACKER_AND_DEFENDER
   - Server sends `CMD_EXECUTE_SETUP_PHASE`, then `CMD_ADVANCE_SETUP_PHASE`.
5. DECLARE_BATTLE_FORMATIONS
   - Server queues decision requests and waits (see next section).

---

## 3) Declare Battle Formations (Simultaneous by player, sequential within each player)

This is the first **simultaneous** decision stage. Each player can resolve their
own formation choices independently while the server waits for both to finish.

1. Server builds formation decisions per player:
   - `CONFIRM_YES_NO` (Hover mode for eligible AIRCRAFT)
   - `ATTACH_LEADER`
   - `ASSIGN_TRANSPORT`
   - `DECLARE_RESERVES`
   - `CHOOSE_PLAGUE` (Nurgle's Gift only, if applicable)
2. Server sends `CMD_REQUEST_DECISION` for each request.
3. Each client resolves its own requests (UI dialogs) and sends `CMD_RESOLVE_DECISION`.
4. Server buffers `RESOLVE_DECISION` for formation decisions:
   - These commands are validated and applied but **not broadcast** yet.
   - The server **waits** until the formation decision queue is empty.
5. Server executes `DECLARE_BATTLE_FORMATIONS` and advances to `DEPLOY_ARMIES`
   without broadcasting those commands.
6. Server broadcasts a `resync` (since_event_id=0, reason `formation_reveal`) so
   both players see final formations **simultaneously**.

If there are **no** formation decisions, the server executes and advances
normally (broadcasting the commands/events).

---

## 4) Post-Formations Setup (Sequential, client-driven)

After formations, the server no longer auto-advances setup phases. The flow is
driven by client decisions and explicit setup commands.

### 4.1) DEPLOY_ARMIES (Sequential by deployment turn)

1. Server waits for the active deployment player to submit placement decisions
   (e.g., `MOVE_UNIT`, `SELECT_FLOOR`).
2. Deployment alternates by the current deployment turn (attacker/defender order).
3. When all units are deployed, the next setup phase can be executed and advanced
   by client command (`CMD_EXECUTE_SETUP_PHASE` / `CMD_ADVANCE_SETUP_PHASE`).

### 4.2) REDEPLOY_UNITS (Sequential)

1. If any redeploy abilities generate DecisionRequests, the server waits on the
   owning player(s) to resolve them.
2. Once done, the phase is executed and advanced by client command.

### 4.3) DETERMINE_FIRST_TURN_ORDER (Sequential)

1. When executed, the engine determines who goes first (dice roll logic).
2. Server waits for the client command to execute and advance the phase.

### 4.4) RESOLVE_PREBATTLE_RULES (Sequential, may include interrupts)

1. Pre-battle rules (for example, Scout moves) are processed in turn order.
2. Remote-only games currently auto-skip Scout moves in the engine.
3. Any DecisionRequests are resolved by the owning player; the server waits for them.

---

## 5) Battle Rounds (Sequential phases, with interrupts)

Once setup completes, the game enters battle rounds. These are **sequential**
by phase and by the active player, with occasional opponent interrupts.

### 5.0) Battle Round Start Decisions (Server-queued)

At the start of a battle round, the server queues any required **detachment/unit**
decisions and broadcasts `CMD_REQUEST_DECISION` to the owning player’s client.
Clients resolve via `CMD_RESOLVE_DECISION`; the server validates and broadcasts the
resulting command/event stream so **both players** see the final outcome.

Currently queued at battle round start (when applicable):
- Blessings of Khorne (World Eaters)
- Templar Vows (Black Templars, BR1)
- Hyper-adaptations (Tyranids Invasion Fleet, BR1)
- Harbingers of Dread (Chaos Knights, BR1/3/5)
- Doctrina Imperatives (Adeptus Mechanicus)
- Shadow Form (Be’lakor)
- Wrathful Presence (Angron)
- Monarch of the Hunt quarry selection (Shalaxi, BR1 and re-pick on quarry destroyed)

1. COMMAND_PHASE
   - Active player resolves start-of-turn decisions (if any).
2. MOVEMENT_PHASE
   - Active player submits movement decisions (`SELECT_MOVEMENT_ACTION`,
     `MOVE_UNIT`, etc).
   - Advance rolls are server-originated dice roll decisions; movement prompts open after the roll resolves.
   - Some opponent reactions can interrupt (e.g., reactive moves) and are handled
     as sequential DecisionRequests.
3. SHOOTING_PHASE
   - Active player declares shots (`DECLARE_SHOTS`), selects weapons, allocates,
     etc.
   - Opponent reactions (Overwatch, etc) are sequential interrupts.
4. CHARGE_PHASE
   - Active player declares charges (`DECLARE_CHARGE`), rolls, and resolves.
   - Charge rolls are server-originated dice roll decisions; charge movement prompts open after the roll resolves.
   - Overwatch and other reactions can interrupt.
5. FIGHT_PHASE
   - Units fight in alternating order (sequential).
   - Each step is driven by DecisionRequests (select unit, targets, weapons, etc).

---

## 6) Waiting Points (Summary)

**Simultaneous**
- Declare Battle Formations (each player resolves their own decisions in parallel)

**Sequential**
- Deployment (by deployment turn)
- All later setup phases
- Every battle phase (active player acts; opponent reactions are interrupts)

**Explicit wait conditions**
- The server waits whenever required DecisionRequests are unresolved.
- The server buffers formation resolutions to reveal them simultaneously.

---

## 7) Message Flow Pattern (Command vs Event)

1. Client sends `CommandMessage` (e.g., `CMD_REQUEST_DECISION`, `CMD_RESOLVE_DECISION`).
2. Server validates and applies the command.
3. Server broadcasts the command (or buffers it, in formation phase).
4. Engine emits `EventMessage` updates that clients apply to their local state.
5. On resync, server sends a `ResyncMessage` with events since an event id
   (or full snapshot when no cursor is provided).

For decision dialog mappings, see `docs/NETWORK_SAVELOAD_DESIGN.md`.
