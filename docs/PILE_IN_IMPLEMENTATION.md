# Pile-In Movement Implementation

## Overview
Pile-in movement is validated in `src/warhammer40k_ai/utility/calcs.py` using the
`MovementType.PILE_IN` rules. The UI surfaces the same rules through the per-model
movement dialog and pile-in range visualization.

## Rules enforced
- Models already in base-to-base contact cannot pile in or consolidate.
- Pile-in must end closer to the closest enemy model (or closest enemy unit when the
  `closest_enemy_unit` rule flag is used).
- If base contact is achievable within the pile-in distance, the move must end in
  base-to-base contact.
- Pile-in distance is capped by `PILE_IN_DISTANCE` (3.0").

## Performance optimization
Pile-in validation only considers enemies within:
`ENGAGEMENT_RANGE_HORIZONTAL + PILE_IN_DISTANCE`.

This reduces the candidate set while keeping validation correct for pile-in legality.

## UI behavior
- `IndividualModelMovementDialog` lists all models and disables those already in base
  contact with a reason tooltip.
- `range_renderer.draw_pile_in_range` visualizes the legal pile-in region and the
  intersection with the "must end closer" requirement.

## Constants
Defined in `src/warhammer40k_ai/utility/constants.py`:
- `PILE_IN_DISTANCE`
- `BASE_CONTACT_EPSILON`

## Tests
Relevant tests include:
- `tests/test_fight_phase_pile_in_consolidate_rules.py`
- `tests/test_pile_in_simple.py`
- `tests/test_pile_in_visualization.py`
- `tests/test_collision_detection.py`
- `tests/test_aircraft_rules.py`
