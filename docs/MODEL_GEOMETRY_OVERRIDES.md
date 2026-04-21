# Model Geometry Overrides

This document defines how model footprint geometry and model height are resolved.

## Why this exists

Some datasheets use `Use model` or otherwise need manual hull footprints.  
`data/model_geometry_overrides.json` provides:

- manual hull dimensions
- compound/multi-part footprints for single-model units
- explicit model height and optional `z_offset`
- Base Size Guide classifications that require manual geometry (`hull` / `unique`)
- default flying-base `z_offset` when no explicit override is provided

## Resolution order

Geometry is resolved in `src/warhammer40k_ai/utility/model_geometry.py` via `resolve_model_geometry(...)`.

1. Parse base from datasheet/base-size text (existing flow).
2. Apply Base Size Guide classification override (if configured).
3. Apply unit geometry override entry (if present).
4. If no unit override is present and `settings.hull_proxy_policy == "bounding"`, flying-base
   `VEHICLE`/`MONSTER` datasheets resolve to an automatic compound footprint:
   - `support_base`: the parsed flying base geometry
   - `hull_proxy`: a deterministic hull rectangle scaled from the support base size class
5. Resolve model height in this order:
   - explicit override (`height_mm` or per-part max for compound)
   - keyword heuristic
   - fallback: base minor-axis diameter (legacy behavior)
6. Resolve `z_offset` in this order:
   - explicit `z_offset_mm` override
   - flying-base size mapping (for bases parsed as `* flying base`)
   - fallback: `0`

For models with a footprint override (e.g. compound base-or-hull vehicles), flying-base
size mapping is derived from the parsed support base size, not from the overridden hull
footprint bounds.

If Base Size Guide marks a unit as `hull` or `unique` and `requires_manual_geometry=true`, missing override data raises a `ValueError`.

## Compound footprints

Compound models are stored as multiple local parts and treated as one model footprint:

- each part has `shape`, dimensions, local `offset_mm`, and optional `rotation_deg`
- rules footprint is the union of all parts
- pathing/LoS/collision use the true union geometry

Important: connectivity metadata is descriptive only.  
For Aegis Defence Line (`DEPLOYMENT` ability), section composition and connectivity are enforced during deployment validation.
The Aegis `platform` section is also used as an elevated support surface for `Emplacement Platform`
placement/movement legality.

## Current seeded entries

`data/model_geometry_overrides.json` currently seeds:

- `Aegis Defence Line` (compound hull footprint)
- `Drop Pod` (manual central-hull footprint; open fins/ramps excluded from collision footprint)
- `Khorne Lord of Skulls` (manual hull rectangle)
- `Goliath Rockgrinder` (manual hull rectangle)
- `Goliath Truck` (separate manual hull rectangle for the Truck build)
- `Baneblade` (manual hull rectangle, including sponson width)
- `Leman Russ Vanquisher` / `Leman Russ` hull variants (manual hull rectangle)
- `Hydra` / Chimera chassis (manual hull rectangle with Hydra turret height)
- `Rhino` / `Chaos Rhino` (manual hull rectangle)
- `Land Raider` / `Chaos Land Raider` (manual hull rectangle)
- `Wave Serpent` (compound support-base + hull proxy footprint for closest-of-base-or-hull measurement)

Vehicle hull overrides use source notes embedded in `data/model_geometry_overrides.json`. Where only
community model measurements are available, the override is a deterministic bounding rectangle and the
source URL is recorded alongside the dimensions.

When `hull_proxy_policy` is `bounding`, flying-base `VEHICLE`/`MONSTER` datasheets without
explicit overrides also receive deterministic auto-generated support-base + hull-proxy geometry.

Aliases are keyed by datasheet IDs and normalized names.

## Serialization

Snapshot model base serialization includes:

- `base.z_offset`
- `base.compound_parts`

So save/load preserves resolved compound geometry.

## Flying-base z-offset defaults

If a model is parsed from a clear flying base and has no explicit `z_offset_mm` override,
the engine applies a default offset by base minor diameter:

- `<=35mm`: 20mm offset
- `<=65mm`: 32mm offset
- `<=100mm`: 45mm offset
- `<=120mm`: 55mm offset
- `>120mm`: 65mm offset
