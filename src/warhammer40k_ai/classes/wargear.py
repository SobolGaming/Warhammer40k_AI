from typing import Union, Dict, List, Optional
from enum import Enum, auto
from collections import namedtuple
import re
from warhammer40k_ai.utility.dice import DiceCollection, get_roll
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

    def get_keywords(self) -> List[str]:
        return self.keywords

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
        if target_unit and target_unit.models:  # Check if target has models before accessing properties
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

    def attack(self, target: 'Unit', attacker: 'Model') -> None:
        wound_instances = []
        hit_instances = []
        num_attacks = 0

        if isinstance(self.attacks, Count):
            num_attacks = self.attacks.resolve()
        else:
            num_attacks = self.attacks or 0

        closest_target, closest_dist = attacker.return_closest_model_in_unit(target)
        if closest_dist <= (self.range.max / 2) and self.is_rapid_fire() > 0:
            print(f"Rapid fire: +{self.is_rapid_fire()} attacks")
            num_attacks = self.is_rapid_fire()

        if self.is_blast():
            target_model_count = len(target.models)
            num_attacks_modifier = int(target_model_count / 5)
            print(f"Blast: +{num_attacks_modifier} attacks")
            num_attacks += num_attacks_modifier

        for _ in range(num_attacks):
            print(f"Attack {_ + 1} of {num_attacks}")
            attack_instance = {
                'crit_hit': False,
                'crit_wound': False,
                'mortal_wound': False,
                'below_half_distanct': closest_dist <= (self.range.max / 2),
                'damage': 0
            }
            # check if we hit
            if self.hit_target(target, attacker, attack_instance):
                hit_instances.append(attack_instance)
            if hasattr(attack_instance, 'sustained_hit'):
                for _ in range(attack_instance['sustained_hit']):
                    hit_instances.append(attack_instance)

        for _, hit_instance in enumerate(hit_instances):
            # check if we wound
            print(f"Wound Evaluation: {_ + 1} of {len(hit_instances)}")
            if self.wound_target(target, attacker, hit_instance):
                wound_instances.append(hit_instance)

        for _, attack_instance in enumerate(wound_instances):
            # Allocate damage instances to the target unit
            target_model = self.opponent_wound_allocation(target)
            if target_model is None:
                print(f"No valid target model found in unit {target.name} - unit may be destroyed")
                continue
                
            if attack_instance['mortal_wound'] or target_model.failed_saving_throw(attack_instance, self.ap):
                dmg_value = self.damage_target(target_model, attacker, attack_instance)
                # 10th Edition: Apply damage to the target model, excess damage is lost
                excess_damage = target_model.take_damage(dmg_value, attack_instance['mortal_wound'])
                print(f"{target_model.name} took {dmg_value}{' mortal' if attack_instance['mortal_wound'] else ''} damage")
                # In 10th edition, excess damage is lost (no spillover to other models)
                if excess_damage > 0:
                    print(f"Excess damage of {excess_damage} is lost (10th edition rules)")
        return

    def hit_target(self, target: 'Unit', attacker: 'Model', attack_instance: Dict) -> bool:
        # TODO - handle cover
        # TODO - handle stealth and other keyword on target unit
        # TODO - handle positive skill modifiers on shooter

        if self.is_torrent():
            print("\tTorrent: always hits")
            return True

        dice_roll = get_roll("D6")
        if dice_roll == 1:  # unmodified dice roll of 1 is always a miss
            print("\tunmodified dice roll of 1 is always a miss")
            return False
        elif dice_roll == 6:  # unmodified dice roll of 6 is always a hit
            print("\tunmodified dice roll of 6 is a crit hit")
            attack_instance['crit_hit'] = True
            if self.is_lethal_hits():
                print("\t\tLethal hits: crit hit is lethal")
                attack_instance['lethal_hit'] = True
            if self.is_sustained_hits() > 0:
                print(f"\t\tSustained hits: +{self.is_sustained_hits()} hits")
                attack_instance['sustained_hit'] = self.is_sustained_hits()
            return True

        dice_modifier = 0
        if self.is_heavy() and attacker.parent_unit.round_state.remained_stationary_this_round:
            print("\tHeavy: +1 to hit modifier since unit remained stationary this round")
            dice_modifier += 1
        dice_modifier = min(max(dice_modifier, -1), 1)  # modifications are capped between -1 and 1
        print(f"\t\tSkill: {self.skill}, dice_modifier: {dice_modifier}, dice_roll: {dice_roll} -> {self.skill > 0 and dice_roll >= (self.skill + dice_modifier)}")
        return self.skill > 0 and dice_roll >= (self.skill + dice_modifier)

    def wound_target(self, target: 'Unit', attacker: 'Model', attack_instance: Dict) -> bool:
        if hasattr(attack_instance, 'lethal_hit') and attack_instance['lethal_hit']:
            print("\tLethal hit: always wounds")
            return True

        # Check if target unit still has models before accessing properties
        if not target.models:
            print(f"\tTarget unit {target.name} has no models left - cannot wound")
            return False

        target_toughness = target.toughness
        strength = self.strength
        dice_roll = get_roll("D6")

        if self.is_twin_linked():
            # TODO - you can re-roll the wound roll
            pass

        if dice_roll == 1:  # unmodified dice roll of 1 is always a miss
            print("\t\tunmodified dice roll of 1 is always a miss")
            return False
        elif dice_roll == 6:  # unmodified dice roll of 6 is always a hit
            print("\t\tunmodified dice roll of 6 is a crit wound")
            attack_instance['crit_wound'] = True
            if self.is_devastating_wounds():
                print("\t\tDevastating wounds: crit wound is mortal")
                attack_instance['mortal_wound'] = True
            return True

        anti_keyword, anti_value = self.is_anti()
        if anti_keyword and target.has_keyword(anti_keyword):
            if dice_roll >= anti_value:
                print(f"\t\tAnti-{anti_keyword}: +{anti_value} to wound modifier")
                attack_instance['crit_wound'] = True
                if self.is_devastating_wounds():
                    print("\t\t\tDevastating wounds: crit wound is mortal")
                    attack_instance['mortal_wound'] = True
                return True

        dice_modifier = 0
        # TODO - handle positive and negative modifiers for wounding
        dice_modifier = min(max(dice_modifier, -1), 1)  # modifications are capped between -1 and 1
        dice_roll += dice_modifier

        if strength >= (target_toughness * 2):
            print(f"\t\tStrength: {strength}, Toughness: {target_toughness}, dice_roll: {dice_roll} -> {dice_roll >= 2}")
            return dice_roll >= 2
        elif strength > target_toughness:
            print(f"\t\tStrength: {strength}, Toughness: {target_toughness}, dice_roll: {dice_roll} -> {dice_roll >= 3}")
            return dice_roll >= 3
        elif strength == target_toughness:
            print(f"\t\tStrength: {strength}, Toughness: {target_toughness}, dice_roll: {dice_roll} -> {dice_roll >= 4}")
            return dice_roll >= 4
        elif strength < (target_toughness / 2):
            print(f"\t\tStrength: {strength}, Toughness: {target_toughness}, dice_roll: {dice_roll} -> {dice_roll >= 5}")
            return dice_roll >= 5
        else:
            print(f"\t\tStrength: {strength}, Toughness: {target_toughness}, dice_roll: {dice_roll} -> {dice_roll >= 6}")
            return dice_roll >= 6
        return False

    def opponent_wound_allocation(self, target: 'Unit') -> Optional['Model']:
        # Check if the unit has any models left
        if not target.models:
            print(f"Warning: Unit {target.name} has no models left for wound allocation")
            return None
            
        _, damaged_model = target.is_max_health()
        if damaged_model:
            return damaged_model
        else:
            # TODO - implement AI selection of target model
            return target.models[0]

    def damage_target(self, target_model: 'Model', attacker: 'Model', attack_instance: Dict) -> int:
        damage_value = self.damage.roll() if isinstance(self.damage, DiceCollection) else self.damage
        if self.is_melta() and attack_instance['below_half_distance']:
            damage_value += self.is_melta()
        return damage_value

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

    def is_lance(self) -> bool:
        return 'lance' in [keyword.lower() for keyword in self.get_keywords()]

    def is_twin_linked(self) -> bool:
        return 'twin-linked' in [keyword.lower() for keyword in self.get_keywords()]

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
                if len(parts) > 2:
                    if parts[2].isdigit():
                        return int(parts[2])
                    else:
                        raise Exception(f"Invalid sustained hits value: {keyword}")
                return 1  # Default to 1 if no number is specified
        return 0

    def is_rapid_fire(self) -> int:
        for keyword in self.get_keywords():
            if keyword.lower().startswith('rapid fire'):
                parts = keyword.split()
                if len(parts) > 2:
                    if parts[2].isdigit():
                        return int(parts[2])
                    else:
                        raise Exception(f"Invalid rapid fire value: {keyword}")
                return 1  # Default to 1 if no number is specified
        return 0

    def is_melta(self) -> int:
        for keyword in self.get_keywords():
            if keyword.lower().startswith('melta'):
                parts = keyword.split()
                assert len(parts) == 2
                return int(parts[2])
        return 0

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

    def get_damage_potential(self, target_unit: Optional['Unit'] = None) -> float:
        """Estimate the total damage potential of this wargear (all profiles)."""
        return max(profile.get_damage_potential(target_unit) for profile in self.profiles.values())

    ### Wargear type checks
    def is_melee(self) -> bool:
        return self.type.lower() == 'melee'

    def is_ranged(self) -> bool:
        return self.type.lower() == 'ranged'

    def maximum_range(self, profile_name: Optional[str] = None) -> int:
        max_range = 0
        if profile_name is None:
            for profile in self.profiles.values():
                max_range = max(max_range, profile.range.max)
        else:
            max_range = self.profiles[profile_name].range.max
        return max_range

    ### Wargear actions
    def attack(self, model: 'Model', target: 'Unit') -> None:
        pass


