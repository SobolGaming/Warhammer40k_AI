from typing import Tuple, Dict, Set, List, Optional
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.classes.enhancement import Enhancement
from warhammer40k_ai.waha_helper import WahaHelper
import codecs
import uuid


# Define custom exception for validation errors
class ArmyValidationError(Exception):
    pass


def get_faction_id_from_name(faction_name: str) -> Optional[str]:
    """
    Map faction names from army list files to faction IDs used in datasheets.
    This mapping helps ensure the correct faction-specific datasheet is loaded.
    """
    import json
    import os
    
    # Normalize faction name for comparison
    faction_name_lower = faction_name.lower().strip()
    
    # Load factions from the JSON file
    factions_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'wahapedia_data', 'Factions.json')
    try:
        with open(factions_file, 'r', encoding='utf-8') as f:
            factions = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load Factions.json: {e}")
        return None
    
    # Try exact match first
    for faction in factions:
        if faction['name'].lower() == faction_name_lower:
            return faction['id']
    
    # Try partial matches for more flexible matching
    for faction in factions:
        faction_name_json = faction['name'].lower()
        if faction_name_json in faction_name_lower or faction_name_lower in faction_name_json:
            return faction['id']
    
    # If no match found, return None (will use generic lookup)
    return None


class Army:
    def __init__(self, faction: str, detachment_type: str, points_limit: int = 2000):
        self._id = str(uuid.uuid4())
        self.faction = faction
        # faction_id from Factions.json if known; set by parse_army_list
        self.faction_id: Optional[str] = None
        self.faction_keyword = []
        self.detachment_type = detachment_type
        self.points_limit = points_limit
        self.units = []
        self.warlord = None
        self.enhancements = []  # List of Enhancements used in the army
        self.detachment_rules = {}  # Placeholder for detachment-specific rules
        self.player = None  # Reference to the owning player
    
    def add_unit(self, unit: Unit) -> bool:
        if not self.faction_keyword:
            self.faction_keyword = unit.faction_keywords
        # TODO - fix once support for things like World Eaters Daemonkin Detachment is added
        #elif unit.faction_keywords != self.faction_keyword:
        #    raise ArmyValidationError(f"Unit {unit.name} does not match army faction {self.faction}.")
        unit.set_parent_army(self)
        self.units.append(unit)
        return True

    # ---------- Command phase CP gain hooks ----------
    def get_command_phase_bonus_cp_gain(self) -> int:
        """
        Return bonus CP gained during the owning player's own Command phase due to abilities.

        This represents CP gained in addition to the normal Command phase CP and should be subject
        to the per-battle-round guardrail.

        Implementation note: this is intentionally conservative and data-driven via `unit.special_rules`
        so armies/characters can set it without hard-coding faction logic here.
        """
        bonus = 0
        for u in list(getattr(self, "units", []) or []):
            try:
                if not getattr(u, "deployed", False):
                    continue
                if not u.is_alive():
                    continue
                if getattr(u, "reserve_status", "deployed") != "deployed":
                    continue
                sr = getattr(u, "special_rules", {}) or {}
                # Accept either key spelling; keep it simple.
                b = int(sr.get("command_phase_bonus_cp", sr.get("command_phase_cp_bonus", 0)) or 0)
                if b > 0:
                    bonus += b
            except Exception:
                continue
        return int(bonus)
    
    def get_total_points(self) -> int:
        return sum(unit.get_unit_cost() for unit in self.units)

    def get_reserve_limits(self) -> dict:
        """
        Calculate the reserve limits for this army according to Warhammer 40k 10th Edition rules.
        
        Returns:
            dict: Contains 'max_units' and 'max_points' limits for reserves
        """
        total_units = len(self.units)
        total_points = self.get_total_points()
        
        # 50% limits (rounded down)
        max_reserve_units = total_units // 2
        max_reserve_points = total_points // 2
        
        return {
            'max_units': max_reserve_units,
            'max_points': max_reserve_points,
            'total_units': total_units,
            'total_points': total_points
        }

    def can_add_unit_to_reserves(self, unit: Unit, current_reserve_units: int, current_reserve_points: int) -> bool:
        """
        Check if a unit can be added to reserves without exceeding limits.
        
        Args:
            unit: The unit to check
            current_reserve_units: Current number of units in reserves
            current_reserve_points: Current points in reserves
            
        Returns:
            bool: True if the unit can be added to reserves
        """
        limits = self.get_reserve_limits()
        unit_points = unit.get_unit_cost()
        
        # Check both unit count and points limits
        can_add_units = current_reserve_units < limits['max_units']
        can_add_points = current_reserve_points + unit_points <= limits['max_points']
        
        return can_add_units and can_add_points

    def validate_reserves_decisions(self, reserves_decisions: dict) -> dict:
        """
        Validate reserves decisions against the 50% limits.
        
        Args:
            reserves_decisions: Dict mapping unit names to reserve status ('deploy', 'reserves', 'strategic_reserves')
            
        Returns:
            dict: Validation result with 'valid' boolean and 'errors' list
        """
        limits = self.get_reserve_limits()
        reserve_units = 0
        reserve_points = 0
        errors = []
        
        for unit in self.units:
            decision = reserves_decisions.get(unit.name, 'deploy')
            if decision in ['reserves', 'strategic_reserves']:
                reserve_units += 1
                reserve_points += unit.get_unit_cost()
        
        # Check unit limit
        if reserve_units > limits['max_units']:
            errors.append(f"Too many units in reserves: {reserve_units}/{limits['max_units']} allowed")
        
        # Check points limit
        if reserve_points > limits['max_points']:
            errors.append(f"Too many points in reserves: {reserve_points}/{limits['max_points']} allowed")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'reserve_units': reserve_units,
            'reserve_points': reserve_points,
            'limits': limits
        }

    def enforce_reserves_limits(self, reserves_decisions: dict) -> dict:
        """
        Enforce reserve limits by modifying decisions if necessary.
        This ensures the final reserves decisions comply with the 50% limits.
        
        Args:
            reserves_decisions: Dict mapping unit names to reserve status
            
        Returns:
            dict: Modified reserves decisions that comply with limits
        """
        limits = self.get_reserve_limits()
        current_reserve_units = 0
        current_reserve_points = 0
        modified_decisions = reserves_decisions.copy()
        
        # First pass: count current reserves
        for unit in self.units:
            decision = modified_decisions.get(unit.name, 'deploy')
            if decision in ['reserves', 'strategic_reserves']:
                current_reserve_units += 1
                current_reserve_points += unit.get_unit_cost()
        
        # Second pass: enforce limits by converting excess reserves to deploy
        for unit in self.units:
            decision = modified_decisions.get(unit.name, 'deploy')
            if decision in ['reserves', 'strategic_reserves']:
                unit_points = unit.get_unit_cost()
                
                # Check if this unit would exceed limits
                would_exceed_units = current_reserve_units > limits['max_units']
                would_exceed_points = current_reserve_points > limits['max_points']
                
                if would_exceed_units or would_exceed_points:
                    # Convert to deploy
                    modified_decisions[unit.name] = 'deploy'
                    current_reserve_units -= 1
                    current_reserve_points -= unit_points
        
        return modified_decisions

    def get_current_reserves_status(self, reserves_decisions: dict) -> dict:
        """
        Get current reserves status and limits information.
        
        Args:
            reserves_decisions: Dict mapping unit names to reserve status
            
        Returns:
            dict: Current reserves status and limits
        """
        limits = self.get_reserve_limits()
        reserve_units = 0
        reserve_points = 0
        reserve_unit_names = []
        strategic_reserve_unit_names = []
        
        for unit in self.units:
            decision = reserves_decisions.get(unit.name, 'deploy')
            if decision == 'reserves':
                reserve_units += 1
                reserve_points += unit.get_unit_cost()
                reserve_unit_names.append(unit.name)
            elif decision == 'strategic_reserves':
                reserve_units += 1
                reserve_points += unit.get_unit_cost()
                strategic_reserve_unit_names.append(unit.name)
        
        return {
            'reserve_units': reserve_units,
            'reserve_points': reserve_points,
            'limits': limits,
            'reserve_unit_names': reserve_unit_names,
            'strategic_reserve_unit_names': strategic_reserve_unit_names,
            'can_add_more_units': reserve_units < limits['max_units'],
            'can_add_more_points': reserve_points < limits['max_points']
        }

    def add_enhancement(self, enhancement, character_unit):
        # Assign an Enhancement to a Character unit
        if not character_unit.is_character or character_unit.is_epic_hero:
            raise ArmyValidationError(f"Enhancements can only be assigned to non-Epic Hero Characters. '{character_unit.name}' is not eligible.")
        if character_unit.enhancement:
            raise ArmyValidationError(f"Character '{character_unit.name}' already has an Enhancement.")
        # Enhancements are detachment-specific in 10e; enforce faction and detachment match when available.
        try:
            if getattr(self, "faction_id", None) and getattr(enhancement, "faction_id", ""):
                if self.faction_id != enhancement.faction_id:
                    raise ArmyValidationError(
                        f"Enhancement '{enhancement.name}' belongs to faction {enhancement.faction_id}, "
                        f"but army faction is {self.faction_id}."
                    )
        except Exception:
            pass
        try:
            if getattr(self, "detachment_type", None) and getattr(enhancement, "detachment", ""):
                if self.detachment_type != enhancement.detachment:
                    raise ArmyValidationError(
                        f"Enhancement '{enhancement.name}' is for detachment '{enhancement.detachment}', "
                        f"but army detachment is '{self.detachment_type}'."
                    )
        except Exception:
            pass
        # We intentionally do NOT strictly enforce model eligibility text from Wahapedia, because it is
        # unstructured and would cause false rejections without a robust parser.
        character_unit.enhancement = enhancement
        try:
            if hasattr(enhancement, "apply_to_unit"):
                enhancement.apply_to_unit(character_unit)
        except Exception:
            pass
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
        unit_leader_map: dict = {}
        leader_units = [unit for unit in self.units if getattr(unit, "is_leader", False)]

        for leader in leader_units:
            attached_to = getattr(leader, "attached_to", None)
            # Leaders may be left unattached in 10e (optional), so only validate if set.
            if attached_to is None:
                continue
            if attached_to not in self.units:
                raise ArmyValidationError(f"Leader '{leader.name}' is attached to an invalid unit.")
            try:
                if hasattr(leader, "can_attach_to") and not leader.can_attach_to(attached_to):
                    raise ArmyValidationError(f"Leader '{leader.name}' cannot be attached to '{attached_to.name}'.")
            except ArmyValidationError:
                raise
            except Exception:
                # If validation can't be performed, fail fast with a clear error.
                raise ArmyValidationError(f"Failed validating leader attachment for '{leader.name}'.")

            unit_leader_map.setdefault(attached_to, []).append(leader)

        # Enforce per-bodyguard leader limits
        for bodyguard, leaders in unit_leader_map.items():
            try:
                max_leaders = bodyguard.max_attached_leaders()
            except Exception:
                max_leaders = 1
            if len(leaders) > max_leaders:
                raise ArmyValidationError(
                    f"Unit '{bodyguard.name}' has {len(leaders)} Leaders attached (max {max_leaders})."
                )

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

    def get_active_units(self) -> List[Unit]:
        return [unit for unit in self.units if unit.deployed and unit.is_alive()]

    def __str__(self):
        return f"Army: {self.faction} - {self.detachment_type}\n{self.units}"

    def __eq__(self, other):
        return self._id == other._id

    def __hash__(self):
        return hash(self._id)

    def set_player(self, player) -> None:
        """Set the player that owns this army."""
        self.player = player

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
    
    # Map faction names to faction IDs for datasheet lookup
    faction_id = get_faction_id_from_name(faction_keyword)
    if faction_id:
        print(f"Using faction ID: {faction_id} for datasheet lookups")
        army.faction_id = faction_id
    else:
        print(f"Warning: Could not determine faction ID for '{faction_keyword}', using generic lookup")

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
            
            # Use faction-specific datasheet lookup if faction_id is available
            if faction_id:
                datasheet = waha_helper.get_full_datasheet_info_by_name(unit_name, faction_id=faction_id)
                if not datasheet:
                    # Fallback to generic lookup if faction-specific lookup fails
                    print(f"Warning: Faction-specific datasheet not found for {unit_name} (faction: {faction_id}), trying generic lookup")
                    datasheet = waha_helper.get_full_datasheet_info_by_name(unit_name)
            else:
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
        for wargear_name, quantity in wargear_list:
            gear_name = wargear_name.lower().replace("’","'")
            matching_gear = next((gear for gear in unit.possible_wargear if gear.name.lower().replace("’","'") == gear_name), None)
            if matching_gear:
                # Add the wargear multiple times based on quantity
                # Distribute wargear among models instead of adding multiple to each
                target_models = []
                if model_name and model_name != unit.name:
                    target_models = [model for model in unit.models if model.name.lower() == model_name.lower()]
                else:
                    target_models = unit.models

                if target_models:
                    if quantity == len(target_models):
                        # 1 item per model
                        for model in target_models:
                            model.wargear.append(matching_gear)
                    elif quantity < len(target_models):
                        # Fewer items than models - give to first N models
                        for i in range(quantity):
                            target_models[i].wargear.append(matching_gear)
                    else:
                        # More items than models - distribute evenly
                        items_per_model = quantity // len(target_models)
                        remainder = quantity % len(target_models)
                        for i, model in enumerate(target_models):
                            for _ in range(items_per_model):
                                model.wargear.append(matching_gear)
                            if i < remainder:
                                model.wargear.append(matching_gear)
                else:
                    # Fallback to old behavior if no target models found
                    for _ in range(quantity):
                        unit.add_wargear([matching_gear if gear.name.lower().replace("’","'") == gear_name else None for gear in unit.possible_wargear], model_name)
            else:
                matching_gear = next((gear for gear in unit.wargear_options if gear_name in gear.wargear_to), None)
                if matching_gear:
                    # Army lists must be deterministic: if an option can't be resolved uniquely, that's an error.
                    unit.apply_wargear_options_strict(gear_name)
                else:
                    matching_ability = next((ability for ability in unit.possible_abilities if ability.name.lower().replace("’","'") == gear_name and ability.type == 'Wargear'), None)
                    if matching_ability:
                        unit.add_ability(matching_ability, model_name)
                    else:
                        print(f"Warning: {gear_name} not found in {unit.name}'s possible wargear or abilities.")
                        for gear in unit.possible_wargear:
                            print(f"  - {gear.name}")
                        for ability in unit.possible_abilities:
                            print(f"  - {ability.name} (Ability Wargear)")

    # Validate final wargear loadout for models in this unit (critical for army-list parsing correctness)
    unit.validate_wargear_selection()

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
                    print(f"    - {model.get_optional_wargear_by_name(wargear_option).name}")
            for ability in model.abilities.keys():
                if ability:
                    print(f"    - {ability} (Ability Wargear)")
            if unit.enhancement:
                print(f"    - Enhancement: {unit.enhancement.name}")
    army.validate()
