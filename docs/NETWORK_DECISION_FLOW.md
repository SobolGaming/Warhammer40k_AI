# Network Decision Flow (As Implemented)

Status: Current behavior (April 2026)

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
- **Headless auto-decisions**: by default, server-side headless auto-resolution handles **dice roll + dice reroll** only when `auto_resolve_dice_rolls` is enabled. Full masked policy auto-resolution is available through `HeadlessPolicyDecisionController` (`src/warhammer40k_ai/engine/headless_policy_controller.py`) when explicitly attached.
- **Decision timeouts**: `DecisionRequest` supports `timeout_seconds` (payload field). Enforcement is a planned server feature; see “Decision Timeouts” below.
- **Candidates + mask**: every DecisionRequest includes deterministic `candidates[]` and a `mask[]` (false = illegal).

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
This progression is orchestrated through the shared `AuthoritativeSessionDriver`
(`src/warhammer40k_ai/engine/authoritative_session_driver.py`), so setup
sequencing logic is not owned exclusively by `NetworkServer`.

The engine now also exposes an explicit pregame step model through
`Game.get_pregame_flow_state()`; see `docs/PREGAME_SETUP_FLOW.md`.
That model records the preview-aligned steps `determine_deployment`,
`optional_twist`, and `select_secondary_missions` as explicit derived/stubbed
steps without changing the current command-level setup compatibility flow.

Local runtime parity note:
- `scripts/main.py` uses `LocalAuthoritativeRuntime` (`src/warhammer40k_ai/engine/local_runtime.py`)
  to run the same driver-managed pre-formation setup phases in-process
  (no websocket loopback).

