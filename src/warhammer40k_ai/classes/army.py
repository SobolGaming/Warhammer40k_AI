from typing import List, Dict
from .unit import Unit


# Define custom exception for validation errors
class ArmyValidationError(Exception):
    pass


class Army:
    def __init__(self, faction_keyword: str, detachment_type: str, points_limit: int = 2000):
        self.faction_keyword = faction_keyword
        self.detachment_type = detachment_type
        self.points_limit = points_limit
        self.units = []
        self.warlord = None
        self.enhancements = []  # List of Enhancements used in the army
        self.detachment_rules = {}  # Placeholder for detachment-specific rules
    
    def add_unit(self, unit: Unit) -> bool:
        if not self._check_faction_consistency(unit):
            return False
        
        self.units.append(unit)
        return True
    
    def get_total_points(self) -> int:
        return sum(unit.get_unit_cost() for unit in self.units)
    
    def _check_faction_consistency(self, unit: Unit) -> bool:
        return unit.faction_keywords[0].lower() == self.faction_keyword.lower()

    def add_enhancement(self, enhancement, character_unit):
        # Assign an Enhancement to a Character unit
        if not character_unit.is_character or character_unit.is_epic_hero:
            raise ArmyValidationError(f"Enhancements can only be assigned to non-Epic Hero Characters. '{character_unit.name}' is not eligible.")
        if character_unit.enhancement:
            raise ArmyValidationError(f"Character '{character_unit.name}' already has an Enhancement.")
        if not enhancement.eligible_keywords <= character_unit.keywords:
            raise ArmyValidationError(f"Character '{character_unit.name}' does not meet the keyword requirements for Enhancement '{enhancement.name}'.")
        character_unit.enhancement = enhancement
        self.enhancements.append(enhancement)

    def select_warlord(self, unit: Unit):
        if not unit.is_character:
            raise ArmyValidationError(f"Only Character units can be selected as Warlord. '{unit.name}' is not a Character.")
        if self.warlord:
            raise ArmyValidationError(f"Warlord has already been selected: '{self.warlord.name}'.")
        unit.is_warlord = True
        self.warlord = unit

    def validate_points_limit(self):
        total_points = self.get_total_points()
        if total_points > self.points_limit:
            raise ArmyValidationError(f"Army exceeds the points limit of {self.points_limit} points. Total points: {total_points}.")

    def validate_unit_limits(self):
        from collections import Counter

        datasheet_counts = Counter()
        battleline_counts = Counter()
        transport_counts = Counter()

        # Count units based on datasheets and keywords
        for unit in self.units:
            datasheet_counts[unit.name] += 1
            if unit.is_battleline:
                battleline_counts[unit.name] += 1
            if unit.is_dedicated_transport:
                transport_counts[unit.name] += 1

        # Validate datasheet limits
        for name, count in datasheet_counts.items():
            unit = next(u for u in self.units if u.name == name)
            if unit.is_battleline:
                if count > 6:
                    raise ArmyValidationError(f"Battleline unit '{name}' exceeds the limit of 6.")
            elif unit.is_dedicated_transport:
                # Dedicated Transports are validated separately
                continue
            else:
                if count > 3:
                    raise ArmyValidationError(f"Unit '{name}' exceeds the limit of 3.")

        # Validate Dedicated Transport limits
        infantry_units_count = sum(1 for unit in self.units if unit.is_infantry)
        allowed_transports = infantry_units_count
        total_transports = sum(1 for unit in self.units if unit.is_dedicated_transport)

        if total_transports > allowed_transports:
            raise ArmyValidationError(
                f"Too many Dedicated Transports. Allowed: {allowed_transports}, Found: {total_transports}."
            )

    def validate_epic_heroes(self):
        epic_heroes = [unit for unit in self.units if unit.is_epic_hero]
        epic_hero_names = [hero.datasheet for hero in epic_heroes]
        if len(epic_hero_names) != len(set(epic_hero_names)):
            duplicates = [name for name in epic_hero_names if epic_hero_names.count(name) > 1]
            raise ArmyValidationError(f"Epic Hero(s) {duplicates} included more than once.")

    def validate_leaders(self):
        # Map of units to their attached Leaders
        unit_leader_map = {}
        leader_units = [unit for unit in self.units if unit.is_leader]

        for leader in leader_units:
            if not leader.attached_to:
                raise ArmyValidationError(f"Leader '{leader.name}' is not attached to any unit.")
            if leader.attached_to not in self.units:
                raise ArmyValidationError(f"Leader '{leader.name}' is attached to an invalid unit.")
            if leader.attached_to in unit_leader_map:
                raise ArmyValidationError(
                    f"Unit '{leader.attached_to.name}' has more than one Leader attached."
                )
            unit_leader_map[leader.attached_to] = leader

    def validate_enhancements(self):
        # Rule 1: Maximum of 3 Enhancements
        if len(self.enhancements) > 3:
            raise ArmyValidationError(f"Army has more than 3 Enhancements assigned.")

        # Rule 2: Enhancements cannot be duplicated
        enhancement_names = [enhancement.name for enhancement in self.enhancements]
        if len(enhancement_names) != len(set(enhancement_names)):
            duplicates = [name for name in enhancement_names if enhancement_names.count(name) > 1]
            raise ArmyValidationError(f"Enhancements {duplicates} are assigned more than once.")

        # Rule 3: Enhancements can only be assigned to non-Epic Hero Characters
        for unit in self.units:
            if unit.enhancement:
                if unit.is_epic_hero:
                    raise ArmyValidationError(f"Epic Hero '{unit.name}' cannot have Enhancements assigned.")

    def validate_warlord(self):
        # Ensure exactly one Warlord is selected
        warlord_units = [unit for unit in self.units if unit.is_warlord]
        if len(warlord_units) != 1:
            raise ArmyValidationError(f"Army must have exactly one Warlord. Found: {len(warlord_units)}.")

        # If there are any Supreme Commanders, they must be the Warlord
        supreme_commanders = [unit for unit in self.units if unit.is_supreme_commander]
        if supreme_commanders:
            supreme_warlords = [unit for unit in supreme_commanders if unit.is_warlord]
            if not supreme_warlords:
                raise ArmyValidationError(
                    "An army that includes any Supreme Commanders must have one of them as the Warlord."
                )
            if len(supreme_warlords) > 1:
                raise ArmyValidationError(
                    "Only one Supreme Commander can be the Warlord."
                )

    def validate_detachment_rules(self):
        # Placeholder for detachment-specific validation
        pass

    def validate_allies(self):
        # Placeholder for ally validation based on specific rules
        pass

    def validate(self) -> None:
        self.validate_points_limit()
        self.validate_unit_limits()
        self.validate_epic_heroes()
        self.validate_leaders()
        self.validate_enhancements()
        self.validate_warlord()
        self.validate_detachment_rules()
        self.validate_allies()
        print("Army is valid and ready for battle!")

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

    #army.validate()