class WargearOptionType(Enum):
    ADDITIONAL = auto()
    REPLACEMENT = auto()


Quantity = namedtuple('Quantity', ['min', 'max'])


class WargearOption:
    def __init__(self, wargear_type: WargearOptionType, wargear_from: List[str] = [], 
                 wargear_to: List[str] = [], model_name: str = '', 
                 model_quantity: Quantity = Quantity(min=1, max=1),
                 item_quantity: Quantity = Quantity(min=1, max=1),
                 conditionals: Optional[List[str]] = []):
        self.wargear_from = wargear_from
        self.wargear_to = wargear_to
        self.wargear_type = wargear_type
        self.model_name = model_name
        # Convert model_quantity to ModelQuantity namedtuple
        if isinstance(model_quantity, (int, float)):
            self.model_quantity = Quantity(min=model_quantity, max=model_quantity)
        elif isinstance(model_quantity, tuple):
            self.model_quantity = Quantity(*model_quantity)
        else:
            self.model_quantity = ModelQuantity(min=1, max=1)  # Default values
        self.item_quantity = item_quantity
        self.conditionals = [conditional.lower() for conditional in conditionals] if conditionals else []

    def __str__(self):
        from_str = ', '.join(str(x) for x in self.wargear_from) if self.wargear_from else 'none'
        to_items = []
        for sublist in self.wargear_to:
            to_items.extend(str(item) for item in sublist)
        to_str = ', '.join(to_items) if to_items else 'none'
        conditionals = f"{self.conditionals}"
        quantity_str = (f"{self.model_quantity.min}-{self.model_quantity.max}" 
                       if self.model_quantity.min != self.model_quantity.max 
                       else str(self.model_quantity.min))
        return (f"{self.wargear_type.name}: {self.item_quantity}x [{from_str}] -> [{to_str}] "
                f"({quantity_str}x {self.model_name}{conditionals})")

    def __repr__(self):
        return (f"WargearOption(wargear_type={self.wargear_type}, "
                f"wargear_from={self.wargear_from!r}, wargear_to={self.wargear_to!r}, "
                f"model_name='{self.model_name}', model_quantity={self.model_quantity}, "
                f"item_quantity={self.item_quantity}, conditionals={self.conditionals!r})")


def parse_option_string(option: str, unit_ref: 'Unit') -> Optional[WargearOption]:
    parsed_result = parse_alternate(option)
    if parsed_result:
        if not parsed_result["original_item"]:
            print(f" PARSED ADDITIONAL RESULT: {parsed_result}")
            return WargearOption(WargearOptionType.ADDITIONAL, parsed_result["original_item"], parsed_result["replacement_options"], parsed_result["model"], parsed_result["model_count"], 1, parsed_result["condition"])
        else:
            print(f"PARSED REPLACEMENT RESULT: {parsed_result}")
            return WargearOption(WargearOptionType.REPLACEMENT, parsed_result["original_item"], parsed_result["replacement_options"], parsed_result["model"], parsed_result["model_count"], 1, parsed_result["condition"])
    return None

