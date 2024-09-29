from typing import List
from .model import Model
from ..utility.model_base import Base, BaseType, ConvertMMToInches
from .wargear import Wargear

class Unit:
    def __init__(self, datasheet):
        self.name = datasheet.name
        self.faction = datasheet.faction_data["name"]
        self.keywords = getattr(datasheet, 'keywords', [])  # Use getattr with a default value
        self.faction_keywords = getattr(datasheet, 'faction_keywords', [])  # Use getattr with a default value
        self.composition = self._parse_composition(datasheet.datasheets_unit_composition)
        self.models = self._create_models(datasheet)
        self.unit_wargear = self._parse_wargear(datasheet)

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
            major = ConvertMMToInches(int(major.strip()) / 2.0)
            minor = ConvertMMToInches(int(minor.strip()) / 2.0)
            return Base(BaseType.ELLIPTICAL, (major, minor))
        else:
            # This handles the standard example: "32mm"
            return Base(BaseType.CIRCULAR, ConvertMMToInches(int(base_size.strip()) / 2.0))

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
                    base_size=self._parse_base_size(datasheet.datasheets_models[0]["base_size"])
                )
                models.append(model)
        return models

    def _parse_wargear(self, datasheet):
        wargear = []
        if hasattr(datasheet, 'datasheets_wargear'):
            for wargear_data in datasheet.datasheets_wargear:
                wargear.append(Wargear(wargear_data))
        return wargear

    def __str__(self):
        return f"{self.name} ({len(self.models)} models)"

    def __repr__(self):
        return f"Unit(name='{self.name}', models={len(self.models)})"
