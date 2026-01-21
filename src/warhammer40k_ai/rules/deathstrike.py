"""
Deathstrike Missile marker system for Plasma Warhead weapons.

Per wahapedia_data/Datasheets_abilities.json:
- Deathstrike Missile: In Shooting phase, if not yet fired, can Designate Target (place marker)
  or Adjust Target (move marker) in addition to normal shooting
- Plasma Warhead: Can only shoot if Remained Stationary, did NOT use Designate/Adjust this phase,
  marker is present, and only in your Shooting phase. Hits all units within 6" of marker center.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Tuple, Dict, List
from dataclasses import dataclass, field
import uuid

if TYPE_CHECKING:
    from ..units.unit import Unit
    from ..roster.army import Army


@dataclass
class DeathstrikeMarker:
    """
    Represents a Deathstrike Target marker on the battlefield.

    Attributes:
        owner_unit_id: ID of the unit that owns this marker
        position: (x, y) coordinates in game inches
        marker_id: Unique identifier for this marker
    """
    owner_unit_id: str
    position: Tuple[float, float]
    marker_id: str
    _id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        """Validate marker data."""
        if not self.owner_unit_id:
            raise ValueError("Marker must have an owner_unit_id")
        if not self.marker_id:
            raise ValueError("Marker must have a marker_id")
        if not isinstance(self.position, tuple) or len(self.position) != 2:
            raise ValueError("Position must be a tuple of (x, y)")
        try:
            self.position = (float(self.position[0]), float(self.position[1]))
        except (TypeError, ValueError) as e:
            raise ValueError(f"Position coordinates must be numeric: {e}")

    @property
    def id(self) -> str:
        """Return the unique ID for this marker (for entity registry)."""
        return self._id


class DeathstrikeManager:
    """
    Manages Deathstrike Target markers for an army.
    
    Tracks:
    - Active markers on the battlefield
    - Per-phase usage of Designate/Adjust actions
    - Per-battle firing status of Deathstrike missiles
    """
    
    def __init__(self, army: 'Army'):
        self.army = army
        # Map of unit_id -> DeathstrikeMarker
        self._markers: Dict[str, DeathstrikeMarker] = {}
        # Track which units used Designate/Adjust this phase
        self._used_designate_adjust_this_phase: set[str] = set()
        # Track which units have fired their Deathstrike missile this battle
        self._fired_deathstrike_this_battle: set[str] = set()
    
    def has_marker(self, unit_id: str) -> bool:
        """Check if a unit has a marker on the battlefield."""
        return unit_id in self._markers
    
    def get_marker(self, unit_id: str) -> Optional[DeathstrikeMarker]:
        """Get the marker for a unit, or None if no marker exists."""
        return self._markers.get(unit_id)
    
    def get_marker_position(self, unit_id: str) -> Optional[Tuple[float, float]]:
        """Get the position of a unit's marker, or None if no marker exists."""
        marker = self.get_marker(unit_id)
        return marker.position if marker else None
    
    def place_marker(self, unit_id: str, position: Tuple[float, float]) -> DeathstrikeMarker:
        """
        Place a new Deathstrike marker for a unit.
        
        Args:
            unit_id: ID of the owning unit
            position: (x, y) coordinates in game inches
            
        Returns:
            The created marker
            
        Raises:
            ValueError: If unit already has a marker
        """
        if self.has_marker(unit_id):
            raise ValueError(f"Unit {unit_id} already has a Deathstrike marker")
        
        marker_id = f"deathstrike_marker_{unit_id}"
        marker = DeathstrikeMarker(
            owner_unit_id=unit_id,
            position=position,
            marker_id=marker_id
        )
        self._markers[unit_id] = marker
        self._used_designate_adjust_this_phase.add(unit_id)
        return marker
    
    def move_marker(self, unit_id: str, new_position: Tuple[float, float]) -> DeathstrikeMarker:
        """
        Move an existing Deathstrike marker to a new position.
        
        Args:
            unit_id: ID of the owning unit
            new_position: New (x, y) coordinates in game inches
            
        Returns:
            The updated marker
            
        Raises:
            ValueError: If unit doesn't have a marker
        """
        if not self.has_marker(unit_id):
            raise ValueError(f"Unit {unit_id} does not have a Deathstrike marker to move")
        
        marker = self._markers[unit_id]
        marker.position = (float(new_position[0]), float(new_position[1]))
        self._used_designate_adjust_this_phase.add(unit_id)
        return marker
    
    def remove_marker(self, unit_id: str) -> None:
        """Remove a unit's marker from the battlefield."""
        self._markers.pop(unit_id, None)
    
    def used_designate_adjust_this_phase(self, unit_id: str) -> bool:
        """Check if a unit used Designate or Adjust this phase."""
        return unit_id in self._used_designate_adjust_this_phase
    
    def has_fired_deathstrike_this_battle(self, unit_id: str) -> bool:
        """Check if a unit has fired its Deathstrike missile this battle."""
        return unit_id in self._fired_deathstrike_this_battle
    
    def mark_deathstrike_fired(self, unit_id: str) -> None:
        """Mark that a unit has fired its Deathstrike missile (ONE SHOT)."""
        self._fired_deathstrike_this_battle.add(unit_id)
        # Remove marker after firing
        self.remove_marker(unit_id)

    def clear_phase_usage(self) -> None:
        """Clear per-phase Designate/Adjust usage tracking. Call at end of Shooting phase."""
        self._used_designate_adjust_this_phase.clear()

    def get_all_markers(self) -> List[DeathstrikeMarker]:
        """Get all active markers on the battlefield."""
        return list(self._markers.values())

    def can_use_deathstrike_ability(self, unit_id: str) -> Tuple[bool, str]:
        """
        Check if a unit can use the Deathstrike Missile ability (Designate/Adjust).

        Returns:
            (can_use, reason) tuple
        """
        if self.has_fired_deathstrike_this_battle(unit_id):
            return False, "Deathstrike missile already fired this battle (ONE SHOT)"
        return True, "OK"

    def can_designate_target(self, unit_id: str) -> Tuple[bool, str]:
        """
        Check if a unit can Designate Target (place new marker).

        Returns:
            (can_designate, reason) tuple
        """
        can_use, reason = self.can_use_deathstrike_ability(unit_id)
        if not can_use:
            return False, reason

        if self.has_marker(unit_id):
            return False, "Unit already has a Deathstrike marker (use Adjust Target instead)"

        return True, "OK"

    def can_adjust_target(self, unit_id: str) -> Tuple[bool, str]:
        """
        Check if a unit can Adjust Target (move existing marker).

        Returns:
            (can_adjust, reason) tuple
        """
        can_use, reason = self.can_use_deathstrike_ability(unit_id)
        if not can_use:
            return False, reason

        if not self.has_marker(unit_id):
            return False, "Unit does not have a Deathstrike marker (use Designate Target instead)"

        return True, "OK"

