from typing import List, Dict
from dataclasses import dataclass, field
from .unit import Unit


@dataclass
class Army:
    faction_keyword: str
    detachment_type: str
    points_limit: int = 2000
    units: List[Unit] = field(default_factory=list)
    
    def add_unit(self, unit: Unit) -> bool:
        if not self._check_faction_consistency(unit):
            return False
        
        if not self._check_unit_limits(unit):
            return False
        
        if self.get_total_points() + unit.get_unit_cost() > self.points_limit:
            return False
        
        self.units.append(unit)
        return True
    
    def get_total_points(self) -> int:
        return sum(unit.get_unit_cost() for unit in self.units)
    
    def _check_faction_consistency(self, unit: Unit) -> bool:
        # Simplified check - in a real implementation, you'd check if the unit's
        # keywords include the army's faction_keyword
        return True
    
    def _check_unit_limits(self, unit: Unit) -> bool:
        unit_counts = self._get_unit_counts()
        
        if unit.is_epic_hero and unit.name in unit_counts:
            return False
        
        if unit.is_battleline and unit_counts.get(unit.name, 0) >= 6:
            return False
        
        if not unit.is_battleline and not unit.is_dedicated_transport and unit_counts.get(unit.name, 0) >= 3:
            return False
        
        if unit.is_dedicated_transport:
            infantry_count = sum(1 for u in self.units if not u.is_dedicated_transport)
            transport_count = unit_counts.get(unit.name, 0)
            if transport_count >= infantry_count:
                return False
        
        return True
    
    def _get_unit_counts(self) -> Dict[str, int]:
        counts = {}
        for unit in self.units:
            counts[unit.name] = counts.get(unit.name, 0) + 1
        return counts

# Example usage:
if __name__ == "__main__":
    army = Army(faction_keyword="CHAOS", detachment_type="Daemonic Incursion")

    from src.warhammer40k_ai.waha_helper import WahaHelper
    waha_helper = WahaHelper()
    datasheet = waha_helper.get_full_datasheet_info_by_name("Bloodcrushers")
    bloodcrushers_unit = Unit(datasheet)
    
    # Add the Bloodcrushers to the army
    army.add_unit(bloodcrushers_unit)
    
    print(f"Total points: {army.get_total_points()}")
    print(f"Number of units: {len(army.units)}")
    for unit in army.units:
        unit.print_unit()
        print(f"{len(unit.models)} models")