def parse_option_string2(option: str, unit_ref: 'Unit') -> Optional[WargearOption]:
    original_option = option
    unique_model_names = unit_ref.get_unique_model_names()
    model_name_1 = unique_model_names[0].rstrip('s')
    if len(unique_model_names) > 1:
        model_name_2 = unique_model_names[1].rstrip('s')
    else:
        model_name_2 = "abcdefghijklmnopqrstuvwxyz"
    if len(unique_model_names) > 2:
        model_name_3 = unique_model_names[2].rstrip('s')
    else:
        model_name_3 = "abcdefghijklmnopqrstuvwxyz"
    if len(unique_model_names) > 3:
        print(f"WARNING: More than 3 unique model names found: {unique_model_names}")

    if any(x in option for x in [" can be equipped with ", " can each be equipped with "]):
        parts = option.split(" be equipped with ")
        if len(parts) != 2:
            print(f"Invalid wargear option format: {option}")
            return
        parts[0] = parts[0].replace("can each", "").replace("can", "")

        model_description, item_description = parts
        model_count = None  # Changed to None as default
        
        # Handle "Any number of models" case
        if model_description.lower().startswith("any number of"):
            model_count = "any"
            model_description = "model"
        # Extract model count if specified
        elif model_description.startswith(('1 ', '2 ', '3 ', '4 ', '5 ', '6 ', '7 ', '8 ', '9 ')):
            model_count = int(model_description.split()[0])
            model_description = ' '.join(model_description.split()[1:])

        item_count = 1 # Default to 1 item
        # Extract item count if specified
        if item_description.startswith(('1 ', '2 ', '3 ', '4 ', '5 ', '6 ', '7 ', '8 ', '9 ')):
            item_count = int(item_description.split()[0])
            item_description = ' '.join(item_description.split()[1:]).strip().replace('.', '')

        # Parse "not equipped with" condition
        not_equipped_with = ''
        if "that is not equipped with" in model_description:
            model_parts = model_description.split("that is not equipped with")
            model_description = model_parts[0].strip()
            not_equipped_with = model_parts[1].strip()
            # Remove leading "a" or "an" from not_equipped_with
            if not_equipped_with.startswith("a "):
                not_equipped_with = not_equipped_with[2:].strip()
            elif not_equipped_with.startswith("an "):
                not_equipped_with = not_equipped_with[3:].strip()
        #print(f"{option}")
        parsed_result = {
            "condition": not_equipped_with,  # Now the condition will be properly included
            "model": model_description.strip(),
            "model_count": 100 if model_count == "any" else int(model_count) if model_count else 0,
            "original_item": [],
            "replacement_options": [item_description]
        }
        print(f" PARSED ADDITIONAL RESULT: {parsed_result}")
        #return WargearOption(WargearOptionType.ADDITIONAL, parsed_result["original_item"], parsed_result["replacement_options"], parsed_result["model"], parsed_result["model_count"], 1, parsed_result["condition"])

    elif any(x in option for x in [" can be replaced with", " can each be replaced with", " can each have their "]):
        # Add handling for "Any number of models" at the start of pattern
        model = "model"
        if option.startswith("Any number of "):
            count = "any"
            option = option.replace("Any number of ", "")
            # Clean up the option string to match our expected format
            if " can each have their " in option:
                option = option.replace(" can each have their ", " ").replace(" replaced with ", " can be replaced with ")
        else:
            count = None  # Default count to None

        # Improved condition extraction
        condition = ""
        if option.startswith("If this unit"):
            condition_end = option.find(",")
            if condition_end != -1:
                condition = option[:condition_end].strip()
                option = option[condition_end + 1:].strip()
        elif option.startswith("For every"):  # Handle mid-sentence conditions
            condition_start = option.find("For every")
            condition_end = option.find(",", condition_start)
            if condition_end != -1:
                condition = option[condition_start:condition_end].strip()
                option = option[:condition_start].strip() + " " + option[condition_end + 1:].strip()
        elif option.startswith("Up to"):
            count_match = re.match(r"Up to (\d+)", option)
            if count_match:
                count = int(count_match.group(1))
                # Remove "Up to" and clean up the option string
                option = re.sub(r"^Up to \d+ models", f"{count} models", option)
                # Also handle the "can each have their" case
                if " can each have their " in option:
                    option = option.replace(" can each have their ", " ").replace(" replaced with ", " can be replaced with ")

        # some pre-pattern cleaning
        description = option.replace("’s", "'s").replace(",", " and")

        pattern = re.compile(
            r"(?P<model>(?:This model|The " + re.escape(model_name_1) + r"|The " + re.escape(model_name_2) + r"|The " + re.escape(model_name_3) + 
            r"|" + re.escape(model_name_1) + r" model|" + re.escape(model_name_2) + r" model|" + re.escape(model_name_3) + r" model|(?:\d+ )?(?:model|models|" + 
            re.escape(model_name_1) + r"s?|" + re.escape(model_name_2) + r"s?|" + re.escape(model_name_3) + r"s?)))"
            # Modified to handle possessive cases with apostrophes
            r"(?:'s|\s+)(?P<original_item>(?:\d+ )?[\w '\-]+(?:\s+and\s+(?:\d+ )?[\w '\-]+)*) can(?:\s+each)? be replaced with(?:\s*:)?\s*"
            r"(?:"
                r"(?P<single_replacement>(?:\d+ )?[\w '\-]+(?:\s+and\s+(?:\d+ )?[\w '\-]+)*(?:$|\.|\;))|"
                r"(?:(?P<first_replacement>(?:\d+ )?[\w '\-]+(?:\s+and\s+(?:\d+ )?[\w '\-]+)*) and )?one of the following:\s*"
                r"(?P<replacement_options>(?:(?:\d+ )?[\w '\-]+(?:\s+and\s+(?:\d+ )?[\w '\-]+)*(?:;|,|\.)(?:\s*(?:\d+ )?[\w '\-]+(?:\s+and\s+(?:\d+ )?[\w '\-]+)*(?:;|,|\.)*)*))"
            r")"
        )
        
        # Match the pattern in the description
        match = pattern.search(description)
        
        if not match:
            print(f"DESCRIPTION: {description}")
            print(f"REPLACEMENT MATCH FAILED - INVALID WARGEAR OPTION: {original_option}")
            return None
        
        # Extract the components and include condition in parsed_result
        model = match.group("model") or model
        original_item = match.group("original_item")
        single_replacement = match.group("single_replacement")
        replacement_options_str = match.group("replacement_options")
        
        # Process replacement options
        if single_replacement:
            options = [single_replacement]
        elif replacement_options_str:
            first_replacement = match.group("first_replacement")
            # Split by semicolon or comma followed by optional whitespace
            parts = re.split(r'[;,]\s*', replacement_options_str)
            options = [part.strip().rstrip('.') for part in parts if part.strip()]
            
            # If there's a first replacement, combine it with all other options
            if first_replacement:
                options = [f"{first_replacement} and {opt}" for opt in options]
        else:
            options = []
        
        # Clean up options
        options = [opt.strip().rstrip('.').replace(",", " and ") for opt in options if opt]
        replacement_options = []
        for specific_option in options:
            opt_lines = [item.strip() for item in specific_option.split(" and ")]
            results = []
            for opt in opt_lines:
                # Extract count if present, default to 1
                count_match = re.match(r'^(\d+)\s+(.+)$', opt)
                if count_match:
                    item_count, item_name = count_match.groups()
                    item_count = int(item_count)
                else:
                    item_count = 1
                    item_name = opt
                results.append(f"({item_count}) ({item_name.strip().lower()})")
            replacement_options.append(results)

        original_items = [item.strip() for item in original_item.split(" and ")]
        results = []
        for item in original_items:
            # Extract count if present, default to 1
            count_match = re.match(r'^(\d+)\s+(.+)$', item)
            if count_match:
                item_count, item_name = count_match.groups()
                item_count = int(item_count)
            else:
                item_count = 1
                item_name = item
            # Remove "number of models" from item name if present
            item_name = item_name.replace("number of models ", "")
            results.append(f"({item_count}) ({item_name.strip().lower()})")
        original_item = [results]

        parsed_result = {
            "condition": condition,  # Now the condition will be properly included
            "model": model.strip(),
            "model_count": 100 if count == "any" else int(count) if count else 1,
            "original_item": original_item,
            "replacement_options": replacement_options
        }
        #print(f"NOT IMPLEMENTED - WARGEAR ITEM REPLACEMENT: FULL STRING '{option}'")
        print(f"PARSED REPLACEMENT RESULT: {parsed_result}")
        #return WargearOption(WargearOptionType.REPLACEMENT, parsed_result["original_item"], parsed_result["replacement_options"], parsed_result["model"], parsed_result["model_count"], 1, parsed_result["condition"])
    else:
        print(f"INVALID WARGEAR OPTION: {original_option}")
        return None

