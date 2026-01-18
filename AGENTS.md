# AGENTS.md — Repository-wide rules for Codex agents and contributors

## Agent permissions
**Enable agent full access** for this repository. The agent may read/write across the repo as needed to implement features, refactors, tests, and documentation updates, subject to the constraints below.

---

## Mission and scope

### What we are building
Implement a **Warhammer 40,000 (10th Edition) game engine** that allows **two armies** to play on a battlefield against each other, supporting the **latest**:
- Core rules and gameplay flow
- Datasheets
- Balance Dataslates
- FAQs
- Errata
- Munitorum Field Manual (MFM) point costs
- Faction Packs

### Explicitly out of scope (do not implement)
We will **NOT** support any units, rules, or abilities tied to:
- Crusade
- Forge Worlds
- Legends
- Boarding Actions
- Kill Teams

If a requested change depends on any out-of-scope content, stop and ask the developer.

---

## Canonical data, rules sources, and documentation

### Documentation location
- Markdown documentation lives in: `docs/`
- Any implementation that changes behavior must include doc updates in `docs/` (or add new docs in `docs/` if missing).

### Canonical structured game data source (in-repo)
Raw information about the following exists in **JSON** under `wahapedia_data/` and should be used as the first-choice structured source:
- ability
- faction
- detachment
- wargear
- stratagem
- enhancement
- model
- wargear options
- keyword
- datasheet

### Rules interpretation sources (official first; latest only)
- For rules/errata/FAQ/dataslate/MFM point costs and other “what is the latest rule?” questions, **prefer official Warhammer Community sources and PDFs first**.
- **Ensure you are using the LATEST rulesets / errata / PDFs**. If multiple versions exist, use the most recent and do not implement against outdated language.

### About using wahapedia.ru
- Do **not** use wahapedia.ru as the default source for implementation details.
- If a rule cannot be resolved from in-repo data and official sources, wahapedia.ru may be consulted **only as a last resort** and the developer must be informed of:
  - what official sources were checked
  - what remains ambiguous
  - what text/interpretation is being proposed
- If there is any discrepancy between sources, **ask the developer before implementing**.

---

## Definition of “implement support for a rule / ability / feature”
When instructed to implement or add support for a rule/ability/feature, that means ALL of the following (unless the developer explicitly says otherwise):

1. **Engine hooks**
   - Add/extend the game engine’s domain model and resolution logic.
   - Integrate into the correct phase/step timing and interaction points.
   - Ensure determinism and reproducibility.

2. **UI hooks**
   - Add/extend UI-facing state, events, and user-facing prompts as needed.
   - Any “human choice” must be represented as an explicit decision point (see “Player choice handling” and “Future AI/RL support”).

3. **Tests**
   - Add tests that validate expected behavior, edge cases, and regressions.
   - Tests must be runnable locally and in CI.

4. **Documentation**
   - Update or add `docs/` content describing the implemented behavior, assumptions, and known limitations.

---

## Player choice handling (mandatory)

### When a rule implies choice
If a rule/ability description states:
- “you can”
- “you may”
- “the player can”
- or any phrasing that indicates an **optional** action or decision

Then the choice **must be presented to the player via a UI dialog** (and represented as an explicit decision/action in the engine).

### Single-dialog pattern for optional selections (preferred)
For choices like “you can pick one unit from …”, do **not** implement two dialogs:
1) Yes/No to decide whether to pick, then
2) A second dialog to pick which unit.

Instead, implement a **single selection dialog** where the choice pool includes:
- all eligible units/options, **plus**
- a `"None"` (or equivalent) option that represents declining the optional choice (“No”)

This rule exists to reduce UI friction and to keep decision/action modeling clean for future AI control.

---

## Testing requirements (pytest)

### Test location
- Tests live in: `tests/`

### Framework
- The testing framework is **pytest**.

### Minimum expectation for all changes
- Any tests created must be run and passed.
- Also run any relevant existing tests affected by the change.

### Full test suite requirement for large/rule-behavior changes
After **large feature changes** or **changes to rule behavior**, in addition to running newly added tests, a **full test suite** run is required using:

`python -m pytest tests/`

