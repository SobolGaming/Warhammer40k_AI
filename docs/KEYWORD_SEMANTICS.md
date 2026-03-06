# Keyword Semantics: Model vs Unit Keywords

## Overview

In Warhammer 40,000 (10th Edition), keywords can exist at both the **model level** and the **unit level**. This document describes how the engine handles keyword storage and resolution.

## Model-Level Keywords

### Storage
- Each `Model` instance stores its own keywords in two lists:
  - `model.keywords` - Standard keywords (e.g., INFANTRY, GRENADES)
  - `model.faction_keywords` - Faction keywords (e.g., IMPERIUM, CHAOS)

### Initialization
- Model keywords are initialized from the datasheet when a unit is created
- Keywords are copied from `datasheet.keywords` and `datasheet.faction_keywords`

### Methods
- `model.has_keyword(keyword)` - Checks if the model has the specified keyword in `model.keywords` (case-insensitive)
- `model.has_any_keyword(keyword)` - Checks if the model has the specified keyword in either `model.keywords` or `model.faction_keywords` (case-insensitive)

## Unit-Level Keywords

### Computed Union
- Unit keywords are **computed on-demand** as the union of all model keywords
- For attached units (leader + bodyguard), the effective keywords include all models from all attached unit members
- This ensures that adding/removing models automatically updates the unit's keyword set

### Methods
- `unit.get_effective_keywords()` - Returns the union of all model keywords from all models in the unit (and attached units if applicable)
- `unit.has_any_keyword(keyword)` - Checks if any model in the unit (or attached units) has the specified keyword

### Ability-Added Keywords
- Some abilities can add keywords to a unit (e.g., Hover mode removes AIRCRAFT keyword)
- These are stored separately at the unit level and included in the effective keyword computation
- Exact bearer-keyword clauses such as `The bearer has the PSYKER keyword.` are parsed and applied.
- For enhancement text using that pattern, the keyword is applied to the resolved enhancement bearer model when available.

## Backwards Compatibility

- The engine maintains both model-level and unit-level keyword storage for backwards compatibility
- Existing code that expects `unit.keywords` continues to work
- New code should use `unit.get_effective_keywords()` for the most accurate keyword set

## Example: Psychic Assassin Wargear Keyword

The Psychic Assassin wargear keyword demonstrates model vs unit keyword semantics:

1. **Keyword Detection**: `WargearProfile.is_psychic_assassin()` checks if the weapon has the "psychic assassin" keyword
2. **Target Eligibility**: `target_unit.has_any_keyword("PSYKER")` checks if any model in the target unit has the PSYKER keyword
3. **Attacks Override**: When both conditions are met, the weapon's Attacks characteristic becomes 6

This works correctly because:
- The weapon keyword is checked at the profile level
- The target keyword is checked at the unit level (which computes the union of all model keywords)
- If any model in the target unit is a PSYKER, the entire unit is considered to have the PSYKER keyword for targeting purposes

## Implementation Notes

- All keyword comparisons are **case-insensitive** (using `.lower()`)
- Keyword checks use try-except blocks for safety to avoid breaking game flow on unexpected data
- The effective keyword computation handles attached units correctly by iterating through all unit members