def parse_alternate(description):
    description = description.replace("’", "'").lower()
    print(f"{description}")
    return {}

    condition = ""
    model_limit = ""
    item_limit = ""
    actor = ""
    base_wargear_qualifier = ""

    if description.startswith("the "):
        marker = description.find("'s ")
        if marker == -1:
            marker = description.find("' ")
        if marker != -1:
            actor = description[4:marker].strip()
            model_limit = "1"
            description = description[marker+3:].strip()

    if description.startswith("for every"):
        marker = description.find(",")
        if marker != -1:
            condition = description[:marker].strip()
            description = description[marker+1:].strip()
    elif description.startswith("for each "):
        marker = description.find(",")
        if marker != -1:
            condition = description[:marker].strip()
            description = description[marker+1:].strip()
        if "model" in condition:
            actor = "model"

    if description.startswith("all of the models in this unit"):
        condition = "all or none"
        model_limit = "100"
        actor = "model"
        description = description[30:].strip()

    if description.startswith("if this unit contains"):
        marker = description.find(",")
        if marker != -1:
            condition = description[:marker].strip()
            description = description[marker+1:].strip()
    elif description.startswith("if this unit's "):
        marker = description.find(",")
        start_marker = 0
        if marker != -1:
            model_marker = description.find("is equipped ")
            if model_marker != -1:
                actor = description[15:model_marker].strip()
                start_marker = model_marker
            condition = description[start_marker:marker].strip()
            description = description[marker+1:].strip()
    elif description.startswith("if this model is equipped with "):
        actor = "model"
        marker = description.find(",")
        if marker != -1:
            condition = description[17:marker].strip()
            description = description[marker+1:].strip()

    if description.startswith("up to "):
        marker = description.find("models")
        if marker != -1:
            parts = description[:marker+6].replace("up to ", "").split(" ")
            model_limit = parts[0]
            actor = parts[1]
            if actor[-1] == "s":
                actor = actor[:-1]
            description = description[marker+6:].strip()
        else:
            marker = description.find("can ")
            if marker != -1:
                model_limit, actor = description[5:marker].replace("up to ", "").strip().split(" ", 1)
                description = description[marker:].strip()
    if description.startswith("this model's"):
        actor = "model"
        model_limit = "1"
        description = description[13:].strip()
    if description.startswith("any number of") or description.startswith("any numbers of"):
        # address inconsistency
        if description.startswith("any numbers of"):
            description = description.replace("any numbers of", "any number of")
        marker = description.find("models")
        if marker != -1:
            model_limit = "any number of"
            actor = "model"
            if description[marker+6] == "'":
                description = description[marker+7:].strip()
            else:
                description = description[marker+6:].strip()
        else:
            marker = description.find("can each")
            if marker != -1:
                model_limit = "any number of"
                actor = description[14:marker].strip()
                description = description[marker+8:].strip()
    if "model's" in description:
        marker = description.find("model's")
        if marker != -1:
            actor = "model"
            if description.startswith("each of this "):
                condition = "per base wargear"
            elif " of this " in description[:marker]:
                base_wargear_qualifier = description[:marker].split(" of this ")[0].strip()
                model_limit = "1"
            else:
                model_limit = description[:marker].strip()
            description = description[marker+7:].strip()
    elif description.startswith("each model ") and "it is equipped with" in description:
        condition = "per base wargear"
        actor = "model"
        description = description[11:].strip()
        description = description.replace("it is equipped with", "")

    if not actor:
        marker = description.find("'")
        if marker != -1:
            parts = description[:marker].split(" ")
            model_limit = parts[0]
            if model_limit == "each":
                model_limit = "1"
                condition = "per model"
            actor = ' '.join(parts[1:]).strip()
            description = description[marker+2:].strip()

    replacement_options = []
    if "replaced with" in description:
        parts = description.split("replaced with")
        base_wargear = [parts[0].replace("can have each", "").replace("can be ", "").replace("can each be ", "").replace("can each ", "").replace("have their ", "").replace("its ", "").strip()]
        replacement_options = parts[1].strip().replace(".", "")
    elif "is equipped with: " in description:
        actor, replacement_options = description.split("is equipped with")
        base_wargear = ""
        model_limit = "1"
    elif "equipped with" in description:
        what, replacement_options = description.rsplit("equipped with", 1)
        two_equipped_with = False
        if "not equipped with" in what:
            two_equipped_with = True
            what = what.replace("not equipped with an", "not equipped with a")
            who, what = what.rsplit("not equipped with a", 1)
            what = what.replace("can have each", "").replace("can be ", "").replace("can each be ", "").replace("can each ", "").replace("have their ", "").replace("its ", "").strip()
            condition = "not equipped with [" + what + "]"
            what = ""
            model_limit, actor = who.split(" ", 1)
            actor = actor.replace("that is", "")
        elif "equipped with" in what:
            two_equipped_with = True
            what = what.replace("equipped with an", "equipped with a")
            who, what = what.rsplit("equipped with a", 1)
            model_limit, actor = who.split(" ", 1)
        elif "this model can be" in what:
            actor = "model"
            model_limit = "1"
            what = what.replace("this model can be", "").strip()
        elif what.startswith("the "):
            marker = what.find("can be ")
            if marker != -1:
                actor = what[4:marker].strip()
                what = what[marker+7:].strip()
        what = what.replace("it can be ", "").replace("can be ", "").replace("can each be ", "").replace("can each ", "").replace("have their ", "").strip()
        if what == "1 model":
            what = ""
            model_limit = "1"
            actor = "model"
        base_wargear = [what] if what else []
        if " additional " in replacement_options and two_equipped_with:
            model_limit, replacement_options = replacement_options.split(" additional ", 1)
        replacement_options = replacement_options.strip().replace(".", "").replace("additional ", "")

    if not replacement_options:
        return {}

    # adjust for inconsistency
    replacement_options = replacement_options.replace("1 of the following: ", "one of the following: ")
    replacement_options = replacement_options.replace("2 of the following: ", "two of the following: ")
    model_limit = model_limit.replace("one", "1").replace("two", "2")

    if "one of the following: " in replacement_options:
        item_limit = "1"
        marker = replacement_options.find("one of the following: ")
        and_marker = replacement_options.find(" and ")
        replacement_option_and = None
        if and_marker != -1 and and_marker < marker:
            replacement_option_and = replacement_options[:and_marker]
            print(f"REPLACEMENT OPTION AND: {replacement_option_and}")
        replacement_options = replacement_options[marker+22:].rstrip(";")
        replacement_options = [item.replace(",", " and").strip() for item in replacement_options.split(";")]
        if replacement_option_and:
            new_replacement_options = []
            for item in replacement_options:
                new_replacement_options.append(replacement_option_and + " and " + item)
            replacement_options = new_replacement_options
    elif "two of the following: " in replacement_options:
        item_limit = "2"
        marker = replacement_options.find("two of the following: ")
        and_marker = replacement_options.find(" and ")
        replacement_option_and = None
        if and_marker != -1 and and_marker < marker:
            replacement_option_and = replacement_options[:and_marker]
        replacement_options = replacement_options[marker+22:].rstrip(";")
        replacement_options = [item.replace(",", " and").strip() for item in replacement_options.split(";")]
        if replacement_option_and:
            new_replacement_options = []
            for item in replacement_options:
                new_replacement_options.append(replacement_option_and + " and " + item)
            replacement_options = new_replacement_options
    else:
        if replacement_options.startswith(":"):
            replacement_options = replacement_options[1:].replace(".",  "").strip()
        if replacement_options[-1] == ";":
            replacement_options = replacement_options[:-1]
        and_marker = replacement_options.find(" and ")
        replacement_option_and = None
        if and_marker != -1:
            replacement_option_and = replacement_options[:and_marker]
        replacement_options = replacement_options.rstrip(";")
        replacement_options = [item.replace(",", " and").strip() for item in replacement_options.split(";")]
        if replacement_option_and:
            new_replacement_options = []
            for item in replacement_options:
                new_replacement_options.append(replacement_option_and + " and " + item)
            replacement_options = new_replacement_options

    if base_wargear_qualifier:
        adjusted_base_wargear = []
        for base_wargear_item in base_wargear:
            adjusted_base_wargear.append(base_wargear_qualifier + " " + base_wargear_item)
        base_wargear = adjusted_base_wargear

    base_wargear = parse_wargear_item(base_wargear)
    replacement_options = parse_wargear_item(replacement_options)

    #print(f"CONDITION: {condition}")
    #print(f"MODEL LIMIT: {model_limit}")
    #print(f"ACTOR: {actor}")
    #print(f"BASE WARGEAR: {base_wargear}")
    #print(f"ITEM LIMIT: {item_limit}")
    #print(f"REPLACEMENT OPTIONS: {replacement_options}\n")

    try:
        parsed_result = {
            "condition": condition,  # Now the condition will be properly included
            "model": actor,
            "model_count": 100 if model_limit == "any number of" else int(model_limit) if model_limit else 1,
            "item_count": 100 if item_limit == "any number of" else int(item_limit) if item_limit else 1,
            "original_item": base_wargear,
            "replacement_options": replacement_options
        }
    except Exception as e:
        #print(f":: ERROR PARSING WARGEAR :: {e}")
        return {}

    return parsed_result

