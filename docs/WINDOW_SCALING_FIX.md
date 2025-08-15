# Window Scaling Fix for Laptop Monitors

## Problem
When running the game on a laptop with smaller monitor resolution, the pygame window (1900x1000 pixels) exceeds the screen size, causing mouse coordinate misalignment due to OS window scaling/clipping.

## Solution Implemented

### ✅ 1. Automatic Window Scaling
**File:** `scripts/main.py`

- **Monitor Detection**: Uses `pygame.display.Info()` to get current monitor resolution
- **Smart Scaling**: Calculates scale factor to fit window within usable screen area
- **Margin Handling**: Leaves 100px width + 150px height margin for window decorations/taskbar

```python
# Get monitor resolution
info = pygame.display.Info()
monitor_width = info.current_w
monitor_height = info.current_h

# Leave margins for decorations
usable_width = monitor_width - 100
usable_height = monitor_height - 150

# Scale down if needed
scale_factor = min(1.0, usable_width / desired_width, usable_height / desired_height)
```

### ✅ 2. UI Component Scaling
**File:** `src/warhammer40k_ai/UI/game_ui.py`

- **Scaled Dimensions**: All UI components use scaled dimensions
- **Roster Panes**: Width and positioning adjusted for scale factor
- **Battlefield**: Rendering area scaled proportionally
- **Info Panel**: Height and position scaled correctly

### ✅ 3. Mouse Coordinate Conversion
**File:** `src/warhammer40k_ai/UI/game_ui.py`

- **Centralized Methods**: Added `screen_to_game_coords()` and `game_to_screen_coords()`
- **Scale Factor Integration**: All coordinate conversions account for UI scaling
- **Consistent Usage**: Updated `get_model_at_position()` to use helper methods

```python
def screen_to_game_coords(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
    """Convert screen coordinates to game coordinates with proper scaling"""
    game_x = (screen_x - self.scaled_roster_width - self.offset_x) / (TILE_SIZE * self.zoom_level * self.ui_scale_factor)
    game_y = (screen_y - self.offset_y) / (TILE_SIZE * self.zoom_level * self.ui_scale_factor)
    return game_x, game_y
```

## Test Results

### Monitor Compatibility
- **Full HD (1920x1080)**: Scaled to 1767x930 (scale: 0.93)
- **Laptop HD (1366x768)**: Scaled to 1174x618 (scale: 0.62) ✅ Your laptop
- **Small laptop (1280x720)**: Scaled to 1083x570 (scale: 0.57)
- **QHD (2560x1440)**: Full size 1900x1000
- **4K (3840x2160)**: Full size 1900x1000

### Benefits
- ✅ **Mouse alignment fixed** - coordinates properly converted
- ✅ **Fits any screen size** - automatic scaling
- ✅ **Maintains proportions** - aspect ratios preserved
- ✅ **Performance optimized** - only scales when needed

## ✅ Complete Implementation

### Comprehensive Coordinate Conversion Updates
**ALL 12 mouse interaction locations have been updated:**

#### Core Game Systems Updated:
- ✅ **Model hover detection** (Line 1293) - Unit selection and tooltips
- ✅ **Unit position detection** (Line 1331) - Battlefield unit clicking  
- ✅ **Deployment click handlers** (Line 2647) - Unit deployment positioning
- ✅ **Shooting target selection** (Line 2833) - Combat targeting system
- ✅ **Movement phase handlers** (Line 3578) - Individual model movement
- ✅ **Charge phase handlers** (Line 3726) - Charge movement targeting
- ✅ **Scout phase handlers** (Line 4597) - Pre-battle movement

#### UI Interaction Systems Updated:
- ✅ **Mouse motion tracking** (Lines 3859, 4572) - Movement previews and hover effects
- ✅ **Visual feedback systems** (Line 4637) - Path rendering and indicators
- ✅ **Path rendering** (Line 1396) - Movement path visualization
- ✅ **Boundary detection** - All UI component area checks now use scaled dimensions

#### Implementation Details:
```python
# Before: Manual calculation with hardcoded values
battlefield_x = (x - ROSTER_PANE_WIDTH - self.offset_x) / (TILE_SIZE * self.zoom_level)

# After: Centralized helper method with scaling
battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)

# Boundary checks also updated:
# Before: if ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
# After: if self.game_view.scaled_roster_width < x < self.game_view.scaled_battlefield_width + self.game_view.scaled_roster_width:
```

## Usage
The fix is automatic - no user configuration needed. The game will:
1. Detect your monitor size
2. Scale the window to fit
3. Adjust all mouse coordinates accordingly
4. Print scaling info: `"🖥️ Scaling window to fit monitor: 1900x1000 → 1174x618 (scale: 0.62)"`
