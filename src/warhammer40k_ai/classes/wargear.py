from typing import Union, Dict, List, Optional
from enum import Enum, auto
from collections import namedtuple
import re
from warhammer40k_ai.utility.dice import DiceCollection, get_roll
from warhammer40k_ai.utility.event_bus import append_dice
from warhammer40k_ai.utility.range import Range
from warhammer40k_ai.utility.count import Count
from dataclasses import dataclass

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .model import Model
    from .unit import Unit
    from .map import Map

# Attack result data structure for comprehensive reporting
@dataclass
class AttackResult:
    """Comprehensive attack result tracking"""
    weapon_name: str
    attacker_name: str
    target_unit_name: str
    
    # Attack generation
    attacks_rolled: int
    attacks_dice_expression: str
    attacks_dice_rolls: List[int]  # Actual dice rolled for attacks
    attacks_special_modifiers: List[str]
    
    # Individual attack results
    hit_results: List[Dict]  # Each dict contains: roll, needed, hit, special_effects
    wound_results: List[Dict]  # Each dict contains: roll, needed, wound, special_effects
    save_results: List[Dict]  # Each dict contains: roll, needed, saved, save_type
    damage_results: List[Dict]  # Each dict contains: damage_rolled, damage_applied, target_model, excess
    
    # Weapon effects
    hazardous_roll: Optional[int]
    hazardous_damage: int
    
    # Summary
    total_hits: int
    total_wounds: int
    total_saves_failed: int
    total_damage_dealt: int
    models_killed: int


