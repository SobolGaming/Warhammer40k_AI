# Tight Clearance and Orientation Policy

Normal move validation now profiles local corridor clearance and applies conservative orientation limits in tight passages.

Implemented rules:
- Local clearance profiling along each move segment.
- Tight interval tags:
  - Elliptical bases: `b <= clearance < a`
  - Hull profiles: `w <= clearance < sqrt(l^2 + w^2)`
- Adaptive sampling step sizes:
  - `0.5"` default
  - `0.25"` in tight intervals
  - `0.1"` in very tight intervals
- Orientation constraint:
  - In tight intervals, yaw change is capped by a conservative yaw band (current default: `15deg`).
