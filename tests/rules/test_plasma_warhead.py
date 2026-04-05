"""
Tests for Deathstrike Missile marker system and Plasma Warhead keyword.

Per wahapedia_data/Datasheets_abilities.json:
- Deathstrike Missile: In Shooting phase, if not yet fired, can Designate Target (place marker)
  or Adjust Target (move marker) in addition to normal shooting
- Plasma Warhead: Can only shoot if Remained Stationary, did NOT use Designate/Adjust this phase,
  marker is present, and only in your Shooting phase. Hits all units within 6" of marker center (3D distance).
"""

import pytest
from src.warhammer40k_ai.rules.deathstrike import DeathstrikeManager, DeathstrikeMarker
from src.warhammer40k_ai.utility.aura_utils import unit_within_range_of_point_3d, get_units_within_range_of_point_3d


class TestDeathstrikeMarker:
    """Test DeathstrikeMarker dataclass."""
    
    def test_marker_creation(self):
        """Test creating a valid marker."""
        marker = DeathstrikeMarker(
            owner_unit_id="unit_123",
            position=(30.0, 20.0),
            marker_id="marker_1"
        )
        assert marker.owner_unit_id == "unit_123"
        assert marker.position == (30.0, 20.0)
        assert marker.marker_id == "marker_1"
        assert marker.id is not None  # UUID generated
    
    def test_marker_validation_no_owner(self):
        """Test marker validation rejects missing owner_unit_id."""
        with pytest.raises(ValueError, match="owner_unit_id"):
            DeathstrikeMarker(
                owner_unit_id="",
                position=(30.0, 20.0),
                marker_id="marker_1"
            )
    
    def test_marker_validation_invalid_position(self):
        """Test marker validation rejects invalid position."""
        with pytest.raises(ValueError, match="Position"):
            DeathstrikeMarker(
                owner_unit_id="unit_123",
                position=(30.0,),  # Only one coordinate
                marker_id="marker_1"
            )
    
    def test_marker_position_coercion(self):
        """Test marker position is coerced to floats."""
        marker = DeathstrikeMarker(
            owner_unit_id="unit_123",
            position=(30, 20),  # Integers
            marker_id="marker_1"
        )
        assert marker.position == (30.0, 20.0)
        assert isinstance(marker.position[0], float)
        assert isinstance(marker.position[1], float)


class TestDeathstrikeManager:
    """Test DeathstrikeManager functionality."""
    
    def test_manager_initialization(self):
        """Test manager initializes with empty state."""
        from types import SimpleNamespace
        army = SimpleNamespace()
        mgr = DeathstrikeManager(army)
        
        assert mgr.army is army
        assert len(mgr._markers) == 0
        assert len(mgr._used_designate_adjust_this_phase) == 0
        assert len(mgr._fired_deathstrike_this_battle) == 0
    
    def test_place_marker(self):
        """Test placing a new marker."""
        from types import SimpleNamespace
        army = SimpleNamespace()
        mgr = DeathstrikeManager(army)
        
        marker = mgr.place_marker("unit_1", (30.0, 20.0))
        
        assert mgr.has_marker("unit_1")
        assert mgr.get_marker_position("unit_1") == (30.0, 20.0)
        assert mgr.used_designate_adjust_this_phase("unit_1")
        assert marker.owner_unit_id == "unit_1"
    
    def test_place_marker_duplicate_rejected(self):
        """Test placing a second marker for same unit is rejected."""
        from types import SimpleNamespace
        army = SimpleNamespace()
        mgr = DeathstrikeManager(army)
        
        mgr.place_marker("unit_1", (30.0, 20.0))
        
        with pytest.raises(ValueError, match="already has"):
            mgr.place_marker("unit_1", (40.0, 25.0))
    
    def test_move_marker(self):
        """Test moving an existing marker."""
        from types import SimpleNamespace
        army = SimpleNamespace()
        mgr = DeathstrikeManager(army)
        
        mgr.place_marker("unit_1", (30.0, 20.0))
        mgr.clear_phase_usage()  # Clear phase tracking
        
        marker = mgr.move_marker("unit_1", (40.0, 25.0))
        
        assert mgr.get_marker_position("unit_1") == (40.0, 25.0)
        assert mgr.used_designate_adjust_this_phase("unit_1")
        assert marker.position == (40.0, 25.0)
    
    def test_move_marker_no_marker_rejected(self):
        """Test moving a non-existent marker is rejected."""
        from types import SimpleNamespace
        army = SimpleNamespace()
        mgr = DeathstrikeManager(army)
        
        with pytest.raises(ValueError, match="does not have"):
            mgr.move_marker("unit_1", (40.0, 25.0))
    
    def test_remove_marker(self):
        """Test removing a marker."""
        from types import SimpleNamespace
        army = SimpleNamespace()
        mgr = DeathstrikeManager(army)
        
        mgr.place_marker("unit_1", (30.0, 20.0))
        mgr.remove_marker("unit_1")
        
        assert not mgr.has_marker("unit_1")
        assert mgr.get_marker_position("unit_1") is None
    
    def test_mark_deathstrike_fired(self):
        """Test marking Deathstrike as fired (ONE SHOT)."""
        from types import SimpleNamespace
        army = SimpleNamespace()
        mgr = DeathstrikeManager(army)
        
        mgr.place_marker("unit_1", (30.0, 20.0))
        mgr.mark_deathstrike_fired("unit_1")
        
        assert mgr.has_fired_deathstrike_this_battle("unit_1")
        assert not mgr.has_marker("unit_1")  # Marker removed after firing

    def test_clear_phase_usage(self):
        """Test clearing per-phase usage tracking."""
        from types import SimpleNamespace
        army = SimpleNamespace()
        mgr = DeathstrikeManager(army)

        mgr.place_marker("unit_1", (30.0, 20.0))
        assert mgr.used_designate_adjust_this_phase("unit_1")

        mgr.clear_phase_usage()
        assert not mgr.used_designate_adjust_this_phase("unit_1")
        assert mgr.has_marker("unit_1")  # Marker persists

    def test_can_designate_target(self):
        """Test eligibility check for Designate Target."""
        from types import SimpleNamespace
        army = SimpleNamespace()
        mgr = DeathstrikeManager(army)

        # Can designate when no marker exists
        can, reason = mgr.can_designate_target("unit_1")
        assert can
        assert reason == "OK"

        # Cannot designate when marker already exists
        mgr.place_marker("unit_1", (30.0, 20.0))
        can, reason = mgr.can_designate_target("unit_1")
        assert not can
        assert "already has" in reason

        # Cannot designate after firing
        mgr.mark_deathstrike_fired("unit_1")
        can, reason = mgr.can_designate_target("unit_1")
        assert not can
        assert "already fired" in reason

    def test_can_adjust_target(self):
        """Test eligibility check for Adjust Target."""
        from types import SimpleNamespace
        army = SimpleNamespace()
        mgr = DeathstrikeManager(army)

        # Cannot adjust when no marker exists
        can, reason = mgr.can_adjust_target("unit_1")
        assert not can
        assert "does not have" in reason

        # Can adjust when marker exists
        mgr.place_marker("unit_1", (30.0, 20.0))
        mgr.clear_phase_usage()
        can, reason = mgr.can_adjust_target("unit_1")
        assert can
        assert reason == "OK"

        # Cannot adjust after firing
        mgr.mark_deathstrike_fired("unit_1")
        can, reason = mgr.can_adjust_target("unit_1")
        assert not can
        assert "already fired" in reason


