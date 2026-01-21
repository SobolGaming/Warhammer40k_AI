# Ork Wargear Keywords Implementation Plan

## Keywords to Implement (Issue #24)

### 1. BUBBLECHUKKA ✅ IMPLEMENTED
**Weapons**: Bubblechukka (3 profiles: big bubble, wobbly bubble, dense bubble)
**Rule Text**: "Before selecting targets for one or more models equipped with this weapon, roll one D6 to determine which profile models equipped with this weapon will make attacks with, comparing the result with the numbers shown on the left."
**Implementation**:
- ✅ Random profile selection via `Wargear.select_bubblechukka_profile()` method
- ✅ Profile selection based on D6 roll:
  - Rolls 1-2: big bubble (2D6 attacks, S6, AP-1, D1)
  - Rolls 3-4: wobbly bubble (D6 attacks, S9, AP-2, D3)
  - Rolls 5-6: dense bubble (D3 attacks, S12, AP-3, D6+3)
- ✅ `WargearProfile.get_bubblechukka_profile_for_roll(roll)` for manual selection
- ✅ `Wargear.is_bubblechukka()` detection method
- **Usage**: Higher-level code (AI agents, UI) should roll **once per unit** before target selection and cache the selected profile for that unit's activation; all Bubblechukka shots in that activation use the cached profile

### 2. DEAD CHOPPY ✅ IMPLEMENTED
**Weapons**: Dread klaw
**Rule Text**: "The Attacks characteristic of this weapon is increased by 1 for each additional dread klaw this model is equipped with."
**Implementation**:
- ✅ Counts number of dread klaws on model during attack resolution
- ✅ Adds +1 Attack for each additional dread klaw (beyond the first)
- ✅ Implemented in `WargearProfile.attack()` method
- ✅ `WargearProfile.is_dead_choppy()` detection method

### 3. HARPOONED ✅ IMPLEMENTED
**Weapons**: Toxinjector Harpoon
**Rule Text**: "After the bearer has shot with this weapon, select one enemy MONSTER or VEHICLE unit hit by one or more of those attacks. Until the end of the turn, each time the bearer selects that unit as a target of a charge, add 2 to the Charge roll."
**Implementation**:
- ✅ Tracks which MONSTER/VEHICLE units were hit via `harpooned_units` flag
- ✅ Sets flag on target unit when hit is scored
- ✅ Implemented in `WargearProfile._hit_target_with_tracking()` method
- ✅ `WargearProfile.is_harpooned()` detection method
- **Note**: Charge roll modification requires higher-level charge system integration

### 4. HOOKED ✅ IMPLEMENTED
**Weapons**: Kroot bolt thrower
**Rule Text**: "Each time the bearer makes an attack with this weapon that targets a MONSTER or VEHICLE unit, if a hit is scored, until the end of the turn, if the bearer selects that unit as a target of a charge, add 2 to Charge rolls made for the bearer and enemy units cannot use the Fire Overwatch Stratagem to shoot at the bearer."
**Implementation**:
- ✅ Tracks which MONSTER/VEHICLE units were hit via `hooked_units` flag
- ✅ Sets flag on target unit when hit is scored
- ✅ Also sets `hooked_no_overwatch` flag to prevent Overwatch
- ✅ Implemented in `WargearProfile._hit_target_with_tracking()` method
- ✅ `WargearProfile.is_hooked()` detection method
- **Note**: Charge roll modification and Overwatch prevention require higher-level integration

### 5. IMPALED ✅ IMPLEMENTED
**Weapons**: Impaler harpoon (appears twice in data)
**Rule Text**: "Each time this weapon scores a hit against an enemy MONSTER or VEHICLE unit, until the end of the turn, if the bearer selects that unit as a target of a charge, add 2 to Charge rolls made for the bearer"
**Implementation**:
- ✅ Tracks which MONSTER/VEHICLE units were hit via `impaled_units` flag
- ✅ Sets flag on target unit when hit is scored
- ✅ Implemented in `WargearProfile._hit_target_with_tracking()` method
- ✅ `WargearProfile.is_impaled()` detection method
- **Note**: Charge roll modification requires higher-level charge system integration

### 6. SNAGGED ✅ IMPLEMENTED
**Weapons**: Stikka kannon (appears twice in data)
**Rule Text**: "Each time this weapon scores a hit against a MONSTER or VEHICLE unit, until the end of the turn, if the bearer selects that unit as a target of a charge, add 2 to Charge rolls made for the bearer and enemy units cannot use the Fire Overwatch Stratagem to shoot at the bearer."
**Implementation**:
- ✅ Tracks which MONSTER/VEHICLE units were hit via `snagged_units` flag
- ✅ Sets flag on target unit when hit is scored
- ✅ Also sets `snagged_no_overwatch` flag to prevent Overwatch
- ✅ Implemented in `WargearProfile._hit_target_with_tracking()` method
- ✅ `WargearProfile.is_snagged()` detection method
- **Note**: Charge roll modification and Overwatch prevention require higher-level integration

## Implementation Strategy

### Phase 1: Detection Methods
Add keyword detection methods to WargearProfile:
- `is_bubblechukka()`
- `is_dead_choppy()`
- `is_harpooned()`
- `is_hooked()`
- `is_impaled()`
- `is_snagged()`

### Phase 2: Core Logic

#### Bubblechukka
- Select profile **once per unit activation**, before target selection
- Cache the selected profile on the attacking unit (or a per-activation context) and reuse it for all Bubblechukka declarations in that activation
- Ensure UI/AI/auto-selection uses the cached profile to drive target selection, not a player-picked profile

#### Dead Choppy
- Implement in get_attacks() or attack resolution
- Count dread klaws on model
- Modify attacks characteristic

#### Harpooned/Hooked/Impaled/Snagged (Charge Modifiers)
- These all provide +2 to charge rolls against hit MONSTER/VEHICLE units
- Hooked and Snagged also prevent Overwatch
- Need to track hit units during shooting phase
- Apply modifiers during charge phase
- **Note**: Current engine may not fully support charge mechanics
- Implement tracking system for future charge implementation

### Phase 3: Testing
Create comprehensive test file: `tests/test_ork_keywords.py`
- Test each keyword detection
- Test Bubblechukka profile selection
- Test Dead Choppy attacks bonus
- Test charge modifier tracking (even if charge mechanics not fully implemented)

### Phase 4: Documentation
Update WARGEAR_KEYWORD_SUPPORT_MATRIX.md using generator script

## Notes
- Harpooned, Hooked, Impaled, and Snagged all affect charge mechanics
- Current engine may not have full charge roll implementation
- Implement tracking/flagging system for future use
- Bubblechukka requires special profile selection logic
- Dead Choppy is straightforward attacks modification
