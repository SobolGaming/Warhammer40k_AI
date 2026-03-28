# Necrons FAQ / Errata Notes

This note tracks engine behaviors added to close FAQ / errata gaps that were
previously marked as supported in faction docs but were missing edge-case
coverage in the rules engine.

## Hypercrypt Legion and Eternity Gate

- Hyperphasing round-one arrivals are legal only during the owning player's
  Movement phase, and only for units marked for that specific Hyperphasing
  return.
- A Hyperphased unit with Deep Strike can arrive from Strategic Reserves in
  battle round 1 when going second.
- `Eternity Gate` can also set up a Hyperphased unit in battle round 1 even
  when that unit does not have Deep Strike.
- `Eternity Gate` setup ignores the normal Strategic Reserves battlefield-edge
  requirement and instead validates only the Monolith anchor, engagement-range,
  and no-charge restrictions from the ability.

## Reanimation Protocols

- Rules that activate Reanimation Protocols for an attached unit only treat the
  unit as eligible while at least one bodyguard model from that attached unit
  remains on the battlefield.

## Reactive movement parity

- Deterministic `DECISION_MOVE_UNIT` resolution now emits the same
  `unit_move_ended` event as the local movement path for Normal, Advance, Fall
  Back, Charge, and reactive moves.
- This keeps reactive-move follow-up rules such as `Wraith Form` consistent
  between local and remote / replay-driven execution.