class WargearProfile:
    def __init__(self, profile_name: str, wargear_data: Dict, parent_wargear: Optional['Wargear'] = None):
        self.name = profile_name
        self.parent_wargear = parent_wargear
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
        # Remove " and normalize common placeholders.
        attribute_value = (attribute_value or "").replace("\"", "").replace("’", "'").strip()
        
        # Remove trailing + if it exists
        if attribute_value.endswith("+"):
            attribute_value = attribute_value[:-1]
            
        # Common placeholders in Wahapedia exports.
        if attribute_value in ("", "-", "–", "N/A"):
            return 0

        if "D" in attribute_value:
            return DiceCollection.from_string(attribute_value)
        else:
            return int(attribute_value)

    def _parse_keywords(self, keywords_string):
        if keywords_string:
            # Wahapedia weapon ability strings are comma-separated. Be defensive and also split on semicolons.
            parts = re.split(r"\s*,\s*|\s*;\s*", str(keywords_string))
            return [p.strip() for p in parts if p and p.strip()]
        return []

    def get_keywords(self) -> List[str]:
        return self.keywords

    def _get_keyword_suffix_count(self, prefix: str, default: int = 1) -> Count:
        """
        Parse keyword forms like:
        - "rapid fire" or "rapid fire 1" or "rapid fire D3"
        - "melta" or "melta 2" or "melta D3+2"
        Returns a Count (flat or dice). If absent, returns Count(FLAT, 0).
        """
        try:
            p = (prefix or "").strip().lower()
            if not p:
                return Count.from_string("0")
            for kw in self.get_keywords():
                raw = (kw or "").strip()
                k = raw.lower()
                if k == p:
                    return Count.from_string(str(default))
                if k.startswith(p + " "):
                    suffix = raw[len(prefix):].strip()
                    if not suffix:
                        return Count.from_string(str(default))
                    # Normalize common cases: "d3" -> "D3"
                    return Count.from_string(suffix.upper())
        except Exception:
            pass
        return Count.from_string("0")

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

        # TWIN-LINKED: re-roll failed wound rolls (boosts wound probability).
        # If base probability is p, rerolling failures gives: p + (1-p)*p = 1 - (1-p)^2.
        if self.is_twin_linked():
            chance_to_wound = 1.0 - (1.0 - chance_to_wound) ** 2

        # Average damage per hit
        if isinstance(self.damage, DiceCollection):
            avg_damage = self.damage.stat_average()
        else:
            avg_damage = self.damage or 0

        #######################################################################
        # Handle special rules (simplified)
        #######################################################################
        # Handle 'Sustained Hits' (approximation)
        # Sustained Hits triggers on critical hits (unmodified 6s) and adds extra hits equal to X.
        # We estimate expected bonus hits as: avg_attacks * chance_to_hit * (avg_X / 6).
        if self.is_sustained_hits():
            try:
                avg_x = float(self.get_sustained_hits_bonus().stat_average())
                sustained_hits_bonus = avg_attacks * chance_to_hit * (avg_x / 6.0)
                avg_attacks += sustained_hits_bonus
            except Exception:
                pass

        # TODO - handle rest of special rules
        #######################################################################

        # Expected damage
        expected_damage = avg_attacks * chance_to_hit * chance_to_wound * avg_damage

        # Return the estimated damage potential
        return expected_damage

    ###########################################################################
    ### Weapon characteristic modifiers (terrain, etc.)
    ###########################################################################
    def _get_game_map_from_model(self, attacker: 'Model'):
        """Best-effort lookup of the current game map from an attacking model.

        This keeps weapon resolution decoupled from UI/simulation scaffolding and
        safely returns None when running in isolated tests.
        """
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit else None
            player = getattr(army, "player", None) if army else None
            game = getattr(player, "game", None) if player else None
            return getattr(game, "map", None) if game else None
        except Exception:
            return None

    def _plunging_fire_applies(self, attacker: 'Model', target: 'Unit') -> bool:
        """PLUNGING FIRE:
        - Attacker is wholly within a RUINS terrain feature
        - Attacker is >= 6" above ground level
        - Every model in the target unit is at ground level
        - Ranged attacks only
        """
        # Ranged attacks only
        try:
            if not (self.parent_wargear and self.parent_wargear.is_ranged()):
                return False
        except Exception:
            return False

        # Attacker must be >= 6" from ground level (z measured in inches)
        try:
            attacker_z = float(getattr(attacker, "z", 0.0))
        except Exception:
            attacker_z = 0.0
        if attacker_z < 6.0:
            return False

        # Target unit must have all alive models at ground level
        alive_targets = [m for m in getattr(target, "models", []) if getattr(m, "is_alive", True)]
        if not alive_targets:
            return False
        for m in alive_targets:
            try:
                z = float(getattr(m, "z", 0.0))
            except Exception:
                z = 0.0
            # Ground level tolerance matches RUINS placement validation tolerance (±1")
            if abs(z) >= 1.0:
                return False

        # Attacker must be wholly within a RUINS feature footprint
        game_map = self._get_game_map_from_model(attacker)
        if not game_map or not hasattr(game_map, "terrain_features"):
            return False

        base_geom = None
        try:
            mb = getattr(attacker, "model_base", None)
            if mb is not None:
                base_geom = mb.get_base_shape_at(mb.x, mb.y, getattr(mb, "facing", 0.0))
        except Exception:
            base_geom = None
        if base_geom is None:
            return False

        try:
            from .map import TerrainType
        except Exception:
            return False

        for terrain in getattr(game_map, "terrain_features", []) or []:
            try:
                if getattr(terrain, "terrain_type", None) != TerrainType.RUINS:
                    continue
                footprint = getattr(terrain, "footprint", None)
                if footprint is None:
                    continue
                # "Wholly within" should allow touching the boundary
                if hasattr(footprint, "covers"):
                    if footprint.covers(base_geom):
                        return True
                else:
                    if footprint.contains(base_geom):
                        return True
            except Exception:
                continue

        return False

    def get_effective_ap(self, attacker: 'Model', target: 'Unit') -> int:
        """Return AP after applying global modifiers like Plunging Fire."""
        try:
            ap_val = int(self.ap)
        except Exception:
            ap_val = 0
        if self._plunging_fire_applies(attacker, target):
            # Improve AP by 1: AP -1 becomes -2, AP 0 becomes -1, etc.
            ap_val -= 1
        return ap_val

    def attack(self, target: 'Unit', attacker: 'Model', game_map: Optional['Map'] = None) -> None:
        # ONE SHOT: enforce once per battle per model per weapon.
        # (Higher-level code also filters declarations, but this is the final guard.)
        try:
            if self.is_one_shot():
                key = self.one_shot_key()
                used = getattr(attacker, "_one_shot_used", set())
                if key and key in used:
                    try:
                        wname = getattr(getattr(self, "parent_wargear", None), "name", None) or getattr(self, "name", "Weapon")
                        print(f"⚠️ ONE SHOT already used for {attacker.name}: {wname}")
                    except Exception:
                        pass
                    return
        except Exception:
            pass

        # Initialize attack result tracking
        # Build proper weapon name: parent weapon + profile (if not default)
        weapon_display_name = self.name
        if hasattr(self, 'parent_wargear') and self.parent_wargear:
            if self.name == 'default':
                weapon_display_name = self.parent_wargear.name
            else:
                weapon_display_name = f"{self.parent_wargear.name} - {self.name}"
        
        attack_result = AttackResult(
            weapon_name=weapon_display_name,
            attacker_name=attacker.name,
            target_unit_name=target.name,
            attacks_rolled=0,
            attacks_dice_expression=str(self.attacks),
            attacks_dice_rolls=[],
            attacks_special_modifiers=[],
            hit_results=[],
            wound_results=[],
            save_results=[],
            damage_results=[],
            hazardous_roll=None,
            hazardous_damage=0,
            total_hits=0,
            total_wounds=0,
            total_saves_failed=0,
            total_damage_dealt=0,
            models_killed=0
        )
        
        wound_instances = []
        hit_instances = []
        num_attacks = 0
        precision_choice_set = False
        precision_choice_model = None  # None means allocate normally to bodyguards

        # INDIRECT FIRE (penalty only if no models in target unit are visible to attacking unit at selection time)
        indirect_fire_no_visible = False
        try:
            if self.is_indirect_fire() and game_map is not None:
                attacker_unit = attacker.parent_unit
                if hasattr(attacker_unit, "_attacking_unit_has_any_los_to_target_unit"):
                    indirect_fire_no_visible = not attacker_unit._attacking_unit_has_any_los_to_target_unit(target, game_map)
        except Exception:
            indirect_fire_no_visible = False

        # Roll attacks for this specific weapon instance
        if isinstance(self.attacks, Count):
            # Provide reroll callback for attacks count
            def _reroll_attacks():
                new_num, new_rolls = self.attacks.resolve_detailed()
                attack_result.attacks_rolled = new_num
                attack_result.attacks_dice_rolls = new_rolls
                return new_num, new_rolls
            num_attacks, dice_rolls = self.attacks.resolve_detailed()
            attack_result.attacks_rolled = num_attacks
            attack_result.attacks_dice_rolls = dice_rolls
            # Publish roll_made for attacks count
            try:
                unit = attacker.parent_unit
                game = unit.get_parent_army().player.game
                game.event_system.publish("roll_made", player=unit.get_parent_army().player, unit=unit, roll_type="attacks", value=num_attacks, dice=dice_rolls, reroll=_reroll_attacks)
            except Exception:
                pass
        else:
            num_attacks = self.attacks or 0
            attack_result.attacks_rolled = num_attacks

        # Enhancement: improve melee weapons' Attacks by X (bearer enhancement).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("enhancement_melee_attacks_bonus", 0) or 0)
                if bonus:
                    num_attacks += bonus
                    attack_result.attacks_special_modifiers.append(f"Enhancement +{bonus}A (melee)")
        except Exception:
            pass
            attack_result.attacks_dice_rolls = []

        # Damaged profile: add attacks to melee weapons (+N).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("damaged_melee_attacks_bonus", 0) or 0)
                if bonus:
                    num_attacks += bonus
                    attack_result.attacks_special_modifiers.append(f"Damaged profile +{bonus}A (melee)")
        except Exception:
            pass

        # Damaged profile: add attacks to a specific named weapon (+N).
        try:
            wname = str(getattr(attacker.parent_unit, "special_rules", {}).get("damaged_attacks_bonus_weapon_name", "") or "").strip().lower()
            amt = int(getattr(attacker.parent_unit, "special_rules", {}).get("damaged_attacks_bonus_weapon_amount", 0) or 0)
            if wname and amt:
                parent_name = str(getattr(getattr(self, "parent_wargear", None), "name", "") or "").strip().lower()
                # Match either exact or substring.
                if parent_name and (parent_name == wname or wname in parent_name or parent_name in wname):
                    num_attacks += amt
                    attack_result.attacks_special_modifiers.append(f"Damaged profile +{amt}A ({wname})")
        except Exception:
            pass

        # Damaged profile: halve attacks characteristic of the model's weapons (round up).
        try:
            if bool(getattr(attacker.parent_unit, "special_rules", {}).get("damaged_half_attacks", False)):
                before = int(num_attacks)
                num_attacks = (before + 1) // 2
                attack_result.attacks_special_modifiers.append("Damaged profile: halve Attacks (round up)")
        except Exception:
            pass

        closest_target, closest_dist = attacker.return_closest_model_in_unit(target)

        # Apply AP modifiers that depend on attacker/target context (e.g., Plunging Fire)
        effective_ap = self.get_effective_ap(attacker, target)
        try:
            base_ap = int(self.ap)
        except Exception:
            base_ap = effective_ap
        if effective_ap == (base_ap - 1):
            attack_result.attacks_special_modifiers.append("Plunging Fire (AP improved by 1)")
        
        # Apply attack modifiers
        if closest_dist <= (self.range.max / 2) and self.is_rapid_fire():
            # Support Rapid Fire N / Rapid Fire D3 / Rapid Fire D6+X, etc.
            try:
                rf = self.get_rapid_fire_bonus()
                rf_bonus = int(rf.resolve())
                attack_result.attacks_special_modifiers.append(f"Rapid Fire +{rf_bonus} ({rf})")
                num_attacks += rf_bonus
            except Exception:
                # Conservative fallback
                attack_result.attacks_special_modifiers.append("Rapid Fire +1")
                num_attacks += 1

        if self.is_blast():
            target_model_count = len(target.models)
            num_attacks_modifier = int(target_model_count / 5)
            attack_result.attacks_special_modifiers.append(f"Blast +{num_attacks_modifier}")
            num_attacks += num_attacks_modifier

        # Ensure the reported attacks count matches the final resolved count after all modifiers.
        try:
            attack_result.attacks_rolled = int(num_attacks)
        except Exception:
            pass

        # Process each attack
        for attack_num in range(num_attacks):
            attack_instance = {
                'crit_hit': False,
                'crit_wound': False,
                'mortal_wound': False,
                'below_half_distance': closest_dist <= (self.range.max / 2),
                'damage': 0
            }

            if indirect_fire_no_visible:
                attack_instance["indirect_fire_no_visible"] = True
            
            # Check if we hit
            hit_result = self._hit_target_with_tracking(target, attacker, attack_instance)
            attack_result.hit_results.append(hit_result)
            
            if hit_result['hit']:
                hit_instances.append(attack_instance)
                attack_result.total_hits += 1
                
                # Handle sustained hits
                if attack_instance.get('sustained_hit', 0) > 0:
                    # Extra hits generated by Sustained Hits must NOT inherit crit/lethal flags
                    # They are normal hits that proceed to a standard wound roll
                    for _ in range(attack_instance['sustained_hit']):
                        extra_instance = {
                            'crit_hit': False,
                            'crit_wound': False,
                            'mortal_wound': False,
                            'below_half_distance': attack_instance['below_half_distance'],
                            'damage': 0
                        }
                        hit_instances.append(extra_instance)
                        attack_result.total_hits += 1

        # Process wound rolls
        for hit_instance in hit_instances:
            wound_result = self._wound_target_with_tracking(target, attacker, hit_instance)
            attack_result.wound_results.append(wound_result)
            
            if wound_result['wound']:
                wound_instances.append(hit_instance)
                attack_result.total_wounds += 1

        # Process saves and damage
        for wound_instance in wound_instances:
            # PRECISION (10e): after a successful wound vs an Attached Unit, attacker may allocate
            # the wound to a visible CHARACTER model in that unit.
            target_model = None
            if self.is_precision() and game_map is not None:
                try:
                    root = target.get_attached_unit_root()
                except Exception:
                    root = target
                try:
                    has_attached_leaders = bool(getattr(root, "attached_leaders", []) or [])
                except Exception:
                    has_attached_leaders = False

                if has_attached_leaders:
                    # Collect visible CHARACTER models in the attached unit.
                    try:
                        all_models = root.get_models_for_collision()
                    except Exception:
                        all_models = list(getattr(root, "models", []) or [])
                    char_models = []
                    for m in all_models:
                        try:
                            if not getattr(m, "is_alive", True):
                                continue
                            pu = getattr(m, "parent_unit", None)
                            if pu is None:
                                continue
                            if not bool(getattr(pu, "is_character", False)):
                                continue
                            # Visibility requirement
                            if hasattr(game_map, "can_model_see_model") and callable(getattr(game_map, "can_model_see_model")):
                                if not game_map.can_model_see_model(attacker, m):
                                    continue
                            char_models.append(m)
                        except Exception:
                            continue

                    if char_models:
                        # Ask once per weapon_profile.attack() call and cache choice for remaining wounds.
                        if not precision_choice_set:
                            precision_choice_set = True
                            provider = getattr(game_map, "precision_allocation_provider", None)
                            try:
                                attacker_player = attacker.parent_unit.get_parent_army().player
                                is_human = bool(getattr(getattr(attacker_player, "type", None), "name", "") == "HUMAN")
                            except Exception:
                                is_human = False

                            if callable(provider) and is_human:
                                try:
                                    precision_choice_model = provider(attacker, root, char_models, self)
                                except Exception:
                                    precision_choice_model = None
                            else:
                                # AI / headless: default to CHARACTER when available
                                precision_choice_model = char_models[0]

                        # If player chose a character model, allocate there (only if still alive/visible)
                        if precision_choice_model is not None:
                            try:
                                if getattr(precision_choice_model, "is_alive", True):
                                    if hasattr(game_map, "can_model_see_model") and callable(getattr(game_map, "can_model_see_model")):
                                        if game_map.can_model_see_model(attacker, precision_choice_model):
                                            target_model = precision_choice_model
                            except Exception:
                                target_model = None

            # Default allocation if precision didn't override it
            if target_model is None:
                target_model = self.opponent_wound_allocation(target)
            if target_model is None:
                continue

            # INDIRECT FIRE: if no target models were visible at selection time, the target gains Benefit of Cover
            # (unless the weapon ignores cover). This stacks with terrain evaluation but is not cumulative (+1 max).
            try:
                if indirect_fire_no_visible:
                    ignores_cover = False
                    if self.parent_wargear is not None and hasattr(self.parent_wargear, "is_ignores_cover"):
                        ignores_cover = bool(self.parent_wargear.is_ignores_cover())
                    if not ignores_cover:
                        wound_instance["benefit_of_cover"] = True
                        wound_instance.setdefault("benefit_of_cover_source", "INDIRECT FIRE")
            except Exception:
                pass

            # Benefit of Cover (RUINS/WOODS only for now, evaluated per allocated model)
            # NOTE: The actual +1 modifier is applied during the save roll, and only for armor saves.
            try:
                is_melee = False
                if self.parent_wargear is not None and hasattr(self.parent_wargear, "is_melee"):
                    is_melee = bool(self.parent_wargear.is_melee())
                if (not is_melee) and game_map is not None:
                    cover_info = game_map.get_benefit_of_cover_for_ranged_attack(
                        attacking_unit=attacker.parent_unit,
                        target_model=target_model,
                        weapon_profile=self,
                        ap=effective_ap,
                    )
                    if cover_info.get("has_benefit_of_cover", False):
                        wound_instance["benefit_of_cover"] = True
                        wound_instance["benefit_of_cover_source"] = cover_info.get("source_terrain_type")
                        wound_instance["benefit_of_cover_reason"] = cover_info.get("reason")
            except Exception:
                pass
                
            save_result = None
            if not wound_instance['mortal_wound']:
                save_result = self._save_with_tracking(target_model, wound_instance, effective_ap)
                attack_result.save_results.append(save_result)
            
            # Apply damage if save failed or mortal wound
            if wound_instance['mortal_wound'] or (save_result and not save_result['saved']):
                if save_result and not save_result['saved']:
                    attack_result.total_saves_failed += 1
                
                damage_result = self._damage_target_with_tracking(target_model, attacker, wound_instance, game_map=game_map)
                attack_result.damage_results.append(damage_result)
                attack_result.total_damage_dealt += damage_result['damage_applied']
                
                if damage_result['model_killed']:
                    attack_result.models_killed += 1
        
        # Handle hazardous weapon effects
        if self.is_hazardous():
            # Provide reroll callback for hazardous test
            def _reroll_hazard():
                new_roll = get_roll("D6")
                try:
                    append_dice(attacker.parent_unit.get_parent_army().player.name, f"Hazardous re-roll: {new_roll} for {attacker.name}")
                except Exception:
                    pass
                return new_roll
            hazard_roll = get_roll("D6")
            attack_result.hazardous_roll = hazard_roll
            # Publish roll_made for hazardous test
            try:
                unit = attacker.parent_unit
                game = unit.get_parent_army().player.game
                game.event_system.publish("roll_made", player=unit.get_parent_army().player, unit=unit, roll_type="hazardous", value=hazard_roll, reroll=_reroll_hazard)
            except Exception:
                pass
            if hazard_roll == 1:
                attack_result.hazardous_damage = 3
                attacker.take_damage(3, is_mortal=True, weapon_profile=None, game_map=game_map)
        
        # Print comprehensive attack summary
        self._print_attack_summary(attack_result)

        # Resolve pending Leader separations only if no attack-resolution window is active.
        # (Sequences like shooting/melee for a whole unit will bracket begin/end around many profiles.)
        try:
            if hasattr(target, "maybe_resolve_pending_separation"):
                target.maybe_resolve_pending_separation(game_map=game_map)
        except Exception:
            pass

        # ONE SHOT: mark expended after resolving (hit or miss).
        try:
            if self.is_one_shot():
                key = self.one_shot_key()
                if key:
                    used = getattr(attacker, "_one_shot_used", set())
                    if not isinstance(used, set):
                        used = set()
                    used.add(key)
                    setattr(attacker, "_one_shot_used", used)
        except Exception:
            pass
        
        return

    def _hit_target_with_tracking(self, target: 'Unit', attacker: 'Model', attack_instance: Dict) -> Dict:
        """Hit resolution with detailed tracking"""
        hit_result = {
            'roll': None,
            'needed': None,
            'base_skill': self.skill,
            'modifiers': [],
            'final_needed': None,
            'hit': False,
            'special_effects': []
        }
        
        # Torrent auto-hits (in case of Overwatch it ignores 6+ restrictions)
        if self.is_torrent():
            hit_result['hit'] = True
            hit_result['special_effects'].append("Torrent (auto-hit)")
            return hit_result

        # Overwatch restriction: only unmodified 6s hit
        if getattr(attacker.parent_unit, '_overwatch_sixes_only', False):
            dice_roll = get_roll("D6")
            weapon_name_for_log = getattr(self, 'parent_wargear', None).name if getattr(self, 'parent_wargear', None) else getattr(self, 'name', 'Weapon')
            append_dice(attacker.parent_unit.get_parent_army().player.name, f"Overwatch Hit roll: {dice_roll} for {attacker.name} with {weapon_name_for_log}")
            hit_result['roll'] = dice_roll
            hit_result['needed'] = 6
            hit_result['final_needed'] = 6
            if dice_roll == 6:
                hit_result['hit'] = True
                hit_result['special_effects'].append("Overwatch: 6 required to hit")
                attack_instance['crit_hit'] = True
            else:
                hit_result['hit'] = False
                hit_result['special_effects'].append("Overwatch: Miss (requires unmodified 6)")
            return hit_result

        # Calculate modifiers first (always do this)
        dice_modifier = 0
        if self.is_heavy() and attacker.parent_unit.round_state.remained_stationary_this_round:
            dice_modifier += 1
            hit_result['modifiers'].append("+1 from Heavy (stationary)")

        # INDIRECT FIRE: if no target models were visible at selection time, -1 to hit
        if attack_instance.get("indirect_fire_no_visible", False):
            dice_modifier -= 1
            hit_result['modifiers'].append("-1 from Indirect Fire (no target models visible)")
        
        # Check for target modifiers (like Stealth)
        if hasattr(target, 'has_stealth') and target.has_stealth():
            dice_modifier -= 1
            hit_result['modifiers'].append("-1 from target Stealth")

        # Damaged profile: subtract N from the Hit roll (stored as negative modifier).
        try:
            dm = int(getattr(attacker.parent_unit, "special_rules", {}).get("damaged_hit_roll_modifier", 0) or 0)
            if dm:
                dice_modifier += dm
                if dm < 0:
                    hit_result['modifiers'].append(f"{dm} from Damaged profile (to hit)")
                else:
                    hit_result['modifiers'].append(f"+{dm} from Damaged profile (to hit)")
        except Exception:
            pass
        
        # Add other potential modifiers here
        # TODO: Add more hit modifiers (cover, moving, etc.)
        
        dice_modifier = min(max(dice_modifier, -1), 1)  # modifications are capped between -1 and 1
        final_needed = self.skill - dice_modifier  # Note: negative dice_modifier makes it harder (higher final_needed)
        
        hit_result['needed'] = self.skill
        hit_result['final_needed'] = final_needed

        # Provide reroll callback for hit
        def _reroll_hit():
            new_roll = get_roll("D6")
            try:
                weapon_name_for_log = getattr(self, 'parent_wargear', None).name if getattr(self, 'parent_wargear', None) else getattr(self, 'name', 'Weapon')
                append_dice(attacker.parent_unit.get_parent_army().player.name, f"Hit re-roll: {new_roll} for {attacker.name} with {weapon_name_for_log}")
            except Exception:
                pass
            return new_roll
        dice_roll = get_roll("D6")
        try:
            # weapon_display_name available in attack(); provide fallback here
            weapon_name_for_log = getattr(self, 'parent_wargear', None).name if getattr(self, 'parent_wargear', None) else getattr(self, 'name', 'Weapon')
            append_dice(attacker.parent_unit.get_parent_army().player.name, f"Hit roll: {dice_roll} for {attacker.name} with {weapon_name_for_log}")
        except Exception:
            pass
        hit_result['roll'] = dice_roll
        # Publish roll_made for hit
        try:
            unit = attacker.parent_unit
            game = unit.get_parent_army().player.game
            game.event_system.publish("roll_made", player=unit.get_parent_army().player, unit=unit, roll_type="hit", value=dice_roll, reroll=_reroll_hit)
        except Exception:
            pass
        
        # INDIRECT FIRE: if no target models were visible at selection time,
        # an unmodified hit roll of 1, 2, or 3 always fails.
        if attack_instance.get("indirect_fire_no_visible", False) and dice_roll in (1, 2, 3):
            hit_result['hit'] = False
            hit_result['special_effects'].append("Indirect Fire: 1-3 always fail (no target models visible)")
            return hit_result

        if dice_roll == 1:  # unmodified dice roll of 1 is always a miss
            hit_result['hit'] = False
            hit_result['special_effects'].append("Natural 1 (auto-miss)")
            return hit_result
        elif dice_roll == 6:  # unmodified dice roll of 6 is always a hit
            hit_result['hit'] = True
            hit_result['special_effects'].append("Natural 6 (auto-hit)")
            attack_instance['crit_hit'] = True
            
            if self.is_lethal_hits():
                hit_result['special_effects'].append("Lethal Hits")
                attack_instance['lethal_hit'] = True
            if self.is_sustained_hits():
                # Support Sustained Hits X / Sustained Hits D3 / etc. Roll per critical hit.
                try:
                    sh = self.get_sustained_hits_bonus()
                    sh_val = int(sh.resolve())
                    hit_result['special_effects'].append(f"Sustained Hits {sh} (+{sh_val})")
                    attack_instance['sustained_hit'] = sh_val
                except Exception:
                    hit_result['special_effects'].append("Sustained Hits (+1)")
                    attack_instance['sustained_hit'] = 1
            return hit_result

        # Normal hit resolution
        hit_result['hit'] = self.skill > 0 and dice_roll >= final_needed
        
        return hit_result

    def _wound_target_with_tracking(self, target: 'Unit', attacker: 'Model', attack_instance: Dict) -> Dict:
        """Wound resolution with detailed tracking"""
        wound_result = {
            'roll': None,
            'needed': None,
            'base_strength': self.strength,
            'target_toughness': None,
            'modifiers': [],
            'final_needed': None,
            'wound': False,
            'special_effects': []
        }
        
        if attack_instance.get('lethal_hit', False):
            wound_result['wound'] = True
            wound_result['special_effects'].append("Lethal Hit (auto-wound)")
            return wound_result

        # Attached units can still be valid targets even if bodyguard models are gone (leaders remain)
        try:
            alloc = target.get_models_for_wound_allocation()
        except Exception:
            alloc = list(getattr(target, "models", []) or [])
        if not alloc:
            wound_result['special_effects'].append("No valid targets")
            return wound_result

        target_toughness = target.toughness
        wound_result['target_toughness'] = target_toughness
        strength = self.strength
        # Enhancement: improve melee weapons' Strength by X (bearer enhancement).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                s_bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("enhancement_melee_strength_bonus", 0) or 0)
                if s_bonus and isinstance(strength, int):
                    strength = strength + s_bonus
                    wound_result.setdefault("modifiers", []).append(f"+{s_bonus}S from Enhancement (melee)")
        except Exception:
            pass
        # Provide reroll callback for wound
        def _reroll_wound():
            new_roll = get_roll("D6")
            try:
                weapon_name_for_log = getattr(self, 'parent_wargear', None).name if getattr(self, 'parent_wargear', None) else getattr(self, 'name', 'Weapon')
                append_dice(attacker.parent_unit.get_parent_army().player.name, f"Wound re-roll: {new_roll} vs T{target_toughness} by {attacker.name} with {weapon_name_for_log}")
            except Exception:
                pass
            return new_roll
        # Precompute wound-roll modifiers (10e-style +/-1 cap)
        dice_modifier = 0
        try:
            # LANCE: if bearer made a Charge move this turn, add 1 to this attack's Wound roll.
            # (Applied only for melee attacks.)
            is_melee = False
            try:
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
            except Exception:
                is_melee = False
            if is_melee and self.is_lance():
                charged = bool(getattr(attacker.parent_unit.round_state, "charged_this_round", False))
                if charged:
                    dice_modifier += 1
                    wound_result['modifiers'].append("+1 to wound from Lance (charged)")
        except Exception:
            pass

        dice_modifier = min(max(dice_modifier, -1), 1)

        dice_roll = get_roll("D6")
        try:
            weapon_name_for_log = getattr(self, 'parent_wargear', None).name if getattr(self, 'parent_wargear', None) else getattr(self, 'name', 'Weapon')
            append_dice(attacker.parent_unit.get_parent_army().player.name, f"Wound roll: {dice_roll} vs T{target_toughness} by {attacker.name} with {weapon_name_for_log}")
        except Exception:
            pass
        wound_result['roll'] = dice_roll
        # Publish roll_made for wound
        try:
            unit = attacker.parent_unit
            game = unit.get_parent_army().player.game
            game.event_system.publish("roll_made", player=unit.get_parent_army().player, unit=unit, roll_type="wound", value=dice_roll, reroll=_reroll_wound)
        except Exception:
            pass

        def _apply_wound_roll(roll: int) -> bool:
            """Apply wound logic for a given (unmodified) roll; respects dice_modifier."""
            # Natural 1 always fails
            if roll == 1:
                return False
            # Natural 6 always wounds (critical wound)
            if roll == 6:
                wound_result['special_effects'].append("Natural 6 (auto-wound)")
                attack_instance['crit_wound'] = True
                if self.is_devastating_wounds():
                    wound_result['special_effects'].append("Devastating Wounds")
                    attack_instance['mortal_wound'] = True
                return True

            # Anti-X can make a roll count as a critical wound
            anti_keyword, anti_value = self.is_anti()
            if anti_keyword and target.has_keyword(anti_keyword):
                if roll >= anti_value:
                    wound_result['special_effects'].append(f"Anti-{anti_keyword} {anti_value}+")
                    attack_instance['crit_wound'] = True
                    if self.is_devastating_wounds():
                        wound_result['special_effects'].append("Devastating Wounds")
                        attack_instance['mortal_wound'] = True
                    return True

            # Determine base wound threshold based on S vs T
            base_needed = None
            strength_comparison = ""
            if strength >= (target_toughness * 2):
                base_needed = 2
                strength_comparison = f"S{strength} ≥ 2×T{target_toughness}"
            elif strength > target_toughness:
                base_needed = 3
                strength_comparison = f"S{strength} > T{target_toughness}"
            elif strength == target_toughness:
                base_needed = 4
                strength_comparison = f"S{strength} = T{target_toughness}"
            elif strength <= (target_toughness / 2):
                base_needed = 6
                strength_comparison = f"S{strength} ≤ T{target_toughness}/2"
            else:
                base_needed = 5
                strength_comparison = f"S{strength} < T{target_toughness}"

            # Note: positive dice_modifier makes it easier (lower needed), capped elsewhere to +/-1
            final_needed = base_needed - dice_modifier
            # Clamp within [2, 6] (wound rolls can never be improved beyond 2+ / worsened beyond 6+)
            final_needed = min(max(final_needed, 2), 6)

            wound_result['needed'] = base_needed
            wound_result['final_needed'] = final_needed
            if strength_comparison:
                wound_result.setdefault('strength_comparison', strength_comparison)
            return roll >= final_needed

        # First attempt
        if dice_roll == 6:
            wound_result['wound'] = True
            wound_result['wound'] = _apply_wound_roll(dice_roll)
        else:
            wound_result['wound'] = _apply_wound_roll(dice_roll)

        # TWIN-LINKED: re-roll failed wound rolls once.
        try:
            if (not wound_result['wound']) and self.is_twin_linked():
                reroll = _reroll_wound()
                wound_result['special_effects'].append("Twin-linked (re-roll failed wound)")
                wound_result['reroll'] = reroll
                wound_result['wound'] = _apply_wound_roll(reroll)
        except Exception:
            pass

        if dice_roll == 1:
            wound_result['special_effects'].append("Natural 1 (auto-fail)")

        return wound_result

    def _save_with_tracking(self, target_model: 'Model', attack_instance: Dict, ap: int) -> Dict:
        """Saving throw resolution with detailed tracking"""
        save_result = {
            'roll': None,
            'needed': None,
            'saved': False,
            'save_type': 'armor',
            'base_save': target_model.save,
            'ap_modifier': ap,
            'final_save': None,
            'special_effects': []
        }
        
        # Calculate save value
        save_value = target_model.save - ap
        save_result['final_save'] = save_value
        inv_save, inv_save_condition = target_model.inv_save
        
        if inv_save:
            # Check invulnerable save condition (string-based, not callable)
            condition_met = True
            if inv_save_condition and inv_save_condition.strip():
                condition_met = self._check_invulnerable_save_condition(inv_save_condition, attack_instance)
            
            if condition_met and inv_save < save_value:
                save_value = inv_save
                save_result['save_type'] = 'invulnerable'
                save_result['final_save'] = save_value

        # Provide reroll callback for save
        def _reroll_save():
            new_roll = get_roll("D6")
            try:
                append_dice(target_model.parent_unit.get_parent_army().player.name, f"Save re-roll: {new_roll} (need {save_value}+) for {target_model.name}")
            except Exception:
                pass
            return new_roll
        dice_roll = get_roll("D6")
        try:
            append_dice(target_model.parent_unit.get_parent_army().player.name, f"Save roll: {dice_roll} (need {save_value}+) for {target_model.name}")
        except Exception:
            pass
        save_result['roll'] = dice_roll
        save_result['needed'] = save_value
        # Publish roll_made for save
        try:
            unit = target_model.parent_unit
            game = unit.get_parent_army().player.game
            game.event_system.publish("roll_made", player=unit.get_parent_army().player, unit=unit, roll_type="save", value=dice_roll, reroll=_reroll_save)
        except Exception:
            pass
        
        if dice_roll == 1:  # unmodified dice roll of 1 is always a fail
            save_result['saved'] = False
            save_result['special_effects'].append("Natural 1 (auto-fail)")
            return save_result

        dice_modifier = 0  # positive/negative save modifiers

        # Benefit of Cover:
        # - Add 1 to the saving throw against ranged attacks.
        # - Does not apply to invulnerable saving throws.
        # - Models with a Save characteristic of 3+ or better cannot benefit vs AP 0.
        # - Multiple instances are not cumulative (we only ever apply +1).
        try:
            if save_result.get('save_type') == 'armor' and attack_instance.get('benefit_of_cover', False):
                ap_val = int(ap)
                if not (ap_val == 0 and int(target_model.save) <= 3):
                    dice_modifier += 1
                    src = attack_instance.get('benefit_of_cover_source')
                    if src:
                        save_result['special_effects'].append(f"Benefit of Cover ({src})")
                    else:
                        save_result['special_effects'].append("Benefit of Cover")
        except Exception:
            pass

        # TODO: Apply other save modifiers (abilities, stratagems, etc.)
        dice_modifier = min(dice_modifier, 1)  # modifications are capped at +1
        save_result['saved'] = (dice_roll + dice_modifier) >= save_value
        
        if dice_modifier != 0:
            save_result['special_effects'].append(f"Modifier {dice_modifier:+d}")
        
        return save_result

    def _check_invulnerable_save_condition(self, condition: str, attack_instance: dict) -> bool:
        """
        Check if an invulnerable save condition is met based on the attacking weapon.
        
        Args:
            condition: The condition string (e.g., "against psychic attacks", "against melee attacks")
            attack_instance: Dictionary containing attack information including weapon profile
            
        Returns:
            bool: True if the condition is met and the invulnerable save should apply
        """
        if not condition or not condition.strip():
            return True  # No condition means always applies
        
        condition_lower = condition.lower().strip()
        
        # Parse "against XXX attacks" pattern
        import re
        pattern = r'against\s+(\w+)\s+attacks?'
        match = re.search(pattern, condition_lower)
        
        if match:
            keyword_to_check = match.group(1)  # Extract the keyword (e.g., "psychic", "melee", "ranged")
            
            # Check if the attacking weapon has this keyword
            weapon_keywords = [kw.lower() for kw in self.get_keywords()]
            
            # Special case mappings for common keywords
            if keyword_to_check == "psychic":
                return "psychic" in weapon_keywords
            elif keyword_to_check == "melee":
                return self.parent_wargear and self.parent_wargear.is_melee()
            elif keyword_to_check == "ranged":
                return self.parent_wargear and self.parent_wargear.is_ranged()
            elif keyword_to_check == "mortal":
                # Check if this attack deals mortal wounds
                return attack_instance.get('is_mortal', False)
            else:
                # Check for exact keyword match
                return keyword_to_check in weapon_keywords
        
        # If we can't parse the condition, default to applying the save
        # This is safer than blocking legitimate saves due to parsing issues
        print(f"⚠️  Unknown invulnerable save condition format: '{condition}' - applying save")
        return True

    def _damage_target_with_tracking(self, target_model: 'Model', attacker: 'Model', attack_instance: Dict, game_map: Optional['Map'] = None) -> Dict:
        """Damage application with detailed tracking"""
        damage_result = {
            'damage_rolled': 0,
            'damage_applied': 0,
            'target_model': target_model.name,
            'excess_damage': 0,
            'model_killed': False,
            'fnp_saves': 0,
            'fnp_rolls': [],
            'damage_dice_rolls': [],
            'damage_expression': str(self.damage),
            'special_effects': []
        }
        
        # Calculate damage with detailed tracking
        if isinstance(self.damage, DiceCollection):
            # Provide reroll callback for damage
            def _reroll_damage():
                new_val, new_rolls = self.damage.roll_detailed()
                return new_val, new_rolls
            damage_value, dice_rolls = self.damage.roll_detailed()
            damage_result['damage_dice_rolls'] = dice_rolls
            # Publish roll_made for damage
            try:
                unit = attacker.parent_unit
                game = unit.get_parent_army().player.game
                game.event_system.publish("roll_made", player=unit.get_parent_army().player, unit=unit, roll_type="damage", value=damage_value, dice=dice_rolls, reroll=_reroll_damage)
            except Exception:
                pass
        else:
            damage_value = self.damage
            damage_result['damage_dice_rolls'] = []
        damage_result['damage_rolled'] = damage_value
        
        if self.is_melta() and attack_instance['below_half_distance']:
            # Support Melta N / Melta D3 / Melta D6+X, etc.
            try:
                melta = self.get_melta_bonus()
                melta_bonus = int(melta.resolve())
                damage_value += melta_bonus
                damage_result['special_effects'].append(f"Melta +{melta_bonus} ({melta})")
            except Exception:
                # Conservative fallback
                damage_value += 1
                damage_result['special_effects'].append("Melta +1")

        # Enhancement: improve melee weapons' Damage by X (bearer enhancement).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                d_bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("enhancement_melee_damage_bonus", 0) or 0)
                if d_bonus:
                    damage_value += d_bonus
                    damage_result['special_effects'].append(f"Enhancement +{d_bonus}D (melee)")
        except Exception:
            pass

        # Enhancement: reduce damage allocated to bearer by X (min 1).
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            red = int(getattr(t_unit, "special_rules", {}).get("enhancement_reduce_damage_taken", 0) or 0)
            if red:
                before = int(damage_value)
                damage_value = max(1, before - red)
                if before != damage_value:
                    damage_result['special_effects'].append(f"Enhancement -{red}D taken (min 1)")
        except Exception:
            pass
        
        # Apply damage with detailed tracking
        was_alive = target_model.is_alive
        damage_result.update(self._apply_damage_with_tracking(target_model, attacker, damage_value, attack_instance['mortal_wound'], game_map=game_map))
        damage_result['model_killed'] = was_alive and not target_model.is_alive
        
        if attack_instance['mortal_wound']:
            damage_result['special_effects'].append("Mortal Wounds")
        
        return damage_result

    def _apply_damage_with_tracking(self, target_model: 'Model', attacker: 'Model', damage_amount: int, is_mortal: bool, game_map: Optional['Map'] = None) -> Dict:
        """Apply damage with detailed tracking of Feel No Pain saves"""
        from warhammer40k_ai.utility.dice import get_roll
        
        result = {
            'damage_applied': 0,
            'fnp_saves': 0,
            'fnp_rolls': [],
            'excess_damage': 0
        }
        
        # Handle Feel No Pain saves
        final_damage = damage_amount
        fnp_abilities = target_model.parent_unit.has_feel_no_pain()
        
        if fnp_abilities:
            # Find the best applicable Feel No Pain ability
            best_fnp = target_model._get_best_applicable_fnp(fnp_abilities, self, is_mortal)
            
            if best_fnp:
                fnp_value, fnp_condition = best_fnp
                fnp_saves = 0
                
                # Roll D6 for each point of damage
                for i in range(damage_amount):
                    fnp_roll = get_roll("D6")
                    fnp_result = {
                        'roll': fnp_roll,
                        'needed': fnp_value,
                        'saved': fnp_roll >= fnp_value,
                        'condition': fnp_condition
                    }
                    result['fnp_rolls'].append(fnp_result)
                    
                    if fnp_result['saved']:
                        fnp_saves += 1
                
                final_damage = damage_amount - fnp_saves
                result['fnp_saves'] = fnp_saves
        
        # Apply the final damage
        result['damage_applied'] = final_damage
        target_model.wounds -= final_damage
        
        # Handle model death
        if not target_model.is_alive:
            # Publish destruction event with attacker/target context (best-effort).
            # This is the primary hook for "on kill" abilities like Trophy Taker.
            try:
                target_unit = getattr(target_model, "parent_unit", None)
                attacker_unit = getattr(attacker, "parent_unit", None)
                if target_unit is not None:
                    setattr(target_unit, "_last_destroyed_by_model", attacker)
                    setattr(target_unit, "_last_destroyed_by_unit", attacker_unit)
                    setattr(target_unit, "_last_destroyed_by_weapon_profile", self)

                game = attacker_unit.get_parent_army().player.game if attacker_unit is not None else None
                if game is not None and hasattr(game, "event_system"):
                    game.event_system.publish(
                        "model_destroyed",
                        attacker_model=attacker,
                        attacker_unit=attacker_unit,
                        target_model=target_model,
                        target_unit=target_unit,
                        weapon_profile=self,
                        is_mortal=is_mortal,
                        game_map=game_map,
                    )
            except Exception:
                pass

            target_model.die(game_map=game_map)
            # Calculate excess damage (10th edition: excess damage is lost)
            if is_mortal and abs(target_model.wounds) > 0:
                result['excess_damage'] = abs(target_model.wounds)
        
        # Check for damaged profile
        target_model._check_damaged_profile()
        
        return result

    def _print_attack_summary(self, result: AttackResult) -> None:
        """Print comprehensive attack summary"""
        print(f"\n🎯 ATTACK SUMMARY: {result.weapon_name}")
        print(f"   Attacker: {result.attacker_name} → Target: {result.target_unit_name}")
        
        # Attack generation with dice details
        modifiers_str = f" ({', '.join(result.attacks_special_modifiers)})" if result.attacks_special_modifiers else ""
        dice_details = ""
        if result.attacks_dice_rolls:
            dice_str = ", ".join(map(str, result.attacks_dice_rolls))
            dice_details = f" - rolled: [{dice_str}]"
        print(f"   🎲 Attacks: {result.attacks_rolled} (from {result.attacks_dice_expression}{dice_details}){modifiers_str}")
        
        # Hit results with needed/rolled format and modifier breakdown
        if result.hit_results:
            hit_rolls = [str(hit['roll']) if hit['roll'] is not None else 'Auto' for hit in result.hit_results]
            hit_rolls_str = ", ".join(hit_rolls)
            
            # Show hit details with modifiers if any
            first_hit = result.hit_results[0]
            if 'final_needed' in first_hit and first_hit['final_needed'] is not None:
                base_skill = first_hit['base_skill']
                final_needed = first_hit['final_needed']
                
                if first_hit.get('modifiers'):
                    modifiers_str = ", ".join(first_hit['modifiers'])
                    needed_str = f"needed {final_needed}+ (base {base_skill}+ with {modifiers_str})"
                else:
                    needed_str = f"needed {final_needed}+"
            else:
                # Fallback for auto-hit or special cases
                needed_str = "auto-hit"
            
            print(f"   ⚔️ Hits: {result.total_hits}/{len(result.hit_results)} - {needed_str} - rolled: [{hit_rolls_str}]")
        
        # Wound results with needed/rolled format and strength comparison
        if result.wound_results:
            wound_rolls = [str(wound['roll']) if wound['roll'] is not None else 'Auto' for wound in result.wound_results]
            wound_rolls_str = ", ".join(wound_rolls)
            
            # Determine display logic based on wound results
            normal_wounds = [w for w in result.wound_results if 'final_needed' in w and w['final_needed'] is not None]
            special_wounds = [w for w in result.wound_results if 'final_needed' not in w or w['final_needed'] is None]
            
            if normal_wounds:
                # Use normal wound logic - show strength vs toughness
                first_normal = normal_wounds[0]
                base_needed = first_normal['needed']
                final_needed = first_normal['final_needed']
                strength_comp = first_normal.get('strength_comparison', '')
                
                if first_normal.get('modifiers'):
                    modifiers_str = ", ".join(first_normal['modifiers'])
                    needed_str = f"needed {final_needed}+ (base {base_needed}+ with {modifiers_str}, {strength_comp})"
                else:
                    needed_str = f"needed {final_needed}+ ({strength_comp})"
            elif special_wounds:
                # All wounds are special cases (lethal hits, natural 6s, anti-X, natural 1, etc.)
                special_effects = []
                any_special_wound_success = False
                for wound in special_wounds:
                    if wound.get('wound'):
                        any_special_wound_success = True
                    if 'special_effects' in wound:
                        special_effects.extend(wound['special_effects'])

                effects_str = f" ({', '.join(set(special_effects))})" if special_effects else ""
                if any_special_wound_success:
                    needed_str = f"auto-wound{effects_str}"
                else:
                    needed_str = f"auto-fail{effects_str}"
            else:
                # Fallback
                needed_str = "auto-fail"
            
            print(f"   🩸 Wounds: {result.total_wounds}/{len(result.wound_results)} - {needed_str} - rolled: [{wound_rolls_str}]")
        
        # Save results with save type and modifiers
        if result.save_results:
            save_rolls = [str(save['roll']) for save in result.save_results]
            save_rolls_str = ", ".join(save_rolls)
            
            # Show save details - assume all saves are the same type for this attack
            first_save = result.save_results[0]
            save_type_str = "Inv" if first_save['save_type'] == 'invulnerable' else "Armor"
            
            if first_save['save_type'] == 'armor' and first_save['ap_modifier'] < 0:
                needed_str = f"needed {first_save['needed']}+ {save_type_str} (base {first_save['base_save']}+ with AP{first_save['ap_modifier']})"
            else:
                needed_str = f"needed {first_save['needed']}+ {save_type_str}"
            
            failed_saves = len(result.save_results) - sum(1 for s in result.save_results if s['saved'])
            print(f"   🛡️ Saves: {failed_saves}/{len(result.save_results)} failed - {needed_str} - rolled: [{save_rolls_str}]")
        
        # Damage results with Feel No Pain details
        if result.damage_results:
            damage_summary = []
            for i, dmg in enumerate(result.damage_results):
                effects = f" [{', '.join(dmg['special_effects'])}]" if dmg['special_effects'] else ""
                killed = " 💀" if dmg['model_killed'] else ""
                fnp_info = ""
                
                # Add Feel No Pain information
                if dmg['fnp_rolls']:
                    fnp_saves = dmg['fnp_saves']
                    fnp_total = len(dmg['fnp_rolls'])
                    fnp_rolls_str = ", ".join([str(roll['roll']) for roll in dmg['fnp_rolls']])
                    fnp_needed = dmg['fnp_rolls'][0]['needed'] if dmg['fnp_rolls'] else 'N/A'
                    fnp_info = f" FNP: {fnp_saves}/{fnp_total} saved (needed {fnp_needed}+ - rolled: [{fnp_rolls_str}])"
                
                # Add damage dice roll information
                damage_info = f"{dmg['damage_rolled']}→{dmg['damage_applied']}"
                if dmg['damage_dice_rolls']:
                    dice_rolls_str = ", ".join([str(roll) for roll in dmg['damage_dice_rolls']])
                    damage_info = f"{dmg['damage_rolled']}→{dmg['damage_applied']} (from {dmg['damage_expression']} - rolled: [{dice_rolls_str}])"
                
                damage_summary.append(f"#{i+1}: {damage_info} to {dmg['target_model']}{fnp_info}{effects}{killed}")
            print(f"   💥 Damage: {result.total_damage_dealt} total - {', '.join(damage_summary)}")
        
        # Hazardous effects
        if result.hazardous_roll is not None:
            hazard_result = "💀 Backfire!" if result.hazardous_roll == 1 else "✓ Safe"
            print(f"   ⚠️ Hazardous: Rolled {result.hazardous_roll} - {hazard_result}")
            if result.hazardous_damage > 0:
                print(f"      {result.attacker_name} takes {result.hazardous_damage} mortal wounds")
        
        # Final summary
        if result.models_killed > 0:
            print(f"   ☠️ Models eliminated: {result.models_killed}")
        
        print()  # Empty line for readability

    # Legacy methods for backwards compatibility
    def hit_target(self, target: 'Unit', attacker: 'Model', attack_instance: Dict) -> bool:
        """Legacy hit target method for backwards compatibility"""
        hit_result = self._hit_target_with_tracking(target, attacker, attack_instance)
        return hit_result['hit']

    def wound_target(self, target: 'Unit', attacker: 'Model', attack_instance: Dict) -> bool:
        """Legacy wound target method for backwards compatibility"""
        wound_result = self._wound_target_with_tracking(target, attacker, attack_instance)
        return wound_result['wound']

    def opponent_wound_allocation(self, target: 'Unit') -> Optional['Model']:
        """Allocate wounds to target models"""
        # Attached units: allocate to bodyguards while any exist; otherwise allocate to leader models.
        try:
            candidates = target.get_models_for_wound_allocation()
        except Exception:
            candidates = list(getattr(target, "models", []) or [])

        if not candidates:
            return None

        # Prefer already-damaged model
        try:
            for m in candidates:
                if getattr(m, "is_alive", True) and (not getattr(m, "is_max_health", True)):
                    return m
        except Exception:
            pass

        return candidates[0]

    def damage_target(self, target_model: 'Model', attacker: 'Model', attack_instance: Dict) -> int:
        """Legacy damage target method for backwards compatibility"""
        damage_result = self._damage_target_with_tracking(target_model, attacker, attack_instance)
        return damage_result['damage_applied']

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

    def is_one_shot(self) -> bool:
        return 'one shot' in [keyword.lower() for keyword in self.get_keywords()]

    def one_shot_key(self) -> str:
        """Stable-ish identifier for per-model one-shot tracking."""
        try:
            parent = getattr(self, "parent_wargear", None)
            parent_name = getattr(parent, "name", "") if parent is not None else ""
            profile_name = getattr(self, "name", "") or ""
            if parent_name:
                # Track at the weapon level so alternative profiles don't bypass ONE SHOT.
                return parent_name
            return profile_name
        except Exception:
            return str(getattr(self, "name", ""))

    def can_shoot_after_advance(self) -> bool:
        """Check if this weapon can be shot after advancing.
        
        Assault weapons can always be shot after advancing.
        """
        return self.is_assault()

    def is_sustained_hits(self) -> bool:
        return any((k or "").strip().lower().startswith("sustained hits") for k in self.get_keywords())

    def get_sustained_hits_bonus(self) -> Count:
        # Defaults to Sustained Hits 1 when unspecified
        return self._get_keyword_suffix_count("sustained hits", default=1)

    def is_rapid_fire(self) -> bool:
        return any((k or "").strip().lower().startswith("rapid fire") for k in self.get_keywords())

    def get_rapid_fire_bonus(self) -> Count:
        # Defaults to Rapid Fire 1 when unspecified
        return self._get_keyword_suffix_count("rapid fire", default=1)

    def is_melta(self) -> bool:
        return any((k or "").strip().lower().startswith("melta") for k in self.get_keywords())

    def get_melta_bonus(self) -> Count:
        # Defaults to Melta 1 when unspecified
        return self._get_keyword_suffix_count("melta", default=1)

    def is_anti(self):
        for keyword in self.get_keywords():
            if keyword.lower().startswith('anti-'):
                parts = keyword[4:].replace('+', '').split(' ')
                if len(parts) == 2 and parts[1].isdigit():
                    return parts[0].lower(), int(parts[1])
        return "", 0

    def is_split_fire(self) -> bool:
        """Check if this weapon has split fire ability"""
        # Check weapon keywords for split fire
        keywords = self.get_keywords()
        if 'Split Fire' in keywords:
            return True
        
        # Check if the weapon profile has split fire in its parent wargear
        if hasattr(self, 'parent_wargear') and self.parent_wargear:
            wargear_keywords = self.parent_wargear.get_keywords()
            if 'Split Fire' in wargear_keywords:
                return True
        
        return False


