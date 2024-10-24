import logging
from typing import List, Dict, Tuple, Optional
from typing import TYPE_CHECKING
from .model import Model
from ..utility.model_base import Base, BaseType
from .wargear import Wargear, WargearOption
from .ability import Ability
from ..utility.range import Range
from ..utility.calcs import get_dist, get_angle, convert_mm_to_inches, a_star, simplify_path, get_pivot_cost, angle_difference, can_end_move_on_terrain
from ..utility.dice import get_roll
from .status_effects import StatusEffect
from ..utility.constants import VIEWING_ANGLE
import math
import uuid
import random
import copy
import numpy as np


# Forward declarations
if TYPE_CHECKING:
    from .map import Map


logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class UnitRoundState:
    remained_stationary_this_round: bool = False
    advanced_this_round: bool = False
    shot_this_round: bool = False
    fell_back_this_round: bool = False
    reinforced_this_round: bool = False
    declared_charge_this_round: bool = False
    num_lost_models_this_round: int = 0


class MovementAction:
    REMAIN_STATIONARY = 0
    MOVE = 1
    ADVANCE = 2
    FALL_BACK = 3


class MovementState:
    IN_ENGAGEMENT_RANGE = 0
    OUT_OF_ENGAGEMENT_RANGE = 1


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
        self.status_effects = []  # List of active status effects
        self.special_rules = {}  # Dictionary of special rules
        self.stats = {}  # Dictionary of stats modifiers
        self.deployed = False

        # Initialize round-tracked variables
        self.initialize_round()

        self.position = None  # Initialize position as None
        self.update_coherency()  # Sets coherency_distance and required_neighbors

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
        self.update_coherency()

    def add_model(self, model: Model) -> None:
        assert model not in self.models
        model.set_parent_unit(self)
        self.models.append(model)
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
        for status_effect in self.status_effects:
            status_effect.check_expiration(self)

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

    def make_leadership_check(self) -> bool:
        return get_roll("2D6") < self.leadership

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
    def is_belisarius_cawl(self) -> bool:
        return "Belisarius Cawl" in self.keywords

    @property
    def is_imperium_primarch(self) -> bool:
        return "Imperium" in self.keywords and "Primarch" in self.keywords

    @property
    def has_circular_base(self) -> bool:
        return self.models[0].has_circular_base

    @property
    def base_size(self) -> float:
        return self.models[0].base_size

    def print_unit(self):
        for model in self.models:
            print(f"\n{model}")

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
        self.update_coherency()

        # Apply wargear to all models
        for model in self.models:
            model.add_wargear(wargear)

    @property
    def abilities(self):
        abilities = []
        for model in self.models:
            abilities.extend(model.abilities)
        return abilities

    @property
    def model_height(self) -> float:
        return max(model.model_base.model_height for model in self.models)

    ###########################################################################
    ### Properties
    ###########################################################################
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

    ###########################################################################
    ###########################################################################
    ### Core Actions
    ###########################################################################
    ###########################################################################

    def apply_command_abilities(self) -> None:
        """Applies command abilities during the Command phase."""
        for ability in self.abilities.get('command_phase', []):
            ability.activate(self)

    ###########################################################################
    ### Command
    ###########################################################################
    def do_command_action(self, game_map: 'Map') -> bool:
        """Executes the command action for the unit."""
        self.initialize_round()
        return True

    ###########################################################################
    ### Movement
    ###########################################################################
    def do_move_action(self, game_map: 'Map') -> bool:
        # Determine the current state
        state = self._get_engagement_state(game_map)

        # Get available actions based on the state
        available_actions = self._get_available_move_actions(state)

        # Choose an action (this is where the RL agent would make a decision)
        chosen_action, destination = self._choose_action(available_actions, game_map)

        # Execute the chosen action
        return self._execute_action(chosen_action, destination, game_map)

    def _get_engagement_state(self, game_map: 'Map') -> int:
        """Determine if the unit is in engagement range of any enemy model."""
        current_position = self.get_position()
        enemy_units = game_map.get_enemy_units(self.faction)
        
        for enemy_unit in enemy_units:
            if game_map.is_within_engagement_range(current_position, enemy_unit):
                return MovementState.IN_ENGAGEMENT_RANGE
        
        return MovementState.OUT_OF_ENGAGEMENT_RANGE

    def _get_available_move_actions(self, state: int) -> List[int]:
        """Get the list of available actions based on the current state."""
        if state == MovementState.IN_ENGAGEMENT_RANGE:
            return [MovementAction.REMAIN_STATIONARY, MovementAction.FALL_BACK]
        else:
            return [MovementAction.REMAIN_STATIONARY, MovementAction.MOVE, MovementAction.ADVANCE]

    def _choose_action(self, available_actions: List[int], game_map: 'Map') -> Tuple[int, Tuple[float, float, float]]:
        """Choose an action from the available actions."""
        # For now, we'll choose randomly. In a real RL setup, this would be where the agent makes a decision.
        current_position = self.get_position()
        chosen_action = random.choice(available_actions)

        if chosen_action == MovementAction.REMAIN_STATIONARY:
            return chosen_action, current_position

        # Determine movement range based on the chosen action
        if chosen_action == MovementAction.ADVANCE:
            movement_range = self.movement + 6  # this is suspect as we would need to roll a 6 on a D6
        else:
            movement_range = self.movement

        # Generate a random destination within the movement range
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(0, movement_range)

        new_x = current_position[0] + distance * math.cos(angle)
        new_y = current_position[1] + distance * math.sin(angle)
        new_z = current_position[2]

        destination = (new_x, new_y, new_z)

        return chosen_action, destination

    def _execute_action(self, action: int, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        """Execute the chosen action."""
        if action == MovementAction.REMAIN_STATIONARY:
            print(f"{self.name} remains stationary")
            return self.remain_stationary()
        elif action == MovementAction.MOVE:
            print(f"{self.name} moves to {destination}")
            return self.move(destination, game_map)
        elif action == MovementAction.ADVANCE:
            print(f"{self.name} advances to {destination}")
            return self.advance(destination, game_map)
        elif action == MovementAction.FALL_BACK:
            print(f"{self.name} falls back")
            return self.fall_back(destination, game_map)
        else:
            raise ValueError(f"Invalid action: {action}")

    def remain_stationary(self) -> bool:
        self.round_state.remained_stationary_this_round = True
        return True

    def advance(self, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        return self.move(destination, game_map, advance=True)

    def move(self, destination: Tuple[float, float, float], game_map: 'Map', advance: bool = False) -> bool:
        """Moves the unit towards the destination up to its movement characteristic or Advance."""
        if not self.models:
            logger.error(f"Cannot move unit {self.name}: no models in unit")
            return False

        current_position = self.get_position()
        if current_position is None:
            logger.error(f"Cannot move unit {self.name}: current position is None")
            return False

        # Get the movement range from the first model (assuming all models have the same movement)
        movement_range = self.movement

        # If advancing, add D6 to the movement range
        if advance:
            advance_roll = get_roll("D6")
            print(f"Advance roll: {advance_roll}")
            if advance_roll is None:
                logger.error(f"Failed to roll dice for advancing unit {self.name}")
                return False
            movement_range += advance_roll

        '''
        # Select the leader model as the one closest to the destination
        leader_model = min(self.models, key=lambda m: get_dist(m.model_base.x - destination[0], m.model_base.y - destination[1]))
        other_models = [model for model in self.models if model != leader_model]

        if not game_map.is_within_boundary(leader_model, destination):
            logger.error(f"Cannot move unit {self.name} to {destination}: out of boundary")
            return False
        
        if game_map.check_collision_with_obstacles(leader_model, destination):
            logger.error(f"Cannot move unit {self.name} to {destination}: obstacle collision at destination")
            return False

        if game_map.check_collision_with_other_units(leader_model, destination):
            logger.error(f"Cannot move unit {self.name} to {destination}: other unit collision at destination")
            return False

        # Calculate pivot cost for the leader model if needed
        direction_to_destination = get_angle(
            destination[1] - leader_model.model_base.y,
            destination[0] - leader_model.model_base.x
        )

        # List to keep track of moved models and their positions
        moved_positions = []

        # Move the leader model first
        path = a_star(leader_model, game_map.obstacles, destination)
        if path is None:
            logger.error(f"Cannot move unit {self.name} - leader model {leader_model} path is None")
            return False  # Leader cannot reach destination
        #path = simplify_path(path, game_map.obstacles, leader_model.model_base.get_base_shape())

        # Move the leader along the path
        distance = 0
        last_node = leader_model.get_location()
        leader_model.last_move_path = [last_node]  # Initialize the path with the starting position

        print(f"Model {leader_model._id} {leader_model.name} moving to {destination}")
        for node in path[1:]:
            dx = node[0] - last_node[0]
            dy = node[1] - last_node[1]
            dz = node[2] - last_node[2] if len(node) > 2 else 0
            segment_distance = get_dist(dx, dy, dz)
            if distance + segment_distance > movement_range:
                break
            distance += segment_distance
            last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
            leader_model.last_move_path.append(last_node)  # Add each node to the path

        # Before setting the leader's new location, check boundary
        if not game_map.is_within_boundary(leader_model):
            logger.error(f"Leader model {leader_model} cannot move outside the battlefield boundaries.")
            return False  # Movement is invalid

        leader_model.set_location(*last_node)
        print(f"Model {leader_model._id} {leader_model.name} moved to {destination} travelling {distance} inches")
        print(f"Model {leader_model._id} path: {leader_model.last_move_path}")
        moved_positions.append(leader_model.get_location())
        '''

        # Now move the other models

        # Generate potential positions for the other models
        potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map) #, seeded_positions=moved_positions)

        for model, destination in zip(self.models, potential_positions):
            print(f"Model {model._id} {model.name} moving to {destination}")
            shortest_path = a_star(model, game_map.obstacles, destination)
            if not shortest_path:
                print(f"Cannot move unit {self.name} - model {model._id} path is None")
                continue  # Model cannot reach destination
            path_distance = sum(get_dist(shortest_path[i][0] - shortest_path[i-1][0], shortest_path[i][1] - shortest_path[i-1][1]) for i in range(1, len(shortest_path)))
            if path_distance > model.movement:
                print(f"Cannot move unit {self.name} - model {model._id} path distance {path_distance} is greater than movement {model.movement}")
                continue  # Model cannot reach destination
            last_node = model.get_location()
            model.last_move_path = [last_node]
            direction_to_destination = get_angle(destination[0] - model.model_base.x, destination[1] - model.model_base.y)
            distance = 0.0
            for node in shortest_path[1:]:
                    dx = node[0] - last_node[0]
                    dy = node[1] - last_node[1]
                    dz = node[2] - last_node[2] if len(node) > 2 else 0
                    segment_distance = get_dist(dx, dy, dz)
                    if distance + segment_distance > movement_range:
                        break
                    distance += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
            model.set_location(*destination)
            print(f"Model {model._id} {model.name} moved to {destination} travelling {distance} inches")
            print(f"Model {model._id} path: {model.last_move_path}")

        # Update unit centroid
        self.reset_position()

        print(f"Unit {self.name} {'advanced' if advance else 'moved'} towards {destination} : Distance {distance}")
        self.round_state.advanced_this_round = advance
        return True

    def fall_back(self, destination: Tuple[float, float, float], path: List[Tuple[float, float, float]], game_map: 'Map') -> bool:
        """Falls back from close combat."""
        # Logic to move the unit out of engagement range
        print(f"{self.name} falls back from combat.")
        self.round_state.fell_back_this_round = True
        return True


    ###########################################################################
    ### Shooting Phase Actions
    ###########################################################################
    def shoot(self, target_unit: 'Unit') -> None:
        if self.round_state.advanced_this_round:
            print(f"{self.name} cannot shoot after advancing.")
            return
        if self.round_state.fell_back_this_round:
            print(f"{self.name} cannot shoot after falling back.")
            return

        """Shoots at the target unit."""
        if self.check_line_of_sight(target_unit):
            for weapon in self.weapons:
                weapon.fire(self, target_unit)
            print(f"{self.name} fired at {target_unit.name}.")
            self.round_state.shot_this_round = True
        else:
            print(f"{self.name} cannot see {target_unit.name}.")

    # Charge Phase Actions
    def declare_charge(self, target_units: List['Unit']) -> None:
        if self.round_state.advanced_this_round:
            print(f"{self.name} cannot charge after advancing.")
            return
        if self.round_state.fell_back_this_round:
            print(f"{self.name} cannot charge after falling back.")
            return

        """Declares a charge against target units."""
        self.charge_targets = target_units
        print(f"{self.name} declares a charge against {[unit.name for unit in target_units]}.")
        self.round_state.declared_charge_this_round = True

    def charge_move(self) -> None:
        if not self.round_state.declared_charge_this_round:
            print(f"{self.name} cannot charge move without a declared charge.")
            return

        """Moves the unit towards the enemy after a successful charge roll."""
        charge_distance = get_roll("2D6")  # 2D6 roll
        # Logic to move towards the closest enemy within declared targets
        print(f"{self.name} charges forward {charge_distance} inches.")

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

    # Battle-shock Phase Actions
    def take_battle_shock_test(self):
        """Takes a battle shock test."""
        test_result = get_roll("2D6")  # 2D6 roll
        leadership = self.models[0].leadership
        if test_result > leadership:
            self.status_effects.append('battle_shocked')
            print(f"{self.name} has failed the battle shock test and is battle shocked.")
        else:
            print(f"{self.name} passes the battle shock test.")

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
    
    def is_alive(self) -> bool:
        return len(self.models) > 0

    def set_position(self, x: float, y: float, z: float = 0.0):
        """Set the position of the unit on the map."""
        self.position = (x, y, z)

    def get_position(self):
        if self.position is not None:
            return self.position
        elif self.models:
            # Calculate the centroid of all model positions
            x_sum = sum(model.get_location()[0] for model in self.models)
            y_sum = sum(model.get_location()[1] for model in self.models)
            z_sum = sum(model.get_location()[2] for model in self.models)
            return (x_sum / len(self.models), y_sum / len(self.models), z_sum / len(self.models))
        else:
            return None

    def reset_position(self):
        if self.models:
            # Calculate the centroid of all model positions
            x_sum = sum(model.get_location()[0] for model in self.models)
            y_sum = sum(model.get_location()[1] for model in self.models)
            z_sum = sum(model.get_location()[2] for model in self.models)
            self.set_position(x_sum / len(self.models), y_sum / len(self.models), z_sum / len(self.models))
        else:
            self.position = None

    def is_point_inside(self, x, y):
        position = self.get_position()
        if position is None:
            return False
        
        center_x, center_y, _ = position
        radius = self.coherency_distance  # Assuming this is defined elsewhere in the class
        
        # Check if the point is within the circular area defined by the unit's position and coherency distance
        distance = get_dist(x - center_x, y - center_y)
        return distance <= radius

    def calculate_model_positions(self, start_x: float, start_y: float, game_map: 'Map', zoom_level: float = 1.0, seeded_positions: List[Tuple[float, float, float, float]] = []) -> List[Tuple[float, float, float, float]]:
        positions = seeded_positions.copy()
        max_attempts = 100  # Maximum number of attempts to place each model

        # Convert start position (mouse position) to game coordinates
        start_x_game = start_x / zoom_level
        start_y_game = start_y / zoom_level

        for i, model in enumerate(self.models):
            placed = False
            attempts = 0
            
            while not placed and attempts < max_attempts:
                if not positions:  # First model
                    x, y = start_x_game, start_y_game
                    z = 0.0  # TODO - should be game_map.get_height_at(x, y)
                    facing = 0.0
                    positions.append((x, y, z, facing))
                    placed = True
                    break
                else:
                    # Try to find a strategic position within coherency distance
                    valid_positions = self._find_strategic_position(model, positions, game_map)
                    if not valid_positions:
                        attempts += 1
                        continue
                    # Check collision with all models in the unit, including the current one
                    for x, y, z, facing in valid_positions:
                        if not self._collides_with_unit_models(x, y, z, facing, positions):
                            if self._is_coherent_within_unit(x, y, z, facing, positions):
                                positions.append((x, y, z, facing))
                                placed = True
                                break
                attempts += 1

            if not placed:
                return []  # Unable to place all models

        # We return game coordinates, not screen coordinates
        return positions

    def _create_potential_base(self, x: float, y: float, z: float, facing: float):
        # Create a new base with the same properties as the model's base
        new_base = copy.deepcopy(self.models[0].model_base)
        new_base.x, new_base.y, new_base.z = x, y, z
        new_base.set_facing(facing)
        return new_base

    def _collides_with_unit_models(self, x: float, y: float, z: float, facing: float, positions: List[Tuple[float, float, float, float]]) -> bool:
        """Check if the model at the given position collides with any other model in the unit."""
        if not positions:
            return False

        new_base = self._create_potential_base(x, y, z, facing)

        for pos in positions:
            print(f"Checking collision: New base at ({x:.4f}, {y:.4f}, {z:.4f}) facing {facing:.2f}")
            print(f"Against existing base at ({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f}) facing {pos[3]:.2f}")

            if (z - pos[2]) > self.model_height:
                print(f"Quick Non-Collision Decision :: Delta Z: {z - pos[2]}, Model Height: {self.model_height}")
                return False
            
            other_base = self._create_potential_base(pos[0], pos[1], pos[2], pos[3])
            
            distance = math.sqrt((x - pos[0])**2 + (y - pos[1])**2)
            angle = get_angle(y - pos[1], x - pos[0])
            combined_radius = new_base.getRadius(angle) + other_base.getRadius(angle)
            print(f"Distance between bases: {distance:.4f}")
            print(f"Combined radius: {combined_radius:.4f}")

            if distance <= combined_radius:
                print(f"Collision detected!")
                return True
        return False

    def _is_coherent_within_unit(self, x: float, y: float, z: float, facing: float, positions: List[Tuple[float, float, float, float]]) -> bool:
        """Check if the model at the given position is within coherency with the unit."""
        new_base = self._create_potential_base(x, y, z, facing)
        new_base_shape = new_base.get_base_shape()

        # Check against already placed models
        found_neighbors = 0
        current_neighbors_needed = 0 if len(positions) == 0 else 1 if len(positions) == 1 else self.required_neighbors

        if current_neighbors_needed == 0:
            return True

        for pos in positions:
            other_base = self._create_potential_base(pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0, pos[3] if len(pos) > 3 else facing)
            if new_base_shape.distance(other_base.get_base_shape()) <= self.coherency_distance:
                found_neighbors += 1
                if found_neighbors >= current_neighbors_needed:
                    return True
        return False

    def _find_strategic_position(self, model: Model, placed_positions: List[Tuple[float, float, float, float]], game_map: 'Map') -> List[Tuple[float, float, float, float]]:
        last_x, last_y, last_z, facing = placed_positions[-1]
        directions = [
            (0, 1), (1, 1), (1, 0), (1, -1),
            (0, -1), (-1, -1), (-1, 0), (-1, 1)
        ]

        valid_positions = []
        for dx, dy in directions:
            radius_at_facing = model.model_base.getRadius(angle=get_angle(dy, dx))
            print(f"{model._id} {model.name} X: {last_x}, Y: {last_y}, Facing: {round(math.degrees(facing), 2)} :: {radius_at_facing} :: {dx} :: {dy}")
            for distance in np.arange(radius_at_facing + 0.1, radius_at_facing + self.coherency_distance, 0.1):
                x = last_x + distance * dx
                y = last_y + distance * dy
                z = last_z  # TODO - should be game_map.get_height_at(x, y)
                
                if self._is_valid_position(x, y, z, facing, game_map, placed_positions):
                    valid_positions.append((x, y, z, facing))
        return valid_positions

    def _is_valid_position(self, x: float, y: float, z: float, facing: float, game_map: 'Map', placed_positions: List[Tuple[float, float, float, float]]) -> bool:
        model = self.models[0]  # Use the first model as a reference
        if not game_map.is_within_boundary(model, (x, y)):
            return False
        if game_map.check_collision_with_obstacles(model, (x, y)):
            return False
        if game_map.check_collision_with_other_units(model, (x, y)):
            return False
        if self._collides_with_unit_models(x, y, z, facing, placed_positions):
            return False
        if self._is_coherent_within_unit(x, y, z, facing, placed_positions):
            return True
        return False

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



