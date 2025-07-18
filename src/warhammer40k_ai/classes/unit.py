import logging
from typing import List, Tuple, Optional
from typing import TYPE_CHECKING
from .model import Model
from ..utility.model_base import Base, BaseType
from .wargear import Wargear, WargearOption, parse_option_string, parse_alternate_3
from .ability import Ability
from ..utility.range import Range
from ..utility.calcs import get_dist, get_angle, convert_mm_to_inches, a_star_enhanced, build_spatial_index, footprint_from_offsets, build_formation_templates, query_spatial_index
from ..utility.dice import get_roll, DiceCollection
from .status_effects import StatusEffect, BattleShockEffect
import uuid
import copy
import re
import numpy as np
from enum import Enum, auto
from shapely.affinity import translate

# Forward declarations
if TYPE_CHECKING:
    from .map import Map
    from .army import Army
    from .game import Game

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class UnitRoundState:
    remained_stationary_this_round: bool = True  # Units are stationary by default until they move
    advanced_this_round: bool = False
    shot_this_round: bool = False
    fell_back_this_round: bool = False
    reinforced_this_round: bool = False
    declared_charge_this_round: bool = False
    moved_this_round: bool = False  # Track if unit has moved during movement phase
    num_lost_models_this_round: int = 0
    advance_roll: int = None  # Store advance roll for the round


class MovementAction(Enum):
    REMAIN_STATIONARY = auto()  
    MOVE = auto()
    ADVANCE = auto()
    FALL_BACK = auto()


class MovementState(Enum):
    IN_ENGAGEMENT_RANGE = auto()
    OUT_OF_ENGAGEMENT_RANGE = auto()


