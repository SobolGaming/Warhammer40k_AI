from typing import Union
from src.warhammer40k_ai.utility.dice import DiceCollection
from src.warhammer40k_ai.utility.range import Range
from src.warhammer40k_ai.utility.count import Count

class Wargear:
    def __init__(self, wargear_data):
        self.name = wargear_data.get('name', '')
        self.type = wargear_data.get('type', '')
        self.range = self._parse_range(wargear_data.get('range', ''))
        self.attacks = self._parse_attacks(wargear_data.get('A', ''))
        self.skill = self._parse_attribute(wargear_data.get('BS_WS', ''))
        self.strength = self._parse_attribute(wargear_data.get('S', ''))
        self.ap = self._parse_attribute(wargear_data.get('AP', ''))
        self.damage = self._parse_attribute(wargear_data.get('D', ''))
        self.keywords = self._parse_keywords(wargear_data.get('description', ''))

    def _parse_range(self, range_string: str) -> Range:
        if "Melee" == range_string:
            return Range.from_string("0")
        return Range.from_string(range_string)

    def _parse_attacks(self, attacks_string: str) -> Count:
        return Count.from_string(attacks_string)

    def _parse_attribute(self, attribute_value: str) -> Union[int, DiceCollection]:
        # Remove " and + from the attribute value
        attribute_value = attribute_value.replace("\"", "").replace("+", "")
        if "D" in attribute_value:
            return DiceCollection.from_string(attribute_value)
        elif 'N/A' == attribute_value:
            return 0
        else:
            return int(attribute_value)

    def _parse_keywords(self, keywords_string):
        if keywords_string:
            return [keyword.strip() for keyword in keywords_string.split(',')]
        return []

    def __str__(self):
        return (f"{self.name} ({self.type}): "
                f"Range {self.range}, A {self.attacks}, "
                f"BS/WS {self.skill}, S {self.strength}, "
                f"AP {self.ap}, D {self.damage}")

    def __repr__(self):
        return (f"Wargear(name='{self.name}', type='{self.type}', "
                f"range={self.range!r}, attacks={self.attacks!r}, "
                f"skill={self.skill!r}, strength={self.strength!r}, "
                f"ap={self.ap!r}, damage={self.damage!r})")
