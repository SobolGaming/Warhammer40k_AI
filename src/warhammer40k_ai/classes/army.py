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
        
        self.units.append(unit)
        return True
    
    def get_total_points(self) -> int:
        return sum(unit.get_unit_cost() for unit in self.units)
    
    def _check_faction_consistency(self, unit: Unit) -> bool:
        return unit.faction_keywords[0].lower() == self.faction_keyword.lower()
    
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

    def validate_army(self) -> List[str]:
        errors = []
        
        if self.get_total_points() > self.points_limit:
            errors.append(f"Army exceeds points limit of {self.points_limit}")
        
        unit_counts = self._get_unit_counts()
        for unit in self.units:
            if unit.is_epic_hero and unit_counts[unit.name] > 1:
                errors.append(f"Only one {unit.name} (Epic Hero) is allowed")
            
            if unit.is_battleline and unit_counts[unit.name] > 6:
                errors.append(f"Maximum of 6 {unit.name} (Battleline) units allowed")
            
            if not unit.is_battleline and not unit.is_dedicated_transport and unit_counts[unit.name] > 3:
                errors.append(f"Maximum of 3 {unit.name} units allowed")
        
        infantry_count = sum(1 for u in self.units if not u.is_dedicated_transport)
        transport_count = sum(unit_counts[u.name] for u in self.units if u.is_dedicated_transport)
        if transport_count > infantry_count:
            errors.append("Too many Dedicated Transports")
        
        return errors

# Example usage:
if __name__ == "__main__":
    army = Army(faction_keyword="Legiones Daemonica", detachment_type="Daemonic Incursion")

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
