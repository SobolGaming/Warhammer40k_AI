# 11th Edition Porting Architecture

This note captures the repository-level guardrails for the 11th-edition port-prep
work described in [docs/implementation/11e_port_pr_plan.md](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/docs/implementation/11e_port_pr_plan.md).

**Status:** PR-001 is completed and was pushed to `dev` on April 5, 2026 in
commit `af21acb1`. Remaining PR status is tracked in
[docs/implementation/11e_port_pr_plan.md](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/docs/implementation/11e_port_pr_plan.md).

PR-001 was structural only. It created landing zones and review guardrails so
subsequent PRs can reduce monolith size without changing canonical gameplay
behavior ahead of release-day rules ingestion.

## Port-prep goals

- Separate army construction from runtime army state.
- Make multi-detachment support a first-class runtime concern.
- Keep descriptors, replay, and telemetry portable across the edition change.
- Replace hard-coded mission/objective assumptions with data-driven seams.
- Centralize edition-level invariants instead of scattering them across faction code.

## Structural guardrails

- Do not add new feature work to a known split-target monolith when an adjacent
  landing-zone module already exists.
- Prefer focused modules with one primary reason to change over further growth in
  `game.py`, `player.py`, `army.py`, `map.py`, `deployment.py`,
  `deployment_solver.py`, `attack_resolution.py`, and `fight_phase_manager.py`.
- Keep runtime/public entrypoints stable by preserving façade modules where the
  repository already depends on them.

## Repository-specific façade rules

The port plan is implemented subject to the existing repository constraints:

- `src/warhammer40k_ai/engine/game.py` remains the authoritative public façade for
  game orchestration while setup, phase, scoring, objective, and serialization
  helpers move outward over time.
- `src/warhammer40k_ai/engine/state_blob.py` remains a stable façade even if its
  schema helpers are split into focused sibling modules.
- `src/warhammer40k_ai/engine/descriptor_compiler.py` remains a stable façade even
  if descriptor compilation moves into focused helpers.
- `src/warhammer40k_ai/units/unit.py` remains the `Unit` façade. New `Unit`
  behavior should continue landing in `src/warhammer40k_ai/units/unit_mixins/`
  rather than re-expanding `unit.py`.
- `src/warhammer40k_ai/rules/stratagems.py` remains the façade/orchestrator for
  stratagem management; faction-specific growth belongs in specialized helper
  modules.

## Test-layout guardrails

- New tests should not be added at the flat `tests/` root when a package-aligned
  directory exists.
- Keep package-aligned test roots for engine, roster, units, battlefield, rules,
  network, replay, AI, pathing, UI, and integration coverage.
- Move companion support data with the tests that consume it when those tests rely
  on sibling-relative paths.

## PR-001 scope boundary [COMPLETED]

PR-001 may:

- add docs that describe the target seams and contributor expectations,
- add empty or no-op scaffold modules for future extractions,
- reorganize tests without changing assertions or gameplay behavior,
- make tiny import/path updates required by moved tests.

PR-001 must not:

- encode new 11th-edition gameplay behavior,
- change runtime schemas or replay payloads,
- claim rules-final 11th support.