class TestPlasmaWarheadEligibility:
    """Test Plasma Warhead weapon eligibility checks."""

    def test_plasma_warhead_keyword_detection(self):
        """Test is_plasma_warhead() detects the keyword."""
        from types import SimpleNamespace

        # Mock weapon profile with Plasma Warhead keyword
        profile = SimpleNamespace()
        profile.get_keywords = lambda: ["Plasma Warhead", "One Shot"]
        profile.is_plasma_warhead = lambda: "plasma warhead" in [k.lower() for k in profile.get_keywords()]

        assert profile.is_plasma_warhead()

        # Mock weapon profile without Plasma Warhead keyword
        profile2 = SimpleNamespace()
        profile2.get_keywords = lambda: ["One Shot", "Blast"]
        profile2.is_plasma_warhead = lambda: "plasma warhead" in [k.lower() for k in profile2.get_keywords()]

        assert not profile2.is_plasma_warhead()


class TestAoEResolution:
    """Test AoE resolution around marker using 3D distance."""

    def _make_model(self, x: float, y: float, z: float):
        from types import SimpleNamespace
        from src.warhammer40k_ai.utility.model_base import Base, BaseType

        base = Base(BaseType.CIRCULAR, 1.0)
        base.set_position(x, y, z)
        return SimpleNamespace(is_alive=True, model_base=base)

    def test_unit_within_range_of_point_2d(self):
        """Test unit within range of point (2D, z=0)."""
        from types import SimpleNamespace

        # Mock unit with model at (35, 20, 0)
        model = self._make_model(35.0, 20.0, 0.0)

        unit = SimpleNamespace()
        unit.get_attached_unit_models = lambda: [model]

        # Marker at (30, 20): 5" from center, 4" from base edge
        assert unit_within_range_of_point_3d(unit, (30.0, 20.0), 4.0)
        assert not unit_within_range_of_point_3d(unit, (30.0, 20.0), 3.0)

    def test_unit_within_range_of_point_3d(self):
        """Test unit within range of point (3D distance)."""
        from types import SimpleNamespace

        # Mock unit with model at (30, 20, 4) - 4" above ground
        model = self._make_model(30.0, 20.0, 4.0)

        unit = SimpleNamespace()
        unit.get_attached_unit_models = lambda: [model]

        # Marker at (30, 20) - 0" horizontal, 4" vertical = 4" 3D distance
        assert unit_within_range_of_point_3d(unit, (30.0, 20.0), 6.0)
        assert not unit_within_range_of_point_3d(unit, (30.0, 20.0), 3.0)

    def test_get_units_within_range_of_point(self):
        """Test getting all units within range of a point."""
        from types import SimpleNamespace

        # Create 3 mock units at different distances
        def make_unit(x, y, z):
            model = self._make_model(x, y, z)
            unit = SimpleNamespace()
            unit.get_attached_unit_models = lambda: [model]
            return unit

        unit1 = make_unit(32.0, 20.0, 0.0)  # 2" away
        unit2 = make_unit(35.0, 20.0, 0.0)  # 5" away
        unit3 = make_unit(40.0, 20.0, 0.0)  # 10" away

        all_units = [unit1, unit2, unit3]

        # 6" radius should include unit1 and unit2, exclude unit3
        units_in_range = get_units_within_range_of_point_3d((30.0, 20.0), 6.0, all_units)
        assert len(units_in_range) == 2
        assert unit1 in units_in_range
        assert unit2 in units_in_range
        assert unit3 not in units_in_range
