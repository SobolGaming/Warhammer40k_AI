# Performance and Regex Analysis

## Scope and goal
This document summarizes regex-related runtime costs from:
- `profiles/ui_profile_20260214_160923.txt`
- `profiles/ui_profile_20260214_165818.txt`

and proposes an architecture to:
1. Improve runtime performance.
2. Remove `re` matching/searching from hot loops (especially movement/pathing and render-time evaluation paths).

## Profile findings

### High-level delta after caching `_normalize_rules_text`
The second profile already reflects a major improvement from `@lru_cache` on `_normalize_rules_text`.

| Profile | Total time | `re.Pattern.sub` | `re.Pattern.search` | `re.Pattern.finditer` | Total regex method time |
|---|---:|---:|---:|---:|---:|
| `ui_profile_20260214_160923` | 81.572s | 24.905s (30.53%) | 5.413s (6.64%) | 0.070s (0.09%) | 30.389s (37.25%) |
| `ui_profile_20260214_165818` | 49.193s | 0.083s (0.17%) | 3.747s (7.62%) | 0.048s (0.10%) | 3.878s (7.88%) |

Takeaway:
- The cache on `_normalize_rules_text` was a large win.
- Remaining regex cost is now mostly `re.search` in repeatedly called ability-gating helpers.

### Current regex hotspots (code audit refresh)
Historical profile data above remains useful, but the current codebase has moved since those captures.

Key audit findings from current source:
- `has_super_heavy_walker()` is now cached as a boolean on `_ability_cache['super_heavy_walker']` after first evaluation.
- Cache invalidation already exists via `_invalidate_ability_cache()` pathways used by attachment/composition mutations.
- The bigger remaining runtime regex pressure is in `utility/aura_effects.py`, where multiple strict parsers run repeatedly inside per-query loops:
  - `_requires_own_shooting_phase`
  - `_parse_simple_plus_one_aura`
  - `_parse_reroll_ones_aura`
  - `_parse_full_hit_reroll_aura`
- `_find_ability_with_patterns` remains a generic text-scan helper and is still expensive for uncached traits.

Implication:
- `has_super_heavy_walker` is no longer the primary optimization target.
- Aura parsing and generic ability text scanning are now the highest-value areas for parse-once caching.

## Important correctness note: `_iter_conditioned_text_segments` cache
`@lru_cache` on `_iter_conditioned_text_segments(self, text)` is not safe.

Reason:
- Output depends on mutable unit state, not just text:
  - attachment state (`attached_to`, attached leaders)
  - `special_rules` flags
- Cache key currently does not encode that state.
- This can return stale segments and silently change rule behavior.

Conclusion:
- Keep caching only for pure transforms.
- Split this method into pure parse and stateful evaluation (see architecture below).

## Why regex is still in hot loops
The current architecture often parses free-text rule descriptions at query time, including inside:
- ability activity checks (`_ability_is_active`)
- aura parsing (`utility/aura_effects.py` strict parser helpers)
- repeated per-frame/per-candidate scans (`_find_ability_with_patterns`)

Even with compiled patterns, repeated matching in high-frequency loops is expensive relative to boolean flag reads.

## Architectural strategy (idiomatic and comprehensive)

### 1) Introduce a two-stage rule pipeline
Stage A: parse once (regex allowed)
- Parse ability text into a structured `RuleIR` / `AbilitySpec` at load/invalidation boundaries.
- Perform normalization, sentence segmentation, and pattern extraction once.
- Store extracted booleans/values and conditioned clauses.

Stage B: evaluate many times (no regex)
- Runtime checks read precomputed fields only.
- Use boolean logic, integer comparisons, and set membership.
- No `re.search/sub/split/finditer` in hot execution paths.

### 2) Replace runtime text scanning with structured flags
For known frequently queried capabilities, store explicit flags in parsed specs, e.g.:
- `requires_leading: bool`
- `requires_not_leading: bool`
- `led_by_model_phrases: tuple[str, ...]`
- `attached_specific_unit_phrases: tuple[str, ...]`
- `has_super_heavy_walker: bool`
- `aura_specs: tuple[AuraSpec, ...]` (parse-once structured aura definitions)
- parsed numeric values (e.g., scouts distance)

Then:
- `has_super_heavy_walker()` becomes an O(1) cached lookup.
- `_ability_requires_leading/not_leading` become O(1) field reads.
- `_find_ability_with_patterns` should no longer scan raw text for common movement/terrain traits.
- aura evaluation should consume pre-parsed `AuraSpec` data, not run regex per query.