class Wargear:
    def __init__(self, wargear_data: Dict):
        self.name = (wargear_data.get('name', '') or '').replace("’", "'")
        if ' – ' in self.name:
            self.name, profile_name = self.name.split(' – ')
        else:
            profile_name = 'default'
        self.type = wargear_data.get('type', '')
        self.profiles = { profile_name: WargearProfile(profile_name, wargear_data, self) }

    def add_profile(self, profile_name: str, wargear_data: Dict):
        self.profiles[profile_name] = WargearProfile(profile_name, wargear_data, self)

    def __str__(self):
        str = f"{self.name} ({self.type}): "
        for profile_name, profile in self.profiles.items():
            str += f"[{profile_name}: "
            str += f"Range {self.get_range(profile_name)}, A {self.get_attacks(profile_name)}, "
            str += f"BS/WS {self.get_skill(profile_name)}, S {self.get_strength(profile_name)}, "
            str += f"AP {self.get_ap(profile_name)}, D {self.get_damage(profile_name)}]"
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
        if profile_name not in self.profiles and self.profiles:
            profile_name = next(iter(self.profiles.keys()))
        return self.profiles[profile_name].range

    def get_attacks(self, profile_name: str = 'default') -> Count:
        if profile_name not in self.profiles and self.profiles:
            profile_name = next(iter(self.profiles.keys()))
        return self.profiles[profile_name].attacks

    def get_skill(self, profile_name: str = 'default') -> int:
        if profile_name not in self.profiles and self.profiles:
            profile_name = next(iter(self.profiles.keys()))
        return self.profiles[profile_name].skill

    def get_strength(self, profile_name: str = 'default') -> int:
        if profile_name not in self.profiles and self.profiles:
            profile_name = next(iter(self.profiles.keys()))
        return self.profiles[profile_name].strength

    def get_ap(self, profile_name: str = 'default') -> int:
        if profile_name not in self.profiles and self.profiles:
            profile_name = next(iter(self.profiles.keys()))
        return self.profiles[profile_name].ap

    def get_damage(self, profile_name: str = 'default') -> int:
        if profile_name not in self.profiles and self.profiles:
            profile_name = next(iter(self.profiles.keys()))
        return self.profiles[profile_name].damage

    def get_keywords(self, profile_name: str = 'default') -> List[str]:
        # If the requested profile doesn't exist, try to use the first available profile
        if profile_name not in self.profiles:
            if self.profiles:
                # Use the first available profile
                profile_name = next(iter(self.profiles.keys()))
            else:
                # No profiles available, return empty list
                return []
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
            # Default values
            self.model_quantity = Quantity(min=1, max=1)
        self.item_quantity = item_quantity
        self.conditionals = [conditional.lower() for conditional in conditionals] if conditionals else []

    def __str__(self):
        from_str = ', '.join(str(x) for x in self.wargear_from) if self.wargear_from else 'none'
        # wargear_to is a list of "choices", each choice is a list[(qty, name)].
        # Present them as distinct choices (avoid flattening, which is misleading).
        if self.wargear_to:
            choice_strs = []
            for choice in self.wargear_to:
                items = ", ".join(f"{qty}x {name}" for qty, name in (choice or []))
                choice_strs.append(f"[{items}]")
            to_str = " OR ".join(choice_strs) if choice_strs else "none"
        else:
            to_str = 'none'
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
    parsed_result = parse_alternate_3(option)
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
        description = option.replace("'s", "'s").replace(",", " and")

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