def parse_warger_actor_string(actor_str: str) -> str:
    actor = actor_str
    condition = ""

    if actor_str[-1] == "s":
        actor = actor_str[:-1]
    if " equipped with " in actor:
        match = re.match(r"^([\w\s'-]+) equipped with an? (.*)", actor)
        actor = match.group(1)
        condition = "equipped with " + match.group(2)
    return actor, condition

def parse_wargear_string_ending(ending: str) -> tuple[list[tuple[int, str]], int]:
    if " additional " in ending:
        ending = ending.replace(" additional ", " ")
    add_post_conditional = False
    if "following:*" in ending:
        ending = ending.replace("*", "")
        add_post_conditional = True

    if "one of the following: " in ending:
        marker = ending.find(" one of the following: ")
        and_marker = ending.find(" and ")
        addition = ""
        if and_marker != -1 and and_marker < marker:
            addition = ending[:and_marker]
            ending = ending[and_marker+5:]
        ending = ending.replace("one of the following: ", "")
        if ending[-1] == ";":
            ending = ending[:-1]
        ending = ending.replace(", ", " and ")
        parsed_ending = ending.split(";")
        if add_post_conditional:
            parsed_ending = [item + "*" for item in parsed_ending]
        if addition:
            new_parsed_ending = []
            for item in parsed_ending:
                new_parsed_ending.append(addition + " and " + item)
            parsed_ending = new_parsed_ending
        return parse_wargear_item(parsed_ending), 1
    elif "up to two of the following: " in ending:
        marker = ending.find(" up to two of the following: ")
        and_marker = ending.find(" and ")
        addition = ""
        if and_marker != -1 and and_marker < marker:
            addition = ending[:and_marker]
            ending = ending[and_marker+5:]
        ending = ending.replace("up to two of the following: ", "")
        if ending[-1] == ";":
            ending = ending[:-1]
        ending = ending.replace(", ", " and ")
        parsed_ending = ending.split(";")
        if add_post_conditional:
            parsed_ending = [item + "*" for item in parsed_ending]
        if addition:
            new_parsed_ending = []
            for item in parsed_ending:
                new_parsed_ending.append(addition + " and " + item)
            parsed_ending = new_parsed_ending
        return parse_wargear_item(parsed_ending), 2
    else:
        return parse_wargear_item([ending]), 1

def parse_wargear_itemlist(item_str: str) -> list[tuple[int, str]]:
    item_str = item_str.replace(" or ", "; ")
    if item_str[-1] == ";":
        item_str = item_str[:-1]
    item_str = item_str.replace(", ", " and ")
    return parse_wargear_item(item_str.split(";"))

def parse_wargear_item(item_str: str) -> list[tuple[int, str]]:
    full_result = []
    for specific_option in item_str:
        #print(f"SPECIFIC OPTION: {specific_option}")
        opt_lines = [item.strip() for item in specific_option.split(" and ")]
        results = []
        for opt in opt_lines:
            # Extract count if present, default to 1
            count_match = re.match(r'^(\d+)\s+(.+)$', opt)
            if count_match:
                item_count, item_name = count_match.groups()
                item_count = int(item_count)
            else:
                item_count = 1
                item_name = opt
            results.append((item_count, item_name.strip().lower()))
        full_result.append(results)
    return full_result