### 3) Split conditioned segments into pure and stateful parts
Current behavior in `_iter_conditioned_text_segments` should be refactored:

- Pure function (cacheable):
  - input: raw text
  - output: parsed segments with structured guard metadata
  - no unit-state reads
  - safe `lru_cache` key: normalized text only

- Stateful filter (not globally cached):
  - input: parsed segments + unit state snapshot
  - output: active segments
  - no regex; only phrase/keyword match logic

This preserves correctness and keeps regex out of repeated runtime evaluation.

### 4) Use generation/versioned caches, not ad-hoc `lru_cache` on methods with `self`
Adopt a consistent cache strategy:
- `unit._rules_parse_cache` for parse artifacts (immutable outputs).
- `unit._ability_cache` for derived runtime flags/specs.
- `unit._rules_cache_generation` increments on mutation events:
  - ability list changes
  - attachment changes
  - special rule changes that affect gating

Cache keys include generation where needed, avoiding stale values.

### 5) Define and enforce hot-loop boundaries
Establish explicit "no regex in hot loop" contract for methods invoked from:
- `utility/calcs.py` movement/pathing checks
- repeated render/combat-phase ability and aura scans

Practical enforcement:
- Add a lightweight test that monkeypatches `re.search/sub/finditer` and asserts they are not called during representative movement/pathfinding loops.
- Keep parser tests separate where regex usage is expected.

### 6) Centralize normalization utilities
Normalization logic is duplicated across mixins (`re.sub` chains repeated many times).
Create a shared normalization utility module with:
- pure normalization helpers
- parse-time-only regex usage
- optional non-regex fast path (`translate` + `split/join`) for simple canonicalization

This reduces both runtime cost and maintenance drift.

## Checklist Task Plan (Implemented)

- [x] Task 1: Remove unsafe stateful caching from `_iter_conditioned_text_segments` and split parse vs runtime evaluation.
  - Result: Removed `@lru_cache` from `ActionsMovementMixin._iter_conditioned_text_segments`.
  - Result: Added pure parse cache `ActionsMovementMixin._parse_conditioned_text_segment_guards(...)` keyed by normalized text.
  - Result: Runtime segment filtering now evaluates unit state against pre-parsed guard descriptors (`always`, `leading_specific_unit`, `attached_specific_unit`) without repeated regex parsing in hot loops.

- [x] Task 2: Add parse-once ability condition metadata for leading/not-leading/model-led checks.
  - Result: Added pure metadata parser cache `ActionsMovementMixin._parse_ability_condition_metadata(...)`.
  - Result: Updated `_ability_requires_leading`, `_ability_requires_not_leading`, `_ability_led_by_model_phrases`, and `_ability_leading_specific_units` to consume cached metadata.
  - Result: Replaced per-call regex normalization in `_ability_is_active` disabled-name filtering with regex-free ASCII token normalization (`_normalize_ascii_alnum_space`).

- [x] Task 3: Remove hot-loop dependence on repeated `has_super_heavy_walker()` text scans.
  - Result: Added `_ability_cache['super_heavy_walker']` caching in `StateAttachmentMixin.has_super_heavy_walker`.
  - Result: Cache is invalidated by existing `_invalidate_ability_cache` pathways.

- [x] Task 4: Improve normalization architecture to parse-time caching and regex-free keyword phrase normalization.
  - Result: Refactored rule text normalization to global pure cache: `KeywordsDetachmentsMixin._normalize_rules_text_cached(...)` (keyed by text, not `self`).
  - Result: Updated `_normalize_rules_text` to call class-level cached normalizer (compatible with lightweight test doubles that call `Unit._normalize_rules_text(self, ...)`).
  - Result: Refactored `_normalize_keyword_phrase` to a cached regex-free ASCII normalization path.

- [x] Task 5: Reduce repeated lowercasing/pattern work inside `_find_ability_with_patterns`.
  - Result: Refactored `PositioningMixin._find_ability_with_patterns` to precompute normalized patterns and extraction matchers once per call.
  - Result: Consolidated scan logic into local `_scan_text(...)` helper to remove repeated nested `pattern.lower()`/`segment.lower()` work.
  - Result: Switched extraction regex construction to `re.escape(pattern)` for safer literal pattern handling.

- [x] Task 6: Add regression tests for correctness of the refactor.
  - Result: Added `tests/test_regex_hotloop_refactors.py`.
  - Result: Added coverage for:
    - state-sensitive conditioned segment evaluation (proves no stale cached result for mutable attachment state),
    - `has_super_heavy_walker` cache + invalidation behavior.

