from typing import Union, Dict, List, Optional
from enum import Enum, auto
import re
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

    ###########################################################################
    ### Wargear profile damage potential
    ###########################################################################
    def get_damage_potential(self, target_unit: Optional['Unit'] = None) -> float:
        """
        Estimate the damage potential of this weapon profile.
        If a target unit is provided, consider its toughness in the calculation.
        """
        # Average number of attacks
        if isinstance(self.attacks, Count):
            avg_attacks = self.attacks.stat_average()
        else:
            avg_attacks = self.attacks or 0

        # Chance to hit
        if self.is_torrent():
            chance_to_hit = 1.0
        elif isinstance(self.skill, int) and self.skill > 0:
            chance_to_hit = (7 - self.skill) / 6.0
        else:
            chance_to_hit = 1.0  # Assume always hits if skill is 0 or invalid

        # Chance to wound
        chance_to_wound = 0.5  # Default to 50% if no target is provided
        if target_unit:
            target_toughness = target_unit.toughness
            strength = self.strength
            if isinstance(strength, int) and isinstance(target_toughness, int):
                if strength >= target_toughness * 2:
                    chance_to_wound = 5/6
                elif strength > target_toughness:
                    chance_to_wound = 4/6
                elif strength == target_toughness:
                    chance_to_wound = 3/6
                elif strength <= target_toughness / 2:
                    chance_to_wound = 1/6
                else:
                    chance_to_wound = 2/6

        # Average damage per hit
        if isinstance(self.damage, DiceCollection):
            avg_damage = self.damage.stat_average()
        else:
            avg_damage = self.damage or 0

        #######################################################################
        # Handle special rules (simplified)
        #######################################################################
        # Handle 'Sustained Hits'
        sustained_hits_value = self.is_sustained_hits()
        if sustained_hits_value > 0:
            sustained_hits_bonus = avg_attacks * chance_to_hit * (sustained_hits_value / 6.0)
            avg_attacks += sustained_hits_bonus

        # TODO - handle rest of special rules
        #######################################################################

        # Expected damage
        expected_damage = avg_attacks * chance_to_hit * chance_to_wound * avg_damage

        # Return the estimated damage potential
        return expected_damage

    ###########################################################################
    ### Wargear profile type checks
    ###########################################################################
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

    def get_damage_potential(self) -> float:
        """Estimate the total damage potential of this wargear (all profiles)."""
        return max(profile.get_damage_potential() for profile in self.profiles.values())

    ### Wargear type checks
    def is_melee(self) -> bool:
        return self.type.lower() == 'melee'

    def is_ranged(self) -> bool:
        return self.type.lower() == 'ranged'

    ### Wargear actions
    def attack(self, model: 'Model', target: 'Unit') -> None:
        pass


class WargearOptionType(Enum):
    ADDITIONAL = auto()
    REPLACEMENT = auto()


class WargearOption:
    def __init__(self, wargear_name: str, wargear_type: WargearOptionType, model_name: str, model_quantity: int, item_quantity: int, exclude_name: Optional[str] = None):
        self.wargear_name = wargear_name.lower()
        self.wargear_type = wargear_type
        self.model_name = model_name
        self.model_quantity = model_quantity
        self.item_quantity = item_quantity
        self.exclude_name = exclude_name.lower() if exclude_name else None

    def __str__(self):
        return f"{self.wargear_type.name}: {self.item_quantity}x {self.wargear_name} ({self.model_quantity}x {self.model_name})"

    def __repr__(self):
        return f"WargearOption(wargear_name='{self.wargear_name}', wargear_type={self.wargear_type.name}, model_name='{self.model_name}', model_quantity={self.model_quantity}, item_quantity={self.item_quantity}, exclude_name='{self.exclude_name}')"


def parse_option_string(option: str, unit_ref: 'Unit') -> WargearOption:
    if " can be equipped with " in option:
        parts = option.split(" can be equipped with ")
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

        return WargearOption(item_description, WargearOptionType.ADDITIONAL, model_description, model_count, item_count, not_equipped_with)
    elif " can be replaced with " in option:
        parts = option.split(" can be replaced with")
        if "This model’s " in parts[0]:
            orig_item = parts[0].replace("This model’s ", "").strip().lower()
        elif f"{unit_ref.name}’s " in parts[0]:
            orig_item = parts[0].replace(f"{unit_ref.name}’s ", "").strip().lower()
        elif f"{unit_ref.models[0].name}’s " in parts[0]:
            orig_item = parts[0].replace(f"{unit_ref.models[0].name}’s ", "").strip().lower()
        else:
            orig_item = parts[0].strip().lower()
        if orig_item.startswith("the"):
            orig_item = orig_item.replace("the ", "")
        if " and one of the following: " in parts[1] or " and 1 of the following: " in parts[1]:
            parts2 = parts[1].split(" and one of the following: ")
            new_item_1 = parts2[0].strip().replace('.', '').lower()
            new_item_2 = parts2[1].strip().lower()
            entries = []
            for entry in new_item_2.split(";"):
                entry = entry.replace(",", "").replace("and ", "")
                pattern = r'(\d+)\s+(.*?)(?=\s+\d+\s+|$)'
                matches = re.findall(pattern, entry)
                results = []
                for count, item in matches:
                    results.append(f"({count}) ({item.strip()})")
                entries.append(results)
            print(f"NOT IMPLEMENTED - WARGEAR ITEM REPLACEMENT: Original Item: {orig_item}, New Item: {new_item_1}, and ONE of: {entries} :: FULL STRING '{option}'")
        elif " one of the following: " in parts[1] or " 1 of the following: " in parts[1]:
            parts2 = parts[1].split(" of the following: ")
            new_item_2 = parts2[1].strip().lower()
            entries = []
            for entry in new_item_2.split(";"):
                entry = entry.replace(",", "").replace("and ", "")
                pattern = r'(\d+)\s+(.*?)(?=\s+\d+\s+|$)'
                matches = re.findall(pattern, entry)
                results = []
                for count, item in matches:
                    results.append(f"({count}) ({item.strip()})")
                if results:
                    entries.append(results)
            print(f"NOT IMPLEMENTED - WARGEAR ITEM REPLACEMENT: Original Item: {orig_item}, New Item ONE of: {entries} :: FULL STRING '{option}'")
        else:
            new_item = parts[1].strip().replace('.', '').lower()
            pattern = r'(\d+)\s+(.*?)(?=\s+\d+\s+|$)'
            matches = re.findall(pattern, new_item)
            results = []
            for count, item in matches:
                results.append(f"({count}) ({item.strip()})")
            print(f"NOT IMPLEMENTED - WARGEAR ITEM REPLACEMENT: Original Item: {orig_item}, New Item: {results} :: FULL STRING '{option}'")