def parse_alternate_2(str_list: list[str]) -> list[WargearOption]:
    from collections import defaultdict
    starts_with_dict = defaultdict(list)

    # stored variables
    wargear_options = []
    unhandled = False

    for line in str_list:
        # reset variables
        is_replacement = False
        actor = ""
        condition = ""
        model_limit = Quantity(min=1, max=1)
        item_limit = Quantity(min=1, max=1)
        items_to_replace = []
        replacement_items = []

        # some sanitization of inconsistencies
        description = line.lower().replace("’", "'").replace(".", "").replace('model"s', "model's").replace("for every four models", "for every 4 models")
        print(f"\nDESCRIPTION: {description}")
        if " replaced " in description or " replace " in description:
            is_replacement = True

        if description.startswith("this model's"):
            starts_with_dict["this model's"].append(description)
            actor = "model"
        elif description.startswith("1 model's") or description.startswith("one model's"):
            starts_with_dict["1 model's"].append(description)
            actor = "model"
        elif description.startswith("this model can be"):
            starts_with_dict["this model can be"].append(description)
            actor = "model"
        elif description.startswith("1 model can be") or description.startswith("one model can be:"):
            starts_with_dict["1 model can be"].append(description)
            actor = "model"
        elif description.startswith("1 model in this unit"):
            starts_with_dict["1 model in this unit"].append(description)
            actor = "model"

        if description.startswith("this unit can be"):
            starts_with_dict["this unit can be"].append(description)
        elif description.startswith("all models in this unit can each have their"):
            starts_with_dict["all models in this unit can each have their"].append(description)
        elif description.startswith("all models in this unit can each be"):
            starts_with_dict["all models in this unit can each be"].append(description)
        elif description.startswith("all of the models in this unit can each have"):
            starts_with_dict["all of the models in this unit can each have"].append(description)
        elif description.startswith("one model equipped with a") or description.startswith("1 model equipped with a"):
            starts_with_dict["1 model equipped with a"].append(description)
        elif description.startswith("if this model is equipped with"):
            starts_with_dict["if this model is equipped with"].append(description)
        elif description.startswith("if this model is not equipped with"):
            starts_with_dict["if this model is not equipped with"].append(description)
        elif description.startswith("this model can each be equipped with"):
            starts_with_dict["this model can each be equipped with"].append(description)
        elif description.startswith("one model can replace its"):
            starts_with_dict["one model can replace its"].append(description)
        elif description.startswith("this model can do one of the following"):
            starts_with_dict["this model can do one of the following"].append(description)
        elif description.startswith("this model must be equipped with one of the following"):
            starts_with_dict["this model must be equipped with one of the following"].append(description)
        elif description.startswith("this unit's"):
            starts_with_dict["this unit's"].append(description)
        elif description.startswith("*") or description.startswith("this weapon cannot be replaced") or description.startswith("to a maximum of"):
            starts_with_dict["*"].append(description)
        elif match := re.match(r"^this model's ([\w\s'-]+) can be replaced with (.*)", description):
            actor = "model"
            items_to_replace = parse_wargear_item([match.group(1)])
            replacement_items = parse_wargear_string_ending(match.group(2))
            starts_with_dict["this model's X can be replaced with"].append(description)
        elif re.match(r"^for every \d+ models in th[ei]s? unit[,:]", description):
            starts_with_dict["for every X models in this unit"].append(description)
        elif re.match(r"^for every \d+ [\w\s']+ in th[ei]s? unit[,:]", description):
            starts_with_dict["for every X Y in this unit"].append(description)
        elif re.match(r"^the [\w\s'-]+ can be", description):
            starts_with_dict["the X can be"].append(description)
        elif re.match(r"^the [\w\s'-]+ can replace its", description):
            starts_with_dict["the X can replace its"].append(description)
        elif re.match(r"^up to \d+ models can each", description):
            starts_with_dict["up to X models can each"].append(description)
        elif re.match(r"^up to \d+ [\w\s']+ can each have their", description):
            starts_with_dict["up to X Y can each have their"].append(description)
        elif match := re.match(r"^any number of ([\w\s']+) can each have their (.*)", description):
            actor = match.group(1).strip()
            if actor[-1] == "s":
                actor = actor[:-1]
            model_limit = Quantity(min=1, max=100)
            if is_replacement:
                orig_item_list, ending = match.group(2).strip().split(" replaced with ", 1)
                items_to_replace = parse_wargear_item([orig_item_list])
                replacement_items = parse_wargear_string_ending(ending)

            starts_with_dict["any number of X can each have their"].append(description)
        elif re.match(r"^any numbers? of [\w\s'-]+ can", description):
            #print(f"ANY NUMBER OF X CAN: {description}")
            starts_with_dict["any number of X can"].append(description)
        elif re.match(r"^[\w\s']+ is equipped with:", description):
            starts_with_dict["X is equipped with:"].append(description)
        elif re.match(r"^1 [\w\s'-]+ can be equipped with", description):
            starts_with_dict["1 X can be equipped with"].append(description)
        elif re.match(r"^one [\w\s'-]+ equipped with", description):
            starts_with_dict["one X equipped with"].append(description)
        elif match := re.match(r"^(?:1|one) ([\w\s'-]+) can be replaced with (.*)", description):
            who_or_what = match.group(1).strip()  # Captures the X part
            if who_or_what.startswith("model's"):
                actor = "model"
                items_to_replace.append(parse_wargear_item([who_or_what.split(" ", 1)[1]]))
            remainder = match.group(2).strip()
            replacement_items = parse_wargear_string_ending(remainder)

            starts_with_dict["1 X can be replaced with"].append(description)
        elif re.match(r"^each [\w\s'-]+ can be", description):
            starts_with_dict["each X can be"].append(description)
        elif re.match(r"^\d+ [\w\s']+ can have its", description):
            starts_with_dict["X can have its"].append(description)
        elif re.match(r"^if this unit's [\w\s'-]+ is equipped with", description):
            starts_with_dict["if this unit's X is equipped with"].append(description)
        elif re.match(r"^if this unit contains \d+ models,", description):
            starts_with_dict["if this unit contains X models"].append(description)
        elif re.match(r"^\d+ of this model's", description):
            starts_with_dict["X of this model's"].append(description)
        elif re.match(r"^all [\w\s'-]+ in this unit can each have their", description):
            starts_with_dict["all X in this unit can each have their"].append(description)
        elif re.match(r"^for each [\w\s'-]+ this model is equipped with", description):
            starts_with_dict["for each X this model is equipped with"].append(description)
        elif re.match(r"^the [\w\s'-]+ can do one of the following:", description):
            starts_with_dict["the X can do one of the following:"].append(description)
        elif re.match(r"^an [\w\s'-]+ can be replaced with", description):
            starts_with_dict["an X can be replaced with"].append(description)
        elif re.match(r"^each model can have each [\w\s'-]+ it is equipped with replaced with", description):
            starts_with_dict["each model can have each X it is equipped with replaced with"].append(description)
        elif re.match(r"^if this unit contains \d+ or fewer models", description):
            starts_with_dict["if this unit contains X or fewer models"].append(description)
        elif re.match(r"^if this unit contains \d+ or more models", description):
            starts_with_dict["if this unit contains X or more models"].append(description)
        elif re.match(r"^if the [\w\s'-]+ is equipped with [\w\s'-]+, it can be equipped with", description):
            starts_with_dict["if the X is equipped with Y, it can be equipped with"].append(description)
        elif re.match(r"^up to \d+ different models that are not equipped with either an?", description):
            starts_with_dict["up to X different models that are not equipped with either an?"].append(description)
        elif re.match(r"^up to \d+ different [\w\s'-]+ equipped with either an?", description):
            starts_with_dict["up to X different Y equipped with either an?"].append(description)
        elif re.match(r"^up to \d+ [\w\s'-]+ can each replace their", description):
            starts_with_dict["up to X Y can each replace their"].append(description)
        elif re.match(r"^both of this model's [\w\s'-]+ can be replaced with", description):
            starts_with_dict["both of this model's X can be replaced with"].append(description)
        else:
            print(f"UNKNOWN: {line}")
            unhandled = True
            starts_with_dict["unknown"].append(description)

        print(f"CONDITION: {condition}")
        print(f"MODEL LIMIT: {model_limit}")
        print(f"ACTOR: {actor}")
        print(f"BASE WARGEAR: {items_to_replace}")
        print(f"ITEM LIMIT: {item_limit}")
        if is_replacement:
            print(f"REPLACEMENT OPTIONS: {replacement_items}\n")
            wargear_options.append(WargearOption(
                WargearOptionType.REPLACEMENT,
                items_to_replace,
                replacement_items,
                actor,
                model_limit,
                item_limit,
                condition
            ))
        else:
            print(f"ITEMS TO ADD: {replacement_items}\n")
            wargear_options.append(WargearOption(
                WargearOptionType.ADDITIONAL,
                items_to_replace,
                replacement_items,
                actor,
                model_limit,
                item_limit,
                condition
            ))

    #for key, value in sorted(starts_with_dict.items()):
    #    print(f"{key}: {len(value)}")
    #    print(f"{value}\n")

    return wargear_options


