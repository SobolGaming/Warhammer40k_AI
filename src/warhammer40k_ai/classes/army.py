from typing import Tuple, Dict, Set
from src.warhammer40k_ai.classes.unit import Unit
from src.warhammer40k_ai.classes.wargear import Wargear
from src.warhammer40k_ai.classes.enhancement import Enhancement
from src.warhammer40k_ai.waha_helper import WahaHelper
import codecs


# Define custom exception for validation errors
class ArmyValidationError(Exception):
    pass


class Army:
    def __init__(self, faction: str, detachment_type: str, points_limit: int = 2000):
        self.faction = faction
        self.faction_keyword = []
        self.detachment_type = detachment_type
        self.points_limit = points_limit
        self.units = []
        self.warlord = None
        self.enhancements = []  # List of Enhancements used in the army
        self.detachment_rules = {}  # Placeholder for detachment-specific rules
    
    def add_unit(self, unit: Unit) -> bool:
        if not self.faction_keyword:
            self.faction_keyword = unit.faction_keywords
        elif unit.faction_keywords != self.faction_keyword:
            raise ArmyValidationError(f"Unit {unit.name} does not match army faction {self.faction}.")
        
        self.units.append(unit)
        return True
    
    def get_total_points(self) -> int:
        return sum(unit.get_unit_cost() for unit in self.units)

    def add_enhancement(self, enhancement, character_unit):
        # Assign an Enhancement to a Character unit
        if not character_unit.is_character or character_unit.is_epic_hero:
            raise ArmyValidationError(f"Enhancements can only be assigned to non-Epic Hero Characters. '{character_unit.name}' is not eligible.")
        if character_unit.enhancement:
            raise ArmyValidationError(f"Character '{character_unit.name}' already has an Enhancement.")
        if not set(enhancement.eligible_keywords).issubset(set(character_unit.keywords)):
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
        epic_hero_names = [hero.name for hero in epic_heroes]
        if len(epic_hero_names) != len(set(epic_hero_names)):
            duplicates = [name for name in epic_hero_names if epic_hero_names.count(name) > 1]
            raise ArmyValidationError(f"Epic Hero(s) {duplicates} included more than once.")

    def validate_leaders(self):
        # Map of units to their attached Leaders
        unit_leader_map = {}
        leader_units = [unit for unit in self.units if unit.is_leader]

        for leader in leader_units:
            #if not leader.attached_to:
            #    raise ArmyValidationError(f"Leader '{leader.name}' is not attached to any unit.")
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

