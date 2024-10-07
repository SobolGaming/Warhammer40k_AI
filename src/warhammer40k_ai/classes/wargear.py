from typing import Union, Dict, List, Optional
from src.warhammer40k_ai.utility.dice import DiceCollection
from src.warhammer40k_ai.utility.range import Range
from src.warhammer40k_ai.utility.count import Count


class WargearProfile:
    def __init__(self, profile_name: str, wargear_data: Dict):
        self.name = profile_name
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


class Wargear:
    def __init__(self, wargear_data: Dict):
        self.name = wargear_data.get('name', '').replace('’', "'")
        if ' – ' in self.name:
            self.name, profile_name = self.name.split(' – ')
        else:
            profile_name = 'default'
        self.type = wargear_data.get('type', '')
        self.profiles = { profile_name: WargearProfile(profile_name, wargear_data) }

    def add_profile(self, profile_name: str, wargear_data: Dict):
        self.profiles[profile_name] = WargearProfile(profile_name, wargear_data)

    def __str__(self):
        str = f"{self.name} ({self.type}): "
        for profile in self.profiles:
            str += f"[{profile.name}: "
            str += f"Range {self.get_range(profile.name)}, A {self.get_attacks(profile.name)}, "
            str += f"BS/WS {self.get_skill(profile.name)}, S {self.get_strength(profile.name)}, "
            str += f"AP {self.get_ap(profile.name)}, D {self.get_damage(profile.name)}]"
        return str

    def __repr__(self):
        str = f"Wargear(name='{self.name}', type='{self.type}', "
        for profile_name, profile in self.profiles.items():
            str += f"[{profile_name}: "
            str += f"range={profile.range!r}, attacks={profile.attacks!r}, "
            str += f"skill={profile.skill!r}, strength={profile.strength!r}, "
            str += f"ap={profile.ap!r}, damage={profile.damage!r}]"
        return str + ")"

    def get_type(self) -> str:
        return self.type

    def get_range(self, profile_name: str = 'default') -> Range:
        return self.profiles[profile_name].range

    def get_attacks(self, profile_name: str = 'default') -> Count:
        return self.profiles[profile_name].attacks

    def get_skill(self, profile_name: str = 'default') -> int:
        return self.profiles[profile_name].skill

    def get_strength(self, profile_name: str = 'default') -> int:
        return self.profiles[profile_name].strength

    def get_ap(self, profile_name: str = 'default') -> int:
        return self.profiles[profile_name].ap

    def get_damage(self, profile_name: str = 'default') -> int:
        return self.profiles[profile_name].damage

    def get_keywords(self, profile_name: str = 'default') -> List[str]:
        return self.profiles[profile_name].keywords


class WargearOption:
    def __init__(self, wargear_name: str, model_name: str, model_quantity: int, item_quantity: int, exclude_name: Optional[str] = None):
        self.wargear_name = wargear_name.lower()
        self.model_name = model_name
        self.model_quantity = model_quantity
        self.item_quantity = item_quantity
        self.exclude_name = exclude_name.lower() if exclude_name else None

    def __str__(self):
        return f"{self.item_quantity}x {self.wargear_name} ({self.model_quantity}x {self.model_name})"

    def __repr__(self):
        return f"WargearOption(wargear_name='{self.wargear_name}', model_name='{self.model_name}', model_quantity={self.model_quantity}, item_quantity={self.item_quantity}, exclude_name='{self.exclude_name}')"
