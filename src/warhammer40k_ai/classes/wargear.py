from typing import Union, Dict, List, Optional
from warhammer40k_ai.utility.dice import DiceCollection
from warhammer40k_ai.utility.range import Range
from warhammer40k_ai.utility.count import Count

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .model import Model
    from .unit import Unit

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

    ### Wargear type checks
    def is_melee(self) -> bool:
        return self.type.lower() == 'melee'

    def is_ranged(self) -> bool:
        return self.type.lower() == 'ranged'

    def is_pistol(self) -> bool:
        return 'pistol' in [keyword.lower() for keyword in self.get_keywords()]

    def is_heavy(self) -> bool:
        return 'heavy' in [keyword.lower() for keyword in self.get_keywords()]

    def is_hazardous(self) -> bool:
        return 'hazardous' in [keyword.lower() for keyword in self.get_keywords()]

    def is_explosive(self) -> bool:
        return 'explosive' in [keyword.lower() for keyword in self.get_keywords()]

    def is_blast(self) -> bool:
        return 'blast' in [keyword.lower() for keyword in self.get_keywords()]

    def is_precision(self) -> bool:
        return 'precision' in [keyword.lower() for keyword in self.get_keywords()]

    def is_psychic(self) -> bool:
        return 'psychic' in [keyword.lower() for keyword in self.get_keywords()]

    def is_assault(self) -> bool:
        return 'assault' in [keyword.lower() for keyword in self.get_keywords()]

    def is_torrent(self) -> bool:
        return 'torrent' in [keyword.lower() for keyword in self.get_keywords()]

    def is_devastating_wounds(self) -> bool:
        return 'devastating wounds' in [keyword.lower() for keyword in self.get_keywords()]

    def is_ignores_cover(self) -> bool:
        return 'ignores cover' in [keyword.lower() for keyword in self.get_keywords()]

    def is_indirect_fire(self) -> bool:
        return 'indirect fire' in [keyword.lower() for keyword in self.get_keywords()]

    def is_lethal_hits(self) -> bool:
        return 'lethal hits' in [keyword.lower() for keyword in self.get_keywords()]

    def is_extra_attacks(self) -> int:
        return 'extra attacks' in [keyword.lower() for keyword in self.get_keywords()]

    def is_sustained_hits(self) -> int:
        for keyword in self.get_keywords():
            if keyword.lower().startswith('sustained hits'):
                parts = keyword.split()
                if len(parts) > 2 and parts[2].isdigit():
                    return int(parts[2])
                return 1  # Default to 1 if no number is specified
        return 0

    def is_rapid_fire(self) -> int:
        for keyword in self.get_keywords():
            if keyword.lower().startswith('rapid fire'):
                parts = keyword.split()
                if len(parts) > 2 and parts[2].isdigit():
                    return int(parts[2])
                return 1  # Default to 1 if no number is specified
        return 0

    def is_melta(self) -> bool:
        for keyword in self.get_keywords():
            if keyword.lower().startswith('melta'):
                parts = keyword.split()
                assert len(parts) == 2
                return parts[2]
        return "0"

    def is_anti(self):
        for keyword in self.get_keywords():
            if keyword.lower().startswith('anti-'):
                parts = keyword[4:].replace('+', '').split(' ')
                if len(parts) == 2 and parts[2].isdigit():
                    return parts[1].lower(), int(parts[2])
        return "", 0

    ### Wargear actions
    def attack(self, model: 'Model', target: 'Unit') -> None:
        pass


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
