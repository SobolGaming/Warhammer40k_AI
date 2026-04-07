# Objective Site Runtime

Status: Current implementation after PR-007 (April 2026)

## Overview

Objective runtime is now split into three explicit concepts:

- `ObjectiveSite`: where the objective exists on the battlefield
- `ControlRegion`: what area is used for control checks
- `ScoreSource`: what scoring surface is bound to that site

This lets the engine represent:

- traditional circular marker objectives
- terrain-footprint objectives
- keyed-feature objectives that resolve against a battlefield feature at runtime

## Runtime modules

- `src/warhammer40k_ai/battlefield/objective_sites.py`
- `src/warhammer40k_ai/battlefield/control_queries.py`
- `src/warhammer40k_ai/battlefield/map_geometry.py`
- `src/warhammer40k_ai/battlefield/terrain_runtime.py`

`src/warhammer40k_ai/battlefield/map.py` remains the stable facade/import surface.

## Current site kinds

- `MARKER`
  - center point plus control radius
- `TERRAIN_FOOTPRINT`
  - polygonal footprint used directly for control checks
- `KEYED_FEATURE`
  - runtime-resolved battlefield feature key, with optional fallback footprint

## Compatibility

- `ObjectivePoint` remains the stable import symbol and now aliases the richer `ObjectiveSite` runtime.
- Existing Chapter Approved mission generation still creates marker-style sites.
- Objective control/state flags such as sticky control, hazards, removed markers, terraform, cleanse, and worldblight tracking remain on the site object.
- Sticky control can now carry a persisted minimum Level of Control floor for rules such as `Claimed for the Dark Gods`.

## Serialization

State blobs, descriptors, and snapshots now preserve:

- site kind / geometry kind
- primary control-region payload
- score-source bindings
- sticky-control minimum Level of Control floors
- optional footprint geometry
- optional keyed-feature references

This is the architectural seam PR-012 will use when final 11th objective semantics land.
