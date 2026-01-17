# Reserve Unit and Point Limits Implementation

This document summarizes the implementation of reserve unit and point limits according to Warhammer 40k 10th Edition rules.

## Overview

The implementation enforces the official Warhammer 40k 10th Edition reserve limits:
- **Maximum 50% of units** can be in reserves (including Strategic Reserves)
- **Maximum 50% of army points** can be in reserves (including Strategic Reserves)

## Implementation Details

### 1. Army Class Enhancements

Added methods to the `Army` class in `src/warhammer40k_ai/roster/army.py`:

#### `get_reserve_limits() -> dict`
- Calculates the 50% limits for the army
- Returns maximum allowed reserve units and points
- Handles rounding down for odd numbers

#### `can_add_unit_to_reserves(unit, current_reserve_units, current_reserve_points) -> bool`
- Checks if a unit can be added to reserves without exceeding limits
- Validates both unit count and points limits
- Used during interactive reserve selection

#### `validate_reserves_decisions(reserves_decisions) -> dict`
- Validates complete reserve decisions against limits
- Returns validation result with errors if any
- Used for final validation before deployment

#### `enforce_reserves_limits(reserves_decisions) -> dict`
- Automatically enforces limits by converting excess reserves to deploy
- Ensures final decisions comply with 50% limits
- Used as fallback when validation fails

#### `get_current_reserves_status(reserves_decisions) -> dict`
- Provides current reserve status and limits information
- Used for UI display and debugging

### 2. Deployment Decision Updates

Updated `src/warhammer40k_ai/classes/deployment.py`:

#### `HumanDeploymentDecisionMaker.declare_reserves()`
- Shows reserve limits to the player during selection
- Prevents selections that exceed limits
- Includes final validation and enforcement
- Provides real-time feedback on current reserve status

### 3. UI Dialog Updates

Updated `src/warhammer40k_ai/UI/dialogs/reserves_selection_dialog.py`:

#### ReservesSelectionDialog
- Displays current reserve limits and status
- Disables buttons when limits would be exceeded
- Shows visual feedback for disabled options
- Includes final validation and enforcement
- Converts unit ID-based choices to unit name-based decisions

## Key Features

### 1. Consistent Enforcement
- All interfaces (UI and console) use the same Army methods
- Prevents bypass bugs where different interfaces allow different limits
- Ensures consistent 50% limits across all game types

### 2. Real-time Validation
- UI prevents players from making invalid selections
- Buttons are disabled when limits would be exceeded
- Provides immediate feedback on current reserve status

### 3. Automatic Enforcement
- If validation fails, limits are automatically enforced
- Excess reserves are converted to deploy status
- Ensures games can always proceed with valid reserve decisions

### 4. Future-Proof Design
- Handles Leaders joining units (when implemented)
- Handles units embarked in transports (when implemented)
- Architecture supports future reserve rule changes

## Usage Examples

### Console Reserve Selection
```python
# Player sees limits and current status
print(f"Reserve Limits: {limits['max_units']}/{limits['total_units']} units")
# System prevents invalid selections
```

### UI Reserve Selection
```python
# Dialog shows limits and disables invalid options
# Final validation ensures compliance
reserves_decisions = dialog.get_final_decisions()
```

## Testing

The implementation includes coverage for:
- Unit limit validation (50% of total units)
- Points limit validation (50% of total points)
- Edge cases (odd numbers, zero units, etc.)
- Enforcement mechanism validation
- Status tracking validation

## Compliance with Warhammer 40k Rules

The implementation follows the official 10th Edition rules:
- Maximum 50% of units in reserves
- Maximum 50% of points in reserves
- Both limits must be satisfied
- Applies to both Reserves and Strategic Reserves
- Handles Leaders and transports correctly (when implemented)

## Architecture Benefits

1. **Centralized Logic**: All reserve limit logic is in the Army class
2. **Consistent Interfaces**: All players use the same validation methods
3. **Prevents Bypass Bugs**: UI cannot exceed limits that other interfaces cannot
4. **Maintainable**: Single source of truth for reserve rules
5. **Extensible**: Easy to modify for future rule changes

This implementation ensures that reserve limits are properly enforced across all player interfaces, providing a consistent and rule-compliant experience.
