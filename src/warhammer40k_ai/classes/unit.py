import logging
from typing import List, Tuple
from .model import Model
from ..utility.model_base import Base, BaseType, convert_mm_to_inches
from .wargear import Wargear

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class UnitRoundState:
    advanced_this_round: bool = False
    shot_this_round: bool = False
    fell_back_this_round: bool = False
    reinforced_this_round: bool = False
    num_lost_models_this_round: int = 0


class Unit:
    def __init__(self, datasheet):
        self.name = datasheet.name
        self.faction = datasheet.faction_data["name"]
        self.keywords = getattr(datasheet, 'keywords', [])  # Use getattr with a default value
        self.faction_keywords = getattr(datasheet, 'faction_keywords', [])  # Use getattr with a default value
        self.composition = self._parse_composition(datasheet.datasheets_unit_composition)
        self.models = self._create_models(datasheet)
        self.default_wargear = self._parse_wargear(datasheet)
        self.wargear_options = self._parse_wargear_options(datasheet)

        self.add_default_wargear()

        # Game State specific attributes
        self.models_lost = []

        # Initialize round-tracked variables
        self.initializeRound()

    def _parse_attribute(self, attribute_value: str) -> int:
        # Remove " and + from the attribute value
        attribute_value = attribute_value.replace("\"", "").replace("+", "")
        if "-" in attribute_value:
            return 0
        return int(attribute_value)
    
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

    def _parse_composition(self, unit_composition) -> List[tuple]:
        # Parse the composition from multiple dictionaries
        parsed = []
        for composition_dict in unit_composition:
            description = composition_dict.get('description', '')
            parsed.extend(self._parse_description(description))
        return parsed

    def _parse_description(self, description: str) -> List[tuple]:
        # Parse a single description and return a list of (count, model_name) tuples
        components = description.split(' and ')
        parsed = []
        for component in components:
            parts = component.strip().split(' ', 1)
            if parts[0].isdigit():
                count = int(parts[0])
                model_name = parts[1]
            else:
                count = 1
                model_name = component.strip()
            parsed.append((count, model_name))
        return parsed

    def _create_models(self, datasheet) -> List[Model]:
        models = []
        for count, model_name in self.composition:
            # Make model_name singular if it's plural
            if model_name.endswith('s'):
                model_name = model_name[:-1]
            for _ in range(count):
                model = Model(
                    name=model_name,
                    movement= self._parse_attribute(datasheet.datasheets_models[0]["M"]),
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
        return models

    def _parse_wargear(self, datasheet):
        default_wargear = []
        if hasattr(datasheet, 'datasheets_wargear'):
            for wargear_data in datasheet.datasheets_wargear:
                default_wargear.append(Wargear(wargear_data))
        return default_wargear

    def _parse_wargear_options(self, datasheet) -> List[str]:
        wargear_options = []
        if hasattr(datasheet, 'datasheets_options'):
            for wargear_option_data in datasheet.datasheets_options:
                wargear_options.append(wargear_option_data["description"])
        return wargear_options

    def apply_wargear_option(self, option: str):
        # Parse the option string
        parts = option.split(' can be equipped with ')
        if len(parts) != 2:
            raise ValueError(f"Invalid wargear option format: {option}")

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

        # Find eligible models
        eligible_models = [
            model for model in self.models
            if model.name in model_description and
            item_description not in model.optional_wargear and
            (not_equipped_with is None or not_equipped_with not in model.optional_wargear)
        ]

        if len(eligible_models) < model_count:
            raise ValueError(f"Not enough eligible models for option: {option}")

        # Apply wargear to eligible models
        for model in eligible_models[:model_count]:
            model.optional_wargear.append(item_description)

    def apply_wargear_options(self, options: List[str]):
        for option in options:
            self.apply_wargear_option(option)

    def add_default_wargear(self):
        for model in self.models:
            for wargear in self.default_wargear:
                model.wargear.append(wargear)

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

    # Set round-tracked variables to default state
    def initializeRound(self) -> None:
        self.round_state = UnitRoundState()

    def print_unit(self):
        for model in self.models:
            print(model)

    def __str__(self):
        return f"{self.name} ({len(self.models)} models)"

    def __repr__(self):
        return f"Unit(name='{self.name}', models={len(self.models)})"