Notes:
- This run can take **20–30 minutes**.
- Ensure appropriate timeouts are used in your execution environment/CI so the run is not prematurely terminated.

### Reporting
When submitting changes, record:
- the exact pytest command(s) run
- pass/fail status
- any skipped tests (only with developer approval)

---

## Engineering standards and constraints

### Error handling (important)
- **Do not add `try/except` unless it makes absolute sense.**
- Avoid broad exception handling (`except Exception`, bare `except`) because it hides failures.
- If an exception must be caught:
  - catch the most specific exception type possible
  - preserve stack traces and context
  - either re-raise or convert to a clear, actionable error surfaced to developers

### No backwards compatibility / no fallbacks
- **Do not create fallback code** or attempt to keep backwards compatibility.
- This is a new application early in development; prefer direct, correct changes over compatibility shims.

### Code quality over speed
- **Efficient, well-formed code is more important than fast and quick responses.**
- Prefer correctness, clarity, and composability over rushed implementation.

### Reuse and modularity
- Clean, functional, reusable code is required.
- **Do not duplicate logic across multiple functions.** If behavior is used in more than one place:
  - extract it into a shared function/module
  - add focused unit tests for the shared code

### File size and separation of concerns
- **Do not create large files.**
- Isolate specific functionality into its own module/file.
- Prefer:
  - small cohesive modules
  - clear boundaries (engine vs UI vs data parsing vs tests)
  - dependency direction that keeps the engine independent of UI

---

## Architecture requirements for future multiplayer support (WebSockets)

We plan to implement **Python WebSocket support** for server/client gameplay.

Design constraints now:
- Game state and game events must be **serializable** and **synchronizable**.
- Avoid hidden, non-serializable state (e.g., open file handles, unstructured globals, lambdas/closures in state objects).
- Prefer explicit schemas for:
  - game state snapshots
  - incremental events / commands
  - deterministic identifiers for entities (units, models, squads, tokens, effects)
- Favor deterministic resolution:
  - if randomness exists, it must be injectable and seedable
  - state transitions should be reproducible from an event log

Practical expectation:
- When adding new state or events, consider how they will be encoded/decoded and validated across a network boundary.

---

## Architecture requirements for future AI (Hierarchical Reinforcement Learning)

We plan to add **hierarchical reinforcement learning** so AI can learn to play at strategic, operational, and tactical levels.

Design constraints now:
- Any human player choice (often expressed via GUI dialogs/HUD choices) must be representable as:
  - an explicit **decision point**
  - with a finite, enumerable action space (or clearly bounded parameterization)
- Any keyboard/mouse clicks (battlefield position clicks or choice clicks) must be modeled as:
  - explicit actions with payloads (e.g., coordinates, target IDs, option IDs)
- The engine must not depend on interactive UI to proceed:
  - UI should be a client of the same decision/action interface an AI agent will use
- Prefer an “engine-first” design:
  - the engine emits “required decisions”
  - the controller (human UI or AI policy) provides “chosen actions”
  - the engine validates and applies actions deterministically

Practical expectation:
- When implementing a feature that introduces a player choice, include:
  - an explicit decision/action definition
  - validation rules
  - tests covering at least one human-like choice path and one invalid choice path

---

## Handling ambiguity and rules questions (mandatory)
If you have **any questions** about:
- rules accuracy
- timing interactions
- intended behavior
- UI intent
- data interpretation
- “latest version” ambiguity across PDFs/errata/dataslates/MFM

**ASK the developer before implementing code.**

Do not guess on rules nuance. Propose a concrete set of questions and a recommended interpretation, then wait for developer direction before proceeding with implementation.

## Distance/range interpretation
Unless an ability explicitly states a distance is measured "horizontally" or "vertically," interpret any stated distance/range as **3D distance**.

---

## Out-of-scope requests and escalation
If a task requires:
- Crusade / Forge Worlds / Legends / Boarding Actions / Kill Teams content
- large refactors that change architecture direction
- adopting non-latest rules text due to missing sources

Stop and ask the developer with:
- what you found
- what you propose
- risks and tradeoffs
- a small-step implementation plan