# Helper function to parse an army list from a text file
def parse_army_list(file_path: str, waha_helper: WahaHelper) -> Army:
    with codecs.open(file_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        
        # Remove BOM if present
        if lines and lines[0].startswith('\ufeff'):
            lines[0] = lines[0][1:]

    # Determine the format
    is_app_format = any("Exported with App Version:" in line for line in lines)

    # Extract army information
    if is_app_format:
        points_limit = int(lines[0].split('(')[1].split()[0])
        faction_keyword = lines[2].strip()
        detachment_type = lines[3].strip()
        start_index = 5
    else:
        points_limit = int(lines[1].split('(')[1].split()[0])
        faction_keyword = lines[0].split(' – ')[-1]
        detachment_type = lines[2].strip()
        start_index = 4

    print(f"Parsing army: {faction_keyword} - {detachment_type} ({points_limit} points)")

    # Create the Army object
    army = Army(faction=faction_keyword, detachment_type=detachment_type, points_limit=points_limit)

    current_unit = None
    current_model_count = 0
    current_model_name = None
    current_wargear = {}
    current_enhancement = None
    is_warlord = False

    for line in lines[start_index:]:
        line = line.strip()
        if not line:
            continue

        if line.upper() in ['CHARACTER', 'CHARACTERS', 'BATTLELINE', 'OTHER DATASHEETS']:
            continue

        if line.startswith('Exported with'):
            break

        if not line.startswith('•') and not line.startswith('◦'):
            if current_unit:
                add_unit_to_army(army, current_unit, current_model_count, current_wargear, current_enhancement, waha_helper, is_warlord)
                current_unit = None
                current_model_name = None
                current_model_count = 0
                current_wargear = {}
                current_enhancement = None
                is_warlord = False

            unit_info = line.split(' (')
            unit_name = unit_info[0].strip()
            
            datasheet = waha_helper.get_full_datasheet_info_by_name(unit_name)
            if datasheet:
                current_unit = Unit(datasheet)
            else:
                print(f"Warning: Datasheet not found for {unit_name}")

        elif line.startswith('•') or line.startswith('◦'):
            data = line[1:].strip()
            if data.lower() == 'warlord':
                is_warlord = True
            elif data.lower().startswith('enhancement'):
                enhancement_name = data.split(':', 1)[1].strip()
                current_enhancement = waha_helper.get_enhancement_by_name(enhancement_name)
                if not current_enhancement:
                    print(f"Warning: Enhancement not found for {enhancement_name}")
            elif data.startswith('Daemonic Allegiance:'):
                allegiance = data.split(':', 1)[1].strip()
                current_unit.daemonic_allegiance = allegiance
            else:
                # This could be either a model count or wargear
                if 'x ' in data:
                    quantity, item_name = data.split('x ', 1)
                    quantity = int(quantity)
                else:
                    quantity = 1
                    item_name = data

                # Check if it's a model count or wargear
                if current_unit and any(item_name.strip() in model_name.rstrip('s') for model_name in current_unit.unit_composition.keys()):
                    current_model_count += quantity
                    current_model_name = item_name.strip()
                    current_wargear[current_model_name] = set()
                else:
                    if current_model_name:
                        current_wargear.setdefault(current_model_name, set()).add((item_name.strip(), quantity))
                    else:
                        current_wargear.setdefault(current_unit.name, set()).add((item_name.strip(), quantity))

    # Don't forget to add the last unit if there is one
    if current_unit:
        add_unit_to_army(army, current_unit, current_model_count, current_wargear, current_enhancement, waha_helper, is_warlord)

    print(f"Finished parsing. Total units: {len(army.units)}")
    return army

def add_unit_to_army(army: Army, unit: Unit, model_count: int, wargear_dict: Dict[str, Set[Tuple[str, int]]], enhancement: Enhancement, waha_helper: WahaHelper, is_warlord: bool):
    # Configure the unit with the correct number of models
    unit.configure_models(model_count, [])

    # Add wargear to the unit
    for model_name, wargear_list in wargear_dict.items():
        for wargear_name, _ in wargear_list:
            gear_name = wargear_name.lower().replace("’", "'")
            matching_gear = next((gear for gear in unit.possible_wargear if gear.name.lower() == gear_name), None)
            if matching_gear:
                unit.add_wargear([matching_gear if gear.name.lower() == gear_name else None for gear in unit.possible_wargear], model_name)
            else:
                matching_gear = next((gear for gear in unit.wargear_options.values() if gear.wargear_name == gear_name), None)
                if matching_gear:
                    unit.apply_wargear_options(gear_name)
                else:
                    matching_ability = next((ability for ability in unit.possible_abilities if ability.name.lower() == gear_name and ability.type == 'Wargear'), None)
                    if matching_ability:
                        unit.add_ability(matching_ability, model_name)
                    else:
                        print(f"Warning: {gear_name} not found in {unit.name}'s possible wargear or abilities.")
                        for gear in unit.possible_wargear:
                            print(f"  - {gear.name}")
                        for ability in unit.possible_abilities:
                            print(f"  - {ability.name} (Ability Wargear)")

    # Add enhancement to the unit if it exists
    if enhancement:
        try:
            army.add_enhancement(enhancement, unit)
        except Exception as e:
            print(f"Warning: Could not add enhancement {enhancement.name} to {unit.name}: {str(e)}")

    # Add the unit to the army
    army.add_unit(unit)

    # Set warlord if applicable
    if is_warlord:
        army.select_warlord(unit)


# Example usage:
if __name__ == "__main__":
    waha_helper = WahaHelper()
    army = parse_army_list("army_lists/warhammer_app_dump.txt", waha_helper)
    print(f"Parsed army: {army.faction_keyword} - {army.detachment_type}")
    print(f"Total points: {army.get_total_points()} out of {army.points_limit}")
    print(f"Number of units: {len(army.units)}")
    for unit in army.units:
        print(f"- {unit.name} ({unit.get_unit_cost()} points)")
        for model in unit.models:
            print(f"  - {model.name} {'(Warlord)' if unit.is_warlord else ''}")
            for wargear in model.wargear:
                if wargear:
                    print(f"    - {wargear.name}")
            if hasattr(model, 'optional_wargear'):
                for wargear_option in model.optional_wargear:
                    print(f"    - {wargear_option}")
            for ability in model.abilities.keys():
                if ability:
                    print(f"    - {ability} (Ability Wargear)")
            if unit.enhancement:
                print(f"    - Enhancement: {unit.enhancement.name}")
    army.validate()