def parse_alternate_3(str_list: list[str], unit_ptr: 'Unit' = None) -> list[WargearOption]:
    post_conditionals = []

    # stored variables
    wargear_options = []
    unhandled = False

    for line in str_list:
        # reset variables
        is_replacement = False
        called_recursively = False
        actor = ""
        conditions = []
        model_limit = Quantity(min=1, max=1)
        item_limit = Quantity(min=1, max=1)
        items_to_replace = []
        replacement_items = []

        # some sanitization of inconsistencies
        description = line.lower().replace("’", "'").replace(".", "").replace('model"s', "model's").replace("for every four ", "for every 4 ")
        description = description.replace(" one of the following ", " one of the following: ").replace(" 1 of the following: ", " one of the following: ").replace(" 2 of the following: ", " two of the following: ")
        description = description.replace("up to two ", "up to 2 ").replace("up to three ", "up to 3 ").replace("up to four ", "up to 4 ")
        print(f"\nDESCRIPTION: {description}")
        if "(" in description and ")" in description:
            marker_1 = description.find("(")
            marker_2 = description.find(")")
            if marker_1 != -1 and marker_2 != -1:
                description = description[:marker_1] + description[marker_2+1:]
                conditions.append(description[marker_1+1:marker_2])
        if " replaced " in description or " replace " in description:
            is_replacement = True

        if description.startswith("*") or description.startswith("this weapon cannot be replaced") or description.startswith("to a maximum of"):
            post_conditionals.append(description)
            continue
        elif match := re.match(r"^(?:this|the|1|one) ([\w\s'-]+) that is not equipped with an? ([\w\s'-]+) can be equipped with (.*)", description):
            assert not is_replacement
            actor, _ = parse_warger_actor_string(match.group(1))
            condition = f"not equipped with {match.group(2)}"
            conditions.append(condition)
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^(?:this|the|1|one) ([\w\s'-]+) can (?:each |)be equipped with:? (.*)", description):
            assert not is_replacement
            actor, condition = parse_warger_actor_string(match.group(1))
            conditions.append(condition)
            replacement_items, limit = parse_wargear_string_ending(match.group(2))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^(?:this|the|1|one|each) ([\w\s-]+)'s? ([\w\s'-]+) can be replaced with:? (.*)", description):
            actor, condition = parse_warger_actor_string(match.group(1))
            conditions.append(condition)
            items_to_replace = parse_wargear_itemlist(match.group(2))
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^(\d+) of this ([\w\s-]+)'s? ([\w\s'-]+) can be replaced with:? (.*)", description):
            actor, condition = parse_warger_actor_string(match.group(2))
            conditions.append(condition)
            items_to_replace = parse_wargear_itemlist(match.group(3))
            count = int(match.group(1))
            for i, item_list in enumerate(items_to_replace):
                for j, item in enumerate(item_list):
                    items_to_replace[i][j] = (count, item[1])
            replacement_items, limit = parse_wargear_string_ending(match.group(4))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^the ([\w\s'-]+) can replace its ([\w\s'-]+) with (.*)", description):
            actor, condition = parse_warger_actor_string(match.group(1))
            conditions.append(condition)
            items_to_replace = parse_wargear_itemlist(match.group(2))
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^any number of ([\w\s'-]+) can each have their ([\w\s'-]+) replaced with (.*)", description):
            assert is_replacement
            actor, condition = parse_warger_actor_string(match.group(1))
            conditions.append(condition)
            model_limit = Quantity(min=1, max=len(unit_ptr.models))
            items_to_replace = parse_wargear_itemlist(match.group(2))
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^any number of ([\w\s-]+)' ([\w\s'-]+) can each be replaced with (.*)", description):
            assert is_replacement
            actor, condition = parse_warger_actor_string(match.group(1))
            conditions.append(condition)
            model_limit = Quantity(min=1, max=len(unit_ptr.models))
            items_to_replace = parse_wargear_itemlist(match.group(2))
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^any number of ([\w\s-]+) can replace their ([\w\s'-]+) with (.*)", description):
            assert is_replacement
            actor, condition = parse_warger_actor_string(match.group(1))
            conditions.append(condition)
            model_limit = Quantity(min=1, max=len(unit_ptr.models))
            items_to_replace = parse_wargear_itemlist(match.group(2))
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^any number of ([\w\s']+) can each be equipped with (.*)", description):
            assert not is_replacement
            actor, condition = parse_warger_actor_string(match.group(1))
            conditions.append(condition)
            model_limit = Quantity(min=1, max=len(unit_ptr.models))
            replacement_items = parse_wargear_itemlist(match.group(2))
        elif match := re.match(r"^up to (\d+) ([\w\s']+) can each have their (.*)", description):
            actor, condition = parse_warger_actor_string(match.group(2))
            conditions.append(condition)
            model_limit = Quantity(min=1, max=int(match.group(1)))
            if is_replacement:
                orig_item_list, ending = match.group(3).strip().split(" replaced with ", 1)
                items_to_replace = parse_wargear_itemlist(orig_item_list)
                replacement_items, limit = parse_wargear_string_ending(ending)
                item_limit = Quantity(min=1, max=limit)
            else:
                raise Exception(f"UNHANDLED 'UP TO' ADDITIONAL: {description}")
        elif match := re.match(r"^for every (\d+) ([\w\s']+) in th[ei]s? unit([,:]+) (.*)", description):
            break_symbol = match.group(3)
            if break_symbol == ",":
                wgo_list = parse_alternate_3([match.group(4)], unit_ptr)
                for wgo in wgo_list:
                    wgo.conditionals.append(description.split(break_symbol)[0].strip())
                wargear_options.extend(wgo_list)
                called_recursively = True
            else:
                raise Exception(f"UNHANDLED BREAK SYMBOL: {break_symbol}")
        elif match := re.match(r"^if this unit's ([\w\s'-]+) is equipped with ([\w\s'-]+), it can be equipped with (.*)", description):
            actor, _ = parse_warger_actor_string(match.group(1))
            conditions.append(f"equipped with {match.group(2)}")
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^if this ([\w\s'-]+) is equipped with ([\w\s'-]+), its ([\w\s'-]+) can be replaced with (.*)", description):
            assert is_replacement
            actor, _ = parse_warger_actor_string(match.group(1))
            conditions.append(f"equipped with {match.group(2)}")
            items_to_replace = parse_wargear_itemlist(match.group(3))
            replacement_items, limit = parse_wargear_string_ending(match.group(4))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^each ([\w\s'-]+) can have each ([\w\s'-]+) it is equipped with replaced with (.*)", description):
            actor, _ = parse_warger_actor_string(match.group(1))
            conditions.append(f"item_limit is equal to number of equipped {match.group(2)}")
            items_to_replace = parse_wargear_item([match.group(2)])
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^(?:this|the|1|one) ([\w\s'-]+) can have its ([\w\s'-]+) replaced with (.*)", description):
            actor, condition = parse_warger_actor_string(match.group(1))
            items_to_replace = parse_wargear_item([match.group(2)])
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^each of this model's ([\w\s'-]+)s can be replaced with (.*)", description):
            actor = "model"
            conditions.append(f"item_limit is equal to number of equipped {match.group(1)}")
            items_to_replace = parse_wargear_itemlist(match.group(1))
            replacement_items, limit = parse_wargear_string_ending(match.group(2))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^all of the ([\w\s'-]+)s in this unit can each have their ([\w\s'-]+) replaced with (.*)", description):
            actor, _ = parse_warger_actor_string(match.group(1))
            model_limit = Quantity(min=len(unit_ptr.models), max=len(unit_ptr.models))
            items_to_replace = parse_wargear_itemlist(match.group(2))
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^if this unit contains (\d+) models, (.*)", description):
            condition = f"contains {match.group(1)} models"
            wgo_list = parse_alternate_3([match.group(2)], unit_ptr)
            for wgo in wgo_list:
                wgo.conditionals.append(condition.strip())
            wargear_options.extend(wgo_list)
            called_recursively = True
        elif match := re.match(r"^if this unit contains (\d+) or ([\w]+) models: (.*)", description):
            condition = f"contains {match.group(1)} or {match.group(2)} models"
            remainder = match.group(3)
            if remainder[-1] == ";":    
                remainder = remainder[:-1]
            for complex_entry in remainder.split(";"):
                wgo_list = parse_alternate_3([complex_entry.strip()], unit_ptr)
                for wgo in wgo_list:
                    wgo.conditionals.append(condition.strip())
                wargear_options.extend(wgo_list)
            called_recursively = True
        elif match := re.match(r"^it can be equipped with (.*)", description):
            replacement_items, limit = parse_wargear_string_ending(match.group(1))
            item_limit = Quantity(min=1, max=limit)
            actor = "model"
        else:
            print(f"UNKNOWN: {line}")
            unhandled = True

        if not called_recursively:
            print(f"CONDITIONS: {conditions}")
            print(f"MODEL LIMIT: {model_limit}")
            print(f"ACTOR: {actor}")
            print(f"BASE WARGEAR: {items_to_replace}")
            print(f"ITEM LIMIT: {item_limit}")

            if is_replacement:
                print(f"REPLACEMENT OPTIONS: {replacement_items}\n")
                wargear_options.append(WargearOption(
                    WargearOptionType.REPLACEMENT,
                    items_to_replace,
                    replacement_items,
                    actor,
                    model_limit,
                    item_limit,
                    conditions
                ))
            else:
                print(f"ITEMS TO ADD: {replacement_items}\n")
                wargear_options.append(WargearOption(
                    WargearOptionType.ADDITIONAL,
                    items_to_replace,
                    replacement_items,
                    actor,
                    model_limit,
                    item_limit,
                    conditions
                ))

        if unhandled:
            raise Exception(f"UNHANDLED: {str_list}")

    for conditional in post_conditionals:
        search_str = None
        if "***" in conditional:
            search_str = "***"
        elif "**" in conditional:
            search_str = "**"
        elif "*" in conditional:
            search_str = "*"
        for option in wargear_options:
            post_conditional_applies = False
            for i, items in enumerate(option.wargear_to):
                for j, item in enumerate(items):
                    if search_str and search_str == item[1][-len(search_str):] and not search_str == item[1][-len(search_str)-1:-1]:
                        post_conditional_applies = True
                        option.wargear_to[i][j] = (item[0], item[1].replace(search_str, ""))
            if post_conditional_applies:
                conditional = conditional.replace("the some model", " the same model")
                if conditional.startswith(f"{search_str} that model's"):
                    new_conditional = conditional[len(f"{search_str} that model's"):].strip()
                    option.conditionals.append(new_conditional)
                elif conditional.startswith(f"{search_str} you cannot select the same weapon from this list more than once per unit"):
                    new_conditional = conditional[len(f"{search_str} "):].strip()
                    option.conditionals.append(new_conditional)
                elif conditional.startswith(f"{search_str} you cannot select the same weapon from this list more than twice per unit"):
                    new_conditional = conditional[len(f"{search_str} "):].strip()
                    option.conditionals.append(new_conditional)
                elif conditional.startswith(f"{search_str} the same model cannot be equipped with more than one of these wargear options"):
                    new_conditional = conditional[len(f"{search_str} "):].strip()
                    option.conditionals.append(new_conditional)
                elif conditional.startswith(f"{search_str} you cannot select both of these options for the same model"):
                    new_conditional = conditional[len(f"{search_str} "):].strip()
                    option.conditionals.append(new_conditional)
                elif match := re.match(r" excluding the (\D+), you cannot select the same weapon from this list more than once per unit$", conditional[len(search_str):]):
                    new_conditional = conditional[len(f"{search_str} "):].strip()
                    option.conditionals.append(new_conditional)
                elif match := re.match(r" a model can only take one of these options, and if it does so its (\D+) cannot be replaced$", conditional[len(search_str):]):
                    new_conditional = conditional[len(f"{search_str} "):].strip()
                    option.conditionals.append(new_conditional)
                elif match := re.match(r" you cannot select the same weapon more than once per unit unless it contains (\d+) models, in which case you cannot select the same weapon more than twice per unit", conditional[len(search_str):]):
                    option.conditionals.append(match.group(0))
                else:
                    print(f"UNHANDLED POST_CONDITIONAL: {conditional}")
                    raise Exception(f"UNHANDLED POST_CONDITIONAL: {conditional}")

    return wargear_options