class Unit:
    def __init__(self, datasheet, quantity=None, enhancement=None):
        self._id = str(uuid.uuid4())
        self._datasheet = datasheet
        self.name = datasheet.name
        self.faction = datasheet.faction_data["name"]
        self.keywords = getattr(datasheet, 'keywords', [])  # Use getattr with a default value
        self.faction_keywords = getattr(datasheet, 'faction_keywords', [])  # Use getattr with a default value
        try:
            self.unit_composition = self._parse_unit_composition(datasheet.datasheets_unit_composition)
        except Exception as e:
            print(f"{self.name} - NEED TO HANDLE - ERROR PARSING UNIT COMPOSITION: {e}")
            self.unit_composition = {}
            return
        try:
            self.models_cost = self._parse_models_cost(datasheet.datasheets_models_cost)
        except Exception as e:
            #print(f"{self.name} - NEED TO HANDLE - ERROR PARSING MODELS COST: {e}")
            self.models_cost = { "spawn_on_death": 0 }
        self.models = self._create_models(datasheet, quantity)

        # Wargear Stuff
        self.possible_wargear = self._parse_wargear(datasheet)
        self.wargear_options = []
        self._parse_wargear_options(datasheet) # this needs to here, sets above variable
        self.possible_abilities = self._parse_abilities(datasheet)
        self.add_wargear()

        # Attachments
        self.can_be_attached_to = getattr(datasheet, 'attached_to', [])

        if hasattr(datasheet, 'damaged_w') and datasheet.damaged_w:
            self.damaged_profile = self._parse_range(datasheet.damaged_w)
            self.damaged_profile_desc = getattr(datasheet, 'damaged_description', None)
        else:
            self.damaged_profile = None
            self.damaged_profile_desc = None

        self.attached_to = None  # For Leaders, to track which unit they are attached to
        self.enhancement = enhancement  # The Enhancement assigned to this unit (if any)
        self.is_warlord = False
        self.parent_army = None

        # Game State specific attributes
        self.models_lost = []
        self.status_effects = []  # List of active status effects
        self.special_rules = {}  # Dictionary of special rules
        self.stats = {}  # Dictionary of stats modifiers
        self.deployed = False

        # Reserves tracking
        self.reserve_status = 'deployed'  # 'deployed', 'reserves', 'strategic_reserves'
        self.reserve_turn_deployed = None  # Turn when unit arrived from reserves
        self.arrived_from_reserves_this_turn = False  # Flag for movement/charge restrictions

        # Initialize round-tracked variables
        self.initialize_round()

        self.position = None  # Initialize position as None
        self.update_coherency()  # Sets coherency_distance and required_neighbors
        
        # Track starting strength for Battle-Shock tests
        self.starting_model_count = len(self.models)
        self.starting_total_wounds = sum(model._base_wounds for model in self.models)
        
        # Ability cache for performance optimization
        self._ability_cache = {}

    def _parse_attribute(self, attribute_value: str) -> int:
        # Remove " and + from the attribute value
        attribute_value = attribute_value.replace("\"", "").replace("+", "").replace("*", "")
        if "-" in attribute_value:
            return 0
        return int(attribute_value)

    def _parse_range(self, range_string: str) -> Range:
        return Range.from_string(range_string)

    def _parse_base_size(self, base_size: str) -> Base:
        base_size = base_size.replace("mm", "")
        if 'flying base' in base_size:
            # TODO - need to implement vertical offset for flying bases
            #print(f"{self.name} has flying base")
            base_size = base_size.replace("flying base", "").strip()
        # Parse the base size from the datasheet
        if 'x' in base_size:
            # This handles the elliptical example: "32 x 16mm"
            major, minor = base_size.split("x")
            major = convert_mm_to_inches(int(major.strip()) / 2.0)
            minor = convert_mm_to_inches(int(minor.strip()) / 2.0)
            return Base(BaseType.ELLIPTICAL, (major, minor))
        elif 'Use model' in base_size:
            #print(f"{self.name} has guessed HULL base size")
            # TODO - not sure how to handle this; assume hull with 80mm radius and 40mm width
            return Base(BaseType.HULL, (convert_mm_to_inches(80 / 2), convert_mm_to_inches(40 / 2)))
        elif 'No official base size' == base_size.strip():
            #print(f"{self.name} has NO officialbase size")
            return Base(BaseType.HULL, (convert_mm_to_inches(80 / 2), convert_mm_to_inches(40 / 2)))
        elif '' == base_size.strip():
            #print(f"{self.name} has NO base size - guessing 32mm")
            return Base(BaseType.CIRCULAR, convert_mm_to_inches(32 / 2.0))
        else:
            # This handles the standard example: "32mm"
            return Base(BaseType.CIRCULAR, convert_mm_to_inches(int(base_size.strip()) / 2.0))

    def _parse_unit_composition(self, unit_composition):
        result = {}
        for comp in unit_composition:
            if comp['description'].startswith("This unit can contain a maximum of "):
                continue
            if comp['description'] == "OR":
                continue
            if comp['description'].startswith("One of the following:"):
                #print(f"{self.name} - NEED TO HANDLE UNIT COMPOSITION")
                continue
            parts = comp['description'].split()
            count = parts[0]
            model_name = ' '.join(parts[1:])  # Everything after the number
            if '-' in count:
                min_size, max_size = map(int, count.split('-'))
            else:
                min_size = max_size = int(count)
            result[model_name] = (min_size, max_size)
        return result

    def _create_models(self, datasheet, quantity=None):
        models = []
        total_models = 0

        if quantity is None:
            # If no quantity is specified, use the minimum number of models
            quantity = sum(min_size for _, (min_size, _) in self.unit_composition.items())

        for model_name, (min_size, max_size) in self.unit_composition.items():
            if isinstance(max_size, tuple):
                max_size = max_size[1]  # Use the second value if it's a tuple
            model_count = min(max_size, max(min_size, quantity - total_models))
            # Remove 's' from the end of model_name if it's plural
            if model_name.endswith('s'):
                model_name = model_name[:-1]
            for _ in range(model_count):
                model = Model(
                    name=model_name,
                    movement=self._parse_attribute(datasheet.datasheets_models[0]["M"]),
                    toughness=self._parse_attribute(datasheet.datasheets_models[0]["T"]),
                    save=self._parse_attribute(datasheet.datasheets_models[0]["Sv"]),
                    wounds=self._parse_attribute(datasheet.datasheets_models[0]["W"]),
                    leadership=self._parse_attribute(datasheet.datasheets_models[0]["Ld"]),
                    objective_control=self._parse_attribute(datasheet.datasheets_models[0]["OC"]),
                    model_base=self._parse_base_size(datasheet.datasheets_models[0]["base_size"]),
                    inv_save=self._parse_attribute(datasheet.datasheets_models[0]["inv_sv"]),
                    inv_save_condition=datasheet.datasheets_models[0]["inv_sv_descr"].lower()
                )
                model.set_parent_unit(self)
                models.append(model)
                total_models += 1
            if total_models >= quantity:
                break
        return models

    def _parse_loadout(self, loadout: str, model_name: str = "") -> List[Wargear]:
        entries = loadout.replace('’', '').lower().split('.')

        def _parse_loadout_quantity(item_name: str) -> Tuple[int, str]:
            if quantity_match := re.match(r"^(\d+) (.*)s$", item_name.strip()):
                return int(quantity_match.group(1)), quantity_match.group(2)
            return 1, item_name.strip()

        starting_wargear = []
        for entry in entries:
            if not entry:
                continue
            entry = entry.strip()

            if match := re.match(r"^this model is equipped with: (.*)$", entry):
                for item_name in match.group(1).split(";"):
                    quantity, item_name = _parse_loadout_quantity(item_name)
                    for wargear in self.possible_wargear:
                        if item_name.strip() == wargear.name.lower():
                            for _ in range(quantity):
                                starting_wargear.append(wargear)
            elif match := re.match(r"^every model is equipped with: (.*)$", entry):
                for item_name in match.group(1).split(";"):
                    quantity, item_name = _parse_loadout_quantity(item_name)
                    for wargear in self.possible_wargear:
                        if item_name.strip() == wargear.name.lower():
                            for _ in range(quantity):
                                starting_wargear.append(wargear)
            elif match := re.match(r"^(?:the|every) (.*) model is equipped with: (.*)$", entry):
                if model_name and model_name == match.group(1).strip():
                    for item_name in match.group(2).split(";"):
                        quantity, item_name = _parse_loadout_quantity(item_name)
                        for wargear in self.possible_wargear:
                            if item_name.strip() == wargear.name.lower():
                                for _ in range(quantity):
                                    starting_wargear.append(wargear)
                else:
                    continue
            elif match := re.match(r"^(?:the|every|a) (\D+) is equipped with: (.*)$", entry):
                actors = [match.group(1)]
                if " and " in actors[0]:
                    actors = actors[0].split(" and ")
                for actor in actors:
                    if model_name and model_name == actor.strip():
                        for item_name in match.group(2).split(";"):
                            quantity, item_name = _parse_loadout_quantity(item_name)
                            for wargear in self.possible_wargear:
                                if item_name.strip() == wargear.name.lower():
                                    for _ in range(quantity):
                                        starting_wargear.append(wargear)
                    else:
                        continue
            elif match := re.match(r"^(\D+) is equipped with: (.*)$", entry):
                actors = [match.group(1)]
                if " and " in actors[0]:
                    actors = actors[0].split(" and ")
                for actor in actors:
                    if model_name and model_name == actor.strip():
                        for item_name in match.group(2).split(";"):
                            quantity, item_name = _parse_loadout_quantity(item_name)
                            for wargear in self.possible_wargear:
                                if item_name.strip() == wargear.name.lower():
                                    for _ in range(quantity):
                                        starting_wargear.append(wargear)
                    else:
                        continue
            elif match := re.match(r"^this (?:model|unit) is equipped with: nothing$", entry):
                continue
            else:
                print(f"UNKNOWN LOADOUT: {entry}")
        return starting_wargear

    def _parse_wargear(self, datasheet):
        possible_wargear = []
        if hasattr(datasheet, 'datasheets_wargear'):
            for wargear_data in datasheet.datasheets_wargear:
                #print(f"Parsing wargear {wargear_data['name']}")
                if ' – ' in wargear_data['name']:
                    name, profile = wargear_data['name'].split(' – ')
                    if name not in [wargear.name for wargear in possible_wargear]:
                        #print(f"Adding wargear {name} with profile {profile}")
                        possible_wargear.append(Wargear(wargear_data))
                    else:
                        for wargear in possible_wargear:
                            if wargear.name == name:
                                #print(f"Adding profile {profile} to wargear {name}")
                                wargear.add_profile(profile, wargear_data)
                                break
                else:
                    #print(f"Adding wargear {wargear_data['name']}")
                    possible_wargear.append(Wargear(wargear_data))
        return possible_wargear

    def _parse_wargear_options(self, datasheet) -> None:
        wargear_options = []
        if hasattr(datasheet, 'datasheets_options'):
            for wargear_option_data in datasheet.datasheets_options:
                wargear_options.append(wargear_option_data["description"])
        self.parse_wargear_options(wargear_options)

    def _parse_abilities(self, datasheet) -> List[Ability]:
        abilities = []
        if hasattr(datasheet, 'datasheets_abilities'):
            for ability in datasheet.datasheets_abilities:
                if 'ability_data' in ability.keys():
                    abilities.append(Ability(ability["ability_data"]["name"],
                                            ability["ability_data"]["faction_id"],
                                            ability["ability_data"]["description"],
                                            ability["type"],
                                            ability["parameter"],
                                            ability["ability_data"]["legend"]))
                else:
                    abilities.append(Ability(ability["name"],
                                            "",
                                            ability["description"],
                                            ability["type"],
                                            ability["parameter"]))
        return abilities

    def parse_wargear_option(self, option: str) -> None:
        return parse_option_string(option, unit_ref=self)

    def parse_wargear_options(self, options: List[str]):
        if len(options) == 1 and options[0].lower() == "none":
            self.wargear_options = {}
            return
        wargear_options = []
        #for option in options:
        wargear_options = parse_alternate_3(options, self) #self.parse_wargear_option(option)
        #    wargear_options.append(wargear_option)
        #print(f"WARGEAR OPTIONS: {wargear_options}")
        self.wargear_options = wargear_options

    def apply_wargear_option(self, wargear_option: WargearOption):
        # Extract wargear names from the nested structure
        wargear_names = []
        if isinstance(wargear_option.wargear_to, list):
            for item_group in wargear_option.wargear_to:
                if isinstance(item_group, list):
                    for item in item_group:
                        if isinstance(item, tuple) and len(item) >= 2:
                            wargear_names.append(item[1])  # Extract name from (quantity, name) tuple
                        elif isinstance(item, str):
                            wargear_names.append(item)
                elif isinstance(item_group, str):
                    wargear_names.append(item_group)
        elif isinstance(wargear_option.wargear_to, str):
            wargear_names.append(wargear_option.wargear_to)
        
        if not wargear_names:
            return  # No valid wargear to apply
        
        # Find eligible models
        eligible_models = []
        for model in self.models:
            # Check if model name matches (case-insensitive)
            model_name_matches = model.name.lower() == wargear_option.model_name.lower()
            
            # Check if any of the wargear names are already equipped
            already_has_wargear = any(wargear_name in model.optional_wargear for wargear_name in wargear_names)
            
            # Check conditionals (exclusion rules)
            meets_conditionals = True
            if wargear_option.conditionals:
                for conditional in wargear_option.conditionals:
                    # Handle "not equipped with X" conditions
                    if conditional.startswith("not equipped with "):
                        excluded_item = conditional.replace("not equipped with ", "").strip()
                        if excluded_item in model.optional_wargear:
                            meets_conditionals = False
                            break
            
            if model_name_matches and not already_has_wargear and meets_conditionals:
                eligible_models.append(model)

        if len(eligible_models) < wargear_option.model_quantity.min:
            # If no eligible models found, this might be due to conditionals, so just skip silently
            return

        # Apply wargear to eligible models up to the limit
        count = 0
        max_count = min(len(eligible_models), wargear_option.item_quantity.max if hasattr(wargear_option.item_quantity, 'max') else wargear_option.item_quantity)
        
        for model in eligible_models:
            if count >= max_count:
                break
            # Add the first wargear name to the model's optional wargear
            if wargear_names:
                model.optional_wargear.append(wargear_names[0])
            count += 1

    def apply_wargear_options(self, wargear_name: Optional[str] = None) -> None:
        for optional_wargear in self.wargear_options:
            if wargear_name:
                if optional_wargear.wargear_to == wargear_name:
                    self.apply_wargear_option(optional_wargear)
                    break
            else:
                self.apply_wargear_option(optional_wargear)

    def add_wargear(self, wargear: List[Wargear]=[], model_name: str=None) -> None:
        for model_instance in self.models:
            wargear_to_add = []
            if not wargear:
                for wargear_instance in self._parse_loadout(getattr(self._datasheet, 'loadout', []), model_instance.name.lower()):
                    wargear_to_add.append(wargear_instance)
            else:
                # TODO - validate wargear against options and their limits and exchanges
                wargear_to_add.extend(wargear)
            for wargear_instance in wargear_to_add:
                if model_name:
                    if model_instance.name.lower() == model_name.lower():
                        if wargear_instance:
                            model_instance.wargear.append(wargear_instance)
                else:
                    if wargear_instance:
                        model_instance.wargear.append(wargear_instance)

    def set_parent_army(self, army_ptr) -> None:
        """Set the parent army of the unit."""
        self.parent_army = army_ptr

    def get_parent_army(self) -> Optional['Army']:
        """Get the parent army of the unit."""
        return self.parent_army

    def add_ability(self, ability: Ability, model_name: str=None, quantity: int=1000) -> None:
        """Add ability to the unit."""
        count = 0
        for model in self.models:
            if count >= quantity:
                break
            if model_name:
                if model.name == model_name:
                    model.add_ability(ability)
            else:
                model.add_ability(ability)
            count += 1
        # Invalidate ability cache since abilities changed
        self._invalidate_ability_cache()

    def _invalidate_ability_cache(self) -> None:
        """Invalidate ability cache when unit state changes."""
        if hasattr(self, '_ability_cache'):
            self._ability_cache.clear()

    # Remove a Model from a Unit (e.g., when it dies)
    def remove_model(self, model: Model, fleed: bool = False, game_map: Optional['Map'] = None) -> None:
        assert model in self.models

        # Check for Deadly Demise ability before removing the model
        if not fleed and game_map is not None:
            self._trigger_deadly_demise(model, game_map)

        # Remove model itself
        self.round_state.num_lost_models_this_round += 1
        self.models_lost.append(model)
        self.models.remove(model)

        # Invalidate ability cache since unit composition changed
        self._invalidate_ability_cache()

        logger.info(f"Unit has {len(self.models)} models left!")
        #if len(self.models) < 1:
        #    if not fleed:
        #        self.callbacks[hook_events.ENEMY_UNIT_KILLED].append(logger.error(self))
        #    self.parent_detachment.removeUnit(self)
        self.update_coherency()

    def _trigger_deadly_demise(self, dying_model: Model, game_map: 'Map') -> None:
        """Trigger Deadly Demise ability when a model is killed.
        
        Args:
            dying_model: The model that is being killed
            game_map: The game map to find nearby units
        """
        # Check if the unit has Deadly Demise ability
        has_deadly_demise, damage_dice = self.has_deadly_demise()
        if not has_deadly_demise:
            return
        
        print(f"💥 {self.name} has Deadly Demise {damage_dice} - checking for explosion!")
        
        # Roll D6 to see if Deadly Demise triggers
        trigger_roll = get_roll("D6")
        if trigger_roll != 6:
            print(f"🎲 Deadly Demise trigger roll: {trigger_roll} (needed 6) - No explosion!")
            return
        
        print(f"🎲 Deadly Demise trigger roll: {trigger_roll} - EXPLOSION! 💥")
        
        # Get the dying model's position
        model_position = dying_model.get_location()
        if not model_position:
            print(f"❌ Cannot determine position of dying model for Deadly Demise")
            return
        
        # Find all units within 6 inches of the dying model
        nearby_units = self._get_units_within_range(model_position, 6.0, game_map)
        
        if not nearby_units:
            print(f"💥 Deadly Demise triggered but no units within 6\" - no damage dealt")
            return
        
        # Apply damage to each nearby unit
        total_damage_dealt = 0
        for target_unit in nearby_units:
            # Roll damage independently for each unit (if it's a dice roll)
            if damage_dice.number > 0:  # It's a dice roll like D3, D6
                damage_amount = damage_dice.roll()
            else:  # It's a fixed number
                damage_amount = damage_dice.modifier
            
            print(f"💥 {target_unit.name} suffers {damage_amount} mortal wounds from Deadly Demise!")
            
            # Apply mortal wounds to the target unit
            models_destroyed = self._apply_mortal_wounds_to_unit(target_unit, damage_amount)
            total_damage_dealt += damage_amount
            
            if models_destroyed > 0:
                print(f"💀 Deadly Demise destroyed {models_destroyed} model(s) in {target_unit.name}")
        
        print(f"💥 Deadly Demise complete: {total_damage_dealt} total mortal wounds dealt to {len(nearby_units)} unit(s)")

    def trigger_deadly_demise_manually(self, dying_model: Model, game_map: 'Map') -> None:
        """Manually trigger Deadly Demise for testing or when game context is available.
        
        This method can be called from the UI or game context when a model is killed
        and the game_map is available.
        
        Args:
            dying_model: The model that is being killed
            game_map: The game map to find nearby units
        """
        self._trigger_deadly_demise(dying_model, game_map)

    def _get_units_within_range(self, position: Tuple[float, float, float, float], range_inches: float, game_map: 'Map') -> List['Unit']:
        """Get all units within the specified range of a position.
        
        Args:
            position: (x, y, z, facing) position to check from
            range_inches: Range in inches to check
            game_map: The game map containing all units
            
        Returns:
            List of units within range (excluding the unit containing the position)
        """
        units_within_range = []
        x, y, z = position[0], position[1], position[2]
        
        for unit in game_map.units:
            if unit == self:  # Skip our own unit
                continue
            
            if not unit.is_alive():  # Skip destroyed units
                continue
            
            # Get the closest model in the unit to our position
            closest_distance = float('inf')
            for model in unit.models:
                if not model.is_alive:
                    continue
                model_pos = model.get_location()
                if model_pos:
                    model_distance = get_dist(
                        x - model_pos[0],
                        y - model_pos[1],
                        z - model_pos[2] if len(model_pos) > 2 else 0
                    )
                    closest_distance = min(closest_distance, model_distance)

            if closest_distance == float('inf'):
                continue

            distance = closest_distance
            
            if distance <= range_inches:
                units_within_range.append(unit)
        
        return units_within_range

    def _apply_mortal_wounds_to_unit(self, target_unit: 'Unit', mortal_wound_amount: int) -> int:
        """Apply mortal wounds to a unit, distributing them among models.
        
        Args:
            target_unit: The unit to apply mortal wounds to
            mortal_wound_amount: Number of mortal wounds to apply
            
        Returns:
            Number of models destroyed by the mortal wounds
        """
        models_destroyed = 0
        
        # Apply mortal wounds one at a time to models in the unit
        for _ in range(mortal_wound_amount):
            if not target_unit.is_alive():
                break  # Unit is destroyed, stop applying wounds
            
            # Find a model to apply the wound to (prioritize damaged models)
            target_model = None
            for model in target_unit.models:
                if not model.is_alive:
                    continue
                if not model.is_max_health:
                    target_model = model
                    break
            
            # If no damaged models, apply to the first alive model
            if target_model is None:
                for model in target_unit.models:
                    if model.is_alive:
                        target_model = model
                        break
            
            if target_model is None:
                break  # No models to apply wounds to
            
            # Apply the mortal wound
            target_model.take_damage(1, is_mortal=True, weapon_profile=None)
            
            # Check if the model was destroyed
            if not target_model.is_alive:
                models_destroyed += 1
        
        return models_destroyed

    def add_model(self, model: Model) -> None:
        assert model not in self.models
        model.set_parent_unit(self)
        self.models.append(model)
        # Invalidate ability cache since unit composition changed
        self._invalidate_ability_cache()
        self.update_coherency()

    def update_coherency(self) -> None:
        if len(self.models) == 1:
            self.coherency_distance = 2.0
            self.required_neighbors = 0
        elif len(self.models) > 5:
            self.coherency_distance = 2.0
            self.required_neighbors = 2
        else:
            self.coherency_distance = 2.0
            self.required_neighbors = 1

    def initialize_round(self) -> None:
        """Reset round-tracked variables to default state."""
        self.round_state = UnitRoundState()
        # Check status effects expiration (with safe defaults)
        for status_effect in self.status_effects:
            try:
                status_effect.check_expiration(self)
            except Exception:
                # If status effect check fails, just continue
                # This prevents crashes from incomplete status effect implementations
                pass
        
        # Reset reserves arrival flag
        self.arrived_from_reserves_this_turn = False

    def is_max_health(self) -> Tuple[bool, Optional[Model]]:
        """
        Check if the unit is at full health.

        Returns:
            Tuple[bool, Optional[Model]]: A tuple containing:
                - A boolean indicating if the unit is at full health
                - The first damaged model found, or None if all models are at full health
        """
        for model in self.models:
            if not model.is_max_health:
                return False, model
        return True, None

    def is_below_half_strength(self) -> bool:
        """
        Check if the unit is below half its starting strength for Battle-Shock purposes.
        
        For multi-model units: Check if current model count is less than half starting count
        For single-model units: Check if current wounds are less than half starting wounds
        
        Returns:
            bool: True if unit is below half strength and should take Battle-Shock tests
        """
        if self.starting_model_count > 1:
            # Multi-model unit: check model count
            current_model_count = len(self.models)
            return current_model_count < (self.starting_model_count / 2.0)
        else:
            # Single-model unit: check wounds
            if not self.models:
                return True  # Unit is destroyed, definitely below half strength
            current_wounds = self.models[0].wounds
            starting_wounds = self.starting_total_wounds
            return current_wounds < (starting_wounds / 2.0)

    def is_battle_shocked(self) -> bool:
        """
        Check if the unit is currently battle-shocked.
        
        Returns:
            bool: True if the unit has a BattleShockEffect status effect
        """
        return any(isinstance(effect, BattleShockEffect) for effect in self.status_effects)

    def pass_leadership_check(self) -> bool:
        """Perform a Leadership test by rolling 2D6 against the unit's Leadership characteristic.
        
        Returns:
            bool: True if the test is passed, False if failed
        """
        roll_result = get_roll("2D6")
        leadership_value = self.leadership
        passed = roll_result >= leadership_value
        
        # Provide detailed feedback
        if passed:
            print(f"🎲 {self.name} Leadership test: 2D6 rolled {roll_result} vs Ld {leadership_value} - PASSED! ✅")
        else:
            print(f"🎲 {self.name} Leadership test: 2D6 rolled {roll_result} vs Ld {leadership_value} - FAILED! ❌")
        
        return passed

    @property
    def is_epic_hero(self) -> bool:
        return "Epic Hero" in self.keywords

    @property
    def is_battleline(self) -> bool:
        return "Battleline" in self.keywords

    @property
    def is_dedicated_transport(self) -> bool:
        return "Dedicated Transport" in self.keywords

    @property
    def is_transport(self) -> bool:
        return "Transport" in self.keywords

    @property
    def is_leader(self) -> bool:
        return len(self.can_be_attached_to) > 0

    @property
    def is_supreme_commander(self) -> bool:
        return "Supreme Commander" in [ability.name for ability in self.possible_abilities]

    @property
    def is_monster(self) -> bool:
        return "Monster" in self.keywords

    @property
    def is_vehicle(self) -> bool:
        return "Vehicle" in self.keywords

    @property
    def is_aircraft(self) -> bool:
        return "Aircraft" in self.keywords

    @property
    def is_fortification(self) -> bool:
        return "Fortification" in self.keywords

    @property
    def is_character(self) -> bool:
        return "Character" in self.keywords

    @property
    def is_psyker(self) -> bool:
        return "Psyker" in self.keywords

    @property
    def is_infantry(self) -> bool:
        return "Infantry" in self.keywords

    @property
    def is_beast(self) -> bool:
        return "Beast" in self.keywords

    @property
    def is_titanic(self) -> bool:
        return "Titanic" in self.keywords

    @property
    def is_towering(self) -> bool:
        return "Towering" in self.keywords

    @property
    def is_flying(self) -> bool:
        return "Fly" in self.keywords

    @property
    def is_smoke(self) -> bool:
        return "Smoke" in self.keywords

    @property
    def is_belisarius_cawl(self) -> bool:
        return "Belisarius Cawl" in self.keywords

    @property
    def is_imperium_primarch(self) -> bool:
        return "Imperium" in self.keywords and "Primarch" in self.keywords

    def has_keyword(self, keyword: str) -> bool:
        return keyword.lower() in [keyword.lower() for keyword in self.keywords]

    @property
    def movement(self) -> int:
        return self.models[0].movement

    @property
    def toughness(self) -> int:
        return self.models[0].toughness

    @property
    def save(self) -> int:
        return self.models[0].save

    @property
    def inv_save(self) -> Optional[int]:
        return self.models[0].inv_save

    @property
    def leadership(self) -> int:
        return self.models[0].leadership

    @property
    def objective_control(self) -> int:
        return self.models[0].objective_control

    @property
    def has_circular_base(self) -> bool:
        return self.models[0].has_circular_base

    @property
    def base_size(self) -> float:
        return self.models[0].base_size

    @property
    def model_height(self) -> float:
        return max(model.model_base.model_height for model in self.models)

    def print_unit(self):
        for model in self.models:
            print(f"\n{model}")

    def get_unique_model_names(self) -> List[str]:
        return list(set(model.name for model in self.models))

    def _parse_models_cost(self, models_cost):
        result = {}
        for cost_entry in models_cost:
            try:
                num_models = int(cost_entry['description'].split()[0])
                cost = int(cost_entry['cost'])
                result[num_models] = cost
            except ValueError:
                num_models = 1
                cost = int(cost_entry['cost'].replace("+", ""))
                result['extra'] = cost
        return result

    def calculate_points(self, num_models):
        for threshold, cost in sorted(self.models_cost.items(), reverse=True):
            if num_models >= threshold:
                return cost
        return 0

    def max_models_for_points(self, max_points):
        max_models = 0
        for num_models, cost in sorted(self.models_cost.items()):
            if cost <= max_points:
                max_models = num_models
            else:
                break
        return max_models

    def get_unit_cost(self) -> int:
        """
        Calculate the cost of the unit based on the number of models.
        If the unit has an enhancement, add the enhancement cost to the unit cost.

        Returns:
            int: The cost of the unit in points (including enhancement cost if applicable)
        """
        num_models = len(self.models)
        return self.calculate_points(num_models) + (self.enhancement.points if self.enhancement else 0)

    def configure_models(self, count, wargear):
        # Recreate the models with the specified count
        self.models = self._create_models(self._datasheet, count)
        self.update_coherency()

        # Apply wargear to all models
        for model in self.models:
            if wargear:
                if type(wargear) == list:
                    for wargear_item in wargear:
                        model.add_wargear(wargear_item)
                else:
                    model.add_wargear(wargear)
            else:
                model.wargear = []

    @property
    def abilities(self):
        abilities = []
        for model in self.models:
            abilities.extend(model.abilities)
        return abilities

    @property
    def health_percent(self) -> float:
        """Calculate the percentage of remaining health."""
        total_wounds = sum(model.wounds for model in self.models)
        max_wounds = sum(model._base_wounds for model in self.models)
        if max_wounds == 0:
            return 0
        return (total_wounds / max_wounds) * 100

    @property
    def is_ranged_unit(self) -> bool:
        """Determine if the unit is primarily a ranged unit."""
        # For simplicity, if the unit has more ranged weapons than melee weapons
        ranged_weapons = 0
        melee_weapons = 0
        for model in self.models:
            for weapon in model.wargear:
                if weapon.is_ranged():
                    ranged_weapons += 1
                elif weapon.is_melee():
                    melee_weapons += 1
        return ranged_weapons >= melee_weapons

    @property
    def is_melee_unit(self) -> bool:
        """Determine if the unit is primarily a melee unit."""
        return not self.is_ranged_unit()

    @property
    def max_charge_distance(self) -> float:
        """Calculate the maximum possible charge distance."""
        return 12.0  # 2D6 maximum roll

    def get_threat_level(self, target_unit: Optional['Unit'] = None) -> Tuple[float, float]:
        """Calculate the threat level of the unit based on offensive capabilities."""
        melee_threat = 0
        ranged_threat = 0
        for model in self.models:
            for weapon in model.wargear:
                if weapon.is_ranged() or weapon.is_melee():
                    dmg_potential = weapon.get_damage_potential(target_unit)
                    #print(f"{weapon.name} damage potential: {dmg_potential}")
                    if weapon.is_ranged():
                        ranged_threat += dmg_potential
                    else:
                        melee_threat += dmg_potential
                else:
                    raise Exception(f"UNHANDLED WEAPON TYPE: {weapon.name}")
        return ranged_threat, melee_threat

    def get_threat_per_cost(self, target_unit: Optional['Unit'] = None) -> Tuple[float, float]:
        ranged_threat, melee_threat = self.get_threat_level(target_unit)
        try:
            cost = self.models_cost[len(self.models)]
        except KeyError:
            try:
                cost = self.models_cost[len(self.models) - 1]
                cost += self.models_cost["extra"]
            except KeyError:
                print(f"No cost found for {self.name}")
                cost = 1000
        return ranged_threat / cost, melee_threat / cost

    ###########################################################################
    ### Core Actions
    ###########################################################################
    def apply_command_abilities(self) -> None:
        """Applies command abilities during the Command phase."""
        for ability in self.abilities.get('command_phase', []):
            ability.activate(self)

    ###########################################################################
    ### Command
    ###########################################################################
    def do_command_action(self, game_map: 'Map', current_turn: int = 1) -> bool:
        """Executes the command action for the unit.
        
        Args:
            game_map: The game map
            current_turn: The current battle round number
        """
        self.initialize_round()

        # Do Battle Shock Test for appropriate units
        if self.is_below_half_strength():
            print(f"⚠️  {self.name} is below half strength - taking Battle-Shock test")
            self.take_battle_shock_test(current_turn)

        return True

    ###########################################################################
    ### Movement
    ###########################################################################
    def do_move_action(self, action: int, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        """Executes the given movement action."""
        return self._execute_action(action, destination, game_map)

    def get_engagement_state(self, game_map: 'Map') -> int:
        """Determine if the unit is in engagement range of any enemy model."""
        enemy_units = game_map.get_enemy_units(self)
        
        for enemy_unit in enemy_units:
            if game_map.is_within_engagement_range(self, enemy_unit):
                return MovementState.IN_ENGAGEMENT_RANGE
        
        return MovementState.OUT_OF_ENGAGEMENT_RANGE

    def get_available_move_actions(self, state: int) -> List[int]:
        """Get the list of available actions based on the current state."""
        if state == MovementState.IN_ENGAGEMENT_RANGE:
            return [MovementAction.REMAIN_STATIONARY.value, MovementAction.FALL_BACK.value]
        else:
            return [MovementAction.REMAIN_STATIONARY.value, MovementAction.MOVE.value, MovementAction.ADVANCE.value]

    def _execute_action(self, action: int, destination: Tuple[float, float, float], game_map: 'Map', advance_roll: int = None) -> bool:
        """Execute a movement action for the unit."""
        success = False
        if action == MovementAction.REMAIN_STATIONARY.value:
            print(f"{self.name} remains stationary")
            success = self.remain_stationary()
        elif action == MovementAction.MOVE.value:
            print(f"{self.name} moves to {destination}")
            success = self.move(destination, game_map)
        elif action == MovementAction.ADVANCE.value:
            print(f"{self.name} advances to {destination}")
            success = self.advance(destination, game_map)
        elif action == MovementAction.FALL_BACK.value:
            print(f"{self.name} falls back")
            # Provide an empty path list for fall back action
            success = self.fall_back(destination, [], game_map)
        else:
            raise ValueError(f"Invalid action: {action}")
        
        # Mark unit as having moved this round if action was successful
        # AND set remained_stationary_this_round to False if the unit actually moved
        if success:
            self.round_state.moved_this_round = True
            # If the unit performed any movement action (not remain stationary), 
            # it did not remain stationary this round
            if action != MovementAction.REMAIN_STATIONARY.value:
                self.round_state.remained_stationary_this_round = False
        
        return success

    def remain_stationary(self) -> bool:
        # Unit explicitly chose to remain stationary, so mark it as such
        self.round_state.remained_stationary_this_round = True
        return True

    def prepare_advance(self) -> int:
        """Pre-roll advance dice for UI display. Returns the advance roll."""
        if not hasattr(self.round_state, 'advance_roll') or self.round_state.advance_roll is None:
            advance_roll = get_roll("D6")
            self.round_state.advance_roll = advance_roll
            print(f"🎲 {self.name} advance roll: {advance_roll}\" (Move {self.movement}\" + {advance_roll}\" = {self.movement + advance_roll}\")")
            return advance_roll
        return self.round_state.advance_roll

    def get_advance_roll(self) -> int:
        """Get the current advance roll, or None if not rolled yet."""
        return getattr(self.round_state, 'advance_roll', None)

    def advance(self, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        # Check if unit can advance after arriving from reserves
        if self.arrived_from_reserves_this_turn and not self.can_advance_after_arriving_from_reserves():
            logger.info(f"{self.name} cannot advance - arrived from reserves this turn")
            return False
        return self.move(destination, game_map, advance=True)

    def move(self, destination: Tuple[float, float, float], game_map: 'Map', advance: bool = False) -> bool:
        """
        Moves the unit towards the destination using optimized individual model pathfinding.
        
        This method now uses the new pathfinding system that:
        1. Moves models individually using optimized pathfinding
        2. Ignores coherency during movement (human player responsibility)
        3. Validates coherency after all models have moved
        4. Removes non-coherent models from play if coherency fails
        """
        if not self.models:
            logger.error(f"Cannot move unit {self.name}: no models in unit")
            return False
        
        # Check if unit can move after arriving from reserves
        if self.arrived_from_reserves_this_turn and not self.can_move_after_arriving_from_reserves():
            logger.info(f"{self.name} cannot move - arrived from reserves this turn")
            return False

        # Get starting position from first model for feedback
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot move unit {self.name}: no valid models")
            return False

        first_model_pos = self.models[0].get_location()
        if not first_model_pos:
            logger.error(f"Cannot move unit {self.name}: first model has no position")
            return False

        # Store starting position for feedback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0

        # BACKUP ORIGINAL POSITIONS - Critical for proper rollback on failure
        original_model_positions = []
        for model in self.models:
            original_model_positions.append(model.get_location())

        # Get the movement range from the first model (assuming all models have the same movement)
        movement_range = self.movement

        # If advancing, use stored advance roll or roll new one
        if advance:
            # Use stored advance roll if available, otherwise roll new one
            if not hasattr(self.round_state, 'advance_roll') or self.round_state.advance_roll is None:
                advance_roll = get_roll("D6")
                self.round_state.advance_roll = advance_roll
                print(f"Advance roll: {advance_roll}")
            else:
                advance_roll = self.round_state.advance_roll
                print(f"Using stored advance roll: {advance_roll}")
            
            if advance_roll is None:
                logger.error(f"Failed to roll dice for advancing unit {self.name}")
                return False
            movement_range += advance_roll

        # Calculate straight-line distance to destination
        distance_to_destination = get_dist(
            destination[0] - start_x,
            destination[1] - start_y,
            destination[2] - start_z
        )

        # Check if destination is within movement range
        if distance_to_destination > movement_range:
            print(f"❌ {self.name} cannot reach destination {distance_to_destination:.1f}\" away (max {'advance' if advance else 'move'}: {movement_range}\")")
            return False

        # Generate potential positions for models with reduced boundary repulsors for better formation finding
        boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
        potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
        
        # Check if formation finding failed
        if potential_positions is None:
            print(f"❌ {self.name} cannot move - no valid formation found at destination")
            return False

        # Use the new individual model pathfinding system
        from ..utility.calcs import get_individual_model_movement_path, process_unit_movement_with_coherency_check
        
        model_movements = []
        successful_moves = 0

        # Move each model individually using optimized pathfinding
        for model_index, (model, model_destination) in enumerate(zip(self.models, potential_positions)):
            model_start = model.get_location()
            logging.debug(f"Model {model._id} {model.name} attempting to move from {model_start} to {model_destination}")
            
            # Calculate straight-line distance for this model
            model_distance = get_dist(
                model_destination[0] - model_start[0],
                model_destination[1] - model_start[1],
                model_destination[2] - model_start[2] if len(model_start) > 2 else 0
            )
            
            # Check if this model can reach its destination
            if model_distance > movement_range:
                print(f"Model {model._id} cannot reach destination {model_distance:.1f}\" away (max: {movement_range}\")")
                continue  # Skip this model, don't move it
            
            # Use new optimized pathfinding for individual model movement
            path = get_individual_model_movement_path(self, model_index, model_destination, game_map, movement_range)
            
            if not path:
                logger.debug(f"Model {model._id} optimized pathfinding failed - destination may violate movement rules")
                continue
            
            # Calculate path distance
            path_distance = sum(get_dist(path[i][0] - path[i-1][0], path[i][1] - path[i-1][1]) for i in range(1, len(path)))
            
            if path_distance > movement_range:
                print(f"Model {model._id} path distance {path_distance:.1f}\" exceeds movement {movement_range}\"")
                # Try to move as far as possible along the path
                last_node = model_start
                model.last_move_path = [last_node]
                distance_along_path = 0.0
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                
                for node in path[1:]:
                    dx = node[0] - last_node[0]
                    dy = node[1] - last_node[1]
                    dz = node[2] - last_node[2] if len(node) > 2 else 0
                    segment_distance = get_dist(dx, dy, dz)
                    
                    if distance_along_path + segment_distance > movement_range:
                        # Stop here, can't go further
                        break
                    
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                # Move to the furthest reachable position
                if distance_along_path > 0:
                    final_position = model.last_move_path[-1]
                    model.set_location(final_position[0], final_position[1], final_position[2], final_position[3])
                    model_movements.append((model_index, model.last_move_path))
                    successful_moves += 1
                    logger.debug(f"Model {model._id} moved along path to {final_position[:3]}, distance: {distance_along_path:.1f}\"")
            else:
                # Path is within range, move to destination
                model.set_location(*model_destination)
                last_node = model_start
                model.last_move_path = [last_node]
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                distance_along_path = 0.0
                
                for node in path[1:]:
                    dx = node[0] - last_node[0]
                    dy = node[1] - last_node[1]
                    dz = node[2] - last_node[2] if len(node) > 2 else 0
                    segment_distance = get_dist(dx, dy, dz)
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                model_movements.append((model_index, model.last_move_path))
                successful_moves += 1
                logger.debug(f"Model {model._id} moved to {model_destination}, path distance: {distance_along_path:.1f}\"")

        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            print(f"❌ {self.name} could not move - no models could reach any valid positions")
            return False

        # NEW: Validate unit coherency after all models have moved
        is_coherent, non_coherent_models = process_unit_movement_with_coherency_check(self, model_movements)
        
        if not is_coherent:
            print(f"⚠️  {self.name} coherency violation after movement!")
            print(f"⚠️  Models {non_coherent_models} are not coherent and must be removed from play")
            
            # Remove non-coherent models from play
            for model_index in sorted(non_coherent_models, reverse=True):
                if model_index < len(self.models):
                    model = self.models[model_index]
                    print(f"💀 Removing {model.name} from play due to coherency violation")
                    # Set wounds to 0 to make the model dead (is_alive property checks wounds > 0)
                    model.wounds = 0
                    # Call die() method to properly remove the model from the unit
                    model.die()
                    
            # Unit position is now determined by model positions
            
            # Check if unit is still viable
            if not self.is_alive():
                print(f"💀 {self.name} has been destroyed due to coherency violations")
                return False
        
        # CRITICAL VALIDATION: Check for illegal overlaps after movement
        # This catches cases where models might be overlapping with enemies after movement
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
        
        # Check for base overlaps with enemy models
        enemy_units = game_map.get_enemy_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for enemy_unit in enemy_units:
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the enemy model's base
                    if model.model_base.collides_with(enemy_model.model_base):
                        print(f"❌ {self.name} cannot move - {model.name} would overlap with {enemy_model.name} from {enemy_unit.name}")
                        # ROLLBACK: Restore original positions
                        for i, original_pos in enumerate(original_model_positions):
                            if i < len(self.models):
                                self.models[i].set_location(*original_pos)
                        return False
        
        # Calculate actual distance the unit moved
        unit_distance_moved = get_dist(end_x - start_x, end_y - start_y)
        
        # Provide detailed feedback
        action_name = 'advanced' if advance else 'moved'
        print(f"✅ {self.name} {action_name} from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if successful_moves < len(self.models):
            print(f"⚠️  Note: Only {successful_moves}/{len(self.models)} models could move to valid positions")

        logger.info(f"Unit {self.name} {action_name} from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        self.round_state.advanced_this_round = advance
        return True

    def charge_move(self, destination: Tuple[float, float, float], game_map: 'Map', target_unit: 'Unit' = None) -> bool:
        """Special movement for charge actions that allows moving into engagement range.
        
        Unlike normal movement, charge movement:
        1. Allows models to move into engagement range of enemy units
        2. Uses relaxed collision detection for final positioning
        3. Prioritizes achieving engagement range over perfect formations
        """
        if not self.models:
            logger.error(f"Cannot charge move unit {self.name}: no models in unit")
            return False
        
        # Get starting position from first model
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot charge move unit {self.name}: no valid models")
            return False

        first_model_pos = self.models[0].get_location()
        if not first_model_pos:
            logger.error(f"Cannot charge move unit {self.name}: first model has no position")
            return False
        
        # Store starting position for feedback and rollback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0
        
        # Store original model positions for potential rollback
        original_model_positions = []
        for model in self.models:
            model_pos = model.get_location()
            original_model_positions.append(model_pos)
        
        # Store original model positions for potential rollback
        
        # Calculate maximum charge distance available
        max_charge_distance = get_dist(
            destination[0] - start_x,
            destination[1] - start_y,
            destination[2] - start_z
        )
        
        # Find enemy models to charge towards
        if target_unit and target_unit.is_alive():
            # Charge toward specific target unit
            all_enemy_models = [model for model in target_unit.models if model.is_alive]
            print(f"🎯 {self.name} charging specifically toward {target_unit.name} ({len(all_enemy_models)} models)")
            if not all_enemy_models:
                print(f"❌ {self.name} cannot charge - no alive models in target unit {target_unit.name}")
                return False
        else:
            # Fallback: charge toward all enemy models (for backward compatibility)
            enemy_units = game_map.get_enemy_units(self)
            all_enemy_models = []
            for enemy_unit in enemy_units:
                if enemy_unit.is_alive():
                    all_enemy_models.extend([model for model in enemy_unit.models if model.is_alive])
            
            if not all_enemy_models:
                print(f"❌ {self.name} cannot charge - no enemy models to charge towards")
                return False
        
        successful_moves = 0
        
        # FAST PATH FOR SINGLE MODEL UNITS - use pathfinding but skip formation complexity
        if len(self.models) == 1:
            print(f"🏃 {self.name} using single-model charge path")
            model = self.models[0]
            model_start = model.get_location()
            
            # Calculate straight-line distance to destination
            model_distance = get_dist(
                destination[0] - model_start[0],
                destination[1] - model_start[1],
                destination[2] - model_start[2] if len(model_start) > 2 else 0
            )
            
            # Check if within charge distance
            if model_distance > max_charge_distance:
                print(f"❌ {self.name} cannot reach charge destination {model_distance:.1f}\" away (max: {max_charge_distance}\")")
                return False
            
            # Use enhanced pathfinding for single model (can navigate around obstacles)
            from ..utility.calcs import a_star_enhanced
            from .unit import MovementAction
            
            pathfinding_result = a_star_enhanced(model, game_map, destination, movement_action=MovementAction.MOVE)
            
            if not pathfinding_result:
                print(f"❌ {self.name} cannot charge to destination - pathfinding failed (obstacles in way)")
                return False
            
            shortest_path, enemy_models_moved_over = pathfinding_result
            
            # Calculate path distance
            path_distance = sum(get_dist(shortest_path[i][0] - shortest_path[i-1][0], shortest_path[i][1] - shortest_path[i-1][1]) for i in range(1, len(shortest_path)))
            
            # Check if path is within charge distance
            if path_distance > max_charge_distance:
                print(f"❌ {self.name} path distance {path_distance:.1f}\" exceeds charge distance {max_charge_distance}\"")
                return False
            
            # Move the model to destination
            new_z = game_map.get_height_at_point(destination[0], destination[1])
            new_facing = self.calculate_strategic_facing(destination[0], destination[1], game_map)
            model.set_location(destination[0], destination[1], new_z, new_facing)
            successful_moves = 1
            
            print(f"✅ {self.name} (single model) charged via pathfinding - distance: {path_distance:.1f}\"")
        
        else:
            # COMPLEX PATH FOR MULTI-MODEL UNITS - use formation positioning
            print(f"🏃 {self.name} using multi-model charge path")
            
            # Generate potential positions for models with enhanced pathfinding for charges
            boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
            potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
            
            # Use formation positioning if available, otherwise fall back to individual positioning
            if potential_positions is not None:
                # Use formation positioning with enhanced pathfinding validation
                for model, model_destination in zip(self.models, potential_positions):
                    model_start = model.get_location()
                    
                    # Calculate distance for this model
                    model_distance = get_dist(
                        model_destination[0] - model_start[0],
                        model_destination[1] - model_start[1],
                        model_destination[2] - model_start[2] if len(model_start) > 2 else 0
                    )
                    
                    # Check if within charge distance
                    if model_distance > max_charge_distance:
                        logger.debug(f"Model {model._id} cannot reach charge destination {model_distance:.1f}\" away (max: {max_charge_distance}\")")
                        continue
                    
                    # Use enhanced pathfinding for charge movement
                    from ..utility.calcs import a_star_enhanced
                    from .unit import MovementAction
                    
                    pathfinding_result = a_star_enhanced(model, game_map, model_destination, movement_action=MovementAction.MOVE)
                    
                    if pathfinding_result:
                        shortest_path, enemy_models_moved_over = pathfinding_result
                        
                        # Calculate path distance
                        path_distance = sum(get_dist(shortest_path[i][0] - shortest_path[i-1][0], shortest_path[i][1] - shortest_path[i-1][1]) for i in range(1, len(shortest_path)))
                        
                        if path_distance <= max_charge_distance:
                            # Move to destination
                            model.set_location(*model_destination)
                            successful_moves += 1
                            logger.debug(f"Model {model._id} charge moved {path_distance:.1f}\" to formation position")
                        else:
                            logger.debug(f"Model {model._id} path distance {path_distance:.1f}\" exceeds charge distance {max_charge_distance}\"")
                    else:
                        logger.debug(f"Model {model._id} cannot charge to formation position - pathfinding failed")
            else:
                print(f"❌ {self.name} charge failed - no valid formation found, trying individual positioning")
            
            # If formation failed or had limited success, try individual model positioning
            if successful_moves < len(self.models) // 2:  # If less than half succeeded
                # Move each model individually using enhanced pathfinding
                for model in self.models:
                    model_start = model.get_location()
                
                    # Find the closest enemy model to this model
                    closest_enemy = None
                    closest_distance = float('inf')
                    
                    for enemy_model in all_enemy_models:
                        enemy_pos = enemy_model.get_location()
                        distance = get_dist(
                            enemy_pos[0] - model_start[0],
                            enemy_pos[1] - model_start[1],
                            enemy_pos[2] - model_start[2] if len(model_start) > 2 else 0
                        )
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_enemy = enemy_model
                    
                    if not closest_enemy:
                        continue
                    
                    # Calculate direction towards closest enemy
                    enemy_pos = closest_enemy.get_location()
                    dx = enemy_pos[0] - model_start[0]
                    dy = enemy_pos[1] - model_start[1]
                    dz = enemy_pos[2] - model_start[2] if len(model_start) > 2 else 0
                    
                    distance_to_enemy = get_dist(dx, dy, dz)
                    
                    if distance_to_enemy == 0:
                        # Already at enemy position, no movement needed
                        successful_moves += 1
                        continue
                    
                    # Normalize direction vector
                    dx /= distance_to_enemy
                    dy /= distance_to_enemy
                    dz /= distance_to_enemy if distance_to_enemy > 0 else 1
                    
                    # Calculate how far to move: use the distance provided by attempt_charge
                    # Get as close as possible to the enemy for better pile-in positioning
                    target_distance = max_charge_distance  # Use the distance calculated by attempt_charge
                    
                    if target_distance <= 0:
                        # Already close enough or can't move closer
                        successful_moves += 1
                        continue
                    
                    # Calculate new position
                    new_x = model_start[0] + dx * target_distance
                    new_y = model_start[1] + dy * target_distance
                    new_z = game_map.get_height_at_point(new_x, new_y)
                    new_facing = self.calculate_strategic_facing(new_x, new_y, game_map)
                    
                    # CRITICAL: Validate position before moving to prevent friendly unit overlaps
                    # Import here to avoid circular imports
                    from ..utility.calcs import check_friendly_ending_collision
                    
                    # Check if the new position would collide with friendly units
                    if check_friendly_ending_collision(model, (new_x, new_y, new_z), game_map):
                        # Position would cause collision - try to find alternative position
                        # Try positions at different distances along the same direction
                        alternative_found = False
                        for distance_factor in [0.9, 0.8, 0.7, 0.6, 0.5]:
                            alt_distance = target_distance * distance_factor
                            alt_x = model_start[0] + dx * alt_distance
                            alt_y = model_start[1] + dy * alt_distance
                            alt_z = game_map.get_height_at_point(alt_x, alt_y)
                            
                            if not check_friendly_ending_collision(model, (alt_x, alt_y, alt_z), game_map):
                                # Found a valid alternative position
                                new_x, new_y, new_z = alt_x, alt_y, alt_z
                                target_distance = alt_distance
                                alternative_found = True
                                logger.debug(f"Model {model._id} found alternative charge position at {distance_factor:.1f} of original distance")
                                break
                        
                        if not alternative_found:
                            # No valid position found - skip this model
                            logger.debug(f"Model {model._id} cannot charge - no valid position found without friendly collisions")
                            continue
                    
                    # Move the model to the validated position
                    model.set_location(new_x, new_y, new_z, new_facing)
                    successful_moves += 1
                    
                    actual_distance_moved = get_dist(
                        new_x - model_start[0],
                        new_y - model_start[1],
                        new_z - model_start[2] if len(model_start) > 2 else 0
                    )
                    target_name = target_unit.name if target_unit else "closest enemy"
                    logger.debug(f"Model {model._id} charge moved {actual_distance_moved:.1f}\" towards {closest_enemy.name} (from {target_name})")
        
        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            print(f"❌ {self.name} could not charge - no models could reach any valid positions")
            return False
        
        # CRITICAL VALIDATION: Final check for any overlaps after all models positioned
        # This catches edge cases where models might still overlap despite individual validation
        friendly_units = game_map.get_friendly_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for friendly_unit in friendly_units:
                if friendly_unit == self or not friendly_unit.is_alive() or not friendly_unit.deployed:
                    continue
                for friendly_model in friendly_unit.models:
                    if not friendly_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the friendly model's base
                    if model.model_base.collides_with(friendly_model.model_base):
                        print(f"❌ {self.name} charge failed - {model.name} would overlap with {friendly_model.name} from {friendly_unit.name}")
                        # ROLLBACK: Restore original positions
                        for i, original_pos in enumerate(original_model_positions):
                            if i < len(self.models):
                                self.models[i].set_location(*original_pos)
                        return False
        
        # Get final position for feedback from first model
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
        
        # Calculate actual distance the unit moved
        unit_distance_moved = get_dist(end_x - start_x, end_y - start_y)
        
        # Provide detailed feedback
        print(f"✅ {self.name} moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if successful_moves < len(self.models):
            print(f"⚠️  Note: Only {successful_moves}/{len(self.models)} models could move to valid positions")
        
        # Mark unit as having moved this round
        self.round_state.moved_this_round = True
        
        logger.info(f"Unit {self.name} charge moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        return True

    def fall_back(self, destination: Tuple[float, float, float], path: List[Tuple[float, float, float]], game_map: 'Map') -> bool:
        """Falls back from close combat.
        
        Battle-Shocked units that fall back must take Desperate Escape Tests.
        Units that fall back can move within engagement range and over enemy models,
        but cannot end within engagement range of any enemy models.
        """
        print(f"🏃 {self.name} falls back from combat")
        
        # Check if unit is Battle-Shocked and must take Desperate Escape Test
        if self.is_battle_shocked():
            models_lost = self.take_desperate_escape_test(game_map)
            
            # Check if unit was wiped out during Desperate Escape Test
            if not self.is_alive():
                print(f"💀 {self.name} was completely destroyed during Desperate Escape Test!")
                return False
        
        # Execute Fall Back movement for each model
        if not self.models:
            logger.error(f"Cannot fall back unit {self.name}: no models in unit")
            return False
        
        # Get starting position from first model
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot fall back unit {self.name}: no valid models")
            return False

        first_model_pos = self.models[0].get_location()
        if not first_model_pos:
            logger.error(f"Cannot fall back unit {self.name}: first model has no position")
            return False

        # Store starting position for feedback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0
        
        # Fall Back movement distance is the unit's Move characteristic
        movement_range = self.movement
        
        # Calculate straight-line distance to destination
        distance_to_destination = get_dist(
            destination[0] - start_x,
            destination[1] - start_y,
            destination[2] - start_z
        )
        
                # Check if destination is within movement range
        if distance_to_destination > movement_range:
            print(f"❌ {self.name} cannot reach fall back destination {distance_to_destination:.1f}\" away (max move: {movement_range}\")")
            return False

        # Generate potential positions for models with reduced boundary repulsors for better formation finding
        boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
        potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
        
        # Check if formation finding failed
        if potential_positions is None:
            print(f"❌ {self.name} cannot fall back - no valid formation found at destination")
            return False
            
        successful_moves = 0
        total_models_moved_over_enemies = 0
        
        for model, model_destination in zip(self.models, potential_positions):
            model_start = model.get_location()
            logging.debug(f"Model {model._id} {model.name} attempting to fall back from {model_start} to {model_destination}")
            
            # Calculate straight-line distance for this model
            model_distance = get_dist(
                model_destination[0] - model_start[0],
                model_destination[1] - model_start[1],
                model_destination[2] - model_start[2] if len(model_start) > 2 else 0
            )
            
            # Check if this model can reach its destination
            if model_distance > movement_range:
                print(f"Model {model._id} cannot reach fall back destination {model_distance:.1f}\" away (max: {movement_range}\")")
                continue  # Skip this model, don't move it
            
            # Try enhanced pathfinding for Fall Back movement
            pathfinding_result = a_star_enhanced(model, game_map, model_destination, movement_action=MovementAction.FALL_BACK)
            
            if not pathfinding_result:
                logger.debug(f"Model {model._id} enhanced pathfinding failed for fall back - destination may be invalid")
                continue
            
            shortest_path, enemy_models_moved_over = pathfinding_result
            
            # Calculate path distance
            path_distance = sum(get_dist(shortest_path[i][0] - shortest_path[i-1][0], shortest_path[i][1] - shortest_path[i-1][1]) for i in range(1, len(shortest_path)))
            
            # Check for Desperate Escape Tests (models that move over enemy models)
            if enemy_models_moved_over and not self.is_titanic and not self.is_flying:
                print(f"⚠️  Model {model._id} must take Desperate Escape Test for moving over {len(enemy_models_moved_over)} enemy model(s)")
                
                # Take Desperate Escape Test for this model
                roll = get_roll("D6")
                if roll <= 2:
                    print(f"🎲 Model {model._id}: Rolled {roll} on Desperate Escape Test - DESTROYED! 💀")
                    self.remove_model(model, fleed=True, game_map=game_map)
                    continue  # Model is destroyed, don't move it
                else:
                    print(f"🎲 Model {model._id}: Rolled {roll} on Desperate Escape Test - Survives ✅")
                    total_models_moved_over_enemies += 1
            
            if path_distance > movement_range:
                print(f"Model {model._id} path distance {path_distance:.1f}\" exceeds movement {movement_range}\"")
                # Try to move as far as possible along the path
                last_node = model_start
                model.last_move_path = [last_node]
                distance_along_path = 0.0
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                
                for node in shortest_path[1:]:
                    dx = node[0] - last_node[0]
                    dy = node[1] - last_node[1]
                    dz = node[2] - last_node[2] if len(node) > 2 else 0
                    segment_distance = get_dist(dx, dy, dz)
                    
                    if distance_along_path + segment_distance > movement_range:
                        # Stop here, can't go further
                        break
                    
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                # Move to the furthest reachable position
                if distance_along_path > 0:
                    final_position = model.last_move_path[-1]
                    model.set_location(final_position[0], final_position[1], final_position[2], final_position[3])
                    successful_moves += 1
                    logger.debug(f"Model {model._id} fell back along path to {final_position[:3]}, distance: {distance_along_path:.1f}\"")
            else:
                # Path is within range, move to destination
                model.set_location(*model_destination)
                last_node = model_start
                model.last_move_path = [last_node]
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                distance_along_path = 0.0
                
                for node in shortest_path[1:]:
                    dx = node[0] - last_node[0]
                    dy = node[1] - last_node[1]
                    dz = node[2] - last_node[2] if len(node) > 2 else 0
                    segment_distance = get_dist(dx, dy, dz)
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                successful_moves += 1
                logger.debug(f"Model {model._id} fell back to {model_destination}, path distance: {distance_along_path:.1f}\"")
        
        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            print(f"❌ {self.name} could not fall back - no models could reach valid positions")
            return False
        
        # Check if unit was wiped out during Desperate Escape Tests
        if not self.is_alive():
            print(f"💀 {self.name} was completely destroyed during Fall Back Desperate Escape Tests!")
            return False
        
        # CRITICAL VALIDATION: Check for illegal overlaps after fall back
        # Fall back has special rules - units can move over enemies but cannot end overlapping
        enemy_units = game_map.get_enemy_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for enemy_unit in enemy_units:
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the enemy model's base
                    if model.model_base.collides_with(enemy_model.model_base):
                        print(f"❌ {self.name} cannot fall back - {model.name} cannot end overlapping with {enemy_model.name} from {enemy_unit.name}")
                        # For fall back, we don't have original positions stored, so this is a critical error
                        # The fall back move should have been validated during pathfinding
                        return False
        
        # Get final position for feedback from first model
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
        
        # Calculate actual distance the unit moved
        unit_distance_moved = get_dist(end_x - start_x, end_y - start_y)
        
        # Provide detailed feedback
        print(f"✅ {self.name} fell back from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if total_models_moved_over_enemies > 0:
            print(f"⚔️  {total_models_moved_over_enemies} model(s) moved over enemy models and survived Desperate Escape Tests")
        
        if successful_moves < len(self.models):
            remaining_models = len(self.models)
            print(f"⚠️  Note: Only {successful_moves} models could fall back to valid positions, {remaining_models} models remain")
        
        logger.info(f"Unit {self.name} fell back from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        self.round_state.fell_back_this_round = True
        return True

    def has_advance_and_shoot(self) -> bool:
        """Check if the unit has an ability that allows shooting after advancing.
        
        This checks for unit abilities that allow shooting after advancing,
        based on actual Warhammer 40k ability descriptions.
        
        Returns:
            bool: True if the unit has an ability that allows shooting after advancing
        """
        # Use cached result if available
        if 'advance_and_shoot' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['advance_and_shoot']
        
        # Look for patterns that match actual 40k ability descriptions
        found, _ = self._find_ability_with_patterns([
            "eligible to shoot in a turn in which it advanced",
            "eligible to shoot in a turn in which it fell back or advanced", 
            "eligible to shoot in a turn in which it advanced or fell back",
            "eligible to shoot and declare a charge in a turn in which it advanced",
            "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
            "that unit is eligible to shoot and declare a charge in a turn in which it advanced",
            "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced"
        ])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['advance_and_shoot'] = found
        
        return found

    def has_advance_and_charge(self) -> bool:
        """Check if the unit has an ability that allows charging after advancing.
        
        This checks for unit abilities that allow charging after advancing,
        based on actual Warhammer 40k ability descriptions.
        
        Returns:
            bool: True if the unit has an ability that allows charging after advancing
        """
        # Use cached result if available
        if 'advance_and_charge' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['advance_and_charge']
        
        # Look for patterns that match actual 40k ability descriptions
        found, _ = self._find_ability_with_patterns([
            "eligible to declare a charge in a turn in which it advanced",
            "eligible to charge in a turn in which it advanced",
            "eligible to shoot and declare a charge in a turn in which it advanced",
            "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
            "that unit is eligible to shoot and declare a charge in a turn in which it advanced",
            "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced"
        ])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['advance_and_charge'] = found
        
        return found

    def has_fell_back_and_shoot(self) -> bool:
        """Check if the unit has an ability that allows shooting after falling back.
        
        This checks for unit abilities that allow shooting after falling back,
        based on actual Warhammer 40k ability descriptions.
        
        Returns:
            bool: True if the unit has an ability that allows shooting after falling back
        """
        # Use cached result if available
        if 'fell_back_and_shoot' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['fell_back_and_shoot']
        
        # Look for patterns that match actual 40k ability descriptions
        found, _ = self._find_ability_with_patterns([
            "eligible to shoot in a turn in which it fell back",
            "eligible to shoot in a turn in which it fell back or advanced", 
            "eligible to shoot in a turn in which it advanced or fell back",
            "eligible to shoot and declare a charge in a turn in which it fell back",
            "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
            "that unit is eligible to shoot and declare a charge in a turn in which it fell back",
            "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced"
        ])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['fell_back_and_shoot'] = found
        
        return found

    def can_shoot_after_advance(self, profile) -> bool:
        """Check if this unit can shoot after advancing with the given weapon profile.
        
        A unit can shoot after advancing if either:
        1. The weapon profile is an Assault weapon, OR
        2. The unit has an ability that allows shooting after advancing
        
        Args:
            profile: The weapon profile to check
            
        Returns:
            bool: True if the unit can shoot this weapon after advancing
        """
        # Check for Assault weapons
        if profile.is_assault():
            return True
            
        # Check for unit abilities that allow advance and shoot
        if self.has_advance_and_shoot():
            return True
            
        return False

    def can_shoot_after_fall_back(self, profile) -> bool:
        """Check if this unit can shoot after falling back with the given weapon profile.
        
        A unit can shoot after falling back if either:
        1. The weapon profile is a Pistol weapon, OR
        2. The unit has an ability that allows shooting after falling back
        
        Args:
            profile: The weapon profile to check
            
        Returns:
            bool: True if the unit can shoot this weapon after falling back
        """
        # Check for Pistol weapons (can always shoot after falling back)
        if profile.is_pistol():
            return True
            
        # Check for unit abilities that allow shooting after falling back
        if self.has_fell_back_and_shoot():
            return True
            
        return False

    def can_charge_after_advance(self) -> bool:
        """Check if this unit can charge after advancing.
        
        A unit can charge after advancing if it has an ability that allows it.
        
        Returns:
            bool: True if the unit can charge after advancing
        """
        return self.has_advance_and_charge()

    def scout_move(self, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        """Execute a scout move for the unit during pre-battle rules phase.
        
        Scout moves have special restrictions:
        - Cannot move within engagement range of enemy units
        - Cannot end within 9" of enemy units
        - Cannot charge or advance during scout move
        - Considered a normal move action (terrain rules apply)
        
        Args:
            destination: Target position (x, y, z)
            game_map: The game map for validation and movement
            
        Returns:
            bool: True if scout move was successful
        """
        if not self.models:
            logger.error(f"Cannot scout move unit {self.name}: no models in unit")
            return False
        
        # Check if unit has scout ability
        has_scout, scout_distance = self.has_scout()
        if not has_scout:
            logger.error(f"Unit {self.name} does not have Scout ability")
            return False
        
        # Check if unit has already made a scout move
        if hasattr(self, 'scout_move_made') and self.scout_move_made:
            logger.error(f"Unit {self.name} has already made a scout move")
            return False
        
        # Check if unit is deployed (not in reserves)
        if not self.deployed or self.reserve_status != 'deployed':
            logger.error(f"Unit {self.name} is not deployed and cannot make scout move")
            return False
        
        # Get starting position from first model
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot scout move unit {self.name}: no valid models")
            return False

        first_model_pos = self.models[0].get_location()
        if not first_model_pos:
            logger.error(f"Cannot scout move unit {self.name}: first model has no position")
            return False

        # Store starting position for feedback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0
        
        # Calculate straight-line distance to destination
        distance_to_destination = get_dist(
            destination[0] - start_x,
            destination[1] - start_y,
            destination[2] - start_z
        )
        
        # Check if destination is within scout distance
        if distance_to_destination > scout_distance:
            print(f"❌ {self.name} cannot reach scout destination {distance_to_destination:.1f}\" away (max scout: {scout_distance}\")")
            return False
        
        # Check if destination would end within 9" of enemy units
        enemy_units = game_map.get_enemy_units(self)
        for enemy_unit in enemy_units:
            if not enemy_unit.is_alive() or not enemy_unit.deployed:
                continue
            
            # Check distance to closest model in enemy unit
            closest_distance = float('inf')
            for enemy_model in enemy_unit.models:
                if enemy_model.is_alive:
                    enemy_pos = enemy_model.get_location()
                    if enemy_pos:
                        distance = get_dist(
                            destination[0] - enemy_pos[0],
                            destination[1] - enemy_pos[1],
                            destination[2] - enemy_pos[2] if len(enemy_pos) > 2 else 0
                        )
                        closest_distance = min(closest_distance, distance)

            if closest_distance != float('inf'):
                distance_to_enemy = closest_distance
                
                if distance_to_enemy < 9.0:
                    print(f"❌ {self.name} cannot scout move to destination - would end within 9\" of {enemy_unit.name}")
                    return False
        
        # Generate potential positions for models with reduced boundary repulsors for better formation finding
        boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
        potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
        
        # Check if formation finding failed
        if potential_positions is None:
            print(f"❌ {self.name} cannot scout move - no valid formation found at destination")
            return False
            
        successful_moves = 0
        
        for model, model_destination in zip(self.models, potential_positions):
            model_start = model.get_location()
            logging.debug(f"Model {model._id} {model.name} attempting scout move from {model_start} to {model_destination}")
            
            # Calculate straight-line distance for this model
            model_distance = get_dist(
                model_destination[0] - model_start[0],
                model_destination[1] - model_start[1],
                model_destination[2] - model_start[2] if len(model_start) > 2 else 0
            )
            
            # Check if this model can reach its destination
            if model_distance > scout_distance:
                print(f"Model {model._id} cannot reach scout destination {model_distance:.1f}\" away (max: {scout_distance}\")")
                continue  # Skip this model, don't move it
            
            # Use new optimized pathfinding for scout move (individual model movement)
            from ..utility.calcs import get_individual_model_movement_path
            
            # Find model index for pathfinding
            model_index = None
            for i, m in enumerate(self.models):
                if m == model:
                    model_index = i
                    break
            
            if model_index is None:
                logger.error(f"Could not find model index for {model.name}")
                continue
            
            path = get_individual_model_movement_path(self, model_index, model_destination, game_map, scout_distance)
            
            if not path:
                logger.debug(f"Model {model._id} optimized pathfinding failed for scout move - destination may be invalid")
                continue
            
            # Calculate path distance
            path_distance = sum(get_dist(path[i][0] - path[i-1][0], path[i][1] - path[i-1][1]) for i in range(1, len(path)))
            
            if path_distance > scout_distance:
                print(f"Model {model._id} path distance {path_distance:.1f}\" exceeds scout distance {scout_distance}\"")
                # Try to move as far as possible along the path
                last_node = model_start
                model.last_move_path = [last_node]
                distance_along_path = 0.0
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                
                for node in path[1:]:
                    dx = node[0] - last_node[0]
                    dy = node[1] - last_node[1]
                    dz = node[2] - last_node[2] if len(node) > 2 else 0
                    segment_distance = get_dist(dx, dy, dz)
                    
                    if distance_along_path + segment_distance > scout_distance:
                        # Stop here, can't go further
                        break
                    
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                # Move to the furthest reachable position
                if distance_along_path > 0:
                    final_position = model.last_move_path[-1]
                    model.set_location(final_position[0], final_position[1], final_position[2], final_position[3])
                    successful_moves += 1
                    logger.debug(f"Model {model._id} scout moved along path to {final_position[:3]}, distance: {distance_along_path:.1f}\"")
            else:
                # Path is within range, move to destination
                model.set_location(*model_destination)
                last_node = model_start
                model.last_move_path = [last_node]
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                distance_along_path = 0.0
                
                for node in path[1:]:
                    dx = node[0] - last_node[0]
                    dy = node[1] - last_node[1]
                    dz = node[2] - last_node[2] if len(node) > 2 else 0
                    segment_distance = get_dist(dx, dy, dz)
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                successful_moves += 1
                logger.debug(f"Model {model._id} scout moved to {model_destination}, path distance: {distance_along_path:.1f}\"")
        
        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            print(f"❌ {self.name} could not scout move - no models could reach valid positions")
            return False
        
        # NEW: Validate unit coherency after all models have moved (scout moves must maintain coherency)
        from ..utility.calcs import validate_unit_coherency_after_movement
        
        # Get final positions of all models
        final_positions = []
        for model in self.models:
            final_positions.append(model.get_location())
        
        is_coherent, non_coherent_models = validate_unit_coherency_after_movement(self, final_positions)
        
        if not is_coherent:
            print(f"⚠️  {self.name} coherency violation after scout move!")
            print(f"⚠️  Models {non_coherent_models} are not coherent and must be removed from play")
            
            # Remove non-coherent models from play
            for model_index in sorted(non_coherent_models, reverse=True):
                if model_index < len(self.models):
                    model = self.models[model_index]
                    print(f"💀 Removing {model.name} from play due to coherency violation")
                    # Set wounds to 0 to make the model dead (is_alive property checks wounds > 0)
                    model.wounds = 0
                    # Call die() method to properly remove the model from the unit
                    model.die()
                    
            # Unit position is now determined by model positions
            
            # Check if unit is still viable
            if not self.is_alive():
                print(f"💀 {self.name} has been destroyed due to coherency violations")
                return False
        
        # CRITICAL VALIDATION: Check for illegal overlaps after scout move
        # Scout moves cannot end overlapping with enemy models
        enemy_units = game_map.get_enemy_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for enemy_unit in enemy_units:
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the enemy model's base
                    if model.model_base.collides_with(enemy_model.model_base):
                        print(f"❌ {self.name} cannot scout move - {model.name} cannot end overlapping with {enemy_model.name} from {enemy_unit.name}")
                        # For scout move, we don't have original positions stored, so this is a critical error
                        # The scout move should have been validated during pathfinding
                        return False
        
        # Get final position for feedback from first model
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
        
        # Calculate actual distance the unit moved
        unit_distance_moved = get_dist(end_x - start_x, end_y - start_y)
        
        # Mark unit as having made a scout move
        self.scout_move_made = True
        
        # Provide detailed feedback
        print(f"🔍 {self.name} scout moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if successful_moves < len(self.models):
            print(f"⚠️  Note: Only {successful_moves}/{len(self.models)} models could scout move to valid positions")
        
        logger.info(f"Unit {self.name} scout moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        return True

    def can_shoot_in_engagement_range(self, game_map: 'Map', profile=None) -> bool:
        """Check if this unit can shoot while in engagement range with the given weapon profile."""
        # Check if unit is in engagement range
        is_engaged = any(game_map.is_within_engagement_range(self, enemy)
                        for enemy in game_map.get_enemy_units(self) if enemy.is_alive())
        
        if not is_engaged:
            return True
            
        # If engaged and no profile provided, assume cannot shoot
        if profile is None:
            return False
            
        # Check for Pistol weapons
        if profile.is_pistol():
            return True
        # Check for Indirect Fire weapons
        if profile.is_indirect_fire():
            return True
        # Vehicles can shoot while engaged
        if self.is_vehicle:
            return True
        # TODO: Add checks for unit abilities that allow shooting in engagement
        # Example: if self.has_ability("shoot_in_engagement"):
        #     return True
        return False

    def can_shoot_at_target_while_engaged(self, target, profile, game_map) -> bool:
        """Check if this unit can shoot at a specific target while engaged with other units."""
        # If unit is not in engagement range, they can always shoot
        if not any(game_map.is_within_engagement_range(self, enemy)
                  for enemy in game_map.get_enemy_units(self) if enemy.is_alive()):
            return True
        # If target is the unit we're engaged with, only Pistols can shoot
        if any(game_map.is_within_engagement_range(self, enemy)
              for enemy in [target] if enemy.is_alive()):
            return profile.is_pistol()
        # If target is not the unit we're engaged with:
        # - Vehicles can shoot at other targets
        # - Other units cannot shoot at other targets while engaged
        return self.is_vehicle

    ###########################################################################
    ### Shooting Phase Actions
    ###########################################################################
    def execute_shooting_declarations(self, weapon_declarations: List[dict], game_map: 'Map') -> bool:
        """
        Execute shooting declarations according to Warhammer 40k rules.
        
        Args:
            weapon_declarations: List of dicts with keys:
                - 'weapon_profile': WargearProfile to use
                - 'target_unit': Unit to target
                - 'models': List of models using this weapon
            game_map: Map instance for line of sight and range checks
            
        Returns:
            bool: True if any attacks were successful
        """
        if not weapon_declarations:
            print(f"❌ {self.name}: No shooting declarations to execute")
            return False
            
        # Check if unit can shoot
        if self.round_state.shot_this_round:
            print(f"❌ {self.name} has already shot this round")
            return False
            
        if self.round_state.fell_back_this_round:
            # Check if any weapons in the declarations can shoot after falling back
            can_shoot_any_weapon = False
            for declaration in weapon_declarations:
                if self.can_shoot_after_fall_back(declaration['weapon_profile']):
                    can_shoot_any_weapon = True
                    break
            
            if not can_shoot_any_weapon:
                print(f"❌ {self.name} cannot shoot after falling back")
                return False
            
        print(f"🎯 {self.name} executing {len(weapon_declarations)} shooting declarations...")
        
        # Mark unit as having shot this round (regardless of success)
        self.round_state.shot_this_round = True
        
        successful_attacks = 0
        
        # Execute each weapon declaration
        for declaration in weapon_declarations:
            weapon_profile = declaration['weapon_profile']
            target_unit = declaration['target_unit']
            models_with_weapon = declaration['models']
            weapon_instance = declaration.get('weapon_instance', None)
            
            # Validate this declaration
            validation = self._validate_shooting_declaration(weapon_profile, target_unit, models_with_weapon, game_map)
            if not validation['valid']:
                print(f"❌ {self.name} - {weapon_profile.name}: {validation['reason']}")
                continue
                
            # Execute attacks with this weapon
            weapon_attacks = self._execute_weapon_attacks(weapon_profile, target_unit, models_with_weapon, game_map, weapon_instance)
            successful_attacks += weapon_attacks
            
        # Report shooting results
        if successful_attacks > 0:
            print(f"✅ {self.name} completed shooting with {successful_attacks} attacks executed")
            
            # Check if target unit was destroyed
            for declaration in weapon_declarations:
                target_unit = declaration['target_unit']
                if not target_unit.is_alive():
                    print(f"💀 {target_unit.name} has been destroyed!")
        else:
            print(f"❌ {self.name} failed to execute any attacks")
            
        return successful_attacks > 0
    
    def _validate_shooting_declaration(self, weapon_profile, target_unit, models_with_weapon, game_map) -> dict:
        """Validate a shooting declaration"""
        # Check if target is an enemy unit
        if target_unit.get_parent_army() == self.get_parent_army():
            return {"valid": False, "reason": "Cannot target friendly units"}
        
        # Check if target is alive
        if not target_unit.is_alive():
            return {"valid": False, "reason": "Target unit is destroyed"}
        
        # Check if unit can shoot after advancing
        if self.round_state.advanced_this_round:
            # Unit method already checks both weapon-specific and unit-specific abilities
            if not self.can_shoot_after_advance(weapon_profile):
                return {"valid": False, "reason": "Unit advanced and cannot shoot with this weapon"}
        
        # Check if unit can shoot after falling back
        if self.round_state.fell_back_this_round:
            if not self.can_shoot_after_fall_back(weapon_profile):
                return {"valid": False, "reason": "Unit fell back and cannot shoot with this weapon"}
        
        # Check if any models can actually shoot this weapon at the target
        models_in_range = []
        for model in models_with_weapon:
            if not model.is_alive:
                continue
                
            # Check if this model has the weapon
            has_weapon = False
            for wargear in model.wargear:
                if weapon_profile.parent_wargear == wargear:
                    has_weapon = True
                    break
            
            if not has_weapon:
                continue
                
            # Check range and line of sight
            if self._can_model_shoot_weapon_at_target(model, weapon_profile, target_unit, game_map):
                models_in_range.append(model)
        
        if not models_in_range:
            return {"valid": False, "reason": "No models in range or line of sight"}
            
        return {"valid": True, "reason": "Valid shooting declaration"}
    
    def _can_model_shoot_weapon_at_target(self, model, weapon_profile, target_unit, game_map) -> bool:
        """Check if a specific model can shoot a weapon at a target"""
        # Check range using edge-to-edge distance (not centroid-to-centroid)
        min_distance = float('inf')
        for target_model in target_unit.models:
            if not target_model.is_alive:
                continue
            # Calculate edge-to-edge distance between model bases
            distance = model.model_base.edge_to_edge_distance(target_model.model_base)
            min_distance = min(min_distance, distance)
        
        if min_distance > weapon_profile.range.max:
            return False
            
        # Check line of sight
        if not self._has_line_of_sight_to_target(model, target_unit, game_map):
            return False
            
        # Check engagement range restrictions
        if not self._can_shoot_while_engaged(model, weapon_profile, target_unit, game_map):
            return False
            
        return True
    
    def _has_line_of_sight_to_target(self, shooting_model, target_unit, game_map) -> bool:
        """Check if shooting model has line of sight to target unit"""
        # Simplified line of sight check - can be enhanced with terrain
        shooting_pos = shooting_model.get_location()
        # Get position from first alive model in target unit
        target_pos = None
        for model in target_unit.models:
            if model.is_alive:
                target_pos = model.get_location()
                break
        
        if not shooting_pos or not target_pos:
            return False
            
        # For now, assume line of sight unless blocked by terrain
        # TODO: Implement proper line of sight checking with terrain
        return True
    
    def _can_shoot_while_engaged(self, model, weapon_profile, target_unit, game_map) -> bool:
        """Check if model can shoot while engaged with other units"""
        # Check if unit is in engagement range
        is_engaged = any(game_map.is_within_engagement_range(self, enemy)
                        for enemy in game_map.get_enemy_units(self) if enemy.is_alive())
        
        if not is_engaged:
            return True
            
        # If engaged, check weapon type and target
        if weapon_profile.is_pistol():
            return True
            
        if weapon_profile.is_indirect_fire():
            return True
            
        if self.is_vehicle:
            return True
            
        # Check if target is the unit we're engaged with
        if game_map.is_within_engagement_range(self, target_unit):
            return weapon_profile.is_pistol()
            
        # If target is different from engaged unit, only vehicles can shoot
        return self.is_vehicle
    
    def _execute_weapon_attacks(self, weapon_profile, target_unit, models_with_weapon, game_map, weapon_instance=None) -> int:
        """Execute attacks with a specific weapon profile"""
        successful_attacks = 0
        
        for model in models_with_weapon:
            if not model.is_alive:
                continue
                
            # Check if this model can still shoot this weapon at this target
            if not self._can_model_shoot_weapon_at_target(model, weapon_profile, target_unit, game_map):
                continue
                
            # Verify the model has this weapon
            has_weapon = False
            for wargear in model.wargear:
                for profile_name, profile in wargear.profiles.items():
                    if profile == weapon_profile:
                        has_weapon = True
                        break
                if has_weapon:
                    break
            
            if not has_weapon:
                continue
                
            # Execute the attack - each declaration represents exactly one weapon firing
            try:
                weapon_display = f"{weapon_profile.parent_wargear.name}"
                if weapon_instance:
                    weapon_display += f" #{weapon_instance}"
                print(f"🎯 {model.name} attacking with {weapon_display}")
                
                # Execute the attack using the weapon profile
                weapon_profile.attack(target_unit, model)
                # Count successful execution of the attack (not damage dealt)
                successful_attacks += 1
            except Exception as e:
                print(f"❌ Error executing attack with {weapon_profile.name}: {e}")
                # Don't increment successful_attacks if there was an exception
                
        return successful_attacks

    # Fight Phase Actions
    def pile_in(self, target_units: List['Unit']) -> None:
        """Moves up to 3 inches towards the nearest enemy unit."""
        # Logic to move closer
        print(f"{self.name} piles in.")

    def fight(self, target_unit: 'Unit') -> None:
        """Engages in close combat with the target unit."""
        for model in self.models:
            for weapon in model.wargear:
                if weapon.is_melee():
                    weapon.attack(model, target_unit)
        print(f"{self.name} fights {target_unit.name} in close combat.")

    def consolidate(self):
        """Moves up to 3 inches after fighting."""
        # Logic to move further into enemy lines
        print(f"{self.name} consolidates after combat.")
    
    def pile_in_towards_enemies(self, game_map: 'Map') -> bool:
        """Execute a pile-in move according to official Warhammer 40k rules.
        
        Pile-In Rules:
        - Only models NOT already in base-to-base contact with enemy models can move
        - Each model can move up to 3 inches
        - Unit must end within Engagement Range of one or more enemy units
        - Unit must maintain Unit Coherency after all moves
        - Each model must end closer to the CLOSEST enemy model
        - Models must get into base-to-base contact if possible while satisfying conditions
        - If conditions cannot be met, NO models can pile in
        
        Args:
            game_map: The game map to find enemy units and calculate distances
            
        Returns:
            bool: True if pile-in was executed successfully
        """
        if not self.is_alive() or not self.deployed:
            return False
        
        # Find all enemy units
        enemy_units = game_map.get_enemy_units(self)
        alive_enemies = [enemy for enemy in enemy_units if enemy.is_alive()]
        
        if not alive_enemies:
            print(f"   {self.name} has no enemies to pile in towards")
            return False
        
        # Get all enemy models for distance calculations
        all_enemy_models = []
        for enemy_unit in alive_enemies:
            all_enemy_models.extend([model for model in enemy_unit.models if model.is_alive])
        
        if not all_enemy_models:
            print(f"   {self.name} has no enemy models to pile in towards")
            return False
        
        # Identify models that can pile in (not already in base-to-base contact)
        models_that_can_pile_in = []
        for model in self.models:
            if not model.is_alive:
                continue
            
            # Check if this model is already in base-to-base contact with any enemy model
            is_in_base_contact = self._is_model_in_base_to_base_contact(model, all_enemy_models, game_map)
            
            if not is_in_base_contact:
                models_that_can_pile_in.append(model)
        
        if not models_that_can_pile_in:
            print(f"   {self.name} has no models that can pile in (all already in base-to-base contact)")
            return True  # This is successful - unit is already fully engaged
        
        # Check if pile-in is possible while maintaining coherency and engagement range
        # For now, this is a simplified check - a full implementation would require 
        # complex pathfinding and collision detection
        if not self._can_pile_in_while_maintaining_conditions(models_that_can_pile_in, all_enemy_models, game_map):
            print(f"   {self.name} cannot pile in while maintaining unit coherency and engagement range")
            return False
        
        # Execute pile-in moves (simplified implementation)
        print(f"   {self.name} executes pile-in moves:")
        successful_moves = 0
        
        # Player chooses order - for AI, we'll use a simple heuristic (closest models first)
        models_that_can_pile_in.sort(key=lambda m: self._get_distance_to_closest_enemy_model(m, all_enemy_models))
        
        for model in models_that_can_pile_in:
            success = self._execute_model_pile_in(model, all_enemy_models, game_map)
            if success:
                successful_moves += 1
                print(f"     {model.name} piles in towards closest enemy")
            else:
                print(f"     {model.name} cannot pile in")
        
        if successful_moves > 0:
            print(f"   {successful_moves}/{len(models_that_can_pile_in)} models successfully piled in")
            return True
        else:
            print(f"   No models could successfully pile in")
            return False
    
    def _is_model_in_base_to_base_contact(self, model: 'Model', enemy_models: List['Model'], game_map: 'Map') -> bool:
        """Check if a model is in base-to-base (edge-to-edge) contact with any enemy model."""
        # Check actual base edge distances for engagement range and base-to-base contact
        for enemy_model in enemy_models:
            # Calculate edge-to-edge distance between model bases
            horizontal_distance = model.model_base.edge_to_edge_distance(enemy_model.model_base)
            
            # Calculate vertical distance  
            vertical_distance = model.model_base.vertical_distance(enemy_model.model_base)
            
            # Check if within engagement range (1" horizontally, 5" vertically)
            from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
            if (horizontal_distance <= ENGAGEMENT_RANGE_HORIZONTAL and
                vertical_distance <= ENGAGEMENT_RANGE_VERTICAL):
                # Further check if they're actually touching for base-to-base contact
                if horizontal_distance <= 0.1:  # Very close for base-to-base contact
                    return True
        
        return False
    
    def _can_pile_in_while_maintaining_conditions(self, models: List['Model'], enemy_models: List['Model'], game_map: 'Map') -> bool:
        """Check if the unit can pile in while maintaining coherency and engagement range."""
        # Simplified check - in a full implementation this would simulate the moves
        # and verify all conditions are met
        
        # Basic check: ensure unit will still be in engagement range after pile-in
        # This is a placeholder for more complex logic
        return True
    
    def _get_distance_to_closest_enemy_model(self, model: 'Model', enemy_models: List['Model']) -> float:
        """Get the distance from a model to the closest enemy model."""
        min_distance = float('inf')
        
        for enemy_model in enemy_models:
            # Calculate distance between models
            dx = enemy_model.x - model.x
            dy = enemy_model.y - model.y
            dz = enemy_model.z - model.z
            distance = (dx*dx + dy*dy + dz*dz) ** 0.5
            
            if distance < min_distance:
                min_distance = distance
        
        return min_distance
    
    def _execute_model_pile_in(self, model: 'Model', enemy_models: List['Model'], game_map: 'Map') -> bool:
        """Execute pile-in move for a single model."""
        # Find the closest enemy model
        closest_enemy = None
        closest_distance = float('inf')
        
        for enemy_model in enemy_models:
            distance = self._get_distance_to_closest_enemy_model(model, [enemy_model])
            if distance < closest_distance:
                closest_distance = distance
                closest_enemy = enemy_model
        
        if not closest_enemy:
            return False
        
        # Calculate direction towards closest enemy
        dx = closest_enemy.x - model.x
        dy = closest_enemy.y - model.y
        distance_to_enemy = (dx*dx + dy*dy) ** 0.5
        
        if distance_to_enemy == 0:
            return False  # Already at same position
        
        # Normalize direction
        dx /= distance_to_enemy
        dy /= distance_to_enemy
        
        # Move up to 3" towards the closest enemy, but ensure we get closer
        max_move_distance = 3.0
        actual_move_distance = min(max_move_distance, distance_to_enemy - 0.1)  # Get closer but don't overshoot
        
        if actual_move_distance <= 0:
            return False
        
        # Calculate new position
        new_x = model.x + dx * actual_move_distance
        new_y = model.y + dy * actual_move_distance
        new_z = game_map.get_height_at_point(new_x, new_y)
        
        # For now, just update the model position
        # In a full implementation, this would check for collisions, coherency, etc.
        model.set_location(new_x, new_y, new_z, model.facing)
        
        return True
    
    def consolidate_towards_enemies(self, game_map: 'Map') -> bool:
        """Execute a consolidate move according to official Warhammer 40k rules.
        
        Consolidation Rules:
        - Only models NOT already in base-to-base contact with enemy models can move
        - Each model can move up to 3 inches
        - Unit must end within Engagement Range of one or more enemy units AND in Unit Coherency
        - If enemy consolidation impossible, try consolidating towards closest OBJECTIVE marker
        - If objective consolidation also impossible, no consolidation occurs
        - Each model MUST end closer to the closest enemy model (or objective)
        - Models must get into base-to-base contact if possible while satisfying conditions
        - Player chooses the ORDER in which to move models
        
        Args:
            game_map: The game map to find enemy units and calculate distances
            
        Returns:
            bool: True if consolidation was executed successfully
        """
        if not self.is_alive() or not self.deployed:
            return False
        
        # Find enemy units to consolidate towards
        enemy_units = game_map.get_enemy_units(self)
        alive_enemies = [enemy for enemy in enemy_units if enemy.is_alive()]
        
        # Get all enemy models
        all_enemy_models = []
        for enemy_unit in alive_enemies:
            all_enemy_models.extend([model for model in enemy_unit.models if model.is_alive])
        
        # Identify models that can consolidate (not already in base-to-base contact)
        models_that_can_consolidate = []
        for model in self.models:
            if not model.is_alive:
                continue
            
            # Check if this model is already in base-to-base contact with any enemy model
            is_in_base_contact = self._is_model_in_base_to_base_contact(model, all_enemy_models, game_map)
            
            if not is_in_base_contact:
                models_that_can_consolidate.append(model)
        
        if not models_that_can_consolidate:
            print(f"   {self.name} has no models that can consolidate (all already in base-to-base contact)")
            return True  # This is successful - unit is already fully engaged
        
        # Try consolidating towards enemies first
        if all_enemy_models and self._can_consolidate_towards_enemies(models_that_can_consolidate, all_enemy_models, game_map):
            return self._execute_enemy_consolidation(models_that_can_consolidate, all_enemy_models, game_map)
        
        # If enemy consolidation impossible, try consolidating towards objectives
        objectives = game_map.objectives if hasattr(game_map, 'objectives') else []
        if objectives:
            closest_objective = self._find_closest_objective(objectives)
            if closest_objective and self._can_consolidate_towards_objective(models_that_can_consolidate, closest_objective, game_map):
                return self._execute_objective_consolidation(models_that_can_consolidate, closest_objective, game_map)
        
        # If neither enemy nor objective consolidation is possible, no consolidation occurs
        print(f"   {self.name} cannot consolidate towards enemies or objectives while maintaining conditions")
        return False
    
    def _can_consolidate_towards_enemies(self, models: List['Model'], enemy_models: List['Model'], game_map: 'Map') -> bool:
        """Check if the unit can consolidate towards enemies while maintaining conditions."""
        # Simplified check - in a full implementation this would simulate the moves
        # and verify engagement range and coherency are maintained
        
        # Basic check: ensure unit will still be in engagement range after consolidation
        # This is a placeholder for more complex logic
        return True
    
    def _can_consolidate_towards_objective(self, models: List['Model'], objective, game_map: 'Map') -> bool:
        """Check if the unit can consolidate towards an objective while maintaining conditions."""
        # Simplified check - verify unit can end within range of objective and maintain coherency
        # This is a placeholder for more complex logic
        return True
    
    def _find_closest_objective(self, objectives: List) -> Optional[object]:
        """Find the closest objective to this unit."""
        if not objectives:
            return None

        if not self.models:
            return objectives[0]  # Fallback to first objective

        closest_objective = None
        closest_distance = float('inf')

        for objective in objectives:
            if hasattr(objective, 'location') and hasattr(objective.location, 'x'):
                obj_pos = (objective.location.x, objective.location.y, objective.location.z)

                # Find the model in this unit that's closest to this objective
                min_distance_to_obj = float('inf')
                for model in self.models:
                    if model.is_alive:
                        model_pos = model.get_location()
                        distance = get_dist(model_pos[0] - obj_pos[0],
                                          model_pos[1] - obj_pos[1],
                                          model_pos[2] - obj_pos[2])
                        if distance < min_distance_to_obj:
                            min_distance_to_obj = distance

                # Check if this objective is the closest overall
                if min_distance_to_obj < closest_distance:
                    closest_distance = min_distance_to_obj
                    closest_objective = objective
        
        return closest_objective
    
    def _execute_enemy_consolidation(self, models: List['Model'], enemy_models: List['Model'], game_map: 'Map') -> bool:
        """Execute consolidation towards enemy models."""
        print(f"   {self.name} consolidates towards enemies:")
        successful_moves = 0
        
        # Player chooses order - for AI, we'll use a simple heuristic (closest models first)
        models.sort(key=lambda m: self._get_distance_to_closest_enemy_model(m, enemy_models))
        
        for model in models:
            success = self._execute_model_enemy_consolidate(model, enemy_models, game_map)
            if success:
                successful_moves += 1
                print(f"     {model.name} consolidates towards closest enemy")
            else:
                print(f"     {model.name} cannot consolidate towards enemies")
        
        if successful_moves > 0:
            print(f"   {successful_moves}/{len(models)} models successfully consolidated towards enemies")
            return True
        else:
            print(f"   No models could consolidate towards enemies")
            return False
    
    def _execute_objective_consolidation(self, models: List['Model'], objective, game_map: 'Map') -> bool:
        """Execute consolidation towards an objective marker."""
        print(f"   {self.name} consolidates towards objective '{objective.name}':")
        successful_moves = 0
        
        # Player chooses order - for AI, we'll use distance to objective
        models.sort(key=lambda m: self._get_distance_to_objective(m, objective))
        
        for model in models:
            success = self._execute_model_objective_consolidate(model, objective, game_map)
            if success:
                successful_moves += 1
                print(f"     {model.name} consolidates towards objective")
            else:
                print(f"     {model.name} cannot consolidate towards objective")
        
        if successful_moves > 0:
            print(f"   {successful_moves}/{len(models)} models successfully consolidated towards objective")
            return True
        else:
            print(f"   No models could consolidate towards objective")
            return False
    
    def _execute_model_enemy_consolidate(self, model: 'Model', enemy_models: List['Model'], game_map: 'Map') -> bool:
        """Execute consolidate move for a single model towards enemies."""
        # Find the closest enemy model
        closest_enemy = None
        closest_distance = float('inf')
        
        for enemy_model in enemy_models:
            distance = self._get_distance_to_closest_enemy_model(model, [enemy_model])
            if distance < closest_distance:
                closest_distance = distance
                closest_enemy = enemy_model
        
        if not closest_enemy:
            return False
        
        # Calculate direction towards closest enemy
        dx = closest_enemy.x - model.x
        dy = closest_enemy.y - model.y
        distance_to_enemy = (dx*dx + dy*dy) ** 0.5
        
        if distance_to_enemy == 0:
            return False  # Already at same position
        
        # Normalize direction
        dx /= distance_to_enemy
        dy /= distance_to_enemy
        
        # Move up to 3" towards the closest enemy, but ensure we get closer
        max_move_distance = 3.0
        actual_move_distance = min(max_move_distance, distance_to_enemy - 0.1)  # Get closer but don't overshoot
        
        if actual_move_distance <= 0:
            return False
        
        # Calculate new position
        new_x = model.x + dx * actual_move_distance
        new_y = model.y + dy * actual_move_distance
        new_z = game_map.get_height_at_point(new_x, new_y)
        
        # Update model position
        # In a full implementation, this would check for collisions, coherency, etc.
        model.set_location(new_x, new_y, new_z, model.facing)
        
        return True
    
    def _execute_model_objective_consolidate(self, model: 'Model', objective, game_map: 'Map') -> bool:
        """Execute consolidate move for a single model towards an objective."""
        if not hasattr(objective, 'location') or not hasattr(objective.location, 'x'):
            return False
        
        # Calculate direction towards objective
        dx = objective.location.x - model.x
        dy = objective.location.y - model.y
        distance_to_objective = (dx*dx + dy*dy) ** 0.5
        
        if distance_to_objective == 0:
            return False  # Already at same position
        
        # Normalize direction
        dx /= distance_to_objective
        dy /= distance_to_objective
        
        # Move up to 3" towards the objective, but ensure we get closer
        max_move_distance = 3.0
        actual_move_distance = min(max_move_distance, distance_to_objective - 0.1)  # Get closer but don't overshoot
        
        if actual_move_distance <= 0:
            return False
        
        # Calculate new position
        new_x = model.x + dx * actual_move_distance
        new_y = model.y + dy * actual_move_distance
        new_z = game_map.get_height_at_point(new_x, new_y)
        
        # Update model position
        # In a full implementation, this would check for collisions, coherency, etc.
        model.set_location(new_x, new_y, new_z, model.facing)
        
        return True
    
    def _get_distance_to_objective(self, model: 'Model', objective) -> float:
        """Get the distance from a model to an objective."""
        if not hasattr(objective, 'location') or not hasattr(objective.location, 'x'):
            return float('inf')
        
        dx = objective.location.x - model.x
        dy = objective.location.y - model.y
        return (dx*dx + dy*dy) ** 0.5

    # Battle-shock Phase Actions
    def take_battle_shock_test(self, current_turn: int = 1):
        """Takes a battle shock test.
        
        Args:
            current_turn: The current battle round number (used for status effect duration)
        """
        # Check if unit is already battle-shocked
        is_already_battle_shocked = any(
            isinstance(effect, BattleShockEffect) for effect in self.status_effects
        )
        
        if is_already_battle_shocked:
            print(f"⚡ {self.name} is already battle-shocked, no test needed")
            return

        if not self.pass_leadership_check():
            battle_shock_effect = BattleShockEffect(current_turn)
            self.apply_status_effect(battle_shock_effect)
            print(f"💥 {self.name} has failed the battle shock test and is battle-shocked!")

    def use_ability(self, ability: Ability, target: 'Unit', game_map: 'Map'):
        """Uses a special ability."""
        from .map import Map  # Import inside the function
        assert isinstance(game_map, Map)
        if ability:
            ability.activate(self)
            print(f"{self.name} uses ability: {ability.name}.")
        else:
            print(f"{self.name} does not have ability: {ability.name}.")

    def embark(self, transport_unit: 'Unit') -> None:
        """Embarks onto a transport unit."""
        if transport_unit.can_transport(self):
            transport_unit.add_passenger(self)
            print(f"{self.name} embarks onto {transport_unit.name}.")
        else:
            print(f"{self.name} cannot embark onto {transport_unit.name}.")

    def disembark(self) -> None:
        """Disembarks from a transport unit."""
        # Logic to disembark
        print(f"{self.name} disembarks from transport.")

    def take_damage(self, amount: int):
        pass
    
    def apply_status_effect(self, status_effect: StatusEffect) -> None:
        status_effect.apply_effect(self)
        self.status_effects.append(status_effect)
    
    def remove_status_effect(self, status_effect: StatusEffect) -> None:
        status_effect.remove_effect(self)
        self.status_effects.remove(status_effect)

    ###########################################################################
    ### Position and Coherency
    ###########################################################################
    def is_alive(self) -> bool:
        return len(self.models) > 0



    def is_point_inside(self, x, y):
        # Check if point is within any model's base
        for model in self.models:
            if not model.is_alive:
                continue
            model_pos = model.get_location()
            if model_pos:
                # Check if point is within model's base radius
                model_radius = getattr(model.model_base, 'radius', 1.0)
                if isinstance(model_radius, (tuple, list)):
                    model_radius = max(model_radius)  # Use larger radius for elliptical bases
                distance = get_dist(x - model_pos[0], y - model_pos[1])
                if distance <= model_radius:
                    return True
        return False

    def score_position(self, x, y, z, facing, game_map, model, placed_positions):
        """
        Score a candidate position for model placement.
        Lower is better. 
        You can enhance this to factor in more things: cover, distance to objective, edge, enemy, etc.
        """
        # Simple version: maximize coherency, avoid edge, avoid obstacles.
        battlefield_width, battlefield_height = game_map.width, game_map.height

        # Distance from board edge (prefer center)
        min_x_dist = min(x, battlefield_width - x)
        min_y_dist = min(y, battlefield_height - y)
        edge_penalty = max(0, 6.0 - min(min_x_dist, min_y_dist)) * 10  # penalize <6" from edge

        # Penalty if near obstacle/impassable (could use game_map.query_cover here)
        cover_bonus = 0
        # TODO: add more logic for proximity to cover/terrain if you want

        # Coherency bonus (number of coherent neighbors)
        coherent_neighbors = 0
        for pos in placed_positions:
            other_x, other_y, other_z, other_facing = pos
            # Assume unit has .coherency_distance
            dist = get_dist(x - other_x, y - other_y, z - other_z)
            if dist <= self.coherency_distance:
                coherent_neighbors += 1
        # Encourage more neighbors
        coherency_bonus = -coherent_neighbors * 20

        return edge_penalty + cover_bonus + coherency_bonus

    def _get_reduced_boundary_repulsors(self, game_map: 'Map') -> List:
        """Get reduced boundary repulsors for formation finding during movement.
        
        These are smaller than the full battlefield edge repulsors to allow better
        formation finding in crowded areas while still preventing units from going
        off the battlefield.
        """
        from shapely.geometry import Polygon
        
        repulsors = []
        repulsor_thickness = 0.25  # Reduced from 0.5 to 0.25 inches
        
        # Left battlefield edge repulsor (reduced)
        left_edge = Polygon([
            (-repulsor_thickness, -repulsor_thickness),
            (0, -repulsor_thickness),
            (0, game_map.height + repulsor_thickness),
            (-repulsor_thickness, game_map.height + repulsor_thickness)
        ])
        repulsors.append(left_edge)
        
        # Right battlefield edge repulsor (reduced)
        right_edge = Polygon([
            (game_map.width, -repulsor_thickness),
            (game_map.width + repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, game_map.height + repulsor_thickness),
            (game_map.width, game_map.height + repulsor_thickness)
        ])
        repulsors.append(right_edge)
        
        # Bottom battlefield edge repulsor (reduced)
        bottom_edge = Polygon([
            (-repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, 0),
            (-repulsor_thickness, 0)
        ])
        repulsors.append(bottom_edge)
        
        # Top battlefield edge repulsor (reduced)
        top_edge = Polygon([
            (-repulsor_thickness, game_map.height),
            (game_map.width + repulsor_thickness, game_map.height),
            (game_map.width + repulsor_thickness, game_map.height + repulsor_thickness),
            (-repulsor_thickness, game_map.height + repulsor_thickness)
        ])
        repulsors.append(top_edge)
        
        return repulsors

    def calculate_strategic_facing(self, x: float, y: float, game_map: 'Map') -> float:
        """Calculate strategic facing direction towards enemies or objectives"""
        
        # Get our army to determine enemies
        army = self.get_parent_army()
        if not army:
            return 0.0  # Default facing if no army context
        
        best_target = None
        min_distance = float('inf')
        
        # Priority 1: Face nearest visible enemy unit
        for unit in game_map.units:
            if unit != self and unit.get_parent_army() != army and unit.is_alive():
                # Find the closest model in the enemy unit to our position
                closest_enemy_distance = float('inf')
                closest_enemy_pos = None

                for model in unit.models:
                    if model.is_alive:
                        enemy_pos = model.get_location()
                        distance = get_dist(x - enemy_pos[0], y - enemy_pos[1])
                        if distance < closest_enemy_distance:
                            closest_enemy_distance = distance
                            closest_enemy_pos = enemy_pos

                if closest_enemy_pos and closest_enemy_distance < min_distance:
                    min_distance = closest_enemy_distance
                    best_target = closest_enemy_pos
        
        # Priority 2: If no enemies, face towards objectives
        if not best_target and hasattr(game_map, 'objectives'):
            for objective in game_map.objectives:
                obj_pos = (objective.location.x, objective.location.y)
                distance = get_dist(x - obj_pos[0], y - obj_pos[1])
                if distance < min_distance:
                    min_distance = distance
                    best_target = obj_pos
        
        # Priority 3: Face towards center of battlefield
        if not best_target:
            center_x = game_map.width / 2
            center_y = game_map.height / 2
            best_target = (center_x, center_y)
        
        # Calculate angle to target
        dx = best_target[0] - x
        dy = best_target[1] - y
        return get_angle(dy, dx)

    def calculate_model_positions(self,
                                start_x: float,
                                start_y: float,
                                game_map: 'Map',
                                grid_step=0.5,
                                relax_iters=5,
                                avoid_friendly_units=True,
                                boundary_repulsors=None):
        """
        Computes (x, y, z, facing) for each model in self.models.
        Tries formation templates (block, wedge, circle, column) built 
        with safe spacing based on base size; falls back to per-model A*.
        
        Args:
            start_x: Target X coordinate for unit placement
            start_y: Target Y coordinate for unit placement
            game_map: The game map
            grid_step: Step size for pathfinding grid (default 0.5)
            relax_iters: Number of relaxation iterations (default 5)
            avoid_friendly_units: Whether to avoid collisions with friendly units
            boundary_repulsors: Optional list of boundary repulsor polygons to avoid
            
        Returns:
            List of (x, y, z, facing) tuples for each model, or None if failed
        """
        if not self.models:
            return []

        if boundary_repulsors is None:
            boundary_repulsors = []

        # Single model - use fast path
        if len(self.models) == 1:
            z = game_map.get_height_at_point(start_x, start_y)
            self.models[0].set_location(start_x, start_y, z, 0.0)
            return [(start_x, start_y, z, 0.0)]

        print(f"🔍 DEBUG: calculate_model_positions for {self.name} ({len(self.models)} models)")
        print(f"🔍 DEBUG: start position: ({start_x:.1f}, {start_y:.1f})")
        print(f"🔍 DEBUG: avoid_friendly_units: {avoid_friendly_units}")
        print(f"🔍 DEBUG: boundary_repulsors: {len(boundary_repulsors) if boundary_repulsors else 0}")

        # FAST PATH FOR SINGLE-MODEL UNITS (avoid terrain & enemy models)
        if len(self.models) == 1:
            print(f"🔍 DEBUG: Using single-model fast path")
            # initial drop
            z = game_map.get_height_at_point(start_x, start_y)
            f = self.calculate_strategic_facing(start_x, start_y, game_map)
            pos = [start_x, start_y, z, f]
            m = self.models[0]

            # Build list of blocking models (enemies + optionally friendlies)
            blocking_models = game_map.get_enemy_models(self)
            if avoid_friendly_units:
                # Add friendly models from other units (excluding self)
                friendly_models = []
                for unit in game_map.get_friendly_units(self):
                    if unit != self:  # Don't include models from the unit being positioned
                        friendly_models.extend(unit.models)
                blocking_models.extend(friendly_models)
            
            # Use provided boundary repulsors or default to empty list
            if boundary_repulsors is None:
                boundary_repulsors = []
            
            # one-off spatial index of terrain + blocking models + boundary repulsors
            tree = build_spatial_index(game_map.obstacles + boundary_repulsors, blocking_models)

            # relax away from any collisions
            for _ in range(relax_iters):
                # build the model's polygon at its trial spot
                base = m.model_base.get_base_shape()
                poly = translate(base,
                                pos[0] - base.centroid.x,
                                pos[1] - base.centroid.y)

                # check for collisions with terrain/enemy/friendly/boundary blockers
                hits = query_spatial_index(tree, poly)
                # if no intersection, we're done
                # DEBUG: Add defensive programming to catch geometry type errors
                try:
                    if not any(poly.intersects(b) for b in hits):
                        break
                except TypeError as e:
                    print(f"DEBUG: TypeError in single-model intersects check: {e}")
                    print(f"DEBUG: poly type: {type(poly)}")
                    print(f"DEBUG: hits count: {len(hits)}")
                    for i, hit in enumerate(hits):
                        print(f"DEBUG: hit {i}: {type(hit)} - {hit}")
                        if hasattr(hit, 'geom_type'):
                            print(f"DEBUG:   geom_type: {hit.geom_type}")
                        if hasattr(hit, 'is_valid'):
                            print(f"DEBUG:   is_valid: {hit.is_valid}")
                    raise

                # repel vector from first blocker
                b = next(b for b in hits if poly.intersects(b))
                vx = poly.centroid.x - b.centroid.x
                vy = poly.centroid.y - b.centroid.y
                norm = get_dist(vx, vy) or 1.0
                pos[0] += (vx / norm) * grid_step
                pos[1] += (vy / norm) * grid_step
                pos[2] = game_map.get_height_at_point(pos[0], pos[1])

            # commit and return
            m.set_location(*pos)
            print(f"🔍 DEBUG: Single-model positioning successful")
            return [(pos[0], pos[1], pos[2], pos[3])]

        print(f"🔍 DEBUG: Using multi-model formation templates")
        # SLOW PATH FOR MULTI-MODEL UNITS
        # 1) Build list of blocking models (enemies + optionally friendlies)
        enemy_models = game_map.get_enemy_models(self)
        blocking_models = enemy_models
        print(f"🔍 DEBUG: Found {len(enemy_models)} enemy models")
        
        if avoid_friendly_units:
            # Add friendly models from other units (excluding self)
            friendly_models = []
            for unit in game_map.get_friendly_units(self):
                if unit != self:  # Don't include models from the unit being positioned
                    friendly_models.extend(unit.models)
            blocking_models.extend(friendly_models)
            print(f"🔍 DEBUG: Added {len(friendly_models)} friendly models from other units")
        
        print(f"🔍 DEBUG: Total blocking models: {len(blocking_models)} (enemies: {len(enemy_models)}, friendlies: {len(blocking_models) - len(enemy_models)})")
        
        # 2) Use provided boundary repulsors or default to empty list
        if boundary_repulsors is None:
            boundary_repulsors = []
        
        # 3) Spatial index of obstacles + blocking models + boundary repulsors
        tree = build_spatial_index(game_map.obstacles + boundary_repulsors, blocking_models)

        # 4) Compute safe spacing from the model base shape
        # Use tighter spacing for deployment to allow formations to fit in crowded areas
        # Models can be in base-to-base contact (spacing = 2 * radius) but we allow slightly tighter
        base_radius = self.models[0].model_base.radius[0]
        spacing = 2 * base_radius * 0.8  # 80% of full spacing allows for tighter formations
        print(f"🔍 DEBUG: Computed spacing: {spacing:.2f} inches (base radius: {base_radius:.2f})")

        # 5) Build formation templates
        templates = build_formation_templates(len(self.models), spacing)
        print(f"🔍 DEBUG: Generated {len(templates)} formation templates: {list(templates.keys())}")

        origin_2d = np.array((start_x, start_y), float)

        # 6) Try each template
        for template_name, offsets in templates.items():
            print(f"🔍 DEBUG: Trying template '{template_name}' with {len(offsets)} positions")
            
            # world positions in 2D & then lift to 3D + facing
            world = []
            pts2d = offsets + origin_2d
            for x, y in pts2d:
                z = game_map.get_height_at_point(x, y)
                f = self.calculate_strategic_facing(x, y, game_map)
                world.append([x, y, z, f])

            # Check individual model base collisions instead of unit footprint
            # This allows unit footprints to overlap as long as individual model bases don't overlap
            model_collision_detected = False
            for i, (dx, dy) in enumerate(offsets):
                model_x = origin_2d[0] + dx
                model_y = origin_2d[1] + dy
                
                # Create temporary model base at this position
                temp_model = self.models[i] if i < len(self.models) else self.models[0]
                temp_base = temp_model.model_base.get_base_shape()
                temp_base_positioned = translate(temp_base, 
                                               model_x - temp_base.centroid.x,
                                               model_y - temp_base.centroid.y)
                
                # Check collision with obstacles and enemy models only
                # (friendly unit avoidance is handled by the avoid_friendly_units parameter)
                base_hits = query_spatial_index(tree, temp_base_positioned)
                if len(base_hits) > 0:
                    # Check if any hits are actual overlaps (not just touching)
                    for hit in base_hits:
                        if temp_base_positioned.overlaps(hit):
                            model_collision_detected = True
                            break
                    if model_collision_detected:
                        break
            
            if model_collision_detected:
                print(f"🔍 DEBUG: Template '{template_name}' rejected - model base overlap detected")
                continue

            print(f"🔍 DEBUG: Template '{template_name}' passed footprint check, starting relaxation")

            # Relaxation loop (terrain + self-collisions)
            for relax_iter in range(relax_iters):
                collided = False
                
                # precompute friendly polys at current trial positions
                friendly = []
                for idx, pos in enumerate(world):
                    base = self.models[idx].model_base.get_base_shape()
                    friendly.append(
                        translate(base, 
                                pos[0] - base.centroid.x, 
                                pos[1] - base.centroid.y)
                    )

                for i, pos in enumerate(world):
                    poly_i = friendly[i]
                    # gather blockers as a pure Python list
                    hits = query_spatial_index(tree, poly_i) \
                        + [p for j,p in enumerate(friendly) if j != i]

                    # DEBUG: Add defensive programming to catch geometry type errors
                    try:
                        intersects_any = any(poly_i.intersects(b) for b in hits)
                    except TypeError as e:
                        print(f"DEBUG: TypeError in multi-model intersects check: {e}")
                        print(f"DEBUG: poly_i type: {type(poly_i)}")
                        print(f"DEBUG: hits count: {len(hits)}")
                        for idx, hit in enumerate(hits):
                            print(f"DEBUG: hit {idx}: {type(hit)} - {hit}")
                            if hasattr(hit, 'geom_type'):
                                print(f"DEBUG:   geom_type: {hit.geom_type}")
                            if hasattr(hit, 'is_valid'):
                                print(f"DEBUG:   is_valid: {hit.is_valid}")
                        raise
                    
                    if intersects_any:
                        # repel along the vector between centroids
                        b = next(b for b in hits if poly_i.intersects(b))
                        vx = poly_i.centroid.x - b.centroid.x
                        vy = poly_i.centroid.y - b.centroid.y
                        norm = get_dist(vx, vy) or 1.0
                        pos[0] += (vx / norm) * grid_step
                        pos[1] += (vy / norm) * grid_step
                        pos[2] = game_map.get_height_at_point(pos[0], pos[1])
                        collided = True
                        
                if not collided:
                    print(f"🔍 DEBUG: Template '{template_name}' completed relaxation after {relax_iter + 1} iterations")
                    break
                elif relax_iter == relax_iters - 1:
                    print(f"🔍 DEBUG: Template '{template_name}' still had collisions after {relax_iters} relaxation iterations")

            # after you've cleared collisions…
            attract_iters = 5
            attract_step = 0.2
            target_min = 0.25
            for _ in range(attract_iters):
                moved = False
                for i, m1 in enumerate(self.models):
                    for j, m2 in enumerate(self.models[i+1:], start=i+1):
                        d = m1.model_base.edge_to_edge_distance(m2.model_base)
                        if d > target_min + 1e-6:
                            # move each halfway toward the other
                            dx = (m2.x - m1.x)
                            dy = (m2.y - m1.y)
                            norm = get_dist(dx, dy)
                            shift = min(attract_step, d/2) / norm
                            m1.model_base.x += dx * shift
                            m1.model_base.y += dy * shift
                            m2.model_base.x -= dx * shift
                            m2.model_base.y -= dy * shift
                            moved = True
                if not moved:
                    break

            # Final overlap catcher
            final_polys = []
            for idx, pos in enumerate(world):
                base = self.models[idx].model_base.get_base_shape()
                final_polys.append(
                    translate(base,
                            pos[0] - base.centroid.x,
                            pos[1] - base.centroid.y)
                )

            # if any true-area overlap, reject this template
            ok = True
            for i in range(len(final_polys)):
                for j in range(i+1, len(final_polys)):
                    if final_polys[i].overlaps(final_polys[j]):
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                print(f"🔍 DEBUG: Template '{template_name}' rejected - final overlap check failed")
                continue

            # Commit & coherency‐graph check
            for m, pos in zip(self.models, world):
                m.set_location(*pos)
                
            coherency_ok = self.check_coherency_graph()
            print(f"🔍 DEBUG: Template '{template_name}' coherency check: {'✅ PASSED' if coherency_ok else '❌ FAILED'}")
            
            if coherency_ok:
                print(f"🔍 DEBUG: Successfully found formation using template '{template_name}'")
                return [(x, y, z, f) for x, y, z, f in world]
            else:
                print(f"🔍 DEBUG: Template '{template_name}' rejected - coherency check failed")

        # 7) If none fit, raise or fallback
        print(f"🔍 DEBUG: All {len(templates)} templates failed - no valid formation found")
        # No valid formation found - return None instead of raising exception
        # This allows auto-deployment to try other positions
        return None

    def _create_potential_base(self, x: float, y: float, z: float, facing: float, model: Model = None):
        # Create a new base with the same properties as the specified model's base
        if model is None:
            model = self.models[0]  # Default to first model
        new_base = copy.deepcopy(model.model_base)
        new_base.x, new_base.y, new_base.z = x, y, z
        new_base.set_facing(facing)
        return new_base

    def _collides_with_unit_models(self, x: float, y: float, z: float, facing: float, positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        """Check if the model at the given position collides with any other model in the unit."""
        if not positions:
            return False

        if len(self.models) == 1:
            return False

        new_base = self._create_potential_base(x, y, z, facing, model)

        for i, pos in enumerate(positions):
            # Use the corresponding model for each position
            other_model = self.models[i] if i < len(self.models) else self.models[0]
            other_base = self._create_potential_base(pos[0], pos[1], pos[2], pos[3], other_model)
            if new_base.collides_with(other_base):
                logger.debug(f"Collision detected!")
                return True
        return False

    def _is_coherent_within_unit(self, x: float, y: float, z: float, facing: float, positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        """Check if the model at the given position is within coherency with the unit."""
        new_base = self._create_potential_base(x, y, z, facing, model)

        # Check against already placed models
        found_neighbors = 0
        current_neighbors_needed = 0 if len(positions) == 0 else 1 if len(positions) == 1 else self.required_neighbors

        if current_neighbors_needed == 0:
            return True

        for i, pos in enumerate(positions):
            # Use the corresponding model for each position
            other_model = self.models[i] if i < len(self.models) else self.models[0]
            other_base = self._create_potential_base(pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0, pos[3] if len(pos) > 3 else facing, other_model)
            if new_base.edge_to_edge_distance(other_base) <= self.coherency_distance:
                found_neighbors += 1
                if found_neighbors >= current_neighbors_needed:
                    return True
        return False

    def check_coherency_graph(self):
        """
        Returns True if every model in the unit
        has the required number of neighbors within edge-to-edge
        coherency_distance.

        - Units of 1–5 models: each model needs at least 1 neighbor.
        - Units of 6+ models: each model needs at least 2 neighbors.
        """
        models = self.models

        for i, m1 in enumerate(models):
            neighbors = 0
            for j, m2 in enumerate(models):
                if i == j:
                    continue
                # use the real edge-to-edge distance between bases
                d = m1.model_base.edge_to_edge_distance(m2.model_base)
                if d <= self.coherency_distance + 1e-6:
                    neighbors += 1
                if neighbors >= self.required_neighbors:
                    break

            if neighbors < self.required_neighbors:
                return False

        return True


    def _is_valid_position(self, x: float, y: float, z: float, facing: float, game_map: 'Map', placed_positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        if model is None:
            model = self.models[0]  # Use the first model as a reference
        if not game_map.is_within_boundary(model, (x, y)):
            return False
        if game_map.check_collision_with_obstacles(model, (x, y)):
            return False
        if game_map.check_collision_with_other_friendly_units(model, (x, y)):
            return False
        if game_map.check_collision_with_other_enemy_units(model, (x, y)):
            return False
        if self._collides_with_unit_models(x, y, z, facing, placed_positions, model):
            return False
        if not self._is_coherent_within_unit(x, y, z, facing, placed_positions, model):
            return False
        return True


    ###########################################################################
    ### Range and Line of Sight
    ###########################################################################
    def maximum_range(self) -> int:
        """Maximum range of the unit."""
        if hasattr(self, 'max_shooting_range'):
            return self.max_shooting_range

        max_range = 0
        for model in self.models:
            max_range = max(max_range, model.maximum_range())
        self.max_shooting_range = max_range
        return max_range

    def find_targets_in_range(self, game_map: 'Map') -> List['Unit']:
        targets = []
        enemy_units = game_map.get_enemy_units(self)
        for enemy_unit in enemy_units:
            for enemy_model in enemy_unit.models:
                in_range = False
                for model in self.models:
                    if get_dist(model.x - enemy_model.x, model.y - enemy_model.y, model.z - enemy_model.z) < model.maximum_range():
                        in_range = True
                        break
                if in_range:
                    # TODO - Check line of sight
                    targets.append(enemy_unit)
                    break
        return targets

    def print_unit(self) -> str:
        return f"{self.name} :: M: {self.movement}\", T: {self.toughness}, Sv: {self.save}, InvSv: {self.inv_save}, OC: {self.objective_control}"

    ###########################################################################
    ### Dunder Methods
    ###########################################################################
    def __str__(self):
        return f"{self.name} ({len(self.models)} models)"

    def __repr__(self):
        return f"Unit(name='{self.name}', models={len(self.models)})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Unit):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def can_declare_charge_against(self, target_unit: 'Unit', game: 'Game') -> bool:
        """Check if this unit can declare a charge against the target unit."""
        if not self.is_alive() or not target_unit.is_alive():
            return False
            
        # Check if unit has already charged this round
        if self.round_state.declared_charge_this_round:
            return False
            
        if self.round_state.advanced_this_round and not self.can_charge_after_advance():
            return False
            
        if self.round_state.fell_back_this_round:
            return False
        
        # Check if unit arrived from reserves this turn and has special charge restrictions
        if self.arrived_from_reserves_this_turn and not self.can_charge_after_arriving_from_reserves():
            return False
            
        # CRITICAL: Units already within engagement range cannot declare charges
        # They are already considered to be "in combat"
        if game.map.is_within_engagement_range(self, target_unit):
            return False
            
        # Check if target is within maximum charge range (2D6 = max 12")
        distance = game.map.get_distance_between_units(self, target_unit)
        if distance > self.max_charge_distance:
            return False
            
        # Check if there's a clear charge path
        # This is simplified - in real 40k you can charge around terrain
        if game.map.is_path_blocked(self, target_unit):
            return False
            
        return True

    def get_threat_value(self) -> float:
        """Calculate the total threat value of this unit."""
        ranged_threat, melee_threat = self.get_threat_level()
        return ranged_threat + melee_threat

    def get_overwatch_risk(self, charging_unit: 'Unit', game: 'Game') -> float:
        """Calculate the risk this unit poses in overwatch to a charging unit.
        
        Args:
            charging_unit (Unit): The unit attempting to charge
            game (Game): The game instance for distance calculations
            
        Returns:
            float: Risk value from 0.0 to 1.0, where higher values indicate more risk
        """
        # Base risk on our ranged threat level
        ranged_threat, _ = self.get_threat_level()
        
        # Modify based on distance (closer = more dangerous)
        distance = game.get_distance_between_units(charging_unit, self)
        distance_modifier = 1.0 / max(distance, 1.0)  # Avoid division by zero
        
        # Consider if we've already shot this round
        if self.round_state.shot_this_round:
            ranged_threat *= 0.5  # Reduced effectiveness if already shot
            
        # Consider remaining CP for stratagems
        army = self.get_parent_army()
        if army and army.player:
            cp_modifier = min(1.0, army.player.command_points / 3.0)  # Scale based on available CP
            ranged_threat *= (1.0 + cp_modifier)  # More CP = more potential threats
        
        return ranged_threat * distance_modifier
    
    def _find_ability_with_patterns(self, patterns: List[str], extract_value: bool = False, value_pattern: str = None) -> Tuple[bool, Optional[str]]:
        r"""
        Helper method to find abilities matching given patterns and optionally extract values.
        
        Args:
            patterns: List of patterns to search for (case-insensitive)
            extract_value: Whether to extract a value from the matched text
            value_pattern: Regex pattern to extract value (e.g., r'(\d+)' for numbers, r'(\d+|D\d+)' for dice)
        
        Returns:
            Tuple[bool, Optional[str]]: (found, extracted_value)
        """
        # Check keywords first
        for keyword in self.keywords:
            for pattern in patterns:
                if pattern.lower() in keyword.lower():
                    if extract_value and value_pattern:
                        match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', keyword.lower())
                        if match:
                            return True, match.group(1)
                        else:
                            raise ValueError(f"{pattern} ability found in keyword '{keyword}' but could not extract value for unit '{self.name}'")
                    else:
                        return True, None
        
        # Check unit-level abilities (possible_abilities)
        for ability in self.possible_abilities:
            if isinstance(ability, str):
                for pattern in patterns:
                    if pattern.lower() in ability.lower():
                        if extract_value and value_pattern:
                            match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.lower())
                            if match:
                                return True, match.group(1)
                            else:
                                raise ValueError(f"{pattern} ability found in ability string '{ability}' but could not extract value for unit '{self.name}'")
                        else:
                            return True, None
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, 'name') and ability.name:
                    for pattern in patterns:
                        if pattern.lower() in ability.name.lower():
                            ability_name_matched = True
                            if extract_value and value_pattern:
                                match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.name.lower())
                                if match:
                                    return True, match.group(1)
                                else:
                                    # Check if ability has a parameter attribute
                                    if hasattr(ability, 'parameter') and ability.parameter:
                                        param_match = re.search(value_pattern, ability.parameter)
                                        if param_match:
                                            return True, param_match.group(1)
                                        else:
                                            raise ValueError(f"{pattern} ability found in ability name '{ability.name}' with parameter '{ability.parameter}' but could not extract value for unit '{self.name}'")
                                    else:
                                        raise ValueError(f"{pattern} ability found in ability name '{ability.name}' but could not extract value for unit '{self.name}'")
                            else:
                                return True, None
                
                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, 'description') and ability.description:
                    for pattern in patterns:
                        if pattern.lower() in ability.description.lower():
                            if extract_value and value_pattern:
                                match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.description.lower())
                                if match:
                                    return True, match.group(1)
                                else:
                                    raise ValueError(f"{pattern} ability found in ability description '{ability.description}' but could not extract value for unit '{self.name}'")
                            else:
                                return True, None
        
        # Check model-level abilities
        for ability in self.abilities:
            if isinstance(ability, str):
                for pattern in patterns:
                    if pattern.lower() in ability.lower():
                        if extract_value and value_pattern:
                            match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.lower())
                            if match:
                                return True, match.group(1)
                            else:
                                raise ValueError(f"{pattern} ability found in model ability string '{ability}' but could not extract value for unit '{self.name}'")
                        else:
                            return True, None
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, 'name') and ability.name:
                    for pattern in patterns:
                        if pattern.lower() in ability.name.lower():
                            ability_name_matched = True
                            if extract_value and value_pattern:
                                match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.name.lower())
                                if match:
                                    return True, match.group(1)
                                else:
                                    # Check if ability has a parameter attribute
                                    if hasattr(ability, 'parameter') and ability.parameter:
                                        param_match = re.search(value_pattern, ability.parameter)
                                        if param_match:
                                            return True, param_match.group(1)
                                        else:
                                            raise ValueError(f"{pattern} ability found in model ability name '{ability.name}' with parameter '{ability.parameter}' but could not extract value for unit '{self.name}'")
                                    else:
                                        raise ValueError(f"{pattern} ability found in model ability name '{ability.name}' but could not extract value for unit '{self.name}'")
                            else:
                                return True, None
                
                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, 'description') and ability.description:
                    for pattern in patterns:
                        if pattern.lower() in ability.description.lower():
                            if extract_value and value_pattern:
                                match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.description.lower())
                                if match:
                                    return True, match.group(1)
                                else:
                                    raise ValueError(f"{pattern} ability found in model ability description '{ability.description}' but could not extract value for unit '{self.name}'")
                            else:
                                return True, None
        
        return False, None

    def has_deep_strike(self) -> bool:
        """Check if the unit has Deep Strike ability."""
        # Use cached result if available
        if 'deep_strike' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['deep_strike']
        
        found, _ = self._find_ability_with_patterns(["deep strike", "deepstrike"])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['deep_strike'] = found
        
        return found

    def has_infiltrate(self) -> bool:
        """Check if the unit has Infiltrate ability."""
        # Use cached result if available
        if 'infiltrate' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['infiltrate']
        
        found, _ = self._find_ability_with_patterns(["infiltrators", "infiltrate"])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['infiltrate'] = found
        
        return found
    
    def has_stealth(self) -> bool:
        """Check if the unit has Stealth ability."""
        # Use cached result if available
        if 'stealth' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['stealth']
        
        found, _ = self._find_ability_with_patterns(["stealth"])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['stealth'] = found
        
        return found
    
    def has_scout(self) -> Tuple[bool, float]:
        """Check if the unit has Scout ability and return the scout distance.
        
        Returns:
            Tuple[bool, float]: A tuple containing:
                - A boolean indicating if the unit has Scout ability
                - The scout distance in inches (0.0 if no Scout ability)
        """
        # Use cached result if available
        if 'scout' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['scout']
        
        found, distance_str = self._find_ability_with_patterns(["scout"], extract_value=True, value_pattern=r'(\d+)')
        result = (True, float(distance_str)) if found else (False, 0.0)
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['scout'] = result
        
        return result
    
    def get_scout_distance_normalized(self, max_scout_distance: float = 12.0) -> float:
        """Get the normalized scout distance for deployment considerations.
        
        Args:
            max_scout_distance (float): Maximum possible scout distance for normalization
            
        Returns:
            float: Normalized scout distance (0.0 to 1.0), where 1.0 represents maximum scout mobility
        """
        has_scout_ability, scout_distance = self.has_scout()
        if not has_scout_ability:
            return 0.0
        
        return min(scout_distance / max_scout_distance, 1.0)
    
    def has_firing_deck(self) -> Tuple[bool, int]:
        """Check if the unit has Firing Deck ability and return the number of weapons.
        
        Returns:
            Tuple[bool, int]: A tuple containing:
                - A boolean indicating if the unit has Firing Deck ability
                - The number of weapons that can fire from the deck (0 if no Firing Deck ability)
        """
        found, number_str = self._find_ability_with_patterns(["firing deck"], extract_value=True, value_pattern=r'(\d+)')
        if found:
            return True, int(number_str)
        return False, 0
    
    def has_fight_first(self) -> bool:
        """Check if the unit has Fight First ability.
        
        Fight First abilities can come from various sources:
        - Unit keywords like "Fight First"
        - Ability names like "Fights First", "Combat Reflexes", etc.
        - Descriptions containing fight first rules
        
        Returns:
            bool: True if the unit has any Fight First ability
        """
        # Use cached result if available
        if 'fight_first' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['fight_first']
        
        found, _ = self._find_ability_with_patterns([
            "fight first", 
            "fights first", 
            "combat reflexes",
            "lightning reflexes",
            "swift strike",
            "martial prowess"
        ])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['fight_first'] = found
        
        return found
    
    def is_eligible_to_fight(self, game_map: 'Map') -> bool:
        """Check if the unit is eligible to fight in the Fight Phase.
        
        A unit is eligible to fight if:
        a) it is within engagement range of one or more enemy units, OR
        b) it made a charge move this turn (current player's turn)
        
        Args:
            game_map: The game map to check for enemy units and engagement range
            
        Returns:
            bool: True if the unit is eligible to fight
        """
        if not self.is_alive() or not self.deployed:
            return False
        
        # Check if unit charged this turn - units that charged can always fight
        if self.round_state.declared_charge_this_round:
            return True
        
        # Check if unit is within engagement range of any enemy unit
        enemy_units = game_map.get_enemy_units(self)
        for enemy_unit in enemy_units:
            if enemy_unit.is_alive() and game_map.is_within_engagement_range(self, enemy_unit):
                return True
        
        return False
    
    def should_fight_first(self) -> bool:
        """Check if this unit should fight in the Fight First stage.
        
        Units fight first if they:
        1. Have an inherent Fight First ability, OR
        2. Charged this turn
        
        Returns:
            bool: True if the unit should fight in the Fight First stage
        """
        # Units that charged this turn fight first
        if self.round_state.declared_charge_this_round:
            return True
            
        # Units with Fight First abilities fight first
        if self.has_fight_first():
            return True
        
        return False
    
    def has_deadly_demise(self) -> Tuple[bool, DiceCollection]:
        """Check if the unit has Deadly Demise ability and return the damage value.
        
        Returns:
            Tuple[bool, DiceCollection]: A tuple containing:
                - A boolean indicating if the unit has Deadly Demise ability
                - A DiceCollection object representing the damage value (e.g., "3", "D3", "D6") or None if no Deadly Demise ability
        """
        # Use cached result if available
        if 'deadly_demise' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['deadly_demise']
        
        found, damage_str = self._find_ability_with_patterns(["deadly demise"], extract_value=True, value_pattern=r'(\d+|D\d+)')
        if found:
            try:
                dice_collection = DiceCollection.from_string(damage_str)
                result = (True, dice_collection)
            except ValueError:
                raise ValueError(f"Deadly Demise ability found but could not parse damage value '{damage_str}' for unit '{self.name}'")
        else:
            result = (False, None)
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['deadly_demise'] = result
        
        return result

    def _find_all_abilities_with_patterns(self, patterns: List[str], value_pattern: str) -> List[Tuple[int, Optional[str]]]:
        """
        Helper method to find all instances of abilities matching given patterns and extract values with conditions.
        Used specifically for Feel No Pain which can have multiple instances with conditions.
        
        Args:
            patterns: List of patterns to search for (case-insensitive)
            value_pattern: Regex pattern to extract value and optional condition
        
        Returns:
            List[Tuple[int, Optional[str]]]: List of (dice_value, condition) tuples
        """
        found_abilities = []
        
        # Check keywords first
        for keyword in self.keywords:
            for pattern in patterns:
                if pattern.lower() in keyword.lower():
                    match = re.search(value_pattern, keyword.lower())
                    if match:
                        dice_value = int(match.group(1))
                        condition = match.group(2).strip() if match.group(2) else None
                        found_abilities.append((dice_value, condition))
                    else:
                        raise ValueError(f"{pattern} ability found in keyword '{keyword}' but could not extract dice value for unit '{self.name}'")
        
        # Check unit-level abilities (possible_abilities)
        for ability in self.possible_abilities:
            if isinstance(ability, str):
                for pattern in patterns:
                    if pattern.lower() in ability.lower():
                        match = re.search(value_pattern, ability.lower())
                        if match:
                            dice_value = int(match.group(1))
                            condition = match.group(2).strip() if match.group(2) else None
                            found_abilities.append((dice_value, condition))
                        else:
                            raise ValueError(f"{pattern} ability found in ability string '{ability}' but could not extract dice value for unit '{self.name}'")
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, 'name') and ability.name:
                    for pattern in patterns:
                        if pattern.lower() in ability.name.lower():
                            ability_name_matched = True
                            match = re.search(value_pattern, ability.name.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                # Check if ability has a parameter attribute (e.g., "5+")
                                if hasattr(ability, 'parameter') and ability.parameter:
                                    param_match = re.search(r'(\d+)\+', ability.parameter)
                                    if param_match:
                                        dice_value = int(param_match.group(1))
                                        found_abilities.append((dice_value, None))
                                    else:
                                        raise ValueError(f"{pattern} ability found in ability name '{ability.name}' with parameter '{ability.parameter}' but could not extract dice value for unit '{self.name}'")
                                else:
                                    raise ValueError(f"{pattern} ability found in ability name '{ability.name}' but could not extract dice value for unit '{self.name}'")
                
                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, 'description') and ability.description:
                    for pattern in patterns:
                        if pattern.lower() in ability.description.lower():
                            match = re.search(value_pattern, ability.description.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                raise ValueError(f"{pattern} ability found in ability description '{ability.description}' but could not extract dice value for unit '{self.name}'")
        
        # Check model-level abilities
        for ability in self.abilities:
            if isinstance(ability, str):
                for pattern in patterns:
                    if pattern.lower() in ability.lower():
                        match = re.search(value_pattern, ability.lower())
                        if match:
                            dice_value = int(match.group(1))
                            condition = match.group(2).strip() if match.group(2) else None
                            found_abilities.append((dice_value, condition))
                        else:
                            raise ValueError(f"{pattern} ability found in model ability string '{ability}' but could not extract dice value for unit '{self.name}'")
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, 'name') and ability.name:
                    for pattern in patterns:
                        if pattern.lower() in ability.name.lower():
                            ability_name_matched = True
                            match = re.search(value_pattern, ability.name.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                # Check if ability has a parameter attribute (e.g., "5+")
                                if hasattr(ability, 'parameter') and ability.parameter:
                                    param_match = re.search(r'(\d+)\+', ability.parameter)
                                    if param_match:
                                        dice_value = int(param_match.group(1))
                                        found_abilities.append((dice_value, None))
                                    else:
                                        raise ValueError(f"{pattern} ability found in model ability name '{ability.name}' with parameter '{ability.parameter}' but could not extract dice value for unit '{self.name}'")
                                else:
                                    raise ValueError(f"{pattern} ability found in model ability name '{ability.name}' but could not extract dice value for unit '{self.name}'")
                
                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, 'description') and ability.description:
                    for pattern in patterns:
                        if pattern.lower() in ability.description.lower():
                            match = re.search(value_pattern, ability.description.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                raise ValueError(f"{pattern} ability found in model ability description '{ability.description}' but could not extract dice value for unit '{self.name}'")
        
        return found_abilities

    def has_feel_no_pain(self) -> List[Tuple[int, Optional[str]]]:
        """Check if the unit has Feel No Pain abilities and return all of them.
        
        Returns:
            List[Tuple[int, Optional[str]]]: A list of tuples containing:
                - The dice roll needed (e.g., 5 for "5+", 6 for "6+")
                - Optional condition string (e.g., "against psychic attacks", "against mortal wounds") (None if unconditional)
        """
        # Use cached result if available
        if 'feel_no_pain' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['feel_no_pain']
        
        result = self._find_all_abilities_with_patterns(
            ["feel no pain", "fnp"], 
            r'(?:feel no pain|fnp)\s*\(?(\d+)\+(?:\)?)(?:\s+(.+))?'
        )
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['feel_no_pain'] = result
        
        return result

    def get_max_weapon_range(self) -> float:
        """Get the maximum range of all weapons in the unit."""
        max_range = 0
        for model in self.models:
            for weapon in model.wargear:
                # Skip melee weapons
                if weapon.is_melee():
                    continue
                
                # Get the maximum range from all profiles
                for profile in weapon.profiles.values():
                    if hasattr(profile, 'range') and profile.range and hasattr(profile.range, 'max'):
                        max_range = max(max_range, profile.range.max)
        
        return max_range

    ###########################################################################
    ### Reserves System
    ###########################################################################
    # Units arriving from reserves (including Deep Strike) have the following restrictions:
    # - CANNOT move normally or advance (unless special rules allow it)
    # - CAN shoot, charge, and fight normally (this is the default rule)
    # - Only special rules would prevent charging/shooting after arriving from reserves
    def set_reserve_status(self, status: str) -> None:
        """Set the reserve status of the unit.
        
        Args:
            status: 'deployed', 'reserves', 'strategic_reserves'
        """
        valid_statuses = ['deployed', 'reserves', 'strategic_reserves']
        if status not in valid_statuses:
            raise ValueError(f"Invalid reserve status: {status}. Must be one of {valid_statuses}")
        
        self.reserve_status = status
        # Note: deployed flag is managed separately by deployment logic
        # deployed=True means deployment decision made, deployed=False means needs decision
        
    def is_in_reserves(self) -> bool:
        """Check if the unit is currently in reserves (any type)."""
        return self.reserve_status in ['reserves', 'strategic_reserves']
    
    def is_in_standard_reserves(self) -> bool:
        """Check if the unit is in standard reserves (Deep Strike, etc.)."""
        return self.reserve_status == 'reserves'
    
    def is_in_strategic_reserves(self) -> bool:
        """Check if the unit is in strategic reserves."""
        return self.reserve_status == 'strategic_reserves'
    
    def can_arrive_from_reserves(self, current_turn: int) -> bool:
        """Check if the unit can arrive from reserves this turn.
        
        Args:
            current_turn: The current battle round number
        
        Returns:
            bool: True if the unit can arrive from reserves this turn
        """
        if not self.is_in_reserves():
            return False
        
        # Units cannot arrive from reserves on Turn 1
        if current_turn < 2:
            return False
        
        # Units must arrive by end of Turn 3 or be destroyed
        if current_turn > 3:
            return False
        
        return True
    
    def must_arrive_from_reserves(self, current_turn: int) -> bool:
        """Check if the unit must arrive from reserves this turn or be destroyed.
        
        Args:
            current_turn: The current battle round number
        
        Returns:
            bool: True if the unit must arrive this turn or be destroyed
        """
        return self.is_in_reserves() and current_turn >= 3
    
    def arrive_from_reserves(self, position: Tuple[float, float, float], turn: int, game_map: Optional['Map'] = None) -> bool:
        """Deploy the unit from reserves at the specified position.
        
        Args:
            position: (x, y, z) coordinates where the unit should be placed
            turn: Current turn number
        
        Returns:
            bool: True if deployment was successful
        """
        if not self.can_arrive_from_reserves(turn):
            return False
        
        # Deploy all models at calculated positions
        try:
            # Use the existing model positioning logic with battlefield edge repulsors
            boundary_repulsors = game_map.get_battlefield_edge_repulsors() if game_map else []
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            model_positions = self.calculate_model_positions(position[0], position[1], game_map, boundary_repulsors=boundary_repulsors, avoid_friendly_units=False)
            
            # Check if formation finding failed
            if model_positions is None:
                logger.warning(f"Could not find valid formation for {self.name} arriving from reserves - using default placement")
                # Default: place all models at the unit position
                for model in self.models:
                    model.set_location(position[0], position[1], position[2], 0.0)
            else:
                for model, model_pos in zip(self.models, model_positions):
                    model.set_location(model_pos[0], model_pos[1], model_pos[2], model_pos[3])
        except Exception as e:
            logger.warning(f"Could not calculate model positions for {self.name} arriving from reserves: {e}")
            # Default: place all models at the unit position
            for model in self.models:
                model.set_location(position[0], position[1], position[2], 0.0)
        
        # Unit position is now determined by model positions
        
        # Update unit status
        self.deployed = True
        self.reserve_status = 'deployed'
        self.reserve_turn_deployed = turn
        self.arrived_from_reserves_this_turn = True
        
        logger.info(f"🪂 {self.name} arrived from reserves at turn {turn}")
        return True
    
    def can_move_after_arriving_from_reserves(self) -> bool:
        """Check if the unit can move normally after arriving from reserves this turn."""
        # Units arriving from reserves cannot move unless they have special rules
        if not self.arrived_from_reserves_this_turn:
            return True
        
        # Check for special abilities that allow movement after arriving from reserves
        for ability in self.possible_abilities:
            if hasattr(ability, 'name') and ability.name:
                if "can move after" in ability.name.lower() or "move after arriving" in ability.name.lower():
                    return True
            if hasattr(ability, 'description') and ability.description:
                if "can move after" in ability.description.lower() or "move after arriving" in ability.description.lower():
                    return True
        
        return False
    
    def can_advance_after_arriving_from_reserves(self) -> bool:
        """Check if the unit can advance after arriving from reserves this turn."""
        if not self.arrived_from_reserves_this_turn:
            return True
        
        # Units arriving from reserves cannot advance unless they have special rules
        # Check for special abilities that allow advancing after arriving from reserves
        for ability in self.possible_abilities:
            if hasattr(ability, 'name') and ability.name:
                if "can advance after" in ability.name.lower() or "advance after arriving" in ability.name.lower():
                    return True
            if hasattr(ability, 'description') and ability.description:
                if "can advance after" in ability.description.lower() or "advance after arriving" in ability.description.lower():
                    return True
        
        return False
    
    def can_charge_after_arriving_from_reserves(self) -> bool:
        """Check if the unit can charge after arriving from reserves this turn."""
        if not self.arrived_from_reserves_this_turn:
            return True
        
        # Units arriving from reserves CAN charge by default (this is the normal rule)
        # Only special restrictions would prevent charging
        for ability in self.possible_abilities:
            if hasattr(ability, 'name') and ability.name:
                if ("cannot charge after" in ability.name.lower() or 
                    "no charge after arriving" in ability.name.lower()):
                    return False
            if hasattr(ability, 'description') and ability.description:
                if ("cannot charge after" in ability.description.lower() or 
                    "no charge after arriving" in ability.description.lower()):
                    return False
        
        return True  # Default: can charge after arriving from reserves

    def take_desperate_escape_test(self, game_map: Optional['Map'] = None) -> int:
        """
        Take a Desperate Escape Test - rolling D6 for each model, destroying on 1-2.
        This is required for Battle-Shocked units that fall back.
        
        Returns:
            int: Number of models destroyed during the test
        """
        print(f"💀 {self.name} is Battle-Shocked and falling back - taking Desperate Escape Test!")
        
        models_to_test = self.models.copy()  # Copy to avoid modifying list while iterating
        models_destroyed = 0
        
        for i, model in enumerate(models_to_test):
            roll = get_roll("D6")
            if roll <= 2:
                # Model is destroyed
                print(f"🎲 Model {i+1}: Rolled {roll} - DESTROYED! 💀")
                self.remove_model(model, fleed=True, game_map=game_map)  # Mark as fled, not killed in combat
                models_destroyed += 1
            else:
                # Model survives
                print(f"🎲 Model {i+1}: Rolled {roll} - Survives ✅")
        
        if models_destroyed > 0:
            print(f"💥 Desperate Escape Test complete: {models_destroyed} model(s) destroyed, {len(self.models)} remain")
        else:
            print(f"✅ Desperate Escape Test complete: All models survived!")
        
        return models_destroyed



