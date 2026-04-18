# DecisionRequest/Command API Audit (Tracked Issues)

Date: January 28, 2026  
Status: Draft (tracking list)

This list enumerates **all known player-facing decisions** that do **not** currently route through the unified DecisionRequest/Command API, including cases where a DecisionRequest is created and then **auto-resolved** inside the engine. Each item should be updated so the decision is emitted and resolved through the deterministic decision/command flow.

## Non-DecisionRequest Flows (Direct UI/Console/Provider)

- (none; resolved)

## Optional Selection Decisions (Player._choose_optional_value)

Each of the following uses `_choose_optional_value` directly instead of a DecisionRequest:

- (none; resolved)

## Optional Yes/No Decisions (Player._should_use_optional_ability)

All current true YES/NO confirmations have been routed through DecisionRequests. Optional target-pick flows that can be declined should use a single selection dialog with a “None/Skip” option; no outstanding DEC-OPT items remain.

## Notes

- Items above should be implemented so **all choices are exposed as DecisionRequests** with deterministic `decision_id` and option IDs, and resolved only through `RESOLVE_DECISION` commands.
- When a decision can be declined, follow the single-dialog pattern with an explicit “None/Skip” option.
- If a decision kind does not exist, add one and update `docs/NETWORK_SAVELOAD_DESIGN.md` mapping accordingly.
