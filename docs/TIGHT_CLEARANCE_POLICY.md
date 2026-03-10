# Tight Clearance and Orientation Policy

Normal move validation now includes a local exact SE(2) corridor refiner for
orientation-sensitive tight-clearance movement.

Implemented rules:
- The CDT surface graph remains the global planner.
- The SE(2) refiner is triggered only when needed:
  - non-circular or compound footprint,
  - narrow corridor/portal relative to footprint width,
  - meaningful start/end facing delta for non-circular models.
- Corridor-local state tracks:
  - progress sample along corridor spine (`s`),
  - lateral offset bin,
  - orientation bin (`theta_bin`),
  - `surface_id`,
  - `pivot_used_flag`.
- Each sampled candidate pose is validated with exact footprint geometry:
  - footprint contained in corridor free-space,
  - support coverage on elevated surfaces,
  - dynamic overlap legality using overlay blockers.
- Refinement is endpoint-anchored:
  - first state is the exact requested start pose,
  - terminal state is the exact segment endpoint (connector anchor or final goal),
  - in-place start rotations are modeled as explicit validated states.
- Pivot cost in the local refiner is applied once per corridor using the same
  unit/base semantics as engine pivot-cost rules (no placeholder constant).
- If refinement fails for the best global route, the planner attempts additional
  global candidate routes before returning unreachable.
- Cross-surface transitions use sampled overlap anchors, so connector routing can
  select an alternate legal anchor when one overlap point is blocked.