- [x] Task 7: Execute validation test runs (targeted + full suite).
  - Result: `uv run python -m pytest tests/test_regex_hotloop_refactors.py -q` -> passed.
  - Result: `uv run python -m pytest tests/test_super_heavy_walker.py -q` -> passed.
  - Result: `uv run python -m pytest tests/test_attached_battleline_infiltrators_scouts.py -q` -> passed.
  - Result: `uv run python -m pytest tests/test_lord_of_murder.py -q` -> passed.
  - Result: `uv run python -m pytest tests/` -> passed (`1985 passed, 16 warnings`).

- [x] Task 8: Post-refactor audit refresh (doc-only).
  - Result: confirmed `has_super_heavy_walker` already uses `_ability_cache` boolean caching.
  - Result: identified `utility/aura_effects.py` parse helpers as the current repeated regex hotspot.
  - Result: added roadmap PR plan to shift aura/runtime checks to parse-once structured data.

## Further performance improvement ideas

1. Add a parsed ability index on unit/root (`ability_name_tokens`, `ability_desc_tokens`, `trait_flags`) to make most `_find_ability_with_patterns` calls O(1) flag lookups.
2. Introduce generation-scoped `_ability_is_active` memoization (per unit/root generation) to avoid recomputing activity across repeated render/path candidate evaluation within the same state.
3. Move additional regex-heavy parsers in `utility/aura_effects.py` and `ability_specs_mixin.py` to shared parse-once cached helpers, mirroring the same parser/runtime split used here.
4. Add a performance guard test that monkeypatches `re.Pattern.search`/`sub` counters for representative movement/pathing and aura-resolution flows and fails on regressions in hot-loop regex activity.
5. Increase cache observability by recording hit/miss stats for key parse caches (`_normalize_rules_text_cached`, `_parse_ability_condition_metadata`, `_parse_conditioned_text_segment_guards`, aura-spec cache) during profiling runs.

## Roadmap PRs (proposed, not implemented)

### PR 1: Profiling baseline refresh and hotspot instrumentation
Scope:
- Re-run deterministic profiling on current head for local UI and client/server action loops.
- Add optional counters for regex invocations in hot paths (movement + aura evaluation).

Acceptance criteria:
- New profile artifacts committed under `profiles/` with date-stamped names.
- Call-count table in this doc updated using current data.
- Repeatable command list documented.

### PR 2: AbilityTraitIndex (parse-once trait flags)
Scope:
- Add a generation-scoped parsed trait index per unit/root.
- Include stable boolean fields for common trait checks (`has_super_heavy_walker`, leading/not-leading gates, other high-frequency tags).
- Route high-frequency trait checks to index reads.

Acceptance criteria:
- Hot-loop callsites read booleans/specs without regex.
- Trait index invalidates on ability/attachment/special-rules mutation.
- Regression tests cover correctness and invalidation.

### PR 3: AuraSpec parse cache and runtime evaluator split
Scope:
- Add parse-once aura spec extraction (regex allowed) keyed by normalized text + ability identity.
- Refactor `utility/aura_effects.py` runtime to consume `AuraSpec` objects only (no regex in per-query loop).

Acceptance criteria:
- Regex parsers run at parse time only.
- Runtime aura evaluation performs boolean/range/keyword checks only.
- Existing aura behavior tests remain green; add targeted cache/invalidation tests.

### PR 4: `_find_ability_with_patterns` migration to indexed lookups
Scope:
- Identify high-frequency callers and replace with trait/index lookups.
- Keep `_find_ability_with_patterns` as compatibility fallback for non-indexed long-tail checks.

Acceptance criteria:
- Reduced call frequency of `_find_ability_with_patterns` in profiled hot paths.
- No behavior regression in movement/pathing and detachment/enhancement checks.

### PR 5: Performance guardrails in CI
Scope:
- Add lightweight tests asserting no regex usage in representative hot loops.
- Add optional benchmark/profiling smoke checks for regression detection.

Acceptance criteria:
- CI fails on reintroduced regex in guarded hot loops.
- Doc includes troubleshooting guide and known exceptions.

## Final recommendation
Continue using cached normalization for pure text transforms, but prioritize parse-once structured evaluation for aura resolution and high-frequency ability trait checks. `has_super_heavy_walker` is already in a good cached state; the next major wins are aura parser caching and indexed trait lookups that remove regex from runtime loops.