1. MUSTER_ARMIES → server advances immediately once both players are ready.
2. SELECT_MISSION_OBJECTIVES
   - Server rolls a random mission-pack entry + layout (deterministic dice).
   - Auto-random currently stays on the default `chapter_approved_2025_2026`
     pack, even though the authoritative UI can expose additional eligible
     provisional packs.
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
   - First applies authored build-time attachment bindings when they can be matched to
     runtime units.
   - `CONFIRM_YES_NO` (Hover mode for eligible AIRCRAFT)
   - `ATTACH_LEADER` (only for Leaders still unresolved after any authored bindings)
   - `ATTACH_SUPPORT_ARTILLERY` (only for joined-support units still unresolved after any authored bindings)
   - `ASSIGN_TRANSPORT`
   - `DECLARE_RESERVES`
   - `CHOOSE_PLAGUE` (Death Guard faction — Nurgle's Gift army rule, if applicable)
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

This preserves current live-format parity:
- rosters without authored attachment bindings still resolve attachments through
  normal formation decisions
- authored bindings only suppress the matching dialogs they have already resolved

---

## 4) Post-Formations Setup (Sequential, client-driven)

After formations, the server no longer auto-advances setup phases. The flow is
driven by client decisions and explicit setup commands.

### 4.1) DEPLOY_ARMIES (Sequential by deployment turn)

1. Server waits for deployment decisions in order:
   `CHOOSE_DEPLOYMENT_ZONE` (defender only), `SELECT_NEXT_DEPLOY_UNIT`, then
   placement (`MOVE_UNIT`, `SELECT_FLOOR`).
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
2. Scout moves are queued as `SCOUT_MOVE` DecisionRequests for the owning player.
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

Every battle round:
- Blessings of Khorne (World Eaters)
- Doctrina Imperatives (Adeptus Mechanicus)
- Shadow Form (Be’lakor)
- Wrathful Presence (Angron)

Battle-round-specific:
- Harbingers of Dread (Chaos Knights — BR 1/3/5)
- Templar Vows (Black Templars — BR1 only)
- Hyper-adaptations (Tyranids Invasion Fleet — BR1 only)
- Monarch of the Hunt quarry selection (Shalaxi Helbane — BR1 only; re‑pick triggered later if the quarry is destroyed)
- Methodical Destruction victim selection (Chaos Knights — BR1 only; re‑pick triggered later if the victim is destroyed)
- Prey selection (e.g., Prey of the Blood God / Psychic Spoor — BR1 only; re‑pick only when the ability text specifies it)

1. COMMAND_PHASE
   - Active player resolves start-of-turn decisions (if any).
2. MOVEMENT_PHASE
   - Active player submits movement decisions (`SELECT_MOVEMENT_ACTION`,
     `MOVE_UNIT`, etc).
   - Advance rolls are server-originated dice roll decisions; movement prompts open after the roll resolves.
   - Fixed-Advance rules that say "do not make an Advance roll; add X\" to Move" still use a server roll request with fixed dice, but do not apply advance-roll modifiers or reroll decisions.
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

### 5.1) Worked Examples (Authoritative server, client chooses)

These examples show how a **single player’s** turn proceeds when the server is authoritative and
clients respond to server‑issued decisions. The client still chooses order/targets; the server
simply **presents valid choices** and validates all selections.

#### Example A — Shooting phase (standard + hazardous weapon)

1. **Server enters SHOOTING_PHASE** and queues `SELECT_UNIT` for the active player.
2. **Client chooses a unit** to shoot by resolving `SELECT_UNIT`.
3. **Server queues `DECLARE_SHOTS`** for that selected unit and validates the submitted declarations.
4. **Server then queues**:
   - target selection (and split‑fire decisions if needed)
   - weapon/profile selection
   - any required on-selection ability decisions (for example `CHOOSE_DARK_PACT`; in Cabal of Chaos, Dark Pact options include the `empyric_wellspring_choice` payload)
5. **Client resolves target/weapon choices.**
6. **Defender reaction window (if applicable)**:
   - If the defender has any reactive abilities/stratagems available on being targeted
     (e.g., Smokescreen, Go to Ground, reactive moves), the server queues those decisions now.
   - Defender resolves them via `RESOLVE_DECISION`; server validates and applies any state changes.
7. **Server resolves the attack sequence** for that unit, step‑by‑step:
   - **Hit roll decision(s)** → server rolls and broadcasts results.
     - If rerolls/stratagems are available, the server queues a reroll decision.
     - Client either selects rerolls or chooses “None” to accept the roll.
   - **Wound roll decision(s)** → same sub‑flow as hits (server rolls, reroll window, accept/none).
   - **Save roll decision(s)** → queued to the **defending player** (server rolls, reroll window, accept/none).
   - **Damage roll decision(s)** as needed (including any required allocation choices).
8. **If any selected weapon is Hazardous**:
   - The server **queues a dice roll decision** for the hazardous test (e.g., `3D6` fail on 1).
   - The client resolves the hazardous roll (server rolls + broadcasts results).
   - For **each failed hazardous die**, the server **requires a model allocation choice** from
     the eligible models with hazardous weapons (UI dialog / selection provider).
   - The server applies the mortal wounds to the chosen model(s), then completes the unit’s shooting.
9. **Only after this unit fully resolves**, the server queues the next `SELECT_UNIT`
   (or allows the player to end the phase).

Key point: the client **never invents a roll**. The server issues the roll request; the client only
confirms it, then selects any required follow‑up allocations.

#### Example B — Charge phase with Fire Overwatch interrupt

1. **Server enters CHARGE_PHASE** and queues `SELECT_UNIT`.
2. **Client chooses a charging unit** by resolving `SELECT_UNIT`.
3. **Server queues `DECLARE_CHARGE`** for that unit.
4. **Client chooses charge targets within 12"** and resolves `DECLARE_CHARGE`.
5. **Server validates** charge eligibility, including the hard 12" declaration gate, and broadcasts the declaration.
6. **Overwatch window opens (interrupt):**
   - If the defending player has CP and Overwatch available, the server **queues**
     `SELECT_OVERWATCH_SHOOTER` for the defender.
   - Defender either selects a shooter or declines; the server resolves Overwatch shots immediately.
7. **Server queues the charge roll** decision for the charging unit.
8. **Client resolves the charge roll** (server rolls + broadcasts results).
9. **If the charge succeeds**, the server queues charge‑move placement decisions for the charger.
10. **After placement completes**, the server proceeds to the next `SELECT_UNIT` (or end phase).

Key point: the server can **pause charge placement** until the Overwatch interrupt is resolved,
but the active player still picks the order of charges.

#### Example C — Fight phase (alternating selections)

1. **Server enters FIGHT_PHASE** and determines eligible units for the active player and stage.
2. **Server queues `SELECT_UNIT`** with fight-phase context (`phase_step="FIGHT_FIRST"` or `phase_step="REMAINING_COMBATANTS"`).
3. **Client chooses a unit** by resolving `SELECT_UNIT`, then selects targets and weapon profiles (as required).
4. **Server resolves attack sequence** and any follow-up roll decisions.
5. **Server then queues the next stage-aware `SELECT_UNIT`** for the appropriate player, repeating steps 2–4.
6. **Phase ends** only after all eligible units have fought or the players pass.

Key point: the server controls the **alternation**, the client controls **which eligible unit fights**.

### 5.2) Phase Transitions + Reaction Windows

Phase changes are **broadcast** (e.g., `CMD_NEXT_PHASE` / `CMD_EXECUTE_SETUP_PHASE`), but they are **not**
reaction windows by themselves. Reaction windows are explicit **DecisionRequests** that the server inserts
*before* it advances the phase when a rule/stratagem allows it.

General pattern:
1. **Server completes the current phase** (resolves all in‑phase actions).
2. **Server checks end‑of‑phase / end‑of‑turn reactions** for either player.
3. If any reactions are available, the server **queues decisions** and waits for `RESOLVE_DECISION`.
4. Once reactions resolve (or are declined), the server **broadcasts the phase transition** and continues.

Examples:
- **Rapid Ingress**: at the end of the opponent’s Movement phase, if the defending player has CP and an
  eligible unit in reserves, the server queues a decision to use Rapid Ingress before advancing to Shooting.
- **Hunters from the Warp (Flesh Hounds)**: at the end of the opponent’s turn (after their Fight phase),
  the server queues the ability decision for the owning player **before** advancing to the next player’s
  Command phase.

If no reactions are available, the server advances phases immediately.

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

---

## 8) Decision Timeouts (Planned / Design)

Reactive decisions (especially interrupts like Rapid Ingress or Overwatch) should not be allowed to stall
the game indefinitely. We plan to add **server‑side timeouts** for DecisionRequests, with these rules:

- **Timeout value**: DecisionRequests may include `timeout_seconds` in their payload.
- **Default behavior on timeout**: server auto‑resolves to a **no‑op / decline** option.
- **Broadcast**: the server broadcasts the auto‑resolution so all clients stay in sync.
- **Audit/logging**: event log records that the decision timed out and which default was applied.

This is **not yet enforced** by the server, but the payload field already exists and the decision flow
assumes eventual enforcement.
