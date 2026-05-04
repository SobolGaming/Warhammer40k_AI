# Headless Matchup Bug Fixes

Batch: `data/headless_matchups_20260504_50_fast`

- Matches 5, 8, and 11 initially emitted stderr `ERROR` lines for routine failed Leadership and Feel No Pain rolls. Those were logging-severity bugs, not gameplay failures. Failed roll outcomes now log at `INFO`, and those matches were rerun with no stderr errors.
- A prior headless batch exposed manual disembark finalization logging recoverable placement rejection at `ERROR`. Manual and automatic disembark placement rejection now use warning-level logging, and failed manual finalization restores speculative model positions.

Final refreshed batch summary:

- Armies generated: 100 exact 2000-point rosters
- Matchups completed: 50/50
- Failed or timed out: 0
- Structured tool diagnostics: 0
- Reserve-arrival diagnostics: 0
- Stderr error lines: 0