def parse_warger_actor_string(actor_str: str) -> str:
    actor = actor_str
    condition = ""

    if actor_str[-1] == "s":
        actor = actor_str[:-1]
    if " equipped with " in actor:
        match = re.match(r"^([\w\s'-]+) equipped with an? (.*)", actor)
        if match:
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
        if not specific_option or not specific_option.strip():
            continue
        #print(f"SPECIFIC OPTION: {specific_option}")
        opt_lines = [item.strip() for item in specific_option.split(" and ")]
        results = []
        for opt in opt_lines:
            if not opt or not opt.strip():
                continue
            # Extract count if present, default to 1
            count_match = re.match(r'^(\d+)\s+(.+)$', opt)
            if count_match:
                item_count, item_name = count_match.groups()
                item_count = int(item_count)
            else:
                item_count = 1
                item_name = opt
            item_name = (item_name or "").strip().lower()
            if not item_name:
                continue
            results.append((item_count, item_name))
        if results:
            full_result.append(results)
    return full_result

def parse_alternate_3(str_list: list[str], unit_ptr: 'Unit' = None) -> list[WargearOption]:
    def _norm_name(s: str) -> str:
        s = (s or "").replace("’", "'").lower().strip()
        s = re.sub(r"[^\w\s\-']", " ", s)
        s = s.replace("'", "")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _count_actor_models(actor: str) -> int:
        """
        Best-effort count of models in the unit that match an actor string.
        Used for "All X in this unit..." which is an all-or-none choice.
        """
        if not unit_ptr or not getattr(unit_ptr, "models", None):
            return 1
        a = _norm_name(actor)
        if a in ("model", "this model", "unit"):
            return len(unit_ptr.models)
        n = 0
        for m in unit_ptr.models:
            mn = _norm_name(getattr(m, "name", ""))
            if not mn:
                continue
            if a == mn or a in mn or mn in a:
                n += 1
        return n or len(unit_ptr.models)

    def _normalize_options_text(text: str) -> str:
        """
        Datasheets_options.json frequently contains HTML lists, e.g.
          "... one of the following:<ul><li>1 x</li><li>1 y</li></ul>"
        Normalize those into a semicolon-delimited form that our parser understands.
        """
        if not text:
            return ""
        t = text.replace("’", "'")
        # turn <li> boundaries into semicolon separators before stripping tags
        t = re.sub(r"</li\s*>", ";", t, flags=re.IGNORECASE)
        t = re.sub(r"<li[^>]*>", "", t, flags=re.IGNORECASE)
        t = re.sub(r"</?(?:ul|ol)[^>]*>", " ", t, flags=re.IGNORECASE)
        t = re.sub(r"<br\s*/?>", ";", t, flags=re.IGNORECASE)
        # strip remaining tags
        t = re.sub(r"<[^>]+>", " ", t)
        # normalize whitespace around separators
        t = re.sub(r"\s*;\s*", "; ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

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
        description = _normalize_options_text(line).lower()
        description = description.replace(".", "").replace('model"s', "model's").replace("for every four ", "for every 4 ")
        description = description.replace(" one of the following ", " one of the following: ").replace(" 1 of the following: ", " one of the following: ").replace(" 2 of the following: ", " two of the following: ")
        description = description.replace("up to two ", "up to 2 ").replace("up to three ", "up to 3 ").replace("up to four ", "up to 4 ")

        # Split combined statements like:
        # "This model can be equipped with 1 havoc launcher or can replace 1 combi-bolter with 1 havoc launcher."
        if (" can be equipped with " in description) and (" or can replace " in description) and (" with " in description):
            m = re.match(
                r"^(this model) can be equipped with (.+?) or can replace (.+?) with (.+?)$",
                description,
            )
            if m:
                part_a = f"{m.group(1)} can be equipped with {m.group(2)}"
                # Normalize to a replacement form our parser already supports.
                part_b = f"{m.group(1)}'s {m.group(3)} can be replaced with {m.group(4)}"
                wargear_options.extend(parse_alternate_3([part_a], unit_ptr))
                wargear_options.extend(parse_alternate_3([part_b], unit_ptr))
                called_recursively = True
                continue

        # Extract "cannot be replaced" lock clauses (keep as conditionals).
        # Common forms:
        # - "that model's lasgun cannot be replaced"
        # - "its lasgun cannot be replaced"
        lock_items = []
        for m in re.finditer(r"(?:that model's|its)\s+([\w\s'-]+?)\s+cannot\s+be\s+replaced", description):
            lock_items.append(m.group(1).strip())
        if lock_items:
            for li in lock_items:
                conditions.append(f"cannot replace {li}")
            # Remove the clause so it doesn't interfere with wargear parsing
            description = re.sub(r"(?:that model's|its)\s+[\w\s'-]+?\s+cannot\s+be\s+replaced", "", description).strip()
        # Debug spam is very noisy during army parsing. Enable manually while developing.
        DEBUG = False
        if DEBUG:
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
        elif match := re.match(r"^(?:this|the|a|an|1|one) ([\w\s'-]+) can (?:each |)be equipped with:? (.*)", description):
            assert not is_replacement
            actor, condition = parse_warger_actor_string(match.group(1))
            conditions.append(condition)
            replacement_items, limit = parse_wargear_string_ending(match.group(2))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^(?:this|the|a|an|1|one) ([\w\s'-]+) can be equipped with up to (\d+) ([\w\s'-]+)", description):
            # e.g. "This model can be equipped with up to 4 big shootas"
            assert not is_replacement
            actor, condition = parse_warger_actor_string(match.group(1))
            conditions.append(condition)
            try:
                limit = int(match.group(2))
            except Exception:
                limit = 1
            replacement_items = parse_wargear_item([match.group(3).strip()])
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^(?:this|the|a|an|1|one|each) ([\w\s'-]+)'s? ([\w\s'-]+) can be replaced with:? (.*)", description):
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
            if break_symbol in (",", ":"):
                wgo_list = parse_alternate_3([match.group(4)], unit_ptr)
                for wgo in wgo_list:
                    # Condition text is everything before the break symbol
                    wgo.conditionals.append(description.split(break_symbol, 1)[0].strip())
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
        elif match := re.match(r"^(?:this|the|a|an|1|one) ([\w\s'-]+) can have its ([\w\s'-]+) replaced with (.*)", description):
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
        elif match := re.match(r"^all models in this unit can each have their ([\w\s'-]+) replaced with (.*)", description):
            # "All" is an all-or-none boolean (every model or none).
            actor = "model"
            model_n = len(unit_ptr.models) if unit_ptr and getattr(unit_ptr, "models", None) else 1
            model_limit = Quantity(min=model_n, max=model_n)
            items_to_replace = parse_wargear_itemlist(match.group(1))
            replacement_items, limit = parse_wargear_string_ending(match.group(2))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^all of the ([\w\s'-]+)s in this unit can each have their ([\w\s'-]+) replaced with (.*)", description):
            actor, _ = parse_warger_actor_string(match.group(1))
            model_n = _count_actor_models(actor)
            model_limit = Quantity(min=model_n, max=model_n)
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
        elif match := re.match(r"^this model's ([\w\s'-]+) can be replaced with one of the following: (.*)", description):
            assert is_replacement
            actor = "model"
            items_to_replace = parse_wargear_itemlist(match.group(1))
            replacement_items, limit = parse_wargear_string_ending(match.group(2))
            item_limit = Quantity(min=1, max=limit)
        elif match := re.match(r"^for each ([\w\s'-]+) this model is equipped with, it can be equipped with one of the following: (.*)", description):
            assert not is_replacement
            actor = "model"
            conditions.append(f"item_limit is equal to number of equipped {match.group(1)}")
            items_to_replace = parse_wargear_itemlist(match.group(1))
            # Parse the "one of the following" list properly
            replacement_items = parse_wargear_itemlist(match.group(2))
            item_limit = Quantity(min=1, max=len(replacement_items))
        else:
            if DEBUG:
                print(f"UNKNOWN: {line}")
            unhandled = True

        if not called_recursively:
            if DEBUG:
                print(f"CONDITIONS: {conditions}")
                print(f"MODEL LIMIT: {model_limit}")
                print(f"ACTOR: {actor}")
                print(f"BASE WARGEAR: {items_to_replace}")
                print(f"ITEM LIMIT: {item_limit}")

            if is_replacement:
                if DEBUG:
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
                if DEBUG:
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
            if DEBUG:
                print(f"UNHANDLED: {str_list}")
            #raise Exception(f"UNHANDLED: {str_list}")

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