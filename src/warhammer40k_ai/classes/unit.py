import logging
from typing import List, Dict, Tuple, Optional
from typing import TYPE_CHECKING
from .model import Model
from ..utility.model_base import Base, BaseType, convert_mm_to_inches
from .wargear import Wargear, WargearOption
from .ability import Ability
from ..utility.range import Range
from .status_effects import StatusEffect
import math
import uuid

if TYPE_CHECKING:
    from .map import Map

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class UnitRoundState:
    advanced_this_round: bool = False
    shot_this_round: bool = False
    fell_back_this_round: bool = False
    reinforced_this_round: bool = False
    num_lost_models_this_round: int = 0


class Unit:
    def __init__(self, datasheet, quantity=None, enhancement=None):
        self._id = str(uuid.uuid4())
        self._datasheet = datasheet
        self.name = datasheet.name
        self.faction = datasheet.faction_data["name"]
        self.keywords = getattr(datasheet, 'keywords', [])  # Use getattr with a default value
        self.faction_keywords = getattr(datasheet, 'faction_keywords', [])  # Use getattr with a default value
        self.unit_composition = self._parse_unit_composition(datasheet.datasheets_unit_composition)
        self.models_cost = self._parse_models_cost(datasheet.datasheets_models_cost)
        self.models = self._create_models(datasheet, quantity)
        self.possible_wargear = self._parse_wargear(datasheet)
        self.wargear_options = None
        self._parse_wargear_options(datasheet) # this needs to here, sets above variable
        self.possible_abilities = self._parse_abilities(datasheet)
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

        # Game State specific attributes
        self.models_lost = []

        # Initialize round-tracked variables
        self.initialize_round()

        self.position = None  # Initialize position as None

    def _parse_attribute(self, attribute_value: str) -> int:
        # Remove " and + from the attribute value
        attribute_value = attribute_value.replace("\"", "").replace("+", "")
        if "-" in attribute_value:
            return 0
        return int(attribute_value)

    def _parse_range(self, range_string: str) -> Range:
        return Range.from_string(range_string)

    def _parse_base_size(self, base_size: str) -> Base:
        base_size = base_size.replace("mm", "")
        # Parse the base size from the datasheet
        if 'x' in base_size:
            # This handles the elliptical example: "32 x 16mm"
            major, minor = base_size.split("x")
            major = convert_mm_to_inches(int(major.strip()) / 2.0)
            minor = convert_mm_to_inches(int(minor.strip()) / 2.0)
            return Base(BaseType.ELLIPTICAL, (major, minor))
        else:
            # This handles the standard example: "32mm"
            return Base(BaseType.CIRCULAR, convert_mm_to_inches(int(base_size.strip()) / 2.0))

    def _parse_unit_composition(self, unit_composition):
        result = {}
        for comp in unit_composition:
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
                    inv_save=self._parse_attribute(datasheet.datasheets_models[0]["inv_sv"]),
                    wounds=self._parse_attribute(datasheet.datasheets_models[0]["W"]),
                    leadership=self._parse_attribute(datasheet.datasheets_models[0]["Ld"]),
                    objective_control=self._parse_attribute(datasheet.datasheets_models[0]["OC"]),
                    model_base=self._parse_base_size(datasheet.datasheets_models[0]["base_size"])
                )
                model.set_parent_unit(self)
                models.append(model)
                total_models += 1
            if total_models >= quantity:
                break
        return models

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

    def parse_wargear_option(self, option: str, result: Dict[str, List[WargearOption]]):
        # Parse the option string
        parts = option.split(' can be equipped with ')
        if len(parts) != 2:
            print(f"Invalid wargear option format: {option}")
            return

        model_description, item_description = parts
        model_count = 1  # Default to 1 model
        
        # Extract model count if specified
        if model_description.startswith(('1 ', '2 ', '3 ', '4 ', '5 ', '6 ', '7 ', '8 ', '9 ')):
            model_count = int(model_description.split()[0])
            model_description = ' '.join(model_description.split()[1:])

        item_count = 1 # Default to 1 item
        # Extract item count if specified
        if item_description.startswith(('1 ', '2 ', '3 ', '4 ', '5 ', '6 ', '7 ', '8 ', '9 ')):
            item_count = int(item_description.split()[0])
            item_description = ' '.join(item_description.split()[1:]).strip().replace('.', '')

        # Parse "not equipped with" condition
        not_equipped_with = None
        if "that is not equipped with" in model_description:
            model_parts = model_description.split("that is not equipped with")
            model_description = model_parts[0].strip()
            not_equipped_with = model_parts[1].strip()
            # Remove leading "a" or "an" from not_equipped_with
            if not_equipped_with.startswith("a "):
                not_equipped_with = not_equipped_with[2:].strip()
            elif not_equipped_with.startswith("an "):
                not_equipped_with = not_equipped_with[3:].strip()

        if item_description.lower() not in result.keys():
            result[item_description.lower()] = WargearOption(item_description, model_description, model_count, item_count, not_equipped_with)

    def parse_wargear_options(self, options: List[str]):
        result = {}
        if len(options) == 1 and options[0].lower() == "none":
            self.wargear_options = {}
            return
        for option in options:
            self.parse_wargear_option(option, result)
        self.wargear_options = result

    def apply_wargear_option(self, wargear_option: WargearOption):
        # Find eligible models
        eligible_models = [
            model for model in self.models
            if model.name in wargear_option.model_name and
            wargear_option.wargear_name not in model.optional_wargear and
            (wargear_option.exclude_name is None or wargear_option.exclude_name.lower() not in model.optional_wargear)
        ]

        if len(eligible_models) < wargear_option.model_quantity:
            raise ValueError(f"Not enough eligible models for option: {wargear_option.wargear_name}")

        count = 0
        for model in eligible_models:
            if count >= wargear_option.item_quantity:
                break
            model.optional_wargear.append(wargear_option.wargear_name)
            count += 1

    def apply_wargear_options(self, wargear_name: Optional[str] = None) -> None:
        for optional_wargear_name in self.wargear_options.keys():
            if wargear_name:
                if optional_wargear_name == wargear_name:
                    self.apply_wargear_option(self.wargear_options[optional_wargear_name])
                    break
            else:
                self.apply_wargear_option(self.wargear_options[optional_wargear_name])

    def add_wargear(self, wargear: List[Wargear]=[], model_name: str=None) -> None:
        for model_instance in self.models:
            wargear_to_add = []
            if not wargear:
                for wargear_instance in self.possible_wargear:
                    wargear_to_add.append(wargear_instance)
            else:
                wargear_to_add.extend(wargear)
            for wargear_instance in wargear_to_add:
                if model_name:
                    if model_instance.name == model_name:
                        model_instance.wargear.append(wargear_instance)
                else:
                    model_instance.wargear.append(wargear_instance)

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

    # Remove a Model from a Unit (e.g., when it dies)
    def remove_model(self, model: Model, fleed: bool = False) -> None:
        assert model in self.models

        # Remove model itself
        self.round_state.num_lost_models_this_round += 1
        self.models_lost.append(model)
        self.models.remove(model)

        logger.info(f"Unit has {len(self.models)} models left!")
        #if len(self.models) < 1:
        #    if not fleed:
        #        self.callbacks[hook_events.ENEMY_UNIT_KILLED].append(logger.error(self))
        #    self.parent_detachment.removeUnit(self)

    def initialize_round(self) -> None:
        """Reset round-tracked variables to default state."""
        self.round_state = UnitRoundState()

    def is_max_health(self) -> Tuple[bool, Optional[Model]]:
        """
        Check if the unit is at full health.

        Returns:
            Tuple[bool, Optional[Model]]: A tuple containing:
                - A boolean indicating if the unit is at full health
                - The first damaged model found, or None if all models are at full health
        """
        for model in self.models:
            if not model.is_max_health():
                return False, model
        return True, None

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
    def is_infantry(self) -> bool:
        return "Infantry" in self.keywords

    @property
    def is_character(self) -> bool:
        return "Character" in self.keywords

    @property
    def is_leader(self) -> bool:
        return len(self.can_be_attached_to) > 0

    @property
    def is_supreme_commander(self) -> bool:
        # TODO: Implement this
        return False

    def print_unit(self):
        for model in self.models:
            print(f"\n{model}")

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

    def _parse_models_cost(self, models_cost):
        result = {}
        for cost_entry in models_cost:
            num_models = int(cost_entry['description'].split()[0])
            cost = int(cost_entry['cost'])
            result[num_models] = cost
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

        # Apply wargear to all models
        for model in self.models:
            model.add_wargear(wargear)

    @property
    def abilities(self):
        abilities = []
        for model in self.models:
            abilities.extend(model.abilities)
        return abilities

    # Core Methods
    def move(self, destination: Tuple[int, int], game_map: 'Map'):
        from .map import Map  # Import inside the function
        assert isinstance(game_map, Map)
        pass
    
    def attack(self, target_unit: 'Unit', game_map: 'Map'):
        from .map import Map  # Import inside the function
        assert isinstance(game_map, Map)
        # Rest of the attack logic
        pass
    
    def use_ability(self, ability: Ability, target: 'Unit', game_map: 'Map'):
        from .map import Map  # Import inside the function
        assert isinstance(game_map, Map)
        pass
    
    def take_damage(self, amount: int):
        pass
    
    def apply_status_effect(self, status_effect: StatusEffect):
        pass
    
    def remove_status_effect(self, status_effect: StatusEffect):
        pass
    
    def is_alive(self) -> bool:
        return len(self.models) > 0

    def set_position(self, x: int, y: int):
        """Set the position of the unit on the map."""
        self.position = (x, y)

    def get_model_positions(self):
        if self.position is None:
            raise ValueError("Unit position has not been set.")
        
        center_x, center_y = self.position
        positions = [(center_x, center_y)]  # Center position

        if len(self.models) > 1:
            radius = 0.5  # Adjust this value to change the spread of models
            angle_step = 2 * math.pi / (len(self.models) - 1)
            for i in range(1, len(self.models)):
                angle = i * angle_step
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                positions.append((x, y))

        return positions