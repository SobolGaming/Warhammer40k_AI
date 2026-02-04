from typing import Union, Dict, List, Optional, Tuple
from enum import Enum, auto
from collections import namedtuple
import copy
import uuid
import re
from warhammer40k_ai.utility.dice import DiceCollection, get_roll
from warhammer40k_ai.utility.hazardous import (
    apply_hazardous_roll_modifier,
    hazardous_roll_modifier,
    is_hazardous_failure,
)
from warhammer40k_ai.utility.event_bus import append_dice, append_action
from warhammer40k_ai.utility.range import Range
from warhammer40k_ai.utility.count import Count
from warhammer40k_ai.utility.entity_ids import get_entity_id
from dataclasses import dataclass

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .model import Model
    from .unit import Unit
    from ..battlefield.map import Map

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


@dataclass(frozen=True)
class AttackCountInfo:
    """Resolved attacks count plus supporting roll/modifier context."""
    num_attacks: int
    dice_rolls: List[int]
    special_modifiers: List[str]


class WargearProfile:
    def __init__(self, profile_name: str, wargear_data: Dict, parent_wargear: Optional['Wargear'] = None):
        self._id = str(uuid.uuid4())
        self.name = profile_name
        self.parent_wargear = parent_wargear
        # Preserve raw strings for Core Rules "unmodifiable" characteristics (e.g. '-', 'N/A', '20+"').
        self._raw_range = wargear_data.get('range', '')
        self._raw_attacks = wargear_data.get('A', '')
        self._raw_skill = wargear_data.get('BS_WS', '')
        self._raw_strength = wargear_data.get('S', '')
        self._raw_ap = wargear_data.get('AP', '')
        self._raw_damage = wargear_data.get('D', '')
        self._raw_description = wargear_data.get('description', '')
        self.range = self._parse_range(wargear_data.get('range', ''))
        self.attacks = self._parse_attacks(wargear_data.get('A', ''))
        self.skill = self._parse_attribute(wargear_data.get('BS_WS', ''))
        self.strength = self._parse_attribute(wargear_data.get('S', ''))
        self.ap = self._parse_attribute(wargear_data.get('AP', ''))
        self.damage = self._parse_attribute(wargear_data.get('D', ''))
        self.keywords = self._parse_keywords(wargear_data.get('description', ''))
        self._wounds_cannot_be_ignored_cached: Optional[bool] = None

    @property
    def id(self) -> str:
        return self._id
    
    def _parse_range(self, range_string: str) -> Range:
        if "Melee" == range_string:
            return Range.from_string("0")
        return Range.from_string(range_string)

    def _parse_attacks(self, attacks_string: str) -> Count:
        return Count.from_string(attacks_string)

    def _parse_attribute(self, attribute_value: str) -> Union[int, DiceCollection]:
        # Remove " and normalize common placeholders.
        attribute_value = (attribute_value or "").replace('"', "").strip()
        attribute_value = (
            attribute_value.replace("\u00e2\u0080\u0099", "'")
            .replace("\u2019", "'")
            .replace("\u00e2\u0080\u0093", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
        )

        # Remove trailing + if it exists.
        if attribute_value.endswith("+"):
            attribute_value = attribute_value[:-1]

        # Common placeholders in Wahapedia exports.
        if attribute_value in ("", "-", "N/A"):
            return 0

        if "D" in attribute_value:
            return DiceCollection.from_string(attribute_value)
        return int(attribute_value)

    def _parse_keywords(self, keywords_string):
        if keywords_string:
            # Wahapedia weapon ability strings are comma-separated. Be defensive and also split on semicolons.
            parts = re.split(r"\s*,\s*|\s*;\s*", str(keywords_string))
            return [p.strip() for p in parts if p and p.strip()]
        return []

    def get_keywords(self) -> List[str]:
        return self.keywords

    def wounds_cannot_be_ignored(self) -> bool:
        """
        Return True if this attack explicitly disables wound-ignoring rules (e.g., Feel No Pain).
        """
        if self._wounds_cannot_be_ignored_cached is not None:
            return bool(self._wounds_cannot_be_ignored_cached)
        text_bits = [str(self._raw_description or "")] + list(self.keywords or [])
        text = " ".join(text_bits).lower()
        patterns = (
            "wounds cannot be ignored",
            "no rules can be used to ignore wounds",
            "no rules can be used to ignore this wound",
            "feel no pain cannot be used",
            "feel no pain cannot be made",
            "cannot use feel no pain",
        )
        self._wounds_cannot_be_ignored_cached = any(p in text for p in patterns)
        return bool(self._wounds_cannot_be_ignored_cached)

    def _get_keyword_suffix_count(self, prefix: str, default: int = 1) -> Count:
        """
        Parse keyword forms like:
        - "rapid fire" or "rapid fire 1" or "rapid fire D3"
        - "melta" or "melta 2" or "melta D3+2"
        If multiple instances exist (e.g. "Sustained Hits 1" and "Sustained Hits 2"), they are NOT cumulative.
        We default to choosing the "best" instance by highest statistical average (player-choice hook could be added later).

        Returns a Count (flat or dice). If absent, returns Count(FLAT, 0).
        """
        try:
            p = (prefix or "").strip().lower()
            if not p:
                return Count.from_string("0")

            candidates: list[Count] = []
            for kw in self.get_keywords():
                raw = (kw or "").strip()
                k = raw.lower()
                if k == p:
                    candidates.append(Count.from_string(str(default)))
                    continue
                if k.startswith(p + " "):
                    suffix = raw[len(prefix):].strip()
                    if not suffix:
                        candidates.append(Count.from_string(str(default)))
                        continue
                    # Normalize common cases: "d3" -> "D3"
                    candidates.append(Count.from_string(suffix.upper()))

            if candidates:
                # Choose the highest expected value (e.g. Sustained Hits 2 over Sustained Hits 1).
                try:
                    return max(candidates, key=lambda c: float(c.stat_average()))
                except Exception:
                    return candidates[0]
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

        # Other special rules are ignored in this estimate to keep it fast and deterministic.
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

    def _unit_special_rules(self, attacker: 'Model') -> dict:
        unit = getattr(attacker, "parent_unit", None)
        sr = getattr(unit, "special_rules", None) if unit is not None else None
        return sr if isinstance(sr, dict) else {}

    def _get_charge_melee_strength_damage_bonus(
        self,
        attacker: 'Model',
        attack_instance: Dict,
    ) -> tuple[int, int, tuple[str, ...], tuple[str, ...]]:
        if not (self.parent_wargear and self.parent_wargear.is_melee()):
            return 0, 0, (), ()
        unit = getattr(attacker, "parent_unit", None)
        if unit is None:
            return 0, 0, (), ()
        round_state = getattr(unit, "round_state", None)
        if not (round_state and bool(getattr(round_state, "charged_this_round", False))):
            return 0, 0, (), ()

        if isinstance(attack_instance, dict) and attack_instance.get("_charge_melee_strength_damage_cached"):
            return (
                int(attack_instance.get("charge_melee_strength_bonus", 0) or 0),
                int(attack_instance.get("charge_melee_damage_bonus", 0) or 0),
                tuple(attack_instance.get("charge_melee_strength_reasons", ()) or ()),
                tuple(attack_instance.get("charge_melee_damage_reasons", ()) or ()),
            )

        entries = []
        if hasattr(unit, "get_melee_charge_strength_damage_entries"):
            entries = list(unit.get_melee_charge_strength_damage_entries() or [])

        strength_bonus = 0
        damage_bonus = 0
        strength_reasons: list[str] = []
        damage_reasons: list[str] = []

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            s_bonus = int(entry.get("strength_bonus", 0) or 0)
            d_bonus = int(entry.get("damage_bonus", 0) or 0)
            source = str(entry.get("source") or "Charge melee bonus").strip() or "Charge melee bonus"
            if s_bonus:
                strength_bonus += s_bonus
                strength_reasons.append(f"+{s_bonus}S from {source} (charged)")
            if d_bonus:
                damage_bonus += d_bonus
                damage_reasons.append(f"+{d_bonus}D from {source} (charged)")

        if isinstance(attack_instance, dict):
            attack_instance["charge_melee_strength_bonus"] = strength_bonus
            attack_instance["charge_melee_damage_bonus"] = damage_bonus
            attack_instance["charge_melee_strength_reasons"] = tuple(strength_reasons)
            attack_instance["charge_melee_damage_reasons"] = tuple(damage_reasons)
            attack_instance["_charge_melee_strength_damage_cached"] = True

        return strength_bonus, damage_bonus, tuple(strength_reasons), tuple(damage_reasons)

    def _current_phase_name(self, attacker: 'Model') -> str:
        unit = getattr(attacker, "parent_unit", None)
        army = unit.get_parent_army() if unit is not None else None
        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        return str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()

    def _attacker_is_enhancement_bearer(self, attacker: 'Model', sr: dict) -> bool:
        bearer_id = sr.get("enhancement_fierce_conqueror_bearer_id") or sr.get("enhancement_bearer_model_id")
        if not bearer_id:
            return False
        attacker_id = str(getattr(attacker, "id", getattr(attacker, "_id", "")) or "")
        return attacker_id == str(bearer_id)

    def _effective_range_max(self, attacker: Optional['Model'] = None) -> int:
        """Return range max after applying model/unit effects (e.g., leading Melta range bonus)."""
        try:
            base_max = int(getattr(self.range, "max", 0) or 0)
        except Exception:
            base_max = 0
        if base_max <= 0:
            return base_max
        if attacker is None:
            return base_max
        bonus = 0
        try:
            if self.is_melta():
                unit = getattr(attacker, "parent_unit", None)
                if unit is not None and hasattr(unit, "leading_unit_melta_range_bonus"):
                    bonus += int(unit.leading_unit_melta_range_bonus() or 0)
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "thousand_sons_detachments", None) if army is not None else None
            if mgr is not None and callable(getattr(mgr, "grand_coven_psychic_range_bonus", None)):
                game = getattr(getattr(army, "player", None), "game", None)
                bonus += int(mgr.grand_coven_psychic_range_bonus(attacker, self, game=game) or 0)
        except Exception:
            pass
        if bonus:
            return base_max + bonus
        return base_max

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
            # Ground level tolerance matches RUINS placement validation tolerance (+/-1")
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
            from ..battlefield.map import TerrainType
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

    def _cabal_twist_of_fate_ap_bonus(self, attacker: 'Model', target: 'Unit') -> int:
        """Return the AP bonus from Cabal of Sorcerers: Twist of Fate, if applicable."""
        if attacker is None or target is None:
            return 0
        try:
            sr = getattr(target, "special_rules", None)
        except Exception:
            sr = None
        if not isinstance(sr, dict):
            return 0
        bonus = int(sr.get("cabal_twist_of_fate_ap_bonus", 0) or 0)
        if bonus <= 0:
            return 0
        try:
            owner = str(sr.get("cabal_twist_of_fate_owner", "") or "")
        except Exception:
            owner = ""
        try:
            unit = attacker.parent_unit
        except Exception:
            unit = None
        if unit is None:
            return 0
        try:
            if owner and owner != str(getattr(unit.get_parent_army(), "_id", "") or ""):
                return 0
        except Exception:
            pass
        try:
            if not (unit.has_any_keyword("THOUSAND SONS") or unit.has_any_keyword("SCINTILLATING LEGIONS")):
                return 0
        except Exception:
            return 0
        return int(bonus)

    def _bondsman_magaera_bonus_applies(self, attacker: 'Model', target: 'Unit') -> bool:
        if attacker is None or target is None:
            return False
        try:
            unit = getattr(attacker, "parent_unit", None)
        except Exception:
            unit = None
        if unit is None:
            return False
        try:
            sr = getattr(unit, "special_rules", None)
        except Exception:
            sr = None
        if not isinstance(sr, dict) or not sr.get("bondsman_magaera_bonus"):
            return False
        try:
            if not (self.parent_wargear and self.parent_wargear.is_ranged()):
                return False
        except Exception:
            return False
        game_map = self._get_game_map_from_model(attacker)
        if game_map is None:
            return False
        try:
            enemies = list(game_map.get_enemy_units(unit) or [])
        except Exception:
            enemies = []
        if not enemies:
            return False
        try:
            target_root = target.get_attached_unit_root()
        except Exception:
            target_root = target
        target_id = get_entity_id(target_root)
        closest = None
        target_dist = None
        seen = set()
        for enemy in enemies:
            try:
                root = enemy.get_attached_unit_root()
            except Exception:
                root = enemy
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            try:
                if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                    continue
            except Exception:
                pass
            try:
                if hasattr(root, "deployed") and not bool(getattr(root, "deployed", True)):
                    continue
            except Exception:
                pass
            try:
                dist = float(game_map.get_distance_between_units(unit, root))
            except Exception:
                continue
            if target_root is root or (target_id and target_id == getattr(root, "_id", None)):
                target_dist = dist
            if closest is None or dist < closest:
                closest = dist
        if closest is None or target_dist is None:
            return False
        return target_dist <= closest + 1e-6

    def get_effective_ap(self, attacker: 'Model', target: 'Unit') -> int:
        """Return AP after applying global modifiers like Plunging Fire."""
        from ..utility.modifiers import apply_characteristic_caps
        try:
            ap_val = int(self.ap)
        except Exception:
            ap_val = 0
        if self._plunging_fire_applies(attacker, target):
            # Improve AP by 1: AP -1 becomes -2, AP 0 becomes -1, etc.
            ap_val -= 1
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                sr = getattr(attacker.parent_unit, "special_rules", None)
                bonus = int(sr.get("pain_melee_ap_bonus", 0) or 0) if isinstance(sr, dict) else 0
                if bonus:
                    ap_val -= bonus
        except Exception:
            pass
        if self.parent_wargear and self.parent_wargear.is_melee():
            sr = self._unit_special_rules(attacker)
            unit_bonus = int(sr.get("enhancement_melee_ap_bonus", 0) or 0)
            if unit_bonus:
                ap_val -= unit_bonus
            bearer_bonus = int(sr.get("enhancement_bearer_melee_ap_bonus", 0) or 0)
            if bearer_bonus and self._attacker_is_enhancement_bearer(attacker, sr):
                ap_val -= bearer_bonus
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                bonus = int(getattr(attacker, "get_temporary_melee_ap_bonus", lambda: 0)() or 0)
                if bonus:
                    ap_val -= bonus
        except Exception:
            pass
        if self.parent_wargear and self.parent_wargear.is_melee():
            from ..utility.aura_effects import get_aura_melee_ap_bonus
            aura_ap, _ = get_aura_melee_ap_bonus(getattr(attacker, "parent_unit", None), self)
            if aura_ap:
                ap_val -= int(aura_ap)
        try:
            from ..utility.aura_effects import get_aura_ap_bonus
            aura_ap, _ = get_aura_ap_bonus(attacker, self, target, game_map=self._get_game_map_from_model(attacker))
            if aura_ap:
                ap_val -= int(aura_ap)
        except Exception:
            pass
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("sensational_performance_active"):
                    apply_bonus = True
                    exp = str(sr.get("sensational_performance_expires_phase", "") or "").strip().upper()
                    if exp:
                        try:
                            army = attacker.parent_unit.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                            pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            pname = ""
                        if pname and pname != exp:
                            apply_bonus = False
                    if apply_bonus:
                        bonus = int(sr.get("sensational_performance_ap_bonus", 0) or 0)
                        if bonus:
                            ap_val -= bonus
        except Exception:
            pass
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                sr = getattr(attacker.parent_unit, "special_rules", None)
                bonus = int(sr.get("hack_and_slash_ap_bonus", 0) or 0) if isinstance(sr, dict) else 0
                if bonus:
                    apply_bonus = True
                    exp = str(sr.get("hack_and_slash_expires_phase", "") or "").strip().upper() if isinstance(sr, dict) else ""
                    if exp:
                        try:
                            army = attacker.parent_unit.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                            pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            pname = ""
                        if pname and pname != exp:
                            apply_bonus = False
                    if apply_bonus:
                        ap_val -= bonus
        except Exception:
            pass
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                sr = getattr(attacker.parent_unit, "special_rules", None)
                bonus = int(sr.get("limb_from_limb_melee_ap_bonus", 0) or 0) if isinstance(sr, dict) else 0
                if bonus:
                    apply_bonus = True
                    exp = str(sr.get("limb_from_limb_expires_phase", "") or "").strip().upper() if isinstance(sr, dict) else ""
                    if exp:
                        try:
                            army = attacker.parent_unit.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                            pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            pname = ""
                        if pname and pname != exp:
                            apply_bonus = False
                    if apply_bonus:
                        ap_val -= bonus
        except Exception:
            pass
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                sr = getattr(attacker.parent_unit, "special_rules", None)
                bonus = int(sr.get("charge_melee_ap_bonus", 0) or 0) if isinstance(sr, dict) else 0
                if bonus:
                    apply_bonus = True
                    exp = str(sr.get("charge_melee_ap_bonus_expires_phase", "") or "").strip().upper() if isinstance(sr, dict) else ""
                    if exp:
                        try:
                            army = attacker.parent_unit.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                            pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            pname = ""
                        if pname and pname != exp:
                            apply_bonus = False
                    if apply_bonus:
                        ap_val -= bonus
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "doctrina_imperatives", None) if army is not None else None
            if mgr is not None and unit is not None:
                game = getattr(getattr(army, "player", None), "game", None)
                game_map = getattr(game, "map", None) if game is not None else None
                if mgr.conqueror_ap_bonus_applies(unit, game=game, game_map=game_map):
                    ap_val -= 1
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
            if mgr is not None and callable(getattr(mgr, "methodical_annihilation_ap_bonus", None)):
                game_map = self._get_game_map_from_model(attacker)
                bonus = int(mgr.methodical_annihilation_ap_bonus(attacker, self, target, game_map=game_map) or 0)
                if bonus:
                    ap_val -= bonus
        except Exception:
            pass
        try:
            if self.parent_wargear and self.parent_wargear.is_ranged():
                sr = getattr(attacker.parent_unit, "special_rules", None)
                bonus = int(sr.get("pain_ranged_ap_bonus", 0) or 0) if isinstance(sr, dict) else 0
                if bonus:
                    ap_val -= bonus
                bonus = int(sr.get("bondsman_ap_bonus_ranged", 0) or 0) if isinstance(sr, dict) else 0
                if bonus:
                    ap_val -= bonus
                if self._bondsman_magaera_bonus_applies(attacker, target):
                    ap_val -= 1
        except Exception:
            pass
        cabal_bonus = self._cabal_twist_of_fate_ap_bonus(attacker, target)
        if cabal_bonus:
            ap_val -= int(cabal_bonus)
        try:
            target_root = target.get_attached_unit_root() if target is not None else target
        except Exception:
            target_root = target
        try:
            attacker_unit = getattr(attacker, "parent_unit", None)
        except Exception:
            attacker_unit = None
        # Post-shoot AP bonus applied to a marked target for friendly keyword attacks.
        if target_root is not None and attacker_unit is not None:
            sr = getattr(target_root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("post_shoot_ap_bonus_active"):
                apply_bonus = True
                exp = str(sr.get("post_shoot_ap_bonus_expires_phase", "") or "").strip().upper()
                if exp:
                    phase_key = self._resolve_phase_key(attacker_unit=attacker_unit, target_unit=target_root)
                    if phase_key and phase_key != exp:
                        apply_bonus = False
                if apply_bonus:
                    owner_id = str(sr.get("post_shoot_ap_bonus_owner", "") or "")
                    if owner_id:
                        attacker_player = None
                        try:
                            army = attacker_unit.get_parent_army()
                            attacker_player = getattr(army, "player", None) if army is not None else None
                        except Exception:
                            attacker_player = None
                        attacker_id = ""
                        if attacker_player is not None:
                            try:
                                attacker_id = get_entity_id(attacker_player)
                            except Exception:
                                attacker_id = str(getattr(attacker_player, "id", "") or "")
                        if attacker_id and owner_id != attacker_id:
                            apply_bonus = False
                if apply_bonus:
                    try:
                        turn = int(sr.get("post_shoot_ap_bonus_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    if turn:
                        game = None
                        try:
                            army = attacker_unit.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                        except Exception:
                            game = None
                        cur_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                        if cur_turn and cur_turn != turn:
                            apply_bonus = False
                if apply_bonus:
                    keyword = str(sr.get("post_shoot_ap_bonus_keyword", "") or "").strip()
                    if keyword and not attacker_unit.has_any_keyword(keyword):
                        apply_bonus = False
                if apply_bonus:
                    attack_type = str(sr.get("post_shoot_ap_bonus_attack_type", "") or "any").strip().lower() or "any"
                    if attack_type in ("ranged", "melee"):
                        try:
                            is_ranged = bool(self.parent_wargear and self.parent_wargear.is_ranged())
                        except Exception:
                            is_ranged = False
                        try:
                            is_melee = bool(self.parent_wargear and self.parent_wargear.is_melee())
                        except Exception:
                            is_melee = False
                        if attack_type == "ranged" and not is_ranged:
                            apply_bonus = False
                        elif attack_type == "melee" and not is_melee:
                            apply_bonus = False
                if apply_bonus:
                    bonus = int(sr.get("post_shoot_ap_bonus_value", 0) or 0)
                    if bonus:
                        ap_val -= bonus
        # Defensive stratagems that worsen AP for attacks against a specific target.
        try:
            if target_root is not None and attacker_unit is not None:
                try:
                    attacker_root = attacker_unit.get_attached_unit_root()
                except Exception:
                    attacker_root = attacker_unit
                attacker_key = get_entity_id(attacker_root)
                sr = getattr(target_root, "special_rules", None)
                if isinstance(sr, dict):
                    spec = sr.get("armour_of_contempt_ap_worsen")
                    if isinstance(spec, dict):
                        bonus = int(spec.get(str(attacker_key), 0) or 0)
                        if bonus:
                            ap_val += bonus
                if isinstance(sr, dict):
                    phase_key = self._resolve_phase_key(attacker_unit=attacker_unit, target_unit=target_root)
                    for entry in self._iter_defensive_entries(
                        target_root,
                        "defensive_ap_worsen_phase",
                        attacker_key=None,
                        attack_type="any",
                        phase_key=phase_key,
                    ):
                        try:
                            ap_val += int(entry.get("value", 0) or 0)
                        except Exception:
                            continue
                    attack_type = "any"
                    try:
                        if self.parent_wargear is not None and self.parent_wargear.is_melee():
                            attack_type = "melee"
                        elif self.parent_wargear is not None and self.parent_wargear.is_ranged():
                            attack_type = "ranged"
                    except Exception:
                        attack_type = "any"
                    for entry in self._iter_defensive_entries(
                        target_root,
                        "defensive_ap_worsen",
                        attacker_key=None,
                        attack_type=attack_type,
                        phase_key="",
                    ):
                        try:
                            ap_val += int(entry.get("value", 0) or 0)
                        except Exception:
                            continue
        except Exception:
            pass
        return int(apply_characteristic_caps("ap", int(ap_val), base_raw=getattr(self, "_raw_ap", None)))

    def _resolve_phase_key(self, attacker_unit: Optional['Unit'] = None, target_unit: Optional['Unit'] = None) -> str:
        try:
            unit = attacker_unit or target_unit
            if unit is None:
                return ""
            army = unit.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None)
            return str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            return ""

    def _iter_defensive_entries(
        self,
        target_unit: Optional['Unit'],
        key: str,
        *,
        attacker_key: Optional[str],
        attack_type: Optional[str],
        phase_key: Optional[str],
    ):
        if target_unit is None:
            return []
        try:
            sr = getattr(target_unit, "special_rules", None)
        except Exception:
            sr = None
        if not isinstance(sr, dict):
            return []
        items = sr.get(key)
        if not isinstance(items, list):
            items = []
        atk_type = str(attack_type or "any").strip().lower()
        phase_key = str(phase_key or "").strip().upper()
        out = []
        for entry in list(items):
            if not isinstance(entry, dict):
                continue
            entry_attack_type = str(entry.get("attack_type") or "any").strip().lower()
            if atk_type and entry_attack_type not in ("any", atk_type):
                continue
            entry_attacker = entry.get("attacker_key")
            if entry_attacker:
                if not attacker_key or str(entry_attacker) != str(attacker_key):
                    continue
            entry_phase = str(entry.get("expires_phase") or "").strip().upper()
            if entry_phase and phase_key and entry_phase != phase_key:
                continue
            req_kw = str(entry.get("requires_leading_keyword", "") or "").strip()
            if req_kw:
                try:
                    root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
                except Exception:
                    root = target_unit
                try:
                    leaders = list(getattr(root, "attached_leaders", []) or [])
                except Exception:
                    leaders = []
                if not leaders:
                    continue
                try:
                    from ..utility.keyword_utils import unit_has_keyword
                except Exception:
                    unit_has_keyword = None
                matched = False
                for leader in leaders:
                    if leader is None:
                        continue
                    try:
                        if unit_has_keyword is not None and unit_has_keyword(leader, req_kw):
                            matched = True
                            break
                        if hasattr(leader, "has_any_keyword") and leader.has_any_keyword(req_kw):
                            matched = True
                            break
                    except Exception:
                        continue
                if not matched:
                    continue
            out.append(entry)
        if key == "defensive_wound_mods":
            try:
                root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
            except Exception:
                root = target_unit
            try:
                leaders = list(getattr(root, "attached_leaders", []) or [])
            except Exception:
                leaders = []
            if leaders:
                try:
                    from ..utility.keyword_utils import unit_has_keyword
                    is_aspect = unit_has_keyword(root, "ASPECT WARRIORS")
                except Exception:
                    is_aspect = False
                if is_aspect:
                    for leader in leaders:
                        sr = getattr(leader, "special_rules", None)
                        if not isinstance(sr, dict):
                            continue
                        if not sr.get("enhancement_shimmerstone"):
                            continue
                        entry_attack_type = "ranged"
                        if atk_type and entry_attack_type not in ("any", atk_type):
                            continue
                        out.append(
                            {
                                "value": 1,
                                "attack_type": entry_attack_type,
                                "source": "Shimmerstone",
                            }
                        )
                        break
            # If no leaders or no enhancement, fall through.
        return out

    def _resolve_attack_count(
        self,
        target: 'Unit',
        attacker: 'Model',
        attack_result: AttackResult,
        *,
        game_map: Optional['Map'] = None,
        closest_dist: float = 0.0,
        attacks_override: Optional[int] = None,
        attacks_override_modifiers: Optional[list[str]] = None,
        attacks_override_note: Optional[str] = None,
        publish_roll_event: bool = True,
        roll_value: Optional[int] = None,
        roll_values: Optional[list[int]] = None,
    ) -> AttackCountInfo:
        if attacks_override is None:
            try:
                weapon_name = ""
                if getattr(self, "parent_wargear", None) is not None:
                    weapon_name = str(getattr(self.parent_wargear, "name", "") or "")
                if not weapon_name:
                    weapon_name = str(getattr(self, "name", "") or "")
                if weapon_name:
                    override_val, override_source = getattr(attacker, "get_temporary_weapon_attacks_override", lambda _n: (0, ""))(
                        weapon_name
                    )
                    if override_val:
                        attacks_override = int(override_val)
                        if not attacks_override_note:
                            label = str(override_source or "").strip()
                            if label:
                                attacks_override_note = f"{label} (Attacks set to {int(override_val)})"
                            else:
                                attacks_override_note = f"Attacks set to {int(override_val)}"
            except Exception:
                pass
        if attacks_override is not None:
            num_attacks = max(0, int(attacks_override))
            attack_result.attacks_rolled = num_attacks
            attack_result.attacks_dice_rolls = []
            if attacks_override_modifiers:
                attack_result.attacks_special_modifiers.extend(list(attacks_override_modifiers))
            if attacks_override_note:
                attack_result.attacks_special_modifiers.append(str(attacks_override_note))
            return AttackCountInfo(
                num_attacks=num_attacks,
                dice_rolls=list(attack_result.attacks_dice_rolls or []),
                special_modifiers=list(attack_result.attacks_special_modifiers or []),
            )

        num_attacks = 0
        if isinstance(self.attacks, Count):
            def _reroll_attacks():
                new_num, new_rolls = self.attacks.resolve_detailed()
                attack_result.attacks_rolled = new_num
                attack_result.attacks_dice_rolls = new_rolls
                return new_num, new_rolls
            if roll_value is not None:
                try:
                    num_attacks = int(roll_value)
                except Exception:
                    num_attacks = 0
                dice_rolls = list(roll_values or [])
            else:
                num_attacks, dice_rolls = self.attacks.resolve_detailed()
            attack_result.attacks_rolled = num_attacks
            attack_result.attacks_dice_rolls = dice_rolls
            if publish_roll_event:
                try:
                    unit = attacker.parent_unit
                    game = unit.get_parent_army().player.game
                    from ..utility.reroll_tracker import prepare_reroll_event
                    roll_id, reroll_cb, reroll_locked = prepare_reroll_event(game, _reroll_attacks)
                    game.event_system.publish(
                        "roll_made",
                        player=unit.get_parent_army().player,
                        unit=unit,
                        roll_type="attacks",
                        value=num_attacks,
                        dice=dice_rolls,
                        reroll=reroll_cb,
                        reroll_locked=bool(reroll_locked),
                        roll_id=roll_id,
                    )
                except Exception:
                    pass
            # Point-blank Devastation: optional reroll of attack dice within half range.
            try:
                if roll_value is None and isinstance(self.attacks, Count) and self.attacks.ctype.name == "DICE":
                    unit = attacker.parent_unit
                    rule = None
                    if unit is not None and hasattr(unit, "get_point_blank_devastation_rule"):
                        rule = unit.get_point_blank_devastation_rule(attacker)
                    if rule and dice_rolls:
                        weapon_name = ""
                        try:
                            if getattr(self, "parent_wargear", None) is not None:
                                weapon_name = str(getattr(self.parent_wargear, "name", "") or "")
                            if not weapon_name:
                                weapon_name = str(getattr(self, "name", "") or "")
                        except Exception:
                            weapon_name = ""
                        weapon_names = list(rule.get("weapon_names", []) or [])
                        if weapon_name and weapon_names and hasattr(unit, "_weapon_name_matches"):
                            if unit._weapon_name_matches(weapon_names, weapon_name):
                                effective_range_max = self._effective_range_max(attacker)
                                if effective_range_max:
                                    within_half_range = float(closest_dist or 0.0) <= (float(effective_range_max) / 2.0)
                                else:
                                    within_half_range = False
                                if within_half_range:
                                    do_reroll = False
                                    game = None
                                    player = None
                                    try:
                                        army = unit.get_parent_army()
                                        player = getattr(army, "player", None) if army is not None else None
                                        game = getattr(player, "game", None) if player is not None else None
                                    except Exception:
                                        game = None
                                        player = None
                                    provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None) if game is not None else None
                                    reason = str(rule.get("source", "") or "Point-blank Devastation").strip() or "Point-blank Devastation"
                                    if provider is not None:
                                        do_reroll = bool(
                                            provider(
                                                player=player,
                                                unit=unit,
                                                roll_type="attacks",
                                                value=num_attacks,
                                                dice=dice_rolls,
                                                reason=reason,
                                            )
                                        )
                                    else:
                                        try:
                                            avg = float(self.attacks.stat_average())
                                            do_reroll = float(num_attacks) < avg
                                        except Exception:
                                            do_reroll = False
                                    if do_reroll:
                                        new_num, new_rolls = self.attacks.resolve_detailed()
                                        num_attacks = new_num
                                        attack_result.attacks_rolled = new_num
                                        attack_result.attacks_dice_rolls = list(new_rolls or [])
                                        attack_result.attacks_special_modifiers.append(
                                            f"{reason}: re-rolled attacks"
                                        )
            except Exception:
                pass
        else:
            num_attacks = self.attacks or 0
            attack_result.attacks_rolled = num_attacks

        from ..utility.modifiers import Modifier, ModifierOp, apply_numeric_modifiers, apply_characteristic_caps
        atk_mods: list[Modifier] = []

        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("enhancement_melee_attacks_bonus", 0) or 0)
                if bonus:
                    atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="enhancement:melee_attacks_add"))
                    attack_result.attacks_special_modifiers.append(f"Enhancement +{bonus}A (melee)")
        except Exception:
            pass
        if self.parent_wargear and self.parent_wargear.is_melee():
            sr = self._unit_special_rules(attacker)
            bearer_bonus = int(sr.get("enhancement_bearer_melee_attacks_bonus", 0) or 0)
            if bearer_bonus and self._attacker_is_enhancement_bearer(attacker, sr):
                exp = str(sr.get("enhancement_bearer_melee_attacks_bonus_expires_phase", "") or "").strip().upper()
                pname = self._current_phase_name(attacker)
                if not exp or (pname and pname == exp):
                    atk_mods.append(
                        Modifier(ModifierOp.ADD, int(bearer_bonus), source="enhancement:bearer_melee_attacks_add")
                    )
                    attack_result.attacks_special_modifiers.append(f"Enhancement bearer +{bearer_bonus}A (melee)")
        try:
            if self.parent_wargear and self.parent_wargear.is_melee() and not self.is_extra_attacks():
                bonus = int(
                    getattr(attacker.parent_unit, "special_rules", {}).get(
                        "enhancement_melee_attacks_bonus_no_extra_attacks", 0
                    )
                    or 0
                )
                if bonus:
                    atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="enhancement:melee_attacks_add_no_extra"))
                    attack_result.attacks_special_modifiers.append(f"Berzerker Glaive +{bonus}A (melee)")
        except Exception:
            pass

        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                bonus = int(getattr(attacker, "get_temporary_melee_attacks_bonus", lambda: 0)() or 0)
                if bonus:
                    atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="ability:temporary_melee_attacks_add"))
                    attack_result.attacks_special_modifiers.append(f"Ability +{bonus}A (melee) [temporary]")
        except Exception:
            pass

        try:
            if self.parent_wargear:
                bonus, reasons = getattr(attacker, "get_temporary_weapon_attacks_bonus", lambda _n: (0, []))(
                    getattr(self.parent_wargear, "name", "")
                )
                if bonus:
                    atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="ability:temporary_weapon_attacks_add"))
                    if reasons:
                        attack_result.attacks_special_modifiers.extend(list(reasons))
                    else:
                        attack_result.attacks_special_modifiers.append(
                            f"Ability +{bonus}A ({getattr(self.parent_wargear, 'name', 'weapon')}) [temporary]"
                        )
        except Exception:
            pass

        try:
            sr = self._unit_special_rules(attacker)
            bonuses = list(sr.get("daemonic_allegiance_weapon_bonuses", []) or []) if isinstance(sr, dict) else []
            if bonuses and self.parent_wargear:
                unit = getattr(attacker, "parent_unit", None)
                weapon_name = str(getattr(self.parent_wargear, "name", "") or getattr(self, "name", "") or "")
                for bonus in bonuses:
                    try:
                        names = list(bonus.get("weapon_names", []) or [])
                    except Exception:
                        names = []
                    if names and unit is not None and hasattr(unit, "_weapon_name_matches"):
                        if not unit._weapon_name_matches(names, weapon_name):
                            continue
                    try:
                        att_bonus = int(bonus.get("attacks_bonus", 0) or 0)
                    except Exception:
                        att_bonus = 0
                    if att_bonus:
                        atk_mods.append(
                            Modifier(ModifierOp.ADD, int(att_bonus), source="daemonic_allegiance:weapon_attacks_add")
                        )
                        source = str(bonus.get("source", "") or "Daemonic Allegiance").strip() or "Daemonic Allegiance"
                        attack_result.attacks_special_modifiers.append(f"{source} +{att_bonus}A ({weapon_name})")
        except Exception:
            pass

        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                unit = getattr(attacker, "parent_unit", None)
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "waaagh", None) if army is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr is not None and mgr.unit_is_affected(unit, game=game):
                    atk_mods.append(Modifier(ModifierOp.ADD, 1, source="ability:waaagh_melee_attacks_add"))
                    attack_result.attacks_special_modifiers.append("Waaagh! +1A (melee)")
        except Exception:
            pass

        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("relentless_rage_melee_attacks_bonus", 0) or 0)
                if bonus:
                    atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="detachment:relentless_rage_attacks"))
                    attack_result.attacks_special_modifiers.append(f"Relentless Rage +{bonus}A (melee)")
        except Exception:
            pass

        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("maddened_ferocity_melee_attacks_bonus", 0) or 0)
                if bonus:
                    atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="detachment:maddened_ferocity_attacks"))
                    attack_result.attacks_special_modifiers.append(f"Maddened Ferocity +{bonus}A (melee)")
        except Exception:
            pass

        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                sr = getattr(attacker.parent_unit, "special_rules", {}) or {}
                bonus = int(sr.get("peerless_warrior_melee_attacks_bonus", 0) or 0)
                if bonus:
                    exp = str(sr.get("peerless_warrior_expires_phase", "") or "").strip().upper()
                    pname = self._current_phase_name(attacker)
                    if not exp or (pname and pname == exp):
                        atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="stratagem:peerless_warrior_attacks"))
                        attack_result.attacks_special_modifiers.append(f"Peerless Warrior +{bonus}A (melee)")
        except Exception:
            pass

        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("pain_melee_attacks_bonus", 0) or 0)
                if bonus:
                    atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="power_from_pain:melee_attacks_add"))
                    attack_result.attacks_special_modifiers.append(f"Power from Pain +{bonus}A (melee)")
        except Exception:
            pass

        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                unit = getattr(attacker, "parent_unit", None)
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
                if mgr is not None:
                    game = getattr(getattr(army, "player", None), "game", None)
                    keys = mgr.get_active_combat_drug_keys_for_model(attacker, game=game)
                    if "ADRENALIGHT" in keys:
                        atk_mods.append(Modifier(ModifierOp.ADD, 1, source="combat_drugs:adrenalight_attacks"))
                        attack_result.attacks_special_modifiers.append("Combat Drugs: Adrenalight +1A (melee)")
        except Exception:
            pass

        try:
            if self.parent_wargear and self.parent_wargear.is_melee() and not bool(getattr(attacker, "is_character", False)):
                set_val = int(getattr(attacker.parent_unit, "special_rules", {}).get("pain_melee_attacks_set_non_character", 0) or 0)
                if set_val:
                    atk_mods.append(Modifier(ModifierOp.SET, int(set_val), source="power_from_pain:melee_attacks_set"))
                    attack_result.attacks_special_modifiers.append(f"Power from Pain set Attacks {set_val} (non-character melee)")
        except Exception:
            pass

        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("damaged_melee_attacks_bonus", 0) or 0)
                if bonus:
                    atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="damaged_profile:melee_attacks_add"))
                    attack_result.attacks_special_modifiers.append(f"Damaged profile +{bonus}A (melee)")
        except Exception:
            pass

        try:
            from ..utility.aura_effects import get_aura_melee_attacks_bonus
            aura_a, aura_reasons = get_aura_melee_attacks_bonus(attacker.parent_unit, self, game_map=game_map)
            if aura_a:
                atk_mods.append(Modifier(ModifierOp.ADD, int(aura_a), source="aura:melee_attacks_add"))
                attack_result.attacks_special_modifiers.extend(list(aura_reasons or ()))
        except Exception:
            pass

        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                unit = getattr(attacker, "parent_unit", None)
                if unit is not None and getattr(unit, "get_two_melee_weapons_bonus", None):
                    bonus, bonus_wargear = unit.get_two_melee_weapons_bonus(attacker)
                    if bonus and bonus_wargear and self.parent_wargear in bonus_wargear:
                        atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="ability:two_melee_weapons_attacks_add"))
                        attack_result.attacks_special_modifiers.append(f"Two melee weapons +{bonus}A")
        except Exception:
            pass

        # Dead Choppy: +1 Attacks for each additional dread klaw equipped.
        if self.is_dead_choppy():
            dread_klaw_count = 0
            model_wargear = getattr(attacker, "wargear", []) or []
            for wg in model_wargear:
                wg_name = str(getattr(wg, "name", "") or "").strip().lower()
                if "dread klaw" in wg_name:
                    dread_klaw_count += 1

            if dread_klaw_count > 1:
                bonus = dread_klaw_count - 1
                atk_mods.append(Modifier(ModifierOp.ADD, int(bonus), source="weapon:dead_choppy"))
                attack_result.attacks_special_modifiers.append(
                    f"Dead Choppy +{bonus}A ({dread_klaw_count} dread klaws)"
                )

        try:
            wname = str(getattr(attacker.parent_unit, "special_rules", {}).get("damaged_attacks_bonus_weapon_name", "") or "").strip().lower()
            amt = int(getattr(attacker.parent_unit, "special_rules", {}).get("damaged_attacks_bonus_weapon_amount", 0) or 0)
            if wname and amt:
                parent_name = str(getattr(getattr(self, "parent_wargear", None), "name", "") or "").strip().lower()
                if parent_name and (parent_name == wname or wname in parent_name or parent_name in wname):
                    atk_mods.append(Modifier(ModifierOp.ADD, int(amt), source=f"damaged_profile:weapon_attacks_add:{wname}"))
                    attack_result.attacks_special_modifiers.append(f"Damaged profile +{amt}A ({wname})")
        except Exception:
            pass

        try:
            if bool(getattr(attacker.parent_unit, "special_rules", {}).get("damaged_half_attacks", False)):
                atk_mods.append(Modifier(ModifierOp.DIV, 2, source="damaged_profile:halve_attacks"))
                attack_result.attacks_special_modifiers.append("Damaged profile: halve Attacks")
        except Exception:
            pass

        effective_range_max = self._effective_range_max(attacker)
        try:
            half_range = float(effective_range_max) / 2.0
        except Exception:
            half_range = float(getattr(self.range, "max", 0) or 0) / 2.0

        applied_pain_rapid_fire = False
        try:
            sr = getattr(attacker.parent_unit, "special_rules", None)
            bonuses = dict(sr.get("pain_rapid_fire_weapon_bonus", {}) or {}) if isinstance(sr, dict) else {}
            if bonuses and self.parent_wargear and self.parent_wargear.is_ranged() and closest_dist <= half_range:
                parent_name = str(getattr(self.parent_wargear, "name", "") or "").strip().lower()
                matched = None
                for key, val in bonuses.items():
                    key_norm = str(key or "").strip().lower()
                    if key_norm and key_norm in parent_name:
                        matched = (key_norm, int(val or 0))
                        break
                if matched and matched[1]:
                    attack_result.attacks_special_modifiers.append(f"Power from Pain Rapid Fire +{matched[1]} ({matched[0]})")
                    atk_mods.append(Modifier(ModifierOp.ADD, int(matched[1]), source="power_from_pain:rapid_fire"))
                    applied_pain_rapid_fire = True
        except Exception:
            applied_pain_rapid_fire = False

        if (not applied_pain_rapid_fire) and closest_dist <= half_range and self.is_rapid_fire():
            try:
                rf = self.get_rapid_fire_bonus()
                rf_bonus = int(rf.resolve())
                attack_result.attacks_special_modifiers.append(f"Rapid Fire +{rf_bonus} ({rf})")
                atk_mods.append(Modifier(ModifierOp.ADD, int(rf_bonus), source="weapon:rapid_fire"))
            except Exception as exc:
                print(f"WARN: Rapid Fire bonus parsing failed for {self.name}: {exc}")

        try:
            sr = getattr(attacker.parent_unit, "special_rules", None)
            order_key = str(sr.get("voice_of_command_order_key", "") or "") if isinstance(sr, dict) else ""
            if order_key == "FIRST_RANK_FIRE" and self.is_rapid_fire():
                attack_result.attacks_special_modifiers.append("First Rank, Fire! Second Rank, Fire! +1A")
                atk_mods.append(Modifier(ModifierOp.ADD, 1, source="voice_of_command:first_rank_fire"))
        except Exception:
            pass

        if self.is_blast():
            try:
                target_model_count = len(target.models)
            except Exception:
                target_model_count = 0
            num_attacks_modifier = int(target_model_count / 5)
            attack_result.attacks_special_modifiers.append(f"Blast +{num_attacks_modifier}")
            atk_mods.append(Modifier(ModifierOp.ADD, int(num_attacks_modifier), source="weapon:blast"))

        num_attacks, _dbg = apply_numeric_modifiers(int(num_attacks), atk_mods, base_raw=getattr(self, "_raw_attacks", None))
        num_attacks = apply_characteristic_caps("attacks", int(num_attacks), base_raw=getattr(self, "_raw_attacks", None))
        try:
            attack_result.attacks_rolled = int(num_attacks)
        except Exception:
            pass

        return AttackCountInfo(
            num_attacks=int(num_attacks),
            dice_rolls=list(attack_result.attacks_dice_rolls or []),
            special_modifiers=list(attack_result.attacks_special_modifiers or []),
        )

    def preview_attack_count(
        self,
        target: 'Unit',
        attacker: 'Model',
        *,
        game_map: Optional['Map'] = None,
        publish_roll_event: bool = True,
    ) -> AttackCountInfo:
        weapon_display_name = self.name
        if hasattr(self, 'parent_wargear') and self.parent_wargear:
            if self.name == 'default':
                weapon_display_name = self.parent_wargear.name
            else:
                weapon_display_name = f"{self.parent_wargear.name} - {self.name}"
        attack_result = AttackResult(
            weapon_name=weapon_display_name,
            attacker_name=getattr(attacker, "name", "Attacker"),
            target_unit_name=getattr(target, "name", "Target"),
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
        closest_dist = 0.0
        try:
            _closest_target, closest_dist = attacker.return_closest_model_in_unit(target)
        except Exception:
            closest_dist = 0.0

        # Apply Psychic Assassin override for preview if applicable
        attacks_override = None
        attacks_override_note = None
        try:
            if self.is_psychic_assassin() and target.has_any_keyword("PSYKER"):
                attacks_override = 6
                attacks_override_note = "Psychic Assassin"
        except Exception:
            pass

        return self._resolve_attack_count(
            target,
            attacker,
            attack_result,
            game_map=game_map,
            closest_dist=float(closest_dist),
            attacks_override=attacks_override,
            attacks_override_note=attacks_override_note,
            publish_roll_event=bool(publish_roll_event),
        )

    def attack(
        self,
        target: 'Unit',
        attacker: 'Model',
        game_map: Optional['Map'] = None,
        *,
        attack_context: Optional[Dict] = None,
        attacks_override: Optional[int] = None,
        attacks_override_modifiers: Optional[list[str]] = None,
        attacks_override_note: Optional[str] = None,
    ) -> Optional[AttackResult]:
        # ONE SHOT: enforce once per battle per model per weapon (guard before queuing).
        try:
            if self.is_one_shot():
                key = self.one_shot_key()
                used = getattr(attacker, "_one_shot_used", set())
                if key and key in used:
                    try:
                        wname = getattr(getattr(self, "parent_wargear", None), "name", None) or getattr(self, "name", "Weapon")
                        print(f"WARN: ONE SHOT already used for {attacker.name}: {wname}")
                    except Exception:
                        pass
                    return
        except Exception:
            pass

        # Interactive dice roll mode: defer to attack manager.
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None and hasattr(unit, "get_parent_army") else None
            player = getattr(army, "player", None) if army is not None else None
            game = getattr(player, "game", None) if player is not None else None
            if game is not None and not bool(getattr(game, "auto_resolve_dice_rolls", True)):
                mgr = getattr(game, "attack_manager", None)
                if mgr is not None:
                    mgr.queue_attack_declarations(
                        game,
                        [
                            {
                                "weapon_profile": self,
                                "target_unit": target,
                                "models": [attacker],
                                "attacks_override": attacks_override,
                                "attacks_override_modifiers": attacks_override_modifiers,
                                "attacks_override_note": attacks_override_note,
                            }
                        ],
                        out_of_phase=False,
                    )
                    # ONE SHOT: mark expended once queued.
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
                    return None
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

        local_context = False
        if not isinstance(attack_context, dict):
            attack_context = {}
            local_context = True
        pending_mortal_by_target = attack_context.setdefault("pending_mortal_wounds", {})
        defer_mortals = bool(attack_context.get("defer_mortal_wounds", True))
        
        wound_instances = []
        hit_instances = []
        num_attacks = 0
        attacker_unit = getattr(attacker, "parent_unit", None)
        attacker_key = None
        try:
            if attacker_unit is not None:
                attacker_root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
                attacker_key = get_entity_id(attacker_root)
        except Exception:
            attacker_key = None

        # INDIRECT FIRE (penalty only if no models in target unit are visible to attacking unit at selection time)
        indirect_fire_no_visible = False
        try:
            if self.is_indirect_fire() and game_map is not None:
                attacker_unit = attacker.parent_unit
                if hasattr(attacker_unit, "_attacking_unit_has_any_los_to_target_unit"):
                    indirect_fire_no_visible = not attacker_unit._attacking_unit_has_any_los_to_target_unit(target, game_map)
        except Exception:
            indirect_fire_no_visible = False

        # TORRENT cannot be used "via Indirect Fire" when no target models are visible at selection time.
        # This should normally be prevented at target selection; keep a safety-net here too.
        if indirect_fire_no_visible and self.is_torrent():
            attack_result.attacks_special_modifiers.append("Torrent cannot be used via Indirect Fire (no target models visible)")
            attack_result.attacks_rolled = 0
            return attack_result
        closest_dist = 0.0
        try:
            _closest_target, closest_dist = attacker.return_closest_model_in_unit(target)
        except Exception:
            closest_dist = 0.0

        attack_count_info = self._resolve_attack_count(
            target,
            attacker,
            attack_result,
            game_map=game_map,
            closest_dist=float(closest_dist),
            attacks_override=attacks_override,
            attacks_override_modifiers=attacks_override_modifiers,
            attacks_override_note=attacks_override_note,
        )
        num_attacks = int(attack_count_info.num_attacks)

        furious_onslaught_applies = False
        try:
            is_ranged = bool(getattr(getattr(self, "parent_wargear", None), "is_ranged", lambda: False)())
            if is_ranged:
                unit = getattr(attacker, "parent_unit", None)
                if unit is not None and getattr(unit, "has_furious_onslaught", None):
                    if unit.has_furious_onslaught(attacker):
                        gm = game_map
                        if gm is None:
                            try:
                                gm = unit.get_parent_army().player.game.map
                            except Exception:
                                gm = None
                        if gm is not None and getattr(unit, "is_target_closest_eligible", None):
                            furious_onslaught_applies = bool(
                                unit.is_target_closest_eligible(attacker, self, target, gm, max_distance=18.0)
                            )
        except Exception:
            furious_onslaught_applies = False
        closest_enemy_hit_reroll_rule = None
        try:
            is_ranged = bool(getattr(getattr(self, "parent_wargear", None), "is_ranged", lambda: False)())
            if is_ranged:
                unit = getattr(attacker, "parent_unit", None)
                if unit is not None and getattr(unit, "get_closest_enemy_hit_reroll_rule", None):
                    rule = unit.get_closest_enemy_hit_reroll_rule(attacker)
                    if rule:
                        gm = game_map
                        if gm is None:
                            try:
                                gm = unit.get_parent_army().player.game.map
                            except Exception:
                                gm = None
                        if gm is not None and getattr(unit, "is_target_closest_eligible", None):
                            if unit.is_target_closest_eligible(attacker, self, target, gm):
                                closest_enemy_hit_reroll_rule = rule
        except Exception:
            closest_enemy_hit_reroll_rule = None
        closest_monster_vehicle_rule = None
        try:
            is_ranged = bool(getattr(getattr(self, "parent_wargear", None), "is_ranged", lambda: False)())
            if is_ranged:
                unit = getattr(attacker, "parent_unit", None)
                if unit is not None and getattr(unit, "get_closest_monster_vehicle_reroll_rule", None):
                    rule = unit.get_closest_monster_vehicle_reroll_rule(attacker)
                    if rule:
                        gm = game_map
                        if gm is None:
                            try:
                                gm = unit.get_parent_army().player.game.map
                            except Exception:
                                gm = None
                        if gm is not None and getattr(unit, "is_target_closest_eligible", None):
                            max_dist = None
                            try:
                                max_dist = int(rule.get("range", 0) or 0)
                            except Exception:
                                max_dist = None
                            closest_monster_vehicle_rule = None
                            if max_dist:
                                if unit.is_target_closest_eligible(
                                    attacker,
                                    self,
                                    target,
                                    gm,
                                    max_distance=float(max_dist),
                                    require_keywords={"monster", "vehicle"},
                                ):
                                    closest_monster_vehicle_rule = rule
        except Exception:
            closest_monster_vehicle_rule = None
        monster_vehicle_reroll_rule = None
        try:
            is_ranged = bool(getattr(getattr(self, "parent_wargear", None), "is_ranged", lambda: False)())
            if is_ranged:
                unit = getattr(attacker, "parent_unit", None)
                if unit is not None and getattr(unit, "get_monster_vehicle_reroll_rule", None):
                    rule = unit.get_monster_vehicle_reroll_rule(attacker)
                    if rule:
                        target_ok = False
                        try:
                            target_ok = bool(target.has_keyword("MONSTER") or target.has_keyword("VEHICLE"))
                        except Exception:
                            try:
                                target_ok = bool(target.has_any_keyword("MONSTER") or target.has_any_keyword("VEHICLE"))
                            except Exception:
                                target_ok = False
                        if target_ok:
                            if rule.get("requires_shooting_phase"):
                                game = None
                                try:
                                    game = unit.get_parent_army().player.game
                                except Exception:
                                    game = None
                                if game is None or not bool(getattr(game, "is_shooting_phase", lambda: False)()):
                                    rule = None
                                else:
                                    try:
                                        if game.get_current_player() is not unit.get_parent_army().player:
                                            rule = None
                                    except Exception:
                                        rule = None
                            if rule:
                                monster_vehicle_reroll_rule = rule
        except Exception:
            monster_vehicle_reroll_rule = None

        # Apply AP modifiers that depend on attacker/target context (e.g., Plunging Fire)
        effective_ap = self.get_effective_ap(attacker, target)
        cabal_ap_bonus = self._cabal_twist_of_fate_ap_bonus(attacker, target)
        try:
            base_ap = int(self.ap)
        except Exception:
            base_ap = effective_ap
        if self.parent_wargear and self.parent_wargear.is_melee():
            from ..utility.aura_effects import get_aura_melee_ap_bonus
            aura_ap, aura_reasons = get_aura_melee_ap_bonus(getattr(attacker, "parent_unit", None), self, game_map=game_map)
            if aura_ap:
                attack_result.attacks_special_modifiers.extend(list(aura_reasons or ()))
        if effective_ap == (base_ap - 1):
            attack_result.attacks_special_modifiers.append("Plunging Fire (AP improved by 1)")
        if cabal_ap_bonus:
            attack_result.attacks_special_modifiers.append(
                f"Twist of Fate (AP improved by {int(cabal_ap_bonus)})"
            )
        sonic_bonus = 0
        try:
            unit = getattr(attacker, "parent_unit", None)
            if unit is not None and hasattr(unit, "get_sonic_destruction_bonus"):
                weapon_name = ""
                try:
                    if getattr(self, "parent_wargear", None) is not None:
                        weapon_name = str(getattr(self.parent_wargear, "name", "") or "")
                    if not weapon_name:
                        weapon_name = str(getattr(self, "name", "") or "")
                except Exception:
                    weapon_name = ""
                sonic_bonus = int(
                    unit.get_sonic_destruction_bonus(
                        model=attacker,
                        target=target,
                        weapon_profile=self,
                        weapon_name=weapon_name,
                    ) or 0
                )
        except Exception:
            sonic_bonus = 0
        if sonic_bonus:
            effective_ap = int(effective_ap) - int(sonic_bonus)
            attack_result.attacks_special_modifiers.append(
                f"Sonic Destruction (+{int(sonic_bonus)} S/AP/D)"
            )

        # CONVERSION: Determine if Conversion is active for this attack sequence
        # Conversion grants critical hits on unmodified successful hit rolls of 4+
        # when the target is more than a specified distance (12"/18"/24") from the bearer
        conversion_active = False
        conversion_distance_threshold = 0.0
        if self.is_conversion():
            conversion_distance_threshold = self.get_conversion_distance(attacker)
            # Strict greater-than check per rules ("more than X")
            conversion_active = closest_dist > conversion_distance_threshold
            if conversion_active:
                attack_result.attacks_special_modifiers.append(
                    f"Conversion active (target >{conversion_distance_threshold}\")"
                )

        effective_range_max = self._effective_range_max(attacker)
        try:
            half_range = float(effective_range_max) / 2.0
        except Exception:
            half_range = float(getattr(self.range, "max", 0) or 0) / 2.0

        # Imperial Agents Kill Team: majority Toughness (tie -> highest) for the attack sequence.
        kill_team_toughness = None
        try:
            root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
            has_kill_team = bool(getattr(root, "attached_unit_has_kill_team", lambda: False)())
            if has_kill_team and hasattr(root, "get_kill_team_majority_toughness"):
                kt = root.get_kill_team_majority_toughness()
                if kt is not None:
                    kill_team_toughness = int(kt)
                    attack_result.attacks_special_modifiers.append(
                        f"Kill Team majority Toughness {kill_team_toughness}"
                    )
        except Exception:
            kill_team_toughness = None

        # Process each attack
        for attack_num in range(num_attacks):
            attack_instance = {
                'crit_hit': False,
                'crit_wound': False,
                'mortal_wound': False,
                'below_half_distance': closest_dist <= half_range,
                'damage': 0,
                'target_toughness_override': kill_team_toughness,
                'conversion_active': conversion_active,
                'distance_to_target': closest_dist,
            }
            if sonic_bonus:
                attack_instance["sonic_destruction_bonus"] = int(sonic_bonus)
            if attacker_unit is not None:
                attack_instance["attacker_unit"] = attacker_unit
            if attacker_key is not None:
                attack_instance["attacker_key"] = attacker_key
            if furious_onslaught_applies:
                attack_instance["furious_onslaught_applies"] = True
            if closest_enemy_hit_reroll_rule:
                attack_instance["closest_enemy_hit_reroll_rule"] = closest_enemy_hit_reroll_rule
            if closest_monster_vehicle_rule:
                attack_instance["closest_monster_vehicle_reroll_rule"] = closest_monster_vehicle_rule
            if monster_vehicle_reroll_rule:
                attack_instance["monster_vehicle_reroll_rule"] = monster_vehicle_reroll_rule

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
                            'damage': 0,
                            'target_toughness_override': kill_team_toughness,
                        }
                        if sonic_bonus:
                            extra_instance["sonic_destruction_bonus"] = int(sonic_bonus)
                        if attacker_unit is not None:
                            extra_instance["attacker_unit"] = attacker_unit
                        if attacker_key is not None:
                            extra_instance["attacker_key"] = attacker_key
                        if furious_onslaught_applies:
                            extra_instance["furious_onslaught_applies"] = True
                        if closest_enemy_hit_reroll_rule:
                            extra_instance["closest_enemy_hit_reroll_rule"] = closest_enemy_hit_reroll_rule
                        if closest_monster_vehicle_rule:
                            extra_instance["closest_monster_vehicle_reroll_rule"] = closest_monster_vehicle_rule
                        if monster_vehicle_reroll_rule:
                            extra_instance["monster_vehicle_reroll_rule"] = monster_vehicle_reroll_rule
                        hit_instances.append(extra_instance)
                        attack_result.total_hits += 1

        # Process wound rolls
        for hit_instance in hit_instances:
            wound_result = self._wound_target_with_tracking(target, attacker, hit_instance)
            attack_result.wound_results.append(wound_result)
            
            if wound_result['wound']:
                wound_instances.append(hit_instance)
                attack_result.total_wounds += 1

        # Process saves and damage.
        #
        # Core rule: resolve all normal damage first; mortal wounds from attacks are applied after.
        for wound_instance in wound_instances:
            # PRECISION (10e): after a successful wound vs an Attached Unit, attacker may allocate
            # the wound to a visible CHARACTER model in that unit.
            target_model = None
            # EPIC CHALLENGE: selected CHARACTER model's melee attacks gain [PRECISION] until end of phase.
            precision_from_epic_challenge = False
            try:
                sr = getattr(attacker, "special_rules", None)
                if isinstance(sr, dict) and sr.get("epic_challenge_precision_active") is True:
                    parent = getattr(self, "parent_wargear", None)
                    if parent is not None and callable(getattr(parent, "is_melee", None)) and parent.is_melee():
                        precision_from_epic_challenge = True
            except Exception:
                precision_from_epic_challenge = False

            precision_from_templar_vows = False
            try:
                parent = getattr(self, "parent_wargear", None)
                if parent is not None and callable(getattr(parent, "is_melee", None)) and parent.is_melee():
                    army = attacker.parent_unit.get_parent_army()
                    mgr = getattr(army, "templar_vows", None) if army is not None else None
                    if mgr is not None and mgr.melee_precision_against(attacker.parent_unit, target):
                        precision_from_templar_vows = True
            except Exception:
                precision_from_templar_vows = False

            precision_from_assassins = False
            try:
                precision_from_assassins = bool(self._assassins_poisons_applies(attacker))
            except Exception:
                precision_from_assassins = False

            bonus_precision = bool(wound_instance.get("bonus_precision"))
            if (self.is_precision() or precision_from_epic_challenge or precision_from_templar_vows or precision_from_assassins or bonus_precision) and game_map is not None:
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
                            if not bool(getattr(m, "is_character", False)):
                                continue
                            # Visibility requirement
                            if hasattr(game_map, "can_model_see_model") and callable(getattr(game_map, "can_model_see_model")):
                                if not game_map.can_model_see_model(attacker, m):
                                    continue
                            char_models.append(m)
                        except Exception:
                            continue

                    if char_models:
                        # Deterministic default: pick the first visible CHARACTER model.
                        precision_choice_model = char_models[0]
                        try:
                            if getattr(precision_choice_model, "is_alive", True):
                                if hasattr(game_map, "can_model_see_model") and callable(getattr(game_map, "can_model_see_model")):
                                    if game_map.can_model_see_model(attacker, precision_choice_model):
                                        target_model = precision_choice_model
                                else:
                                    target_model = precision_choice_model
                        except Exception:
                            target_model = None

            # Default allocation if precision didn't override it
            if target_model is None:
                target_model = self.opponent_wound_allocation(target, attacker=attacker, game_map=game_map)
            if target_model is None:
                continue
            wound_instance["_allocated_model"] = target_model

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
            is_mortal_only = bool(wound_instance.get("mortal_wound", False)) and not bool(
                wound_instance.get("mortal_wound_in_addition", False)
            )
            is_mortal_additional = bool(wound_instance.get("mortal_wound_in_addition", False))

            if not is_mortal_only:
                save_result = self._save_with_tracking(target_model, wound_instance, effective_ap)
                attack_result.save_results.append(save_result)
            
            # Apply damage if save failed or mortal wound
            if save_result and not save_result.get('saved'):
                attack_result.total_saves_failed += 1
                damage_result = self._damage_target_with_tracking(
                    target_model, attacker, wound_instance, game_map=game_map
                )
                self._record_damage_result(attack_result, damage_result)

            if is_mortal_only or is_mortal_additional:
                amount = 0
                if is_mortal_additional:
                    amount = self._resolve_mortal_wound_amount(wound_instance.get("mortal_wound_amount"))
                    if amount <= 0:
                        try:
                            wname = getattr(getattr(self, "parent_wargear", None), "name", None) or getattr(self, "name", "Weapon")
                            print(f"WARN: {wname} mortal_wound_in_addition set without amount")
                        except Exception:
                            pass
                if is_mortal_only or amount > 0:
                    target_key = self._pending_mortal_target_key(target)
                    pending_mortal_by_target.setdefault(target_key, []).append(
                        {
                            "weapon_profile": self,
                            "attacker": attacker,
                            "target_unit": target,
                            "target_model": target_model,
                            "attack_instance": wound_instance,
                            "attack_result": attack_result,
                            "no_spill": bool(is_mortal_only),
                            "mortal_wound_amount": int(amount),
                        }
                    )

        if local_context or not defer_mortals:
            self.resolve_pending_mortal_wounds_for_target(
                pending_mortal_by_target, target, game_map=game_map
            )
        
        # Handle hazardous weapon effects
        hazardous_active = self.is_hazardous()
        sr = getattr(getattr(attacker, "parent_unit", None), "special_rules", None)
        if isinstance(sr, dict) and sr.get("pain_melee_hazardous_non_character"):
            if self.parent_wargear and self.parent_wargear.is_melee() and not bool(getattr(attacker, "is_character", False)):
                hazardous_active = True
        target_melee_hazardous = False
        if self.parent_wargear and self.parent_wargear.is_melee():
            target_root = target.get_attached_unit_root() if (target is not None and hasattr(target, "get_attached_unit_root")) else target
            fn = getattr(target_root, "enemy_melee_weapons_hazardous_while_targeted", None) if target_root is not None else None
            if callable(fn):
                target_melee_hazardous = bool(fn())
        if target_melee_hazardous:
            hazardous_active = True
        if hazardous_active:
            # Provide reroll callback for hazardous test
            def _reroll_hazard():
                new_roll = get_roll("D6")
                try:
                    append_dice(attacker.parent_unit.get_parent_army().player, f"Hazardous re-roll: {new_roll} for {attacker.name}")
                except Exception:
                    pass
                return new_roll
            hazard_roll = get_roll("D6")
            attack_result.hazardous_roll = hazard_roll
            # Publish roll_made for hazardous test
            try:
                unit = attacker.parent_unit
                game = unit.get_parent_army().player.game
                from ..utility.reroll_tracker import prepare_reroll_event
                roll_id, reroll_cb, reroll_locked = prepare_reroll_event(game, _reroll_hazard)
                game.event_system.publish(
                    "roll_made",
                    player=unit.get_parent_army().player,
                    unit=unit,
                    roll_type="hazardous",
                    value=hazard_roll,
                    reroll=reroll_cb,
                    reroll_locked=bool(reroll_locked),
                    roll_id=roll_id,
                )
            except Exception:
                pass
            if is_hazardous_failure(self, hazard_roll):
                attack_result.hazardous_damage = 3
                # 10e: For each failed test, select an eligible model in that unit equipped with one or more Hazardous weapons.
                # Priority: wounded eligible; otherwise non-Character eligible; otherwise eligible Character.
                from ..utility.damage_allocation import DamageAllocationCtx, choose_hazardous_failure_model
                try:
                    root_unit = attacker.parent_unit.get_attached_unit_root()
                except Exception:
                    root_unit = attacker.parent_unit
                # Eligible models: alive models in the (attached) unit equipped with >=1 Hazardous weapon
                root_sr = getattr(root_unit, "special_rules", None)
                pain_hazardous = isinstance(root_sr, dict) and root_sr.get("pain_melee_hazardous_non_character")
                try:
                    from ..utility.hazardous import collect_hazardous_eligible_models
                    eligible = collect_hazardous_eligible_models(
                        root_unit,
                        include_melee_non_character=bool(pain_hazardous),
                        include_melee_all=bool(target_melee_hazardous),
                    )
                except Exception:
                    eligible = []

                # If somehow no eligible model found, fall back to the attacker model.
                if not eligible:
                    eligible = [attacker]

                chosen = choose_hazardous_failure_model(
                    root_unit,
                    eligible,
                    ctx=DamageAllocationCtx(reason="HAZARDOUS failed test - select model", damage_source="hazardous"),
                )
                if chosen is None:
                    chosen = eligible[0]
                chosen.take_damage(3, is_mortal=True, weapon_profile=self, game_map=game_map, damage_source="hazardous")
        
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

        # Optional hit tracking hook for melee or custom attack contexts.
        try:
            hit_tracker = attack_context.get("hit_tracker")
            hit_models_by_target = attack_context.get("hit_models_by_target")
        except Exception:
            hit_tracker = None
            hit_models_by_target = None
        if hit_tracker is not None:
            try:
                hits = int(getattr(attack_result, "total_hits", 0) or 0)
            except Exception:
                hits = 0
            if hits > 0:
                hit_tracker[target] = int(hit_tracker.get(target, 0) or 0) + hits
                if hit_models_by_target is not None:
                    try:
                        hit_models_by_target.setdefault(target, set()).add(attacker)
                    except Exception:
                        pass
        
        return attack_result

    def _leading_unmodified_six_phase_key(self, unit: Optional['Unit'], game: Optional[object]) -> str:
        if game is None and unit is not None:
            try:
                game = getattr(getattr(unit.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            phase = getattr(game, "phase", None)
            pname = str(getattr(phase, "name", "") or phase or "").strip().upper()
        except Exception:
            pname = ""
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        if current_player is None and unit is not None:
            try:
                current_player = getattr(unit.get_parent_army(), "player", None)
            except Exception:
                current_player = None
        owner = str(getattr(current_player, "id", "") or getattr(current_player, "name", "") or "")
        return f"{br}:{pname}:{owner}"

    def _maybe_apply_leading_unmodified_six(
        self,
        attacker: 'Model',
        target: 'Unit',
        roll_type: str,
        roll_value: Optional[int],
        needed: Optional[int] = None,
    ) -> tuple[Optional[int], Optional[str]]:
        """
        Leading ability: once per phase, set one hit/wound/damage roll for the unit to an unmodified 6.
        Returns (new_roll_value, decision_str) where decision_str is ability_key or "skip".
        """
        try:
            if roll_value is None:
                return roll_value, None
            if int(roll_value) == 6:
                return roll_value, None
        except Exception:
            return roll_value, None

        unit = getattr(attacker, "parent_unit", None)
        if unit is None:
            return roll_value, None
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit

        try:
            specs = list(getattr(root, "leading_unmodified_six_specs", lambda: [])() or [])
        except Exception:
            specs = []
        if not specs:
            return roll_value, None

        is_support_weapon_model = False
        try:
            is_support_weapon_model = bool(unit.has_support_weapon_ability())
        except Exception:
            is_support_weapon_model = False

        player = None
        game_map = None
        is_human = False
        provider = None
        game = None
        try:
            army = root.get_parent_army()
            player = getattr(army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
            game_map = getattr(game, "map", None) if game is not None else None
            is_human = bool(getattr(player, "has_control", lambda: False)())
            provider = getattr(game_map, "leading_unmodified_six_provider", None) if game_map is not None else None
        except Exception:
            player = None
            game_map = None
            game = None
            is_human = False
            provider = None

        phase_key = self._leading_unmodified_six_phase_key(root, game)
        available: list[dict] = []
        for spec in list(specs or []):
            try:
                if spec.get("exclude_support_weapon") and is_support_weapon_model:
                    continue
            except Exception:
                pass
            leader = spec.get("leader")
            ability_key = str(spec.get("ability_key", "") or "")
            if leader is None or not ability_key:
                continue
            try:
                sr = getattr(leader, "special_rules", None)
            except Exception:
                sr = None
            if not isinstance(sr, dict):
                sr = {}
            used_map = sr.get("leading_unmodified_six_used_phase_key", {})
            if isinstance(used_map, dict) and str(used_map.get(ability_key, "")) == str(phase_key):
                continue
            available.append(spec)

        if not available:
            return roll_value, None

        # Deterministic ordering for options.
        def _spec_sort_key(item: dict) -> tuple:
            return (
                str(item.get("ability_key", "")),
                str(item.get("leader_id", "")),
                str(item.get("source", "")),
            )

        available = sorted(available, key=_spec_sort_key)
        option_entries = []
        for spec in available:
            leader_name = ""
            try:
                leader_name = str(getattr(spec.get("leader"), "name", "") or "")
            except Exception:
                leader_name = ""
            source = str(spec.get("source", "") or "").strip()
            if leader_name and source and leader_name != source:
                label = f"{source} ({leader_name})"
            else:
                label = source or leader_name or "Leading ability"
            option_entries.append(
                {
                    "ability_key": str(spec.get("ability_key", "") or ""),
                    "label": label,
                    "leader_id": str(spec.get("leader_id", "") or ""),
                    "source": source or "Leading ability",
                }
            )

        decision = None
        if is_human and callable(provider):
            try:
                decision = provider(
                    player=player,
                    unit=root,
                    roll_type=str(roll_type or ""),
                    value=int(roll_value),
                    needed=needed,
                    options=option_entries,
                    attacker=attacker,
                    target=target,
                    weapon_name=getattr(getattr(self, "parent_wargear", None), "name", None)
                    or getattr(self, "name", "Weapon"),
                )
            except Exception:
                decision = None
        else:
            decision = None
            if game is not None and player is not None:
                try:
                    from warhammer40k_ai.engine.decision_kinds import DECISION_USE_LEADING_UNMODIFIED_SIX
                    from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
                    from warhammer40k_ai.utility.decision_utils import resolve_decision_value
                    from warhammer40k_ai.utility.entity_ids import get_entity_id
                except Exception:
                    decision = None
                else:
                    unit_id = ""
                    attacker_id = ""
                    try:
                        unit_id = get_entity_id(root)
                    except Exception:
                        unit_id = ""
                    try:
                        attacker_id = get_entity_id(attacker)
                    except Exception:
                        attacker_id = ""
                    req_options = [DecisionOption.create("Don't Use", payload={"action": "skip"})]
                    for entry in option_entries:
                        req_options.append(
                            DecisionOption.create(
                                f"Use {entry.get('label')}",
                                payload={"choice": "use", "ability_key": entry.get("ability_key", "")},
                            )
                        )
                    req = DecisionRequest.create(
                        DECISION_USE_LEADING_UNMODIFIED_SIX,
                        "Leading Ability: Unmodified 6",
                        player_id=getattr(player, "id", None),
                        options=req_options,
                        context={
                            "unit_id": unit_id,
                            "attacker_model_id": attacker_id,
                            "roll_type": str(roll_type or ""),
                            "roll_value": int(roll_value),
                            "ability_keys": [e.get("ability_key", "") for e in option_entries],
                        },
                    )
                    if hasattr(game, "request_decision"):
                        game.request_decision(req)

                    choice = None
                    try:
                        overrides = getattr(player, "_next_optional_selections", None)
                        if isinstance(overrides, dict) and "LEADING_UNMODIFIED_SIX" in overrides:
                            choice = overrides.pop("LEADING_UNMODIFIED_SIX")
                    except Exception:
                        choice = None
                    choice_norm = str(choice or "").strip().lower()
                    desired_key = ""
                    if choice_norm in ("use", "yes", "true"):
                        desired_key = str(option_entries[0].get("ability_key", "") or "") if option_entries else ""
                    elif choice_norm in ("skip", "no", "false"):
                        desired_key = ""
                    else:
                        # Allow explicit ability_key selection.
                        for entry in option_entries:
                            if str(entry.get("ability_key", "")).lower() == choice_norm:
                                desired_key = str(entry.get("ability_key", "") or "")
                                break
                    option_id = None
                    try:
                        if not desired_key:
                            for opt in list(getattr(req, "options", []) or []):
                                payload = dict(getattr(opt, "payload", {}) or {})
                                if str(payload.get("action", "") or "") == "skip":
                                    option_id = opt.option_id
                                    break
                        else:
                            for opt in list(getattr(req, "options", []) or []):
                                payload = dict(getattr(opt, "payload", {}) or {})
                                if str(payload.get("ability_key", "") or "") == desired_key:
                                    option_id = opt.option_id
                                    break
                    except Exception:
                        option_id = None
                    if option_id:
                        value, apply_result = resolve_decision_value(
                            game,
                            req,
                            option_id,
                            player_id=getattr(player, "id", None),
                        )
                        if apply_result is not None and getattr(apply_result, "ok", False):
                            decision = value
            if decision is None:
                decision = "skip"

        decision_key = ""
        if isinstance(decision, dict):
            if str(decision.get("choice", "") or "") == "use":
                decision_key = str(decision.get("ability_key", "") or "")
        else:
            if str(decision or "").strip().lower() == "use":
                decision_key = str(option_entries[0].get("ability_key", "") or "") if option_entries else ""
            else:
                decision_key = str(decision or "")

        decision_key = str(decision_key or "").strip()
        if not decision_key:
            return roll_value, "skip"

        spec_map = {str(s.get("ability_key", "")): s for s in available if str(s.get("ability_key", ""))}
        spec = spec_map.get(decision_key)
        if spec is None:
            return roll_value, "skip"

        leader = spec.get("leader")
        if leader is None:
            return roll_value, "skip"

        try:
            sr = getattr(leader, "special_rules", None)
        except Exception:
            sr = None
        if not isinstance(sr, dict):
            sr = {}
        used_map = sr.get("leading_unmodified_six_used_phase_key", {})
        if not isinstance(used_map, dict):
            used_map = {}
        used_map[decision_key] = str(phase_key or "")
        sr["leading_unmodified_six_used_phase_key"] = used_map
        leader.special_rules = sr

        try:
            from warhammer40k_ai.utility.event_bus import append_dice, append_action
            rt = str(roll_type or "").strip().lower()
            label = "roll"
            if rt == "hit":
                label = "Hit roll"
            elif rt == "wound":
                label = "Wound roll"
            elif rt == "damage":
                label = "Damage roll"
            append_dice(player, f"{label} made {int(roll_value)}, leading ability used to change value to 6")
            uname = getattr(root, "name", "Unit")
            source = str(spec.get("source", "") or "Leading ability")
            append_action(player, f"{uname}: {source} used to change {label} {int(roll_value)} to 6")
        except Exception:
            pass

        return 6, decision_key

    def _maybe_apply_model_unmodified_six(
        self,
        model: 'Model',
        roll_type: str,
        roll_value: Optional[int],
        needed: Optional[int] = None,
        *,
        attacker: Optional['Model'] = None,
        target: Optional['Unit'] = None,
    ) -> tuple[Optional[int], Optional[str]]:
        """
        Model ability: once per battle, after making a hit/wound/save roll, set it to an unmodified 6.
        Returns (new_roll_value, decision_str) where decision_str is ability_key or "skip".
        """
        try:
            if roll_value is None:
                return roll_value, None
            if int(roll_value) == 6:
                return roll_value, None
        except Exception:
            return roll_value, None

        rt = str(roll_type or "").strip().lower()
        if rt not in ("hit", "wound", "save"):
            return roll_value, None

        if model is None:
            return roll_value, None
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return roll_value, None

        try:
            specs = list(getattr(unit, "model_once_per_battle_unmodified_six_specs", lambda _m: [])(model) or [])
        except Exception:
            specs = []
        if not specs:
            return roll_value, None

        available: list[dict] = []
        for spec in list(specs or []):
            key = str(spec.get("key", "") or "").strip().lower()
            if not key:
                continue
            try:
                if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                    continue
            except Exception:
                continue
            available.append(spec)

        if not available:
            return roll_value, None

        def _spec_sort_key(item: dict) -> tuple:
            return (
                str(item.get("key", "")),
                str(item.get("source", "")),
            )

        available = sorted(available, key=_spec_sort_key)
        option_entries = []
        for spec in available:
            source = str(spec.get("source", "") or "Ability").strip()
            option_entries.append(
                {
                    "ability_key": str(spec.get("key", "") or ""),
                    "label": source or "Ability",
                    "source": source or "Ability",
                }
            )

        player = None
        game_map = None
        is_human = False
        provider = None
        game = None
        try:
            army = unit.get_parent_army()
            player = getattr(army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
            game_map = getattr(game, "map", None) if game is not None else None
            is_human = bool(getattr(player, "has_control", lambda: False)())
            provider = getattr(game_map, "model_unmodified_six_provider", None) if game_map is not None else None
        except Exception:
            player = None
            game_map = None
            game = None
            is_human = False
            provider = None

        decision = None
        if is_human and callable(provider):
            try:
                decision = provider(
                    player=player,
                    model=model,
                    roll_type=rt,
                    value=int(roll_value),
                    needed=needed,
                    options=option_entries,
                    attacker=attacker,
                    target=target,
                    weapon_name=getattr(getattr(self, "parent_wargear", None), "name", None)
                    or getattr(self, "name", "Weapon"),
                )
            except Exception:
                decision = None
        else:
            decision = None
            if game is not None and player is not None:
                try:
                    from warhammer40k_ai.engine.decision_kinds import DECISION_USE_MODEL_UNMODIFIED_SIX
                    from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
                    from warhammer40k_ai.utility.decision_utils import resolve_decision_value
                    from warhammer40k_ai.utility.entity_ids import get_entity_id
                except Exception:
                    decision = None
                else:
                    model_id = ""
                    unit_id = ""
                    try:
                        model_id = get_entity_id(model)
                    except Exception:
                        model_id = ""
                    try:
                        unit_id = get_entity_id(unit)
                    except Exception:
                        unit_id = ""
                    req_options = [DecisionOption.create("Don't Use", payload={"action": "skip"})]
                    for entry in option_entries:
                        req_options.append(
                            DecisionOption.create(
                                f"Use {entry.get('label')}",
                                payload={"choice": "use", "ability_key": entry.get("ability_key", "")},
                            )
                        )
                    req = DecisionRequest.create(
                        DECISION_USE_MODEL_UNMODIFIED_SIX,
                        "Ability: Unmodified 6",
                        player_id=getattr(player, "id", None),
                        options=req_options,
                        context={
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "roll_type": rt,
                            "roll_value": int(roll_value),
                            "ability_keys": [e.get("ability_key", "") for e in option_entries],
                        },
                    )
                    if hasattr(game, "request_decision"):
                        game.request_decision(req)

                    choice = None
                    try:
                        overrides = getattr(player, "_next_optional_selections", None)
                        if isinstance(overrides, dict) and "MODEL_UNMODIFIED_SIX" in overrides:
                            choice = overrides.pop("MODEL_UNMODIFIED_SIX")
                    except Exception:
                        choice = None
                    choice_norm = str(choice or "").strip().lower()
                    desired_key = ""
                    if choice_norm in ("use", "yes", "true"):
                        desired_key = str(option_entries[0].get("ability_key", "") or "") if option_entries else ""
                    elif choice_norm in ("skip", "no", "false"):
                        desired_key = ""
                    else:
                        for entry in option_entries:
                            if str(entry.get("ability_key", "")).lower() == choice_norm:
                                desired_key = str(entry.get("ability_key", "") or "")
                                break
                    option_id = None
                    try:
                        if not desired_key:
                            for opt in list(getattr(req, "options", []) or []):
                                payload = dict(getattr(opt, "payload", {}) or {})
                                if str(payload.get("action", "") or "") == "skip":
                                    option_id = opt.option_id
                                    break
                        else:
                            for opt in list(getattr(req, "options", []) or []):
                                payload = dict(getattr(opt, "payload", {}) or {})
                                if str(payload.get("ability_key", "") or "") == desired_key:
                                    option_id = opt.option_id
                                    break
                    except Exception:
                        option_id = None
                    if option_id:
                        value, apply_result = resolve_decision_value(
                            game,
                            req,
                            option_id,
                            player_id=getattr(player, "id", None),
                        )
                        if apply_result is not None and getattr(apply_result, "ok", False):
                            decision = value
            if decision is None:
                decision = "skip"

        decision_key = ""
        if isinstance(decision, dict):
            if str(decision.get("choice", "") or "") == "use":
                decision_key = str(decision.get("ability_key", "") or "")
        else:
            if str(decision or "").strip().lower() == "use":
                decision_key = str(option_entries[0].get("ability_key", "") or "") if option_entries else ""
            else:
                decision_key = str(decision or "")

        decision_key = str(decision_key or "").strip().lower()
        if not decision_key:
            return roll_value, "skip"

        spec_map = {str(s.get("key", "")).strip().lower(): s for s in available if str(s.get("key", "") or "").strip()}
        spec = spec_map.get(decision_key)
        if spec is None:
            return roll_value, "skip"

        try:
            ability_name = str(spec.get("source", "") or "Ability").strip()
            model.mark_used_once_per_battle(decision_key, ability_name=ability_name, source="datasheet")
        except Exception:
            pass

        try:
            from warhammer40k_ai.utility.event_bus import append_dice, append_action
            label = "roll"
            if rt == "hit":
                label = "Hit roll"
            elif rt == "wound":
                label = "Wound roll"
            elif rt == "save":
                label = "Save roll"
            append_dice(player, f"{label} made {int(roll_value)}, ability used to change value to 6")
            source = str(spec.get("source", "") or "Ability")
            append_action(player, f"{getattr(model, 'name', 'Model')}: {source} used to change {label} {int(roll_value)} to 6")
        except Exception:
            pass

        return 6, decision_key

    def _maybe_apply_aspect_shrine_token(
        self,
        attacker: 'Model',
        target: 'Unit',
        roll_type: str,
        roll_value: Optional[int],
        needed: Optional[int] = None,
    ) -> tuple[Optional[int], Optional[str]]:
        """
        Aeldari Aspect Shrine Token: optionally set a hit/wound roll to an unmodified 6.
        Returns (new_roll_value, decision_str) where decision_str is "use", "skip", or "suppress".
        """
        try:
            if roll_value is None:
                return roll_value, None
            if int(roll_value) == 6:
                return roll_value, None
        except Exception:
            return roll_value, None

        try:
            if bool(getattr(attacker, "is_character", False)):
                return roll_value, None
        except Exception:
            pass

        unit = getattr(attacker, "parent_unit", None)
        if unit is None:
            return roll_value, None
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit

        try:
            if not hasattr(root, "get_aspect_shrine_token_remaining"):
                return roll_value, None
            if int(root.get_aspect_shrine_token_remaining() or 0) <= 0:
                return roll_value, None
            if bool(root.is_aspect_shrine_prompt_suppressed()):
                return roll_value, None
        except Exception:
            return roll_value, None

        player = None
        game_map = None
        is_human = False
        provider = None
        game = None
        try:
            army = root.get_parent_army()
            player = getattr(army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
            game_map = getattr(game, "map", None) if game is not None else None
            is_human = bool(getattr(player, "has_control", lambda: False)())
            provider = getattr(game_map, "aspect_shrine_provider", None) if game_map is not None else None
        except Exception:
            player = None
            game_map = None
            game = None
            is_human = False
            provider = None

        decision = None
        tokens_remaining = 0
        try:
            tokens_remaining = int(root.get_aspect_shrine_token_remaining() or 0)
        except Exception:
            tokens_remaining = 0

        if is_human and callable(provider):
            try:
                decision = provider(
                    player=player,
                    unit=root,
                    roll_type=str(roll_type or ""),
                    value=int(roll_value),
                    needed=needed,
                    tokens_remaining=tokens_remaining,
                    attacker=attacker,
                    target=target,
                    weapon_name=getattr(getattr(self, "parent_wargear", None), "name", None)
                    or getattr(self, "name", "Weapon"),
                )
            except Exception:
                decision = None
        else:
            try:
                ctx = {
                    "roll_type": str(roll_type or ""),
                    "roll": int(roll_value),
                    "needed": int(needed) if needed is not None else None,
                    "tokens_remaining": int(tokens_remaining or 0),
                    "unit": root,
                    "attacker": attacker,
                    "target": target,
                }
            except Exception:
                ctx = {}
            decision = None
            if game is not None and player is not None:
                try:
                    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_ASPECT
                    from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
                    from warhammer40k_ai.utility.decision_utils import resolve_decision_value
                    from warhammer40k_ai.utility.entity_ids import get_entity_id
                except Exception:
                    decision = None
                else:
                    unit_id = ""
                    try:
                        unit_id = get_entity_id(root)
                    except Exception:
                        unit_id = ""
                    options = [
                        DecisionOption.create("Use", payload={"choice": "use"}),
                        DecisionOption.create("Don't Use", payload={"choice": "skip"}),
                        DecisionOption.create("Don't Use for this Unit", payload={"choice": "suppress"}),
                    ]
                    req = DecisionRequest.create(
                        DECISION_CHOOSE_ASPECT,
                        "Aspect Shrine Token",
                        player_id=getattr(player, "id", None),
                        options=options,
                        context={"unit_id": unit_id, "roll_type": str(roll_type or ""), "roll_value": int(roll_value)},
                    )
                    if hasattr(game, "request_decision"):
                        game.request_decision(req)

                    choice = None
                    try:
                        overrides = getattr(player, "_next_optional_selections", None)
                        if isinstance(overrides, dict) and "ASPECT_SHRINE_TOKEN" in overrides:
                            choice = overrides.pop("ASPECT_SHRINE_TOKEN")
                    except Exception:
                        choice = None
                    choice_norm = str(choice or "").strip().lower()
                    if choice_norm in ("use", "yes", "true"):
                        desired = "use"
                    elif choice_norm in ("suppress", "dont use for this unit", "dont_use_for_this_unit", "dont_use_for_unit", "skip_unit"):
                        desired = "suppress"
                    else:
                        desired = "skip"
                    option_id = None
                    try:
                        for opt in list(getattr(req, "options", []) or []):
                            payload = dict(getattr(opt, "payload", {}) or {})
                            if str(payload.get("choice", "") or "") == desired:
                                option_id = opt.option_id
                                break
                    except Exception:
                        option_id = None
                    if option_id:
                        value, apply_result = resolve_decision_value(
                            game,
                            req,
                            option_id,
                            player_id=getattr(player, "id", None),
                        )
                        if apply_result is not None and getattr(apply_result, "ok", False):
                            decision = value
            if decision is None:
                decision = "skip"

        decision_norm = str(decision or "").strip().lower()
        if decision_norm in ("dont use for this unit", "dont_use_for_unit", "dont_use_for_this_unit", "dont_unit", "skip_unit", "suppress", "unit"):
            try:
                root.set_aspect_shrine_prompt_suppressed(True)
                try:
                    from warhammer40k_ai.utility.event_bus import append_action
                    uname = getattr(root, "name", "Unit")
                    append_action(player, f"{uname}: Aspect Shrine Token prompt suppressed for this activation")
                except Exception:
                    pass
            except Exception:
                pass
            return roll_value, "suppress"

        if decision_norm in ("use", "yes", "true"):
            try:
                if root.spend_aspect_shrine_token(1):
                    try:
                        from warhammer40k_ai.utility.event_bus import append_dice
                        rt = str(roll_type or "").strip().lower()
                        label = "roll"
                        if rt == "hit":
                            label = "Hit roll"
                        elif rt == "wound":
                            label = "Wound roll"
                        append_dice(player, f"{label} made {int(roll_value)}, Aspect Shrine Token used to change value to 6")
                    except Exception:
                        pass
                    try:
                        from warhammer40k_ai.utility.event_bus import append_action
                        uname = getattr(root, "name", "Unit")
                        rt = str(roll_type or "").strip().lower()
                        label = "roll"
                        if rt == "hit":
                            label = "Hit roll"
                        elif rt == "wound":
                            label = "Wound roll"
                        append_action(player, f"{uname}: Aspect Shrine Token used to change {label} {int(roll_value)} to 6")
                    except Exception:
                        pass
                    return 6, "use"
            except Exception:
                return roll_value, None
        return roll_value, "skip"

    def _ignore_hit_modifier_rule_name(self, attacker: 'Model') -> Optional[str]:
        rule = None
        try:
            rule = self._ignore_hit_modifier_rule(attacker)
        except Exception:
            rule = None
        if not rule:
            return None
        return str(rule.get("name") or "Ignore modifiers")

    def _ignore_hit_modifier_rule(self, attacker: 'Model') -> Optional[dict]:
        """
        Detect unit/leader abilities that allow ignoring BS/WS and Hit roll modifiers.
        Returns a rule dict with:
            - name: ability name
            - attack_type: "ranged"|"melee"|"any"
            - skill_kinds: set("ballistic","weapon")
            - allow_hit: bool
        """
        unit = getattr(attacker, "parent_unit", None)
        if unit is None:
            return None
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit

        entries = []
        try:
            for name, desc in root._iter_ability_entries_for_rules():
                entries.append((name, desc))
        except Exception:
            pass
        try:
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "")
                except Exception:
                    name = ""
                    desc = ""
                entries.append((name, desc))
        except Exception:
            pass

        for name, desc in entries:
            text_src = desc or name or ""
            try:
                text = root._normalize_rules_text(text_src)
            except Exception:
                text = str(text_src or "")
            if not text:
                continue
            low = text.lower()
            if "ignore" not in low or "modifier" not in low:
                continue
            if "hit roll" not in low:
                continue
            has_bs = "ballistic skill" in low
            has_ws = "weapon skill" in low
            if not has_bs and not has_ws:
                continue
            attack_type = "any"
            if ("ranged attack" in low) or ("ranged attacks" in low) or ("ranged weapon" in low):
                attack_type = "ranged"
            if ("melee attack" in low) or ("melee attacks" in low) or ("melee weapon" in low):
                attack_type = "melee" if attack_type == "any" else "any"
            return {
                "name": str(name or "Ignore modifiers"),
                "attack_type": attack_type,
                "skill_kinds": {"ballistic" if has_bs else None, "weapon" if has_ws else None} - {None},
                "allow_hit": True,
            }
        return None

    def _hit_target_with_tracking(
        self, 
        target: 'Unit', 
        attacker: 'Model', 
        attack_instance: Dict,
        *,
        roll_value: Optional[int] = None,
        allow_rerolls: bool = True,
        log_roll: bool = True,
        preview_modifiers: bool = False,
    ) -> Dict:
        """Hit resolution with detailed tracking"""
        hit_result = {
            'roll': None,
            'needed': None,
            'base_skill': self.skill,
            'modifiers': [],
            'final_needed': None,
            'hit': False,
            'special_effects': [],
            'unmodified_roll': None,  # Track unmodified roll (after rerolls, before modifiers)
            'modified_roll': None,    # Track final modified roll
            'hit_modifier_total': 0,  # Track total modifier applied
        }
        rerolls_allowed = bool(allow_rerolls)

        base_skill = self.skill
        skill_mods: list[tuple[int, str]] = []

        def _add_skill_mod(delta, reason: str):
            try:
                val = int(delta)
            except Exception:
                return
            if val == 0:
                return
            msg = str(reason or "").strip()
            if not msg:
                msg = f"{val:+d} to skill"
            skill_mods.append((val, msg))

        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "for_the_greater_good", None) if army is not None else None
            if mgr is not None:
                bonus = mgr.guided_attack_bonus(unit, target)
                if isinstance(bonus, dict) and bonus.get("bs_improve"):
                    try:
                        val = int(bonus.get("bs_improve", 0) or 0)
                    except Exception:
                        val = 0
                    if val:
                        _add_skill_mod(val, f"For the Greater Good: Guided (+{val} BS)")
                if isinstance(bonus, dict) and bonus.get("ignores_cover"):
                    attack_instance["ignores_cover"] = True
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "doctrina_imperatives", None) if army is not None else None
            if mgr is not None and unit is not None:
                game = getattr(getattr(army, "player", None), "game", None)
                imperative = mgr.get_active_imperative_for_unit(unit, game=game)
                if imperative is not None:
                    is_ranged = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_ranged())
                    is_melee = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_melee())
                    if imperative.key == "PROTECTOR" and is_ranged:
                        _add_skill_mod(1, "Protector Imperative: +1 BS")
                    elif imperative.key == "CONQUEROR" and is_melee:
                        _add_skill_mod(1, "Conqueror Imperative: +1 WS")
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            sr = getattr(unit, "special_rules", None)
            order_key = str(sr.get("voice_of_command_order_key", "") or "") if isinstance(sr, dict) else ""
            if order_key:
                is_ranged = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_ranged())
                is_melee = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_melee())
                if order_key == "TAKE_AIM" and is_ranged:
                    _add_skill_mod(1, "Take Aim!: +1 BS")
                elif order_key == "FIX_BAYONETS" and is_melee:
                    _add_skill_mod(1, "Fix Bayonets!: +1 WS")
        except Exception:
            pass
        attacker_unit = getattr(attacker, "parent_unit", None)
        if attacker_unit is not None:
            from ..rules.psychic_guidance import psychic_guidance_skill_bonus
            bonus = psychic_guidance_skill_bonus(attacker)
            if bonus and isinstance(base_skill, int) and int(base_skill) > 0:
                _add_skill_mod(int(bonus), f"Psychic Guidance: +{int(bonus)} BS/WS")
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
            if mgr is not None:
                game = getattr(getattr(army, "player", None), "game", None)
                keys = mgr.get_active_combat_drug_keys_for_model(attacker, game=game)
                if keys:
                    is_melee = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_melee())
                    is_ranged = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_ranged())
                    if is_melee and "SERPENTIN" in keys:
                        _add_skill_mod(1, "Combat Drugs: Serpentin +1 WS")
                    if is_ranged and "SPLINTERMIND" in keys:
                        _add_skill_mod(1, "Combat Drugs: Splintermind +1 BS")
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            sr = getattr(unit, "special_rules", None) if unit is not None else None
            is_melee = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_melee())
            if is_melee and isinstance(sr, dict) and sr.get("enhancement_knight_diabolus"):
                if self._attacker_is_enhancement_bearer(attacker, sr):
                    _add_skill_mod(1, "Knight Diabolus: +1 WS")
        except Exception:
            pass

        # Drukhari: ignore cover from Deadly Retinue or Nowhere to Hide (Pain).
        try:
            is_ranged = bool(getattr(self.parent_wargear, "is_ranged", lambda: False)())
        except Exception:
            is_ranged = False
        if is_ranged:
            try:
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("pain_ignores_cover_ranged"):
                    attack_instance["ignores_cover"] = True
            except Exception:
                pass
            try:
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("bearer_unit_ignores_cover"):
                    attack_instance["ignores_cover"] = True
            except Exception:
                pass
            try:
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("warp_vision_ignores_cover_active"):
                    attack_instance["ignores_cover"] = True
            except Exception:
                pass
            try:
                tsr = getattr(target, "special_rules", None)
                if isinstance(tsr, dict) and tsr.get("pain_no_cover_active"):
                    attack_instance["ignores_cover"] = True
            except Exception:
                pass
            try:
                tsr = getattr(target, "special_rules", None)
                if isinstance(tsr, dict) and tsr.get("post_shoot_no_cover_active"):
                    attack_instance["ignores_cover"] = True
            except Exception:
                pass
        
        bonus_lethal = False
        bonus_sustained_value = 0
        bonus_sustained_label = ""
        bonus_devastating = False
        bonus_twin_linked = False
        bonus_heavy = False
        bonus_heavy_label = ""
        bonus_lance = False
        bonus_lance_label = ""
        bonus_anti_specs = ()
        bonus_precision_on_crit = False
        bonus_precision = False
        def _set_bonus_sustained(value: int, label: str) -> None:
            nonlocal bonus_sustained_value, bonus_sustained_label
            try:
                val = int(value or 0)
            except Exception:
                val = 0
            if val <= 0:
                return
            if val > bonus_sustained_value:
                bonus_sustained_value = val
                bonus_sustained_label = str(label or "")
            elif val == bonus_sustained_value and label:
                if bonus_sustained_label:
                    if str(label) not in bonus_sustained_label:
                        bonus_sustained_label = f"{bonus_sustained_label} + {label}"
                else:
                    bonus_sustained_label = str(label)
        try:
            attack_is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
        except Exception:
            attack_is_melee = False
        try:
            attack_is_ranged = bool(getattr(self.parent_wargear, "is_ranged", lambda: False)())
        except Exception:
            attack_is_ranged = False
        def _merge_anti_specs(existing, incoming):
            merged = list(existing or ())
            for spec in list(incoming or ()):
                if spec not in merged:
                    merged.append(spec)
            return tuple(merged)

        def _apply_keyword_bonus(bonus, *, sustained_label: str = "", heavy_label: str = "", lance_label: str = "") -> None:
            nonlocal bonus_lethal, bonus_sustained_value, bonus_sustained_label
            nonlocal bonus_devastating, bonus_twin_linked, bonus_heavy, bonus_heavy_label
            nonlocal bonus_lance, bonus_lance_label, bonus_anti_specs, bonus_precision
            if not isinstance(bonus, dict):
                return
            if bool(bonus.get("lethal_hits")):
                bonus_lethal = True
            if bool(bonus.get("precision")):
                bonus_precision = True
            bonus_sustained_val = int(bonus.get("sustained_hits_value", 0) or 0)
            if bonus_sustained_val:
                _set_bonus_sustained(bonus_sustained_val, sustained_label)
            if bool(bonus.get("devastating_wounds")):
                bonus_devastating = True
            if bool(bonus.get("twin_linked")):
                bonus_twin_linked = True
            if bool(bonus.get("heavy")):
                bonus_heavy = True
                if heavy_label and not bonus_heavy_label:
                    bonus_heavy_label = heavy_label
            if bool(bonus.get("lance")):
                bonus_lance = True
                if lance_label and not bonus_lance_label:
                    bonus_lance_label = lance_label
            bonus_anti_specs = _merge_anti_specs(bonus_anti_specs, tuple(bonus.get("anti_specs") or ()))
            if bool(bonus.get("ignores_cover")) and attack_is_ranged:
                attack_instance["ignores_cover"] = True

        try:
            unit = getattr(attacker, "parent_unit", None)
            attack_type = "melee" if attack_is_melee else "ranged" if attack_is_ranged else "any"
            bonus = None
            if unit is not None and hasattr(unit, "get_attack_keyword_bonuses"):
                bonus = unit.get_attack_keyword_bonuses(
                    target=target,
                    attack_type=attack_type,
                    model=attacker,
                )
                _apply_keyword_bonus(bonus, sustained_label="Objective Target", heavy_label="Objective Target", lance_label="Objective Target")
            within_half_range = None
            try:
                if "below_half_distance" in attack_instance:
                    within_half_range = bool(attack_instance.get("below_half_distance", False))
            except Exception:
                within_half_range = None
            if within_half_range is None:
                try:
                    dist = float(attack_instance.get("distance_to_target", 0.0) or 0.0)
                    effective_range_max = self._effective_range_max(attacker)
                    if effective_range_max:
                        within_half_range = dist <= (float(effective_range_max) / 2.0)
                except Exception:
                    within_half_range = None
            if within_half_range is None:
                within_half_range = False
            if unit is not None and hasattr(unit, "get_attack_half_range_keyword_bonuses"):
                half_bonus = unit.get_attack_half_range_keyword_bonuses(
                    attack_type=attack_type,
                    model=attacker,
                    within_half_range=bool(within_half_range),
                    weapon_profile=self,
                )
                _apply_keyword_bonus(half_bonus, sustained_label="Half Range", heavy_label="Half Range", lance_label="Half Range")
            if unit is not None and hasattr(unit, "get_model_weapon_keyword_bonuses"):
                weapon_name = ""
                try:
                    if getattr(self, "parent_wargear", None) is not None:
                        weapon_name = str(getattr(self.parent_wargear, "name", "") or "")
                    if not weapon_name:
                        weapon_name = str(getattr(self, "name", "") or "")
                except Exception:
                    weapon_name = ""
                model_bonus = unit.get_model_weapon_keyword_bonuses(
                    attack_type=attack_type,
                    model=attacker,
                    weapon_profile=self,
                    weapon_name=weapon_name,
                    target=target,
                )
                _apply_keyword_bonus(model_bonus, lance_label="Ability")

            if bonus_devastating:
                attack_instance["bonus_devastating_wounds"] = True
            if bonus_twin_linked:
                attack_instance["bonus_twin_linked"] = True
            if bonus_lance:
                attack_instance["bonus_lance"] = True
                if bonus_lance_label:
                    attack_instance["bonus_lance_source"] = bonus_lance_label
            if bonus_anti_specs:
                attack_instance["bonus_anti_specs"] = bonus_anti_specs
            if bonus_precision:
                attack_instance["bonus_precision"] = True
        except Exception:
            bonus_lethal = False
            bonus_sustained_value = 0
            bonus_sustained_label = ""
            bonus_devastating = False
            bonus_twin_linked = False
            bonus_heavy = False
            bonus_heavy_label = ""
            bonus_lance = False
            bonus_lance_label = ""
            bonus_anti_specs = ()
            bonus_precision_on_crit = False
            bonus_precision = False

        # Enhancement: Aspect of Murder grants Precision to bearer melee weapons.
        try:
            if attack_is_melee:
                sr = self._unit_special_rules(attacker)
                if isinstance(sr, dict) and sr.get("enhancement_bearer_melee_precision"):
                    if self._attacker_is_enhancement_bearer(attacker, sr):
                        attack_instance["bonus_precision"] = True
        except Exception:
            pass

        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "thousand_sons_detachments", None) if army is not None else None
            if mgr is not None and callable(getattr(mgr, "grand_coven_devastating_wounds", None)):
                game = getattr(getattr(army, "player", None), "game", None)
                if mgr.grand_coven_devastating_wounds(attacker, self, game=game):
                    attack_instance["bonus_devastating_wounds"] = True
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            sr = getattr(unit, "special_rules", None) if unit is not None else None
            is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
            if is_melee and isinstance(sr, dict) and sr.get("enhancement_furnace_of_plagues"):
                attack_instance["bonus_devastating_wounds"] = True
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            sr = getattr(unit, "special_rules", None) if unit is not None else None
            is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
            if is_melee and isinstance(sr, dict) and sr.get("enhancement_headwoppas_killchoppa"):
                if not self.is_extra_attacks() and self._attacker_is_enhancement_bearer(attacker, sr):
                    attack_instance["bonus_devastating_wounds"] = True
        except Exception:
            pass

        try:
            sr = getattr(attacker.parent_unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_angels_fang"):
                if attack_is_melee:
                    target_is_character = bool(getattr(target, "is_character", False))
                    target_is_monster = bool(getattr(target, "is_monster", False))
                    target_is_vehicle = bool(getattr(target, "is_vehicle", False))
                    try:
                        if hasattr(target, "has_keyword"):
                            if target.has_keyword("Character"):
                                target_is_character = True
                            if target.has_keyword("Monster"):
                                target_is_monster = True
                            if target.has_keyword("Vehicle"):
                                target_is_vehicle = True
                        elif hasattr(target, "has_any_keyword"):
                            if target.has_any_keyword("Character"):
                                target_is_character = True
                            if target.has_any_keyword("Monster"):
                                target_is_monster = True
                            if target.has_any_keyword("Vehicle"):
                                target_is_vehicle = True
                    except Exception:
                        pass
                    if target_is_character or target_is_monster or target_is_vehicle:
                        _set_bonus_sustained(2, "Angel's Fang")
        except Exception:
            pass

        # Tyranids: Hyper-adaptations (Invasion Fleet).
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None and hasattr(unit, "get_parent_army") else None
            mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
            if mgr is not None:
                game = getattr(getattr(army, "player", None), "game", None)
                adaptation = getattr(mgr, "get_active_hyper_adaptation_for_unit", lambda *_a, **_k: None)(
                    unit,
                    game=game,
                )
            else:
                adaptation = None
            if adaptation is not None:
                try:
                    target_keywords = tuple(getattr(adaptation, "target_keywords", ()) or ())
                except Exception:
                    target_keywords = ()

                def _target_has_any(keywords: tuple[str, ...]) -> bool:
                    if not keywords:
                        return False
                    for kw in keywords:
                        if not kw:
                            continue
                        try:
                            if hasattr(target, "has_any_keyword") and target.has_any_keyword(kw):
                                return True
                        except Exception:
                            pass
                        try:
                            attr_flag = f"is_{str(kw).strip().lower()}"
                            if bool(getattr(target, attr_flag, False)):
                                return True
                        except Exception:
                            pass
                    return False

                if _target_has_any(target_keywords):
                    if int(getattr(adaptation, "sustained_hits_value", 0) or 0) > 0:
                        _set_bonus_sustained(
                            int(getattr(adaptation, "sustained_hits_value", 0) or 0),
                            f"Hyper-adaptations: {getattr(adaptation, 'name', '')}",
                        )
                    if bool(getattr(adaptation, "lethal_hits", False)):
                        bonus_lethal = True
                    if bool(getattr(adaptation, "precision_on_crit", False)):
                        bonus_precision_on_crit = True
        except Exception:
            pass

        # Torrent auto-hits (in case of Overwatch it ignores 6+ restrictions)
        if self.is_torrent():
            hit_result['hit'] = True
            hit_result['special_effects'].append("Torrent (auto-hit)")
            return hit_result

        # Overwatch restriction: only unmodified 6s hit
        if getattr(attacker.parent_unit, '_overwatch_sixes_only', False):
            dice_roll = None
            miracle_used = False
            try:
                unit = attacker.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr is not None and mgr.can_use_act_of_faith(unit, game=game):
                    dice_roll, _dice, miracle_used = mgr.resolve_roll(
                        unit,
                        roll_type="hit",
                        game=game,
                        dice_count=1,
                        die_faces=6,
                        needed=6,
                    )
            except Exception:
                dice_roll = None
                miracle_used = False
            if dice_roll is None:
                dice_roll = get_roll("D6")
            weapon_name_for_log = getattr(self, 'parent_wargear', None).name if getattr(self, 'parent_wargear', None) else getattr(self, 'name', 'Weapon')
            try:
                if miracle_used:
                    append_dice(attacker.parent_unit.get_parent_army().player, f"Miracle die used for Overwatch Hit roll: {dice_roll} for {attacker.name} with {weapon_name_for_log}")
                else:
                    append_dice(attacker.parent_unit.get_parent_army().player, f"Overwatch Hit roll: {dice_roll} for {attacker.name} with {weapon_name_for_log}")
            except Exception:
                pass
            hit_result['roll'] = dice_roll
            hit_result['needed'] = 6
            hit_result['final_needed'] = 6
            new_roll, decision = self._maybe_apply_leading_unmodified_six(
                attacker,
                target,
                roll_type="hit",
                roll_value=dice_roll,
                needed=6,
            )
            if new_roll is not None and int(new_roll) != int(dice_roll):
                dice_roll = int(new_roll)
                hit_result['roll'] = dice_roll
                hit_result['special_effects'].append("Leading ability: set roll to 6")
            new_roll, decision = self._maybe_apply_model_unmodified_six(
                attacker,
                roll_type="hit",
                roll_value=dice_roll,
                needed=6,
                attacker=attacker,
                target=target,
            )
            if new_roll is not None and int(new_roll) != int(dice_roll):
                dice_roll = int(new_roll)
                hit_result['roll'] = dice_roll
                hit_result['special_effects'].append("Ability: set roll to 6")
            new_roll, decision = self._maybe_apply_aspect_shrine_token(
                attacker,
                target,
                roll_type="hit",
                roll_value=dice_roll,
                needed=6,
            )
            if new_roll is not None and int(new_roll) != int(dice_roll):
                dice_roll = int(new_roll)
                hit_result['roll'] = dice_roll
                hit_result['special_effects'].append("Aspect Shrine Token: set roll to 6")
            if dice_roll == 6:
                hit_result['hit'] = True
                hit_result['special_effects'].append("Overwatch: 6 required to hit")
                if miracle_used:
                    hit_result['special_effects'].append("Miracle die")
                attack_instance['crit_hit'] = True
            else:
                hit_result['hit'] = False
                hit_result['special_effects'].append("Overwatch: Miss (requires unmodified 6)")
                if miracle_used:
                    hit_result['special_effects'].append("Miracle die")
            return hit_result

        # Calculate modifiers first (always do this)
        hit_mods: list[tuple[int, tuple[str, ...]]] = []
        def _add_hit_mod(delta, reason=None):
            try:
                val = int(delta)
            except Exception:
                return
            if val == 0:
                return
            reasons = []
            if isinstance(reason, (list, tuple)):
                reasons = [str(r) for r in reason if str(r or "").strip()]
            else:
                r = str(reason or "").strip()
                if r:
                    reasons = [r]
            hit_mods.append((val, tuple(reasons)))

        heavy_from_doctrina = False
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "doctrina_imperatives", None) if army is not None else None
            if mgr is not None and unit is not None:
                game = getattr(getattr(army, "player", None), "game", None)
                if mgr.protector_heavy_applies(unit, game=game):
                    if getattr(self, "parent_wargear", None) and self.parent_wargear.is_ranged():
                        heavy_from_doctrina = True
        except Exception:
            heavy_from_doctrina = False
        if (self.is_heavy() or heavy_from_doctrina or bonus_heavy) and attacker.parent_unit.round_state.remained_stationary_this_round:
            if bonus_heavy and not self.is_heavy():
                label = bonus_heavy_label or "Objective Target"
                _add_hit_mod(1, f"+1 from Heavy [{label}]")
            elif heavy_from_doctrina and not self.is_heavy():
                _add_hit_mod(1, "+1 from Protector Imperative (counts as Heavy)")
            else:
                _add_hit_mod(1, "+1 from Heavy (stationary)")

        # INDIRECT FIRE: if no target models were visible at selection time, -1 to hit
        if attack_instance.get("indirect_fire_no_visible", False):
            _add_hit_mod(-1, "-1 from Indirect Fire (no target models visible)")

        # BIG GUNS NEVER TIRE (BGNT):
        # When a VEHICLE/MONSTER makes ranged attacks and it was Locked in Combat when it selected targets,
        # apply -1 to Hit unless the attack is made with a Pistol.
        try:
            pu = attacker.parent_unit
            if is_ranged and getattr(pu, "_bgnt_locked_at_target_selection", False) and (pu.is_vehicle or pu.is_monster) and (not self.is_pistol()):
                _add_hit_mod(-1, "-1 from Big Guns Never Tire (locked when selecting targets)")
        except Exception:
            pass

        # BGNT target exception: ranged attacks vs an engaged enemy MONSTER/VEHICLE are -1 to hit (unless Pistol).
        try:
            pu = getattr(attacker, "parent_unit", None)
            if is_ranged and pu is not None and (not self.is_pistol()) and (target.is_vehicle or target.is_monster):
                game_map = None
                try:
                    game_map = pu.get_parent_army().player.game.map
                except Exception:
                    game_map = None
                if game_map is not None:
                    engaged_with_friendly = any(
                        game_map.is_within_engagement_range(friendly, target)
                        for friendly in game_map.get_friendly_units(pu)
                        if friendly.is_alive() and getattr(friendly, "deployed", True)
                    )
                    if engaged_with_friendly:
                        _add_hit_mod(-1, "-1 from Big Guns Never Tire (target engaged)")
        except Exception:
            pass

        # Fortification: target only engaged with friendly Fortifications can be shot, but at -1 to hit (non-Pistol).
        try:
            pu = getattr(attacker, "parent_unit", None)
            if is_ranged and pu is not None and (not self.is_pistol()):
                game = getattr(getattr(pu.get_parent_army(), "player", None), "game", None)
                game_map = getattr(game, "map", None) if game is not None else None
                if game_map is not None and hasattr(target, "is_only_within_enemy_fortifications"):
                    if target.is_only_within_enemy_fortifications(game_map, enemy_unit=pu):
                        _add_hit_mod(-1, "-1 from Fortification")
        except Exception:
            pass
        
        # Check for target modifiers (like Stealth)
        if hasattr(target, 'has_stealth') and target.has_stealth():
            _add_hit_mod(-1, "-1 from target Stealth")
        # Warhost: Lightning-Fast Reactions (-1 to hit while active).
        try:
            try:
                troot = target.get_attached_unit_root()
            except Exception:
                troot = target
            sr = getattr(troot, "special_rules", None)
            if isinstance(sr, dict) and sr.get("lightning_fast_reactions_active") is True:
                _add_hit_mod(-1, "-1 from Lightning-Fast Reactions")
        except Exception:
            pass
        # Generic defensive penalty: -1 to hit when targeting this unit/model.
        try:
            if hasattr(target, "get_target_hit_roll_penalty"):
                is_melee = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_melee())
                attack_type = "melee" if is_melee else "ranged"
                penalty, reasons = target.get_target_hit_roll_penalty(
                    attack_type,
                    target_model=attack_instance.get("target_model"),
                )
                if penalty:
                    _add_hit_mod(-int(penalty), reasons or f"-{int(penalty)} to hit")
        except Exception:
            pass
        # Defensive reaction stratagems: -1 to hit (generic template).
        try:
            try:
                troot = target.get_attached_unit_root()
            except Exception:
                troot = target
            attack_type = "melee" if (self.parent_wargear and self.parent_wargear.is_melee()) else "ranged"
            attacker_key = attack_instance.get("attacker_key")
            if not attacker_key:
                try:
                    attacker_unit = getattr(attacker, "parent_unit", None)
                    if attacker_unit is not None:
                        attacker_root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
                        attacker_key = get_entity_id(attacker_root)
                except Exception:
                    attacker_key = None
            phase_key = self._resolve_phase_key(attacker_unit=getattr(attacker, "parent_unit", None), target_unit=troot)
            for entry in self._iter_defensive_entries(
                troot,
                "defensive_hit_mods",
                attacker_key=attacker_key,
                attack_type=attack_type,
                phase_key=phase_key,
            ):
                penalty = int(entry.get("value", 0) or 0)
                if penalty:
                    src = entry.get("source") or "Defensive stratagem"
                    _add_hit_mod(-penalty, f"-{penalty} to hit from {src}")
        except Exception:
            pass
        # First Prince of Chaos (Shadow Legion Tzeentch): -1 to hit when targeting this unit.
        try:
            if hasattr(target, "has_first_prince_tzeentch_defense") and target.has_first_prince_tzeentch_defense():
                _add_hit_mod(-1, "-1 from First Prince of Chaos (Tzeentch)")
        except Exception:
            pass
        # Suppressed units take -1 to hit (e.g. Agonising Suppression, post-shoot suppression).
        try:
            sr = getattr(attacker.parent_unit, "special_rules", None)
            if isinstance(sr, dict):
                if sr.get("pain_suppressed_active"):
                    _add_hit_mod(-1, "-1 from Agonising Suppression (suppressed)")
                if sr.get("post_shoot_suppressed_active"):
                    _add_hit_mod(-1, "-1 from Suppressed")
        except Exception:
            pass
        # Fight selection engagement penalty: -1 to hit for melee attacks while active.
        try:
            if is_melee:
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("fight_selected_enemy_melee_hit_penalty_active"):
                    sources = [str(s) for s in (sr.get("fight_selected_enemy_melee_hit_penalty_sources", []) or []) if str(s or "").strip()]
                    source_label = sources[0] if sources else "Engagement melee hit penalty"
                    _add_hit_mod(-1, f"-1 from {source_label}")
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            target_army = target.get_parent_army() if target is not None else None
            mgr = getattr(target_army, "doctrina_imperatives", None) if target_army is not None else None
            if mgr is not None and getattr(self, "parent_wargear", None) and self.parent_wargear.is_melee():
                game = getattr(getattr(target_army, "player", None), "game", None)
                game_map = getattr(game, "map", None) if game is not None else None
                if mgr.protector_melee_hit_penalty_applies(target, game=game, game_map=game_map):
                    _add_hit_mod(-1, "-1 from Protector Imperative (battleline screen)")
        except Exception:
            pass
        # Nurgle's Gift (Aura): Skullsquirm Blight (-1 to hit for afflicted units).
        try:
            unit = attacker.parent_unit
            game = None
            game_map = None
            try:
                army = unit.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
                game_map = getattr(game, "map", None) if game is not None else None
            except Exception:
                game = None
                game_map = None
            from ..rules.nurgles_gift import NurglesGiftManager, PLAGUE_SKULLSQUIRM
            plague = NurglesGiftManager.get_afflicted_plague_for_unit(unit, game=game, game_map=game_map)
            if plague is not None and plague.key == PLAGUE_SKULLSQUIRM.key:
                _add_hit_mod(-1, "-1 to hit from Skullsquirm Blight (Nurgle's Gift)")
        except Exception:
            pass
        # Leagues of Votann: Prioritised Efficiency (Hostile/Fortify hit bonus).
        try:
            unit = attacker.parent_unit
            army = None
            game = None
            try:
                army = unit.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
            mgr = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if mgr is not None:
                bonus, reason = mgr.hit_roll_bonus(unit, target, game=game)
                if bonus:
                    _add_hit_mod(int(bonus), reason)
        except Exception:
            pass
        # Necrons: Relentless Onslaught (+1 to hit vs targets within objective range).
        try:
            unit = attacker.parent_unit
            army = None
            game = None
            try:
                army = unit.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
            mgr = getattr(army, "necrons_detachments", None) if army is not None else None
            if mgr is not None:
                bonus, reason = mgr.relentless_onslaught_hit_bonus(unit, target, game=game)
                if bonus:
                    _add_hit_mod(int(bonus), reason)
        except Exception:
            pass
        # Adepta Sororitas: The Blood of Martyrs (Hallowed Martyrs).
        unit = getattr(attacker, "parent_unit", None)
        army = (
            unit.get_parent_army()
            if unit is not None and hasattr(unit, "get_parent_army") and hasattr(unit, "parent_army")
            else None
        )
        mgr = getattr(army, "adepta_sororitas_detachments", None) if army is not None else None
        bonus_fn = getattr(mgr, "blood_of_martyrs_hit_bonus", None) if mgr is not None else None
        if callable(bonus_fn):
            bonus, reason = bonus_fn(attacker, unit)
            if bonus:
                _add_hit_mod(int(bonus), reason or f"+{int(bonus)} to hit from The Blood of Martyrs")
        # Adeptus Custodes: Against All Odds (+1 to hit when isolated).
        unit = getattr(attacker, "parent_unit", None)
        army = None
        if unit is not None and hasattr(unit, "get_parent_army") and hasattr(unit, "parent_army"):
            army = unit.get_parent_army()
        mgr = getattr(army, "adeptus_custodes_detachments", None) if army is not None else None
        if mgr is not None and callable(getattr(mgr, "against_all_odds_hit_bonus", None)):
            game = getattr(getattr(army, "player", None), "game", None)
            game_map = getattr(game, "map", None) if game is not None else None
            if game_map is None:
                game_map = self._get_game_map_from_model(attacker)
            bonus = int(mgr.against_all_odds_hit_bonus(attacker, target, game=game, game_map=game_map) or 0)
            if bonus:
                _add_hit_mod(bonus, f"+{bonus} to hit from Against All Odds")
        # Harbingers of Dread: Darkness (-1 to hit against Chaos Knights).
        try:
            target_army = target.get_parent_army()
            mgr = getattr(target_army, "harbingers_of_dread", None) if target_army is not None else None
            if mgr is not None:
                from ..rules.harbingers_of_dread import DARKNESS
                if mgr.is_dread_active(DARKNESS.key, unit=target):
                    attacker_unit = attacker.parent_unit
                    apply_darkness = False
                    try:
                        if attacker_unit.is_battle_shocked():
                            apply_darkness = True
                    except Exception:
                        apply_darkness = False
                    if not apply_darkness:
                        try:
                            army = attacker_unit.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                            game_map = getattr(game, "map", None) if game is not None else None
                        except Exception:
                            game_map = None
                        if game_map is not None:
                            try:
                                dist = float(game_map.get_distance_between_units(attacker_unit, target))
                                if dist > 18.0:
                                    apply_darkness = True
                            except Exception:
                                apply_darkness = False
                    if apply_darkness:
                        _add_hit_mod(-1, "-1 to hit from Darkness (Harbingers of Dread)")
        except Exception:
            pass

        # Bondsman: Crusader's Duty (+1 to hit for ranged attacks) and Warden's Duty (ignores cover).
        try:
            unit = attacker.parent_unit
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict):
                is_ranged = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_ranged())
                if is_ranged and sr.get("bondsman_ranged_hit_bonus"):
                    bonus = int(sr.get("bondsman_ranged_hit_bonus", 0) or 0)
                    if bonus:
                        _add_hit_mod(bonus, "+1 to hit from Bondsman (Crusader's Duty)")
                if is_ranged and sr.get("bondsman_ignores_cover_ranged"):
                    attack_instance["ignores_cover"] = True
        except Exception:
            pass

        # Aeldari: Guiding Presence (+1 to hit for selected Vehicle unit).
        try:
            unit = attacker.parent_unit
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("guiding_presence_active"):
                is_ranged = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_ranged())
                if is_ranged:
                    bonus = int(sr.get("guiding_presence_bonus", 1) or 1)
                    if bonus:
                        source = str(sr.get("guiding_presence_source", "") or "Guiding Presence").strip()
                        _add_hit_mod(bonus, f"+{bonus} to hit from {source}")
        except Exception:
            pass

        # Damaged profile: subtract N from the Hit roll (stored as negative modifier).
        try:
            dm = int(getattr(attacker.parent_unit, "special_rules", {}).get("damaged_hit_roll_modifier", 0) or 0)
            if dm:
                if dm < 0:
                    _add_hit_mod(dm, f"{dm} from Damaged profile (to hit)")
                else:
                    _add_hit_mod(dm, f"+{dm} from Damaged profile (to hit)")
        except Exception:
            pass
        
        # Apply externally supplied hit roll modifiers (e.g. stratagem hooks).
        extra_hit_mods = attack_instance.get("hit_roll_modifiers")
        if extra_hit_mods:
            for mod in extra_hit_mods:
                val = None
                reason = None
                if isinstance(mod, dict):
                    val = mod.get("value", mod.get("modifier"))
                    reason = mod.get("reason", mod.get("source"))
                elif isinstance(mod, (tuple, list)):
                    if mod:
                        val = mod[0]
                        if len(mod) > 1:
                            reason = mod[1]
                else:
                    val = mod
                if val is None:
                    continue
                if reason:
                    _add_hit_mod(val, reason)
                else:
                    _add_hit_mod(val, "External hit modifier")

        # Friendly aura modifiers (e.g. "Beacons of Rage (Aura)")
        aura_mods = attack_instance.get("_aura_attack_mods")
        if aura_mods is None:
            from ..utility.aura_effects import get_aura_attack_modifiers
            aura_mods = get_aura_attack_modifiers(attacker.parent_unit, target, self)
            attack_instance["_aura_attack_mods"] = aura_mods
        if getattr(aura_mods, "hit", 0):
            _add_hit_mod(int(aura_mods.hit), list(getattr(aura_mods, "hit_reasons", ()) or ()))

        # Attached leader leading bonuses (e.g., Drill Boss)
        lead_mods = None
        unit_hit_mods = None
        is_melee = bool(getattr(self, "parent_wargear", None) and self.parent_wargear.is_melee())
        attack_type = "melee" if is_melee else "ranged"
        try:
            unit = attacker.parent_unit
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            lead_mods = root.get_leading_attack_roll_modifiers(attack_type, target=target)
            if isinstance(lead_mods, dict) and int(lead_mods.get("hit", 0) or 0):
                bonus = int(lead_mods.get("hit", 0) or 0)
                _add_hit_mod(bonus, list(lead_mods.get("hit_reasons", ()) or ()))
        except Exception:
            lead_mods = None
        try:
            unit = attacker.parent_unit
            unit_hit_mods = unit.get_unit_hit_reroll_modifiers(attack_type, target=target)
            if isinstance(unit_hit_mods, dict) and int(unit_hit_mods.get("hit", 0) or 0):
                bonus = int(unit_hit_mods.get("hit", 0) or 0)
                _add_hit_mod(bonus, list(unit_hit_mods.get("hit_reasons", ()) or ()))
        except Exception:
            unit_hit_mods = None

        # Model-specific: attack roll modifiers from parsed ability text.
        try:
            unit = attacker.parent_unit
            model_attack_mods = attack_instance.get("_model_attack_mods")
            if model_attack_mods is None:
                model_attack_mods = unit.model_attack_roll_modifiers_vs_weakened_target(
                    attacker,
                    attack_type=attack_type,
                    target=target,
                )
                attack_instance["_model_attack_mods"] = model_attack_mods
            if isinstance(model_attack_mods, dict) and int(model_attack_mods.get("hit", 0) or 0):
                bonus = int(model_attack_mods.get("hit", 0) or 0)
                _add_hit_mod(bonus, list(model_attack_mods.get("hit_reasons", ()) or ()))
        except Exception:
            pass
        attacker_unit = getattr(attacker, "parent_unit", None)
        if attacker_unit is not None:
            from ..rules.psychic_guidance import psychic_guidance_hit_bonus_applies
            if psychic_guidance_hit_bonus_applies(attacker_unit):
                _add_hit_mod(1, "+1 to hit from Psychic Guidance")
        # Movement phase selected target hit bonus (e.g., Aeldari).
        try:
            attacker_unit = getattr(attacker, "parent_unit", None)
            army = attacker_unit.get_parent_army() if attacker_unit is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            bonus, reason = target.get_movement_phase_visible_hit_bonus(attacker_unit, game=game)
            if bonus:
                _add_hit_mod(int(bonus), reason or f"+{int(bonus)} to hit from Movement phase bonus")
        except Exception:
            pass
        # Dark Ritual (once per battle): +1 to hit until end of turn.
        try:
            attacker_unit = getattr(attacker, "parent_unit", None)
            if attacker_unit is not None and hasattr(attacker_unit, "get_dark_ritual_bonuses"):
                army = attacker_unit.get_parent_army() if attacker_unit is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                hit_bonus, _wound_bonus, source = attacker_unit.get_dark_ritual_bonuses(game=game)
                if hit_bonus:
                    _add_hit_mod(int(hit_bonus), f"+{int(hit_bonus)} to hit from {source}")
        except Exception:
            pass
        from ..utility.modifier_choice import (
            CHOICE_KEEP_ALL,
            CHOICE_IGNORE_NEGATIVE,
            CHOICE_IGNORE_POSITIVE,
            CHOICE_IGNORE_ALL,
            options_for_signed_pairs,
            options_for_signed_values,
            filter_signed_modifiers,
        )

        if preview_modifiers:
            hit_result["skill_mods"] = list(skill_mods)
            hit_result["hit_mods"] = list(hit_mods)
            hit_result["base_skill"] = base_skill
            return hit_result

        def _resolve_modifier_choice(
            mods,
            *,
            choice_key: str,
            provider_attr: str,
            ability_label: str,
            player=None,
            game_map=None,
        ):
            if roll_value is None and mods:
                choice = attack_instance.get(choice_key)
                options = options_for_signed_pairs(mods)
                if choice is None:
                    if options:
                        provider = getattr(game_map, provider_attr, None) if game_map is not None else None
                        if callable(provider):
                            try:
                                choice = provider(
                                    player=player,
                                    attacker=attacker,
                                    target=target,
                                    weapon_profile=self,
                                    ability_name=ability_label,
                                    choices=options,
                                )
                            except Exception:
                                choice = None
                    if choice not in options:
                        choice = CHOICE_KEEP_ALL
                    attack_instance[choice_key] = choice
                if choice is None:
                    choice = CHOICE_KEEP_ALL
                if choice != CHOICE_KEEP_ALL:
                    kept, ignored = filter_signed_modifiers(mods, choice)
                    return choice, kept, ignored
            return CHOICE_KEEP_ALL, mods, []

        driven_by_ultimate_rage = False
        driven_rule_name = ""
        try:
            if is_melee and attacker_unit is not None:
                from ..rules.wrathful_presence import driven_by_ultimate_rage_applies, DRIVEN_BY_ULTIMATE_RAGE_NAME
                game_map = None
                try:
                    army = attacker_unit.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None)
                    game_map = getattr(game, "map", None) if game is not None else None
                except Exception:
                    game_map = None
                if driven_by_ultimate_rage_applies(attacker_unit, game_map=game_map):
                    driven_by_ultimate_rage = True
                    driven_rule_name = DRIVEN_BY_ULTIMATE_RAGE_NAME
        except Exception:
            driven_by_ultimate_rage = False
            driven_rule_name = ""

        ignore_rule = None
        try:
            ignore_rule = self._ignore_hit_modifier_rule(attacker)
        except Exception:
            ignore_rule = None

        if ignore_rule:
            rule_attack_type = str(ignore_rule.get("attack_type") or "any").strip().lower()
            if rule_attack_type == "ranged" and not attack_is_ranged:
                ignore_rule = None
            elif rule_attack_type == "melee" and not attack_is_melee:
                ignore_rule = None
        if ignore_rule:
            skill_kinds = set(ignore_rule.get("skill_kinds") or ())
            allow_hit = bool(ignore_rule.get("allow_hit", True))
            allow_skill = False
            skill_label = "Skill"
            if attack_is_melee:
                allow_skill = "weapon" in skill_kinds
                skill_label = "Weapon Skill"
            elif attack_is_ranged:
                allow_skill = "ballistic" in skill_kinds
                skill_label = "Ballistic Skill"
            else:
                allow_skill = bool(skill_kinds)
                if "weapon" in skill_kinds:
                    skill_label = "Weapon Skill"
                elif "ballistic" in skill_kinds:
                    skill_label = "Ballistic Skill"
            if allow_skill or allow_hit:
                player = None
                game_map = None
                try:
                    army = attacker.parent_unit.get_parent_army()
                    player = getattr(army, "player", None)
                    game = getattr(player, "game", None) if player is not None else None
                    game_map = getattr(game, "map", None) if game is not None else None
                except Exception:
                    player = None
                    game_map = None
                if allow_skill and skill_mods:
                    provider_attr = "skill_modifier_choice_provider"
                    if game_map is not None and not callable(getattr(game_map, provider_attr, None)):
                        provider_attr = "hit_modifier_choice_provider"
                    _choice, skill_mods, _ignored = _resolve_modifier_choice(
                        skill_mods,
                        choice_key="skill_modifier_choice",
                        provider_attr=provider_attr,
                        ability_label=f"{ignore_rule.get('name', 'Ignore modifiers')} ({skill_label})",
                        player=player,
                        game_map=game_map,
                    )
                if allow_hit and hit_mods:
                    _choice, hit_mods, _ignored = _resolve_modifier_choice(
                        hit_mods,
                        choice_key="hit_modifier_choice",
                        provider_attr="hit_modifier_choice_provider",
                        ability_label=f"{ignore_rule.get('name', 'Ignore modifiers')} (Hit roll)",
                        player=player,
                        game_map=game_map,
                    )

        if driven_by_ultimate_rage:
            skill_choice = attack_instance.get("skill_modifier_choice")
            hit_choice = attack_instance.get("hit_modifier_choice")
            ignored_skill = []
            ignored_hit = []
            skill_filtered = False
            hit_filtered = False
            if roll_value is None and skill_choice is None and skill_mods:
                player = None
                game_map = None
                try:
                    army = attacker.parent_unit.get_parent_army()
                    player = getattr(army, "player", None)
                    game = getattr(player, "game", None) if player is not None else None
                    game_map = getattr(game, "map", None) if game is not None else None
                except Exception:
                    player = None
                    game_map = None
                choice, skill_mods, ignored_skill = _resolve_modifier_choice(
                    skill_mods,
                    choice_key="skill_modifier_choice",
                    provider_attr="skill_modifier_choice_provider"
                    if (game_map is None or callable(getattr(game_map, "skill_modifier_choice_provider", None)))
                    else "hit_modifier_choice_provider",
                    ability_label=f"{driven_rule_name} (Weapon Skill)",
                    player=player,
                    game_map=game_map,
                )
                skill_choice = choice
                skill_filtered = True
            if roll_value is None and hit_choice is None and hit_mods:
                player = None
                game_map = None
                try:
                    army = attacker.parent_unit.get_parent_army()
                    player = getattr(army, "player", None)
                    game = getattr(player, "game", None) if player is not None else None
                    game_map = getattr(game, "map", None) if game is not None else None
                except Exception:
                    player = None
                    game_map = None
                choice, hit_mods, ignored_hit = _resolve_modifier_choice(
                    hit_mods,
                    choice_key="hit_modifier_choice",
                    provider_attr="hit_modifier_choice_provider",
                    ability_label=f"{driven_rule_name} (Hit roll)",
                    player=player,
                    game_map=game_map,
                )
                hit_choice = choice
                hit_filtered = True
            if skill_choice is None:
                skill_choice = CHOICE_KEEP_ALL
            if hit_choice is None:
                hit_choice = CHOICE_KEEP_ALL
            if skill_choice != CHOICE_KEEP_ALL:
                if not skill_filtered:
                    kept_skill, ignored_skill = filter_signed_modifiers(skill_mods, skill_choice)
                    skill_mods = kept_skill
                try:
                    if ignored_skill:
                        sr = getattr(attacker_unit, "special_rules", None)
                        if not isinstance(sr, dict):
                            sr = {}
                        ignored_sources = tuple(
                            sorted({str(r) for _v, rs in ignored_skill for r in rs if str(r or "").strip()})
                        )
                        kept_sources = tuple(
                            sorted({str(r) for _v, rs in kept_skill for r in rs if str(r or "").strip()})
                        )
                        sig = (ignored_sources, kept_sources, str(skill_choice))
                        if sr.get("driven_by_ultimate_rage_ws_mod_signature") != sig:
                            sr["driven_by_ultimate_rage_ws_mod_signature"] = sig
                            attacker_unit.special_rules = sr
                            from ..utility.event_bus import append_action
                            pn = attacker_unit.get_parent_army().player
                            ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                            tag = "negative" if skill_choice == CHOICE_IGNORE_NEGATIVE else "positive" if skill_choice == CHOICE_IGNORE_POSITIVE else "all"
                            append_action(pn, f"Driven by Ultimate Rage: ignored {tag} Weapon Skill modifiers ({ignored_text}).")
                            if kept_sources:
                                kept_text = ", ".join(s for s in kept_sources if s)
                                if kept_text:
                                    append_action(pn, f"Driven by Ultimate Rage: applied Weapon Skill modifiers ({kept_text}).")
                except Exception:
                    pass
            if hit_choice != CHOICE_KEEP_ALL:
                if not hit_filtered:
                    kept_hit, ignored_hit = filter_signed_modifiers(hit_mods, hit_choice)
                    hit_mods = kept_hit
                try:
                    if ignored_hit:
                        sr = getattr(attacker_unit, "special_rules", None)
                        if not isinstance(sr, dict):
                            sr = {}
                        ignored_sources = tuple(
                            sorted({str(r) for _v, rs in ignored_hit for r in rs if str(r or "").strip()})
                        )
                        kept_sources = tuple(
                            sorted({str(r) for _v, rs in kept_hit for r in rs if str(r or "").strip()})
                        )
                        sig = (ignored_sources, kept_sources, str(hit_choice))
                        if sr.get("driven_by_ultimate_rage_hit_mod_signature") != sig:
                            sr["driven_by_ultimate_rage_hit_mod_signature"] = sig
                            attacker_unit.special_rules = sr
                            from ..utility.event_bus import append_action
                            pn = attacker_unit.get_parent_army().player
                            ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                            tag = "negative" if hit_choice == CHOICE_IGNORE_NEGATIVE else "positive" if hit_choice == CHOICE_IGNORE_POSITIVE else "all"
                            append_action(pn, f"Driven by Ultimate Rage: ignored {tag} Hit roll modifiers ({ignored_text}).")
                            if kept_sources:
                                kept_text = ", ".join(s for s in kept_sources if s)
                                if kept_text:
                                    append_action(pn, f"Driven by Ultimate Rage: applied Hit roll modifiers ({kept_text}).")
                except Exception:
                    pass

        if skill_mods:
            for _val, reason in skill_mods:
                if reason:
                    hit_result['special_effects'].append(str(reason))
            try:
                if isinstance(base_skill, int) and int(base_skill) > 0:
                    total = sum(int(val) for val, _ in skill_mods)
                    base_skill = max(2, int(base_skill) - int(total))
            except Exception:
                pass
        hit_result['base_skill'] = base_skill

        modifiers_list = []
        for val, reasons in hit_mods:
            if reasons:
                modifiers_list.extend(list(reasons))
            else:
                modifiers_list.append(f"{int(val):+d} to hit")
        hit_result['modifiers'] = modifiers_list

        dice_modifier = sum(int(val) for val, _ in hit_mods)
        dice_modifier = min(max(dice_modifier, -1), 1)  # modifications are capped between -1 and 1
        final_needed = base_skill - dice_modifier  # Note: negative dice_modifier makes it harder (higher final_needed)
        
        hit_result['needed'] = base_skill
        hit_result['final_needed'] = final_needed

        # Provide reroll callback for hit
        def _reroll_hit():
            new_roll = get_roll("D6")
            if log_roll:
                try:
                    weapon_name_for_log = getattr(self, 'parent_wargear', None).name if getattr(self, 'parent_wargear', None) else getattr(self, 'name', 'Weapon')
                    append_dice(attacker.parent_unit.get_parent_army().player, f"Hit re-roll: {new_roll} for {attacker.name} with {weapon_name_for_log}")
                except Exception:
                    pass
            return new_roll
        dice_roll = None
        miracle_used = False
        if roll_value is not None:
            try:
                dice_roll = int(roll_value)
            except Exception:
                dice_roll = None
        if dice_roll is None:
            try:
                unit = attacker.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr is not None and mgr.can_use_act_of_faith(unit, game=game):
                    dice_roll, _dice, miracle_used = mgr.resolve_roll(
                        unit,
                        roll_type="hit",
                        game=game,
                        dice_count=1,
                        die_faces=6,
                        needed=final_needed,
                    )
            except Exception:
                dice_roll = None
                miracle_used = False
        if dice_roll is None:
            dice_roll = get_roll("D6")
        if log_roll:
            try:
                # Use parent wargear name when available for log context.
                weapon_name_for_log = getattr(self, 'parent_wargear', None).name if getattr(self, 'parent_wargear', None) else getattr(self, 'name', 'Weapon')
                if miracle_used:
                    append_dice(attacker.parent_unit.get_parent_army().player, f"Miracle die used for Hit roll: {dice_roll} for {attacker.name} with {weapon_name_for_log}")
                else:
                    append_dice(attacker.parent_unit.get_parent_army().player, f"Hit roll: {dice_roll} for {attacker.name} with {weapon_name_for_log}")
            except Exception:
                pass

        # Value-based and full rerolls from aura/leading/unit rules.
        reroll_used = False
        reroll_hit_values = set()
        reroll_value_reasons: list[str] = []
        reroll_full_reasons: list[str] = []
        try:
            if aura_mods is not None:
                for v in list(getattr(aura_mods, "reroll_hit_values", ()) or ()):
                    try:
                        reroll_hit_values.add(int(v))
                    except Exception:
                        continue
                if bool(getattr(aura_mods, "reroll_hit_ones", False)):
                    reroll_hit_values.add(1)
                reroll_value_reasons.extend(list(getattr(aura_mods, "reroll_hit_reasons", ()) or ()))
                if bool(getattr(aura_mods, "reroll_hit_full", False)):
                    reroll_full_reasons.extend(list(getattr(aura_mods, "reroll_hit_full_reasons", ()) or ()))
        except Exception:
            pass
        try:
            if isinstance(lead_mods, dict):
                for v in list(lead_mods.get("reroll_hit_values", ()) or ()):
                    try:
                        reroll_hit_values.add(int(v))
                    except Exception:
                        continue
                if bool(lead_mods.get("reroll_hit_ones", False)):
                    reroll_hit_values.add(1)
                reroll_value_reasons.extend(list(lead_mods.get("reroll_hit_reasons", ()) or ()))
                if bool(lead_mods.get("reroll_hit_full", False)):
                    reroll_full_reasons.extend(list(lead_mods.get("reroll_hit_full_reasons", ()) or ()))
        except Exception:
            pass
        try:
            if isinstance(unit_hit_mods, dict):
                for v in list(unit_hit_mods.get("reroll_hit_values", ()) or ()):
                    try:
                        reroll_hit_values.add(int(v))
                    except Exception:
                        continue
                if bool(unit_hit_mods.get("reroll_hit_ones", False)):
                    reroll_hit_values.add(1)
                reroll_value_reasons.extend(list(unit_hit_mods.get("reroll_hit_reasons", ()) or ()))
                if bool(unit_hit_mods.get("reroll_hit_full", False)):
                    reroll_full_reasons.extend(list(unit_hit_mods.get("reroll_hit_full_reasons", ()) or ()))
        except Exception:
            pass
        try:
            unit = attacker.parent_unit
            model_hit_mods = attack_instance.get("_model_hit_reroll_mods")
            if model_hit_mods is None:
                model_hit_mods = unit.get_model_hit_reroll_modifiers(attacker, attack_type=attack_type, target=target)
                attack_instance["_model_hit_reroll_mods"] = model_hit_mods
            if isinstance(model_hit_mods, dict):
                for v in list(model_hit_mods.get("reroll_hit_values", ()) or ()):
                    try:
                        reroll_hit_values.add(int(v))
                    except Exception:
                        continue
                reroll_value_reasons.extend(list(model_hit_mods.get("reroll_hit_reasons", ()) or ()))
                if bool(model_hit_mods.get("reroll_hit_full", False)):
                    reroll_full_reasons.extend(list(model_hit_mods.get("reroll_hit_full_reasons", ()) or ()))
        except Exception:
            pass
        # Contextual reroll sources carried on the attack instance (best-effort).
        try:
            if bool(attack_instance.get("furious_onslaught_applies")):
                reroll_full_reasons.append("Furious Onslaught")
        except Exception:
            pass
        try:
            rule = attack_instance.get("closest_enemy_hit_reroll_rule")
            if rule:
                reason = str(rule.get("source", "") or "Closest enemy unit").strip() or "Closest enemy unit"
                reroll_full_reasons.append(reason)
        except Exception:
            pass
        try:
            rule = attack_instance.get("monster_vehicle_reroll_rule")
            if rule and bool(rule.get("reroll_hit")):
                reason = str(rule.get("source", "") or "Monster/Vehicle rerolls").strip() or "Monster/Vehicle rerolls"
                reroll_full_reasons.append(reason)
        except Exception:
            pass
        # Grey Knights: Hallowed Ground (Warpbane Task Force) hit rerolls.
        unit = getattr(attacker, "parent_unit", None)
        army = unit.get_parent_army() if unit is not None and hasattr(unit, "get_parent_army") else None
        mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
        if mgr is not None and hasattr(mgr, "hallowed_ground_hit_reroll_mods"):
            game = getattr(getattr(army, "player", None), "game", None)
            game_map = getattr(game, "map", None) if game is not None else None
            target_visible = None
            if attack_type == "ranged":
                if game_map is not None and hasattr(unit, "_has_line_of_sight_to_target") and target is not None:
                    target_visible = bool(unit._has_line_of_sight_to_target(attacker, target, game_map))
                else:
                    target_visible = not bool(attack_instance.get("indirect_fire_no_visible", False))
            mods = mgr.hallowed_ground_hit_reroll_mods(
                attacker,
                target,
                attack_type=attack_type,
                game=game,
                game_map=game_map,
                target_visible=target_visible,
            )
            if isinstance(mods, dict):
                for v in list(mods.get("reroll_values", ()) or ()):
                    try:
                        reroll_hit_values.add(int(v))
                    except Exception:
                        continue
                reroll_value_reasons.extend(list(mods.get("reroll_reasons", ()) or ()))
                if bool(mods.get("reroll_full")):
                    reroll_full_reasons.extend(list(mods.get("reroll_full_reasons", ()) or ()))

        hit_result["reroll_values"] = list(sorted(reroll_hit_values))
        hit_result["reroll_value_reasons"] = list(reroll_value_reasons)
        hit_result["reroll_full_reasons"] = list(reroll_full_reasons)

        if rerolls_allowed:
            try:
                if rerolls_allowed and dice_roll in reroll_hit_values and "reroll" not in hit_result:
                    rr = _reroll_hit()
                    if reroll_value_reasons:
                        hit_result.setdefault("special_effects", []).extend(reroll_value_reasons)
                    else:
                        hit_result.setdefault("special_effects", []).append("Re-roll Hit roll")
                    if dice_roll == 1:
                        hit_result["reroll_of_one"] = 1
                    hit_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
            except Exception:
                pass

        if rerolls_allowed:
            try:
                if rerolls_allowed and reroll_full_reasons and "reroll" not in hit_result:
                    try:
                        success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        unit = attacker.parent_unit
                        game = unit.get_parent_army().player.game
                        player = unit.get_parent_army().player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                    reason = reroll_full_reasons[0] if reroll_full_reasons else "Unit ability"
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="hit",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason=reason,
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll:
                        rr = _reroll_hit()
                        hit_result.setdefault("special_effects", []).extend(reroll_full_reasons)
                        hit_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
            except Exception:
                pass

        # Grey Knights: Fury of Titan (Deep Strike) re-roll Hit rolls of 1.
        try:
            if rerolls_allowed and dice_roll == 1 and "reroll" not in hit_result:
                unit = attacker.parent_unit
                sr = getattr(unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("fury_of_titan_active"):
                    rr = _reroll_hit()
                    hit_result.setdefault("special_effects", []).append("Fury of Titan: re-roll Hit roll of 1")
                    hit_result["reroll_of_one"] = 1
                    hit_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # World Eaters: Furious Onslaught (Forgefiend) re-roll Hit roll vs closest eligible target within 18" (optional).
        try:
            if rerolls_allowed and attack_instance.get("furious_onslaught_applies") and "reroll" not in hit_result:
                try:
                    success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                except Exception:
                    success = False
                do_reroll = False
                try:
                    unit = attacker.parent_unit
                    game = unit.get_parent_army().player.game
                    player = unit.get_parent_army().player
                    is_human = bool(getattr(player, "has_control", lambda: False)())
                    provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                except Exception:
                    is_human = False
                    provider = None
                    player = None
                if is_human and callable(provider):
                    try:
                        do_reroll = bool(provider(
                            player=player,
                            unit=unit,
                            roll_type="hit",
                            value=dice_roll,
                            dice=None,
                            needed=final_needed,
                            success=success,
                            reason="Furious Onslaught",
                        ))
                    except Exception:
                        do_reroll = False
                else:
                    do_reroll = (not success)
                if do_reroll:
                    rr = _reroll_hit()
                    hit_result.setdefault("special_effects", []).append("Furious Onslaught: re-roll Hit roll")
                    hit_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass
        # Closest enemy unit: re-roll Hit roll (optional).
        try:
            rule = attack_instance.get("closest_enemy_hit_reroll_rule")
            if rerolls_allowed and rule and "reroll" not in hit_result:
                try:
                    success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                except Exception:
                    success = False
                do_reroll = False
                try:
                    reason = str(rule.get("source", "") or "Closest enemy unit").strip() or "Closest enemy unit"
                except Exception:
                    reason = "Closest enemy unit"
                try:
                    unit = attacker.parent_unit
                    game = unit.get_parent_army().player.game
                    player = unit.get_parent_army().player
                    is_human = bool(getattr(player, "has_control", lambda: False)())
                    provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                except Exception:
                    is_human = False
                    provider = None
                    player = None
                if is_human and callable(provider):
                    try:
                        do_reroll = bool(provider(
                            player=player,
                            unit=unit,
                            roll_type="hit",
                            value=dice_roll,
                            dice=None,
                            needed=final_needed,
                            success=success,
                            reason=reason,
                        ))
                    except Exception:
                        do_reroll = False
                else:
                    do_reroll = (not success)
                if do_reroll:
                    rr = _reroll_hit()
                    hit_result.setdefault("special_effects", []).append(f"{reason}: re-roll Hit roll")
                    hit_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # MONSTER/VEHICLE target: re-roll Hit roll (optional).
        try:
            rule = attack_instance.get("monster_vehicle_reroll_rule")
            if rerolls_allowed and rule and rule.get("reroll_hit") and "reroll" not in hit_result:
                try:
                    success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                except Exception:
                    success = False
                do_reroll = False
                try:
                    reason = str(rule.get("source", "") or "Monster/Vehicle rerolls").strip() or "Monster/Vehicle rerolls"
                except Exception:
                    reason = "Monster/Vehicle rerolls"
                try:
                    unit = attacker.parent_unit
                    game = unit.get_parent_army().player.game
                    player = unit.get_parent_army().player
                    is_human = bool(getattr(player, "has_control", lambda: False)())
                    provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                except Exception:
                    is_human = False
                    provider = None
                    player = None
                if is_human and callable(provider):
                    try:
                        do_reroll = bool(provider(
                            player=player,
                            unit=unit,
                            roll_type="hit",
                            value=dice_roll,
                            dice=None,
                            needed=final_needed,
                            success=success,
                            reason=reason,
                        ))
                    except Exception:
                        do_reroll = False
                else:
                    do_reroll = (not success)
                if do_reroll:
                    rr = _reroll_hit()
                    hit_result.setdefault("special_effects", []).append(f"{reason}: re-roll Hit roll")
                    hit_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # Emperor's Children: Pledges to the Dark Prince (1+) re-roll Hit rolls of 1.
        try:
            if rerolls_allowed and dice_roll == 1 and "reroll" not in hit_result:
                unit = attacker.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is not None and mgr.pact_points_at_least(1) and mgr.is_emperors_children_unit(unit):
                    rr = _reroll_hit()
                    hit_result.setdefault("special_effects", []).append("Pledges to the Dark Prince: re-roll Hit roll of 1")
                    hit_result["reroll_of_one"] = 1
                    hit_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # Emperor's Children: Mechanised Murder re-roll Hit rolls of 1.
        try:
            if rerolls_allowed and dice_roll == 1 and "reroll" not in hit_result:
                unit = attacker.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is not None and mgr.mechanised_murder_applies(unit):
                    rr = _reroll_hit()
                    hit_result.setdefault("special_effects", []).append("Mechanised Murder: re-roll Hit roll of 1")
                    hit_result["reroll_of_one"] = 1
                    hit_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # Cabal of Sorcerers: Destiny's Ruin rerolls (TS/Scintillating Legions only).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                unit = attacker.parent_unit
                sr = getattr(target, "special_rules", None)
                if isinstance(sr, dict):
                    mode = str(sr.get("cabal_destinys_ruin_mode", "") or "").strip().lower()
                    owner = str(sr.get("cabal_destinys_ruin_owner", "") or "")
                else:
                    mode = ""
                    owner = ""
                if mode and unit is not None:
                    try:
                        if owner and owner != str(getattr(unit.get_parent_army(), "_id", "") or ""):
                            mode = ""
                    except Exception:
                        pass
                if mode and unit is not None:
                    try:
                        if not (unit.has_any_keyword("THOUSAND SONS") or unit.has_any_keyword("SCINTILLATING LEGIONS")):
                            mode = ""
                    except Exception:
                        mode = ""
                if mode == "ones" and dice_roll == 1:
                    rr = _reroll_hit()
                    hit_result.setdefault("special_effects", []).append("Destiny's Ruin: re-roll Hit rolls of 1")
                    hit_result["reroll_of_one"] = 1
                    hit_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
                elif mode == "full":
                    try:
                        success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        army = unit.get_parent_army()
                        game = army.player.game
                        player = army.player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="hit",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason="Destiny's Ruin",
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll:
                        rr = _reroll_hit()
                        hit_result.setdefault("special_effects", []).append("Destiny's Ruin: re-roll Hit roll")
                        hit_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # Oath of Moment: attacks vs the selected target can re-roll the Hit roll (optional).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                unit = attacker.parent_unit
                army = unit.get_parent_army()
                mgr = getattr(army, "oath_of_moment", None) if army is not None else None
                if mgr is not None and mgr.can_reroll_hit(unit, target):
                    # Determine success at this stage (before auto-hit/miss shortcuts below).
                    try:
                        success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                    except Exception:
                        success = False

                    do_reroll = False
                    try:
                        game = army.player.game
                        player = army.player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None

                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="hit",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason="Oath of Moment",
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)

                    if do_reroll:
                        rr = _reroll_hit()
                        hit_result.setdefault("special_effects", []).append("Oath of Moment: re-roll Hit roll")
                        hit_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # Bondsman: Atrapos's Duty re-roll Hit rolls vs TITANIC/TOWERING targets.
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                unit = attacker.parent_unit
                sr = getattr(unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("bondsman_reroll_hit_wound_vs_titanic"):
                    try:
                        is_big = bool(getattr(target, "is_titanic", False) or getattr(target, "is_towering", False))
                    except Exception:
                        is_big = False
                    if is_big:
                        try:
                            success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                        except Exception:
                            success = False
                        do_reroll = False
                        try:
                            army = unit.get_parent_army()
                            game = army.player.game
                            player = army.player
                            is_human = bool(getattr(player, "has_control", lambda: False)())
                            provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        except Exception:
                            is_human = False
                            provider = None
                            player = None
                        if is_human and callable(provider):
                            try:
                                do_reroll = bool(provider(
                                    player=player,
                                    unit=unit,
                                    roll_type="hit",
                                    value=dice_roll,
                                    dice=None,
                                    needed=final_needed,
                                    success=success,
                                    reason="Bondsman (Atrapos's Duty)",
                                ))
                            except Exception:
                                do_reroll = False
                        else:
                            do_reroll = (not success)
                        if do_reroll:
                            rr = _reroll_hit()
                            hit_result.setdefault("special_effects", []).append("Bondsman: re-roll Hit roll (Atrapos's Duty)")
                            hit_result["reroll"] = rr
                            dice_roll = rr
                            reroll_used = True
        except Exception:
            pass

        # Bondsman: Gallant's Duty re-roll Hit rolls in melee (optional).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                if is_melee:
                    unit = attacker.parent_unit
                    sr = getattr(unit, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("bondsman_reroll_hit_melee"):
                        try:
                            success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                        except Exception:
                            success = False
                        do_reroll = False
                        try:
                            army = unit.get_parent_army()
                            game = army.player.game
                            player = army.player
                            is_human = bool(getattr(player, "has_control", lambda: False)())
                            provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        except Exception:
                            is_human = False
                            provider = None
                            player = None
                        if is_human and callable(provider):
                            try:
                                do_reroll = bool(provider(
                                    player=player,
                                    unit=unit,
                                    roll_type="hit",
                                    value=dice_roll,
                                    dice=None,
                                    needed=final_needed,
                                    success=success,
                                    reason="Bondsman (Gallant's Duty)",
                                ))
                            except Exception:
                                do_reroll = False
                        else:
                            do_reroll = (not success)
                        if do_reroll:
                            rr = _reroll_hit()
                            hit_result.setdefault("special_effects", []).append("Bondsman: re-roll Hit roll (Gallant's Duty)")
                            hit_result["reroll"] = rr
                            dice_roll = rr
                            reroll_used = True
        except Exception:
            pass

        # Code Chivalric: Martial Valour re-roll Hit roll (one per selection).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                unit = attacker.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "code_chivalric", None) if army is not None else None
                if mgr is not None and mgr.can_use_reroll(attacker, kind="hit"):
                    try:
                        success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        game = army.player.game
                        player = army.player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="hit",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason="Code Chivalric",
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll and attacker.consume_code_chivalric_reroll("hit"):
                        rr = _reroll_hit()
                        hit_result.setdefault("special_effects", []).append("Code Chivalric: re-roll Hit roll")
                        hit_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # Selected to shoot: re-roll one Hit roll (one per selection).
        try:
            if rerolls_allowed and "reroll" not in hit_result and attack_is_ranged:
                if getattr(attacker, "can_use_selected_to_shoot_reroll", None) and attacker.can_use_selected_to_shoot_reroll("hit"):
                    try:
                        success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        unit = attacker.parent_unit
                        game = unit.get_parent_army().player.game
                        player = unit.get_parent_army().player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                        unit = None
                    reason = ""
                    try:
                        reason = str(getattr(attacker, "get_selected_to_shoot_reroll_source", lambda: "")() or "")
                    except Exception:
                        reason = ""
                    label = reason or "Selected to shoot"
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="hit",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason=label,
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll and attacker.consume_selected_to_shoot_reroll("hit"):
                        rr = _reroll_hit()
                        hit_result.setdefault("special_effects", []).append(f"{label}: re-roll Hit roll")
                        hit_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # Selected to shoot or fight: re-roll one Hit roll or one Wound roll (one per selection).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                action = "shoot" if attack_is_ranged else "fight" if attack_is_melee else ""
                if action and getattr(attacker, "can_use_selected_to_action_reroll", None) and attacker.can_use_selected_to_action_reroll("hit", action):
                    try:
                        success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        unit = attacker.parent_unit
                        game = unit.get_parent_army().player.game
                        player = unit.get_parent_army().player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                        unit = None
                    reason = ""
                    try:
                        reason = str(getattr(attacker, "get_selected_to_action_reroll_source", lambda _a=None: "")(action) or "")
                    except Exception:
                        reason = ""
                    default_label = "Selected to shoot" if action == "shoot" else "Selected to fight"
                    label = reason or default_label
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="hit",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason=label,
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll and attacker.consume_selected_to_action_reroll("hit", action):
                        rr = _reroll_hit()
                        hit_result.setdefault("special_effects", []).append(f"{label}: re-roll Hit roll")
                        hit_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # Drukhari: Power from Pain (Hatred Eternal) re-roll Hit rolls (optional).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("pain_reroll_hit"):
                    try:
                        success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        unit = attacker.parent_unit
                        game = unit.get_parent_army().player.game
                        player = unit.get_parent_army().player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="hit",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason="Power from Pain",
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll:
                        rr = _reroll_hit()
                        hit_result.setdefault("special_effects", []).append("Power from Pain: re-roll Hit roll")
                        hit_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # Drukhari: Power from Pain (Winged Strike) re-roll Hit rolls for ranged attacks (optional).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                is_ranged = bool(getattr(self.parent_wargear, "is_ranged", lambda: False)())
                if is_ranged:
                    sr = getattr(attacker.parent_unit, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("pain_reroll_hit_ranged"):
                        try:
                            success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                        except Exception:
                            success = False
                        do_reroll = False
                        try:
                            unit = attacker.parent_unit
                            game = unit.get_parent_army().player.game
                            player = unit.get_parent_army().player
                            is_human = bool(getattr(player, "has_control", lambda: False)())
                            provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        except Exception:
                            is_human = False
                            provider = None
                            player = None
                        if is_human and callable(provider):
                            try:
                                do_reroll = bool(provider(
                                    player=player,
                                    unit=unit,
                                    roll_type="hit",
                                    value=dice_roll,
                                    dice=None,
                                    needed=final_needed,
                                    success=success,
                                    reason="Power from Pain (Winged Strike)",
                                ))
                            except Exception:
                                do_reroll = False
                        else:
                            do_reroll = (not success)
                        if do_reroll:
                            rr = _reroll_hit()
                            hit_result.setdefault("special_effects", []).append("Power from Pain: re-roll Hit roll (ranged)")
                            hit_result["reroll"] = rr
                            dice_roll = rr
                            reroll_used = True
        except Exception:
            pass

        # Drukhari: Power from Pain (Goaded Savagery) re-roll Hit rolls for non-character melee attacks (optional).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                if is_melee and not bool(getattr(attacker, "is_character", False)):
                    sr = getattr(attacker.parent_unit, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("pain_beast_reroll_hit"):
                        try:
                            success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                        except Exception:
                            success = False
                        do_reroll = False
                        try:
                            unit = attacker.parent_unit
                            game = unit.get_parent_army().player.game
                            player = unit.get_parent_army().player
                            is_human = bool(getattr(player, "has_control", lambda: False)())
                            provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        except Exception:
                            is_human = False
                            provider = None
                            player = None
                        if is_human and callable(provider):
                            try:
                                do_reroll = bool(provider(
                                    player=player,
                                    unit=unit,
                                    roll_type="hit",
                                    value=dice_roll,
                                    dice=None,
                                    needed=final_needed,
                                    success=success,
                                    reason="Power from Pain (Goaded Savagery)",
                                ))
                            except Exception:
                                do_reroll = False
                        else:
                            do_reroll = (not success)
                        if do_reroll:
                            rr = _reroll_hit()
                            hit_result.setdefault("special_effects", []).append("Power from Pain: re-roll Hit roll (beast melee)")
                            hit_result["reroll"] = rr
                            dice_roll = rr
                            reroll_used = True
        except Exception:
            pass

        # Drukhari: Power from Pain (Splinter Racks) re-roll Hit rolls with Anti weapons (optional).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("pain_splinter_racks_active"):
                    is_ranged = bool(getattr(self.parent_wargear, "is_ranged", lambda: False)())
                    has_anti = bool(self.get_anti_specs())
                    has_passengers = bool(getattr(attacker.parent_unit, "transport_passengers", []) or [])
                    if is_ranged and has_anti and has_passengers:
                        try:
                            success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                        except Exception:
                            success = False
                        do_reroll = False
                        try:
                            unit = attacker.parent_unit
                            game = unit.get_parent_army().player.game
                            player = unit.get_parent_army().player
                            is_human = bool(getattr(player, "has_control", lambda: False)())
                            provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        except Exception:
                            is_human = False
                            provider = None
                            player = None
                        if is_human and callable(provider):
                            try:
                                do_reroll = bool(provider(
                                    player=player,
                                    unit=unit,
                                    roll_type="hit",
                                    value=dice_roll,
                                    dice=None,
                                    needed=final_needed,
                                    success=success,
                                    reason="Power from Pain (Splinter Racks)",
                                ))
                            except Exception:
                                do_reroll = False
                        else:
                            do_reroll = (not success)
                        if do_reroll:
                            rr = _reroll_hit()
                            hit_result.setdefault("special_effects", []).append("Power from Pain: re-roll Hit roll (Splinter Racks)")
                            hit_result["reroll"] = rr
                            dice_roll = rr
                            reroll_used = True
        except Exception:
            pass

        # Seductive Gambit: melee attacks can re-roll the Hit roll (optional).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                if is_melee:
                    unit = attacker.parent_unit
                    if hasattr(unit, "_seductive_gambit_active") and unit._seductive_gambit_active():
                        # Determine success at this stage (before auto-hit/miss shortcuts below).
                        try:
                            success = (dice_roll != 1) and (self.skill > 0) and (dice_roll >= final_needed)
                        except Exception:
                            success = False

                        do_reroll = False
                        try:
                            unit = attacker.parent_unit
                            game = unit.get_parent_army().player.game
                            player = unit.get_parent_army().player
                            is_human = bool(getattr(player, "has_control", lambda: False)())
                            provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        except Exception:
                            is_human = False
                            provider = None
                            player = None

                        if is_human and callable(provider):
                            try:
                                do_reroll = bool(provider(
                                    player=player,
                                    unit=unit,
                                    roll_type="hit",
                                    value=dice_roll,
                                    dice=None,
                                    needed=final_needed,
                                    success=success,
                                    reason="Monarch of the Hunt",
                                ))
                            except Exception:
                                do_reroll = False
                        else:
                            do_reroll = (not success)

                        if do_reroll:
                            rr = _reroll_hit()
                            hit_result.setdefault("special_effects", []).append("Seductive Gambit: re-roll Hit roll")
                            hit_result["reroll"] = rr
                            dice_roll = rr
                            reroll_used = True
        except Exception:
            pass

        # MONARCH OF THE HUNT (Shalaxi): melee vs quarry => optional re-roll of the Hit roll (even if successful),
        # to allow "fishing" for 6s (e.g. Devastating Wounds downstream on critical wounds, etc).
        # Note: a dice cannot be re-rolled more than once, so skip if a reroll already occurred.
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                if is_melee:
                    quarry_ids = getattr(attacker.parent_unit, "_monarch_of_the_hunt_quarry_ids", None)
                    if quarry_ids:
                        try:
                            tid = getattr(target, "_id", None)
                            rid = getattr(target.get_attached_unit_root(), "_id", None)
                        except Exception:
                            tid = getattr(target, "_id", None)
                            rid = None
                        is_quarry = (tid in quarry_ids) or (rid in quarry_ids)
                        if is_quarry:
                            try:
                                unit = attacker.parent_unit
                                game = unit.get_parent_army().player.game
                                player = unit.get_parent_army().player
                                provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                            except Exception:
                                provider = None
                                player = None
                                game = None

                            # Determine "success" at this stage (before auto-hit/miss shortcuts below).
                            # Natural 1 always fails; otherwise use final_needed.
                            try:
                                success = (dice_roll != 1) and (base_skill > 0) and (dice_roll >= final_needed)
                            except Exception:
                                success = False

                            do_reroll = False
                            if callable(provider):
                                try:
                                    do_reroll = bool(provider(
                                        player=player,
                                        unit=unit,
                                        roll_type="hit",
                                        value=dice_roll,
                                        dice=None,
                                        needed=final_needed,
                                        success=success,
                                    ))
                                except Exception:
                                    do_reroll = False

                            if do_reroll:
                                rr = _reroll_hit()
                                hit_result.setdefault("special_effects", []).append("Monarch of the Hunt: re-roll Hit roll (melee vs quarry)")
                                hit_result["reroll"] = rr
                                dice_roll = rr
                                reroll_used = True
        except Exception:
            pass

        # PREY SELECTION: optional re-roll of the Hit roll vs prey (if enabled).
        try:
            if rerolls_allowed and "reroll" not in hit_result:
                unit = attacker.parent_unit
                prey_ids = getattr(unit, "_prey_selection_prey_ids", None)
                if prey_ids and bool(getattr(unit, "_prey_selection_reroll_hit", False)):
                    melee_only = bool(getattr(unit, "_prey_selection_melee_only", False))
                    is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                    if (not melee_only) or is_melee:
                        try:
                            tid = getattr(target, "_id", None)
                            rid = getattr(target.get_attached_unit_root(), "_id", None)
                        except Exception:
                            tid = getattr(target, "_id", None)
                            rid = None
                        is_prey = (tid in prey_ids) or (rid in prey_ids)
                        if is_prey:
                            try:
                                game = unit.get_parent_army().player.game
                                player = unit.get_parent_army().player
                                provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                            except Exception:
                                provider = None
                                player = None
                                game = None

                            try:
                                success = (dice_roll != 1) and (base_skill > 0) and (dice_roll >= final_needed)
                            except Exception:
                                success = False

                            do_reroll = False
                            if callable(provider):
                                try:
                                    reason = str(getattr(unit, "_prey_selection_source", "") or "Prey selection")
                                    do_reroll = bool(provider(
                                        player=player,
                                        unit=unit,
                                        roll_type="hit",
                                        value=dice_roll,
                                        dice=None,
                                        needed=final_needed,
                                        success=success,
                                        reason=reason,
                                    ))
                                except Exception:
                                    do_reroll = False

                            if do_reroll:
                                rr = _reroll_hit()
                                label = str(getattr(unit, "_prey_selection_source", "") or "Prey selection")
                                hit_result.setdefault("special_effects", []).append(f"{label}: re-roll Hit roll (prey)")
                                hit_result["reroll"] = rr
                                dice_roll = rr
                                reroll_used = True
        except Exception:
            pass
        hit_result['roll'] = dice_roll
        if miracle_used:
            hit_result['special_effects'].append("Miracle die")
        # Publish roll_made for hit
        if log_roll:
            try:
                unit = attacker.parent_unit
                game = unit.get_parent_army().player.game
                from ..utility.reroll_tracker import prepare_reroll_event
                roll_id, reroll_cb, reroll_locked = prepare_reroll_event(
                    game,
                    _reroll_hit,
                    reroll_used=bool(reroll_used),
                    used_result=dice_roll,
                )
                game.event_system.publish(
                    "roll_made",
                    player=unit.get_parent_army().player,
                    unit=unit,
                    roll_type="hit",
                    value=dice_roll,
                    reroll=reroll_cb,
                    reroll_locked=bool(reroll_locked),
                    roll_id=roll_id,
                    miracle_used=bool(miracle_used),
                )
            except Exception:
                pass

        # Leading ability: once per phase, optionally set the roll to an unmodified 6.
        new_roll, decision = self._maybe_apply_leading_unmodified_six(
            attacker,
            target,
            roll_type="hit",
            roll_value=dice_roll,
            needed=final_needed,
        )
        if new_roll is not None and int(new_roll) != int(dice_roll):
            dice_roll = int(new_roll)
            hit_result['roll'] = dice_roll
            hit_result['special_effects'].append("Leading ability: set roll to 6")

        new_roll, decision = self._maybe_apply_model_unmodified_six(
            attacker,
            roll_type="hit",
            roll_value=dice_roll,
            needed=final_needed,
            attacker=attacker,
            target=target,
        )
        if new_roll is not None and int(new_roll) != int(dice_roll):
            dice_roll = int(new_roll)
            hit_result['roll'] = dice_roll
            hit_result['special_effects'].append("Ability: set roll to 6")

        # Aspect Shrine Token (Aeldari): optionally set the roll to an unmodified 6.
        new_roll, decision = self._maybe_apply_aspect_shrine_token(
            attacker,
            target,
            roll_type="hit",
            roll_value=dice_roll,
            needed=final_needed,
        )
        if new_roll is not None and int(new_roll) != int(dice_roll):
            dice_roll = int(new_roll)
            hit_result['roll'] = dice_roll
            hit_result['special_effects'].append("Aspect Shrine Token: set roll to 6")

        # Store unmodified roll (after rerolls/roll replacement, before modifiers) for Conversion and other rules
        hit_result['unmodified_roll'] = dice_roll
        
        # INDIRECT FIRE: if no target models were visible at selection time,
        # an unmodified hit roll of 1, 2, or 3 always fails.
        if attack_instance.get("indirect_fire_no_visible", False) and dice_roll in (1, 2, 3):
            hit_result['hit'] = False
            hit_result['unmodified_roll'] = dice_roll
            hit_result['special_effects'].append("Indirect Fire: 1-3 always fail (no target models visible)")
            return hit_result

        # Determine critical hit threshold (default 6).
        crit_threshold = 6
        crit_hit_reasons: list[str] = []
        empowered_sustained = False
        try:
            if aura_mods is not None and getattr(aura_mods, "crit_hit_threshold", None):
                crit_threshold = min(int(crit_threshold), int(aura_mods.crit_hit_threshold))
                crit_hit_reasons.extend(list(getattr(aura_mods, "crit_hit_reasons", ()) or ()))
        except Exception:
            pass
        try:
            if isinstance(lead_mods, dict) and lead_mods.get("crit_hit_threshold"):
                crit_threshold = min(int(crit_threshold), int(lead_mods.get("crit_hit_threshold")))
                crit_hit_reasons.extend(list(lead_mods.get("crit_hit_reasons", ()) or ()))
        except Exception:
            pass
        try:
            if isinstance(unit_hit_mods, dict) and unit_hit_mods.get("crit_hit_threshold"):
                crit_threshold = min(int(crit_threshold), int(unit_hit_mods.get("crit_hit_threshold")))
                crit_hit_reasons.extend(list(unit_hit_mods.get("crit_hit_reasons", ()) or ()))
        except Exception:
            pass
        try:
            is_ranged = bool(getattr(self.parent_wargear, "is_ranged", lambda: False)())
        except Exception:
            is_ranged = False
        if is_ranged:
            try:
                game = None
                unit = getattr(attacker, "parent_unit", None)
                army = unit.get_parent_army() if unit is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if hasattr(attacker, "has_temporary_crit_on_successful_hit"):
                    if attacker.has_temporary_crit_on_successful_hit(game=game):
                        crit_threshold = min(int(crit_threshold), int(final_needed))
                        crit_hit_reasons.append("Cry of the Wind: critical hit on successful hit")
            except Exception:
                pass
        try:
            unit = attacker.parent_unit
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is not None:
                if mgr.pact_points_at_least(7) and mgr.is_emperors_children_unit(unit):
                    crit_threshold = min(int(crit_threshold), 5)
                if mgr.is_carnival_of_excess():
                    game = getattr(getattr(army, "player", None), "game", None)
                    if mgr.is_empowered(unit, game=game):
                        if self.is_sustained_hits():
                            crit_threshold = min(int(crit_threshold), 5)
                        else:
                            empowered_sustained = True
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            sr = getattr(unit, "special_rules", None) if unit is not None else None
            is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
            if is_melee and isinstance(sr, dict) and sr.get("enhancement_daemon_weapon_of_nurgle"):
                crit_threshold = min(int(crit_threshold), 5)
                crit_hit_reasons.append("Daemon Weapon of Nurgle: critical hit on 5+")
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            if unit is not None and hasattr(unit, "get_attached_unit_root"):
                unit = unit.get_attached_unit_root()
            sr = getattr(unit, "special_rules", None) if unit is not None else None
            is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
            if is_melee and isinstance(sr, dict) and sr.get("unbridled_carnage_active"):
                exp = str(sr.get("unbridled_carnage_expires_phase", "") or "").strip().upper()
                phase_name = self._current_phase_name(attacker)
                if not exp or exp == phase_name:
                    crit_threshold = min(int(crit_threshold), 5)
                    crit_hit_reasons.append("Unbridled Carnage: critical hit on 5+")
        except Exception:
            pass

        hit_result["crit_threshold"] = int(crit_threshold)

        # Precompute attack context (for Blitzing Firepower and critical hit effects).
        try:
            is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
        except Exception:
            is_melee = False
        try:
            is_ranged = bool(getattr(self.parent_wargear, "is_ranged", lambda: False)())
        except Exception:
            is_ranged = False

        # WORLD EATERS: Blessings of Khorne keyword injection (melee-only).
        # - Warp Blades => Lethal Hits
        # - Martial Excellence => Sustained Hits 1
        blessings_lethal = False
        blessings_sustained = False
        try:
            if is_melee:
                unit = getattr(attacker, "parent_unit", None)
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
                game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                if mgr is not None and br > 0:
                    # Eligibility: attached unit group qualifies if any member has Blessings of Khorne ability
                    try:
                        qualifies = bool(unit.get_attached_unit_root().attached_unit_has_blessings_of_khorne())
                    except Exception:
                        qualifies = False
                    if qualifies:
                        blessings_lethal = bool(mgr.is_blessing_active_for_unit("WARP_BLADES", unit, battle_round=br))
                        blessings_sustained = bool(mgr.is_blessing_active_for_unit("MARTIAL_EXCELLENCE", unit, battle_round=br))
        except Exception:
            blessings_lethal = False
            blessings_sustained = False

        dark_pacts_choice = None
        try:
            sr = getattr(attacker.parent_unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("dark_pacts_active"):
                dark_pacts_choice = str(sr.get("dark_pacts_choice", "") or "").strip().upper()
        except Exception:
            dark_pacts_choice = None
        dark_pacts_lethal = dark_pacts_choice == "LETHAL HITS"
        dark_pacts_sustained = bool(dark_pacts_choice and dark_pacts_choice.startswith("SUSTAINED"))

        malefic_lethal = False
        malefic_sustained_value = 0
        malefic_diabolic_active = False
        try:
            unit = getattr(attacker, "parent_unit", None)
            root = unit.get_attached_unit_root() if unit is not None else None
        except Exception:
            root = None
        try:
            sr = getattr(root or getattr(attacker, "parent_unit", None), "special_rules", None)
            if isinstance(sr, dict) and sr.get("malefic_surge_diabolic_active"):
                exp = str(sr.get("malefic_surge_diabolic_expires_phase", "") or "").strip().upper()
                if exp:
                    try:
                        game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                        pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    except Exception:
                        pname = ""
                    if pname and pname != exp:
                        exp = ""
                if exp != "":
                    attack_type = str(sr.get("malefic_surge_diabolic_attack_type", "") or "").strip().lower()
                    if not attack_type or (attack_type == "melee" and is_melee) or (attack_type == "ranged" and is_ranged):
                        malefic_diabolic_active = True
                        choice = str(sr.get("malefic_surge_diabolic_choice", "") or "").strip().upper()
                        if choice == "LETHAL HITS":
                            malefic_lethal = True
                        elif "SUSTAINED" in choice:
                            m = re.search(r"(\\d+)", choice)
                            malefic_sustained_value = int(m.group(1)) if m else 1
        except Exception:
            malefic_lethal = False
            malefic_sustained_value = 0
            malefic_diabolic_active = False
        malefic_sustained = bool(malefic_sustained_value)
        try:
            if malefic_diabolic_active and is_melee:
                unit = getattr(attacker, "parent_unit", None)
                sr = getattr(unit, "special_rules", None) if unit is not None else None
                if isinstance(sr, dict) and sr.get("enhancement_knight_diabolus"):
                    if self._attacker_is_enhancement_bearer(attacker, sr):
                        attack_instance["bonus_lance"] = True
                        attack_instance.setdefault("bonus_lance_source", "Knight Diabolus (Diabolic Power)")
        except Exception:
            pass

        bondsman_lethal = False
        bondsman_sustained = False
        bondsman_sustained_ranged = False
        try:
            unit = getattr(attacker, "parent_unit", None)
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict):
                bondsman_lethal = bool(sr.get("bondsman_lethal_hits"))
                bondsman_sustained = bool(sr.get("bondsman_sustained_hits"))
                bondsman_sustained_ranged = bool(sr.get("bondsman_sustained_hits_ranged"))
                if bondsman_sustained_ranged:
                    bondsman_sustained_ranged = bool(
                        getattr(self.parent_wargear, "is_ranged", lambda: False)()
                    )
        except Exception:
            bondsman_lethal = False
            bondsman_sustained = False
            bondsman_sustained_ranged = False

        martial_katah_lethal = False
        martial_katah_sustained = False
        try:
            if is_melee:
                unit = getattr(attacker, "parent_unit", None)
                root = unit.get_attached_unit_root() if unit is not None else None
                if root is not None and root.attached_unit_has_martial_katah():
                    sr = getattr(root, "special_rules", None)
                    choice = ""
                    if isinstance(sr, dict):
                        choice = str(sr.get("martial_katah_choice", "") or "").strip().upper()
                    if choice == "RENDAX":
                        martial_katah_lethal = True
                    elif choice == "DACATARAI":
                        martial_katah_sustained = True
                    elif choice == "BOTH":
                        martial_katah_lethal = True
                        martial_katah_sustained = True
        except Exception:
            martial_katah_lethal = False
            martial_katah_sustained = False

        leading_lethal = False
        try:
            unit = getattr(attacker, "parent_unit", None)
            root = unit.get_attached_unit_root() if unit is not None else None
            if root is not None and hasattr(root, "leading_unit_weapons_have_lethal_hits"):
                attack_type = "melee" if is_melee else "ranged" if is_ranged else None
                leading_lethal = bool(root.leading_unit_weapons_have_lethal_hits(attack_type=attack_type))
        except Exception:
            leading_lethal = False

        pact_lethal = False
        pact_sustained = False
        exquisite_lethal = False
        exquisite_sustained = False
        pain_lethal = False
        pain_sustained = False
        pain_sustained_value = 0
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is not None and mgr.is_emperors_children_unit(unit):
                if mgr.pact_points_at_least(5) and is_melee:
                    pact_lethal = True
                    pact_sustained = True
            if is_melee:
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                sr = getattr(root, "special_rules", None) if root is not None else None
                if not isinstance(sr, dict):
                    sr = None
            if is_melee and sr:
                choice = str(sr.get("exquisite_swordsmanship_choice", "") or "").strip().upper()
                exp = str(sr.get("exquisite_swordsmanship_expires_phase", "") or "").strip().upper()
                if exp:
                    try:
                        game = getattr(getattr(army, "player", None), "game", None)
                        pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    except Exception:
                        pname = ""
                    if pname and pname != exp:
                        choice = ""
                if choice == "LETHAL":
                    exquisite_lethal = True
                elif choice == "SUSTAINED":
                    exquisite_sustained = True
        except Exception:
            pact_lethal = False
            pact_sustained = False
            exquisite_lethal = False
            exquisite_sustained = False
        try:
            sr = getattr(attacker.parent_unit, "special_rules", None)
            if isinstance(sr, dict):
                if bool(sr.get("pain_lethal_hits")):
                    pain_lethal = True
                if is_melee and bool(sr.get("pain_lethal_hits_melee")):
                    pain_lethal = True
                if self._assassins_poisons_applies(attacker):
                    pain_lethal = True
                pain_sustained_value = int(sr.get("pain_sustained_hits_value", 0) or 0)
                if is_ranged:
                    target_is_vehicle = False
                    try:
                        target_is_vehicle = bool(getattr(target, "is_vehicle", False)) or bool(target.has_keyword("Vehicle"))
                    except Exception:
                        target_is_vehicle = bool(getattr(target, "is_vehicle", False))
                    if target_is_vehicle:
                        pain_sustained_value = max(
                            int(sr.get("pain_sustained_hits_ranged_vs_vehicle", 0) or 0),
                            int(pain_sustained_value or 0),
                        )
                    else:
                        pain_sustained_value = max(
                            int(sr.get("pain_sustained_hits_ranged_vs_non_vehicle", 0) or 0),
                            int(pain_sustained_value or 0),
                        )
        except Exception:
            pain_lethal = False
            pain_sustained_value = 0
        pain_sustained = bool(pain_sustained_value)

        bearer_unit_sustained_value = 0
        try:
            sr = getattr(attacker.parent_unit, "special_rules", None)
            if isinstance(sr, dict):
                bearer_unit_sustained_value = int(sr.get("bearer_unit_sustained_hits_value", 0) or 0)
                if is_melee:
                    bearer_unit_sustained_value = max(
                        bearer_unit_sustained_value,
                        int(sr.get("bearer_unit_sustained_hits_value_melee", 0) or 0),
                    )
                if is_ranged:
                    bearer_unit_sustained_value = max(
                        bearer_unit_sustained_value,
                        int(sr.get("bearer_unit_sustained_hits_value_ranged", 0) or 0),
                    )
        except Exception:
            bearer_unit_sustained_value = 0
        bearer_unit_sustained = bool(bearer_unit_sustained_value)

        war_horde_sustained_value = 0
        if is_melee:
            unit = getattr(attacker, "parent_unit", None)
            army = None
            get_parent_army = getattr(unit, "get_parent_army", None) if unit is not None else None
            if callable(get_parent_army):
                army = get_parent_army()
            mgr = getattr(army, "orks_detachments", None) if army is not None else None
            value_fn = getattr(mgr, "war_horde_sustained_hits_value", None) if mgr is not None else None
            if callable(value_fn):
                war_horde_sustained_value = int(value_fn(unit, attack_type="melee") or 0)
        war_horde_sustained = bool(war_horde_sustained_value)
        bonus_sustained = bool(bonus_sustained_value)

        sustained_base = (
            self.is_sustained_hits()
            or blessings_sustained
            or dark_pacts_sustained
            or martial_katah_sustained
            or bondsman_sustained
            or bondsman_sustained_ranged
            or pact_sustained
            or exquisite_sustained
            or empowered_sustained
            or pain_sustained
            or bearer_unit_sustained
            or war_horde_sustained
            or bonus_sustained
            or malefic_sustained
        )

        blitzing_grants_sustained = False
        try:
            if is_ranged:
                unit = getattr(attacker, "parent_unit", None)
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("blitzing_firepower_active") is True:
                    in_range = False
                    try:
                        _closest, dist = attacker.return_closest_model_in_unit(target)
                        in_range = float(dist) <= 12.0 + 1e-6
                    except Exception:
                        try:
                            game = getattr(getattr(unit, "get_parent_army", lambda: None)(), "player", None)
                            game = getattr(game, "game", None) if game is not None else None
                            game_map = getattr(game, "map", None) if game is not None else None
                            if game_map is not None:
                                dist = game_map.get_distance_between_units(root, target)
                                in_range = float(dist) <= 12.0 + 1e-6
                        except Exception:
                            in_range = False
                    if in_range:
                        if sustained_base:
                            crit_threshold = min(int(crit_threshold), 5)
                        else:
                            blitzing_grants_sustained = True
        except Exception:
            blitzing_grants_sustained = False

        if dice_roll == 1:  # unmodified dice roll of 1 is always a miss
            hit_result['hit'] = False
            hit_result['unmodified_roll'] = dice_roll
            hit_result['special_effects'].append("Natural 1 (auto-miss)")
            return hit_result

        # Check for baseline critical hit (unmodified 6, or lower threshold from abilities)
        baseline_critical = dice_roll >= crit_threshold
        if baseline_critical:
            hit_result['hit'] = True
            if dice_roll == 6:
                hit_result['special_effects'].append("Natural 6 (auto-hit)")
            elif crit_threshold < 6:
                hit_result['special_effects'].append(f"Critical hit ({crit_threshold}+)")
            if crit_hit_reasons:
                hit_result['special_effects'].extend(crit_hit_reasons)
            attack_instance['crit_hit'] = True
            if bonus_precision_on_crit:
                attack_instance["bonus_precision"] = True
                hit_result['special_effects'].append("Precision")

            if self.is_lethal_hits() or blessings_lethal or dark_pacts_lethal or martial_katah_lethal or bondsman_lethal or pact_lethal or exquisite_lethal or pain_lethal or leading_lethal or bonus_lethal or malefic_lethal:
                hit_result['special_effects'].append("Lethal Hits")
                attack_instance['lethal_hit'] = True
            # For Sustained Hits, do not override an existing Sustained Hits X on the weapon.
            if self.is_sustained_hits() or blessings_sustained or dark_pacts_sustained or martial_katah_sustained or bondsman_sustained or bondsman_sustained_ranged or pact_sustained or exquisite_sustained or empowered_sustained or pain_sustained or bearer_unit_sustained or war_horde_sustained or bonus_sustained or malefic_sustained or blitzing_grants_sustained:
                # Support Sustained Hits X / Sustained Hits D3 / etc. Roll per critical hit.
                if self.is_sustained_hits():
                    try:
                        sh = self.get_sustained_hits_bonus()
                        sh_val = int(sh.resolve())
                        hit_result['special_effects'].append(f"Sustained Hits {sh} (+{sh_val})")
                        attack_instance['sustained_hit'] = sh_val
                    except Exception:
                        hit_result['special_effects'].append("Sustained Hits (+1)")
                        attack_instance['sustained_hit'] = 1
                else:
                    sustained_val = 1
                    label = "Sustained Hits (+1)"
                    if blitzing_grants_sustained:
                        label = "Sustained Hits (+1) [Blitzing Firepower]"
                    elif pain_sustained_value:
                        sustained_val = max(int(sustained_val), int(pain_sustained_value))
                        label = f"Sustained Hits (+{sustained_val}) [Power from Pain]"
                    elif bearer_unit_sustained_value:
                        sustained_val = max(int(sustained_val), int(bearer_unit_sustained_value))
                        label = f"Sustained Hits (+{sustained_val}) [Bearer Unit]"
                    elif war_horde_sustained_value:
                        sustained_val = max(int(sustained_val), int(war_horde_sustained_value))
                        label = f"Sustained Hits (+{sustained_val}) [War Horde]"
                    elif bonus_sustained_value:
                        sustained_val = max(int(sustained_val), int(bonus_sustained_value))
                        if bonus_sustained_label:
                            label = f"Sustained Hits (+{sustained_val}) [{bonus_sustained_label}]"
                        else:
                            label = f"Sustained Hits (+{sustained_val})"
                    elif malefic_sustained_value:
                        sustained_val = max(int(sustained_val), int(malefic_sustained_value))
                        label = f"Sustained Hits (+{sustained_val}) [Malefic Surge]"
                    elif blessings_sustained:
                        label += " [Blessings of Khorne]"
                    elif dark_pacts_sustained:
                        label += " [Dark Pacts]"
                    elif martial_katah_sustained:
                        label += " [Martial Ka'tah]"
                    elif bondsman_sustained or bondsman_sustained_ranged:
                        label += " [Bondsman]"
                    elif pact_sustained:
                        label += " [Pact Points]"
                    elif exquisite_sustained:
                        label += " [Exquisite Swordsmanship]"
                    elif empowered_sustained:
                        label += " [Daemonic Empowerment]"
                    hit_result['special_effects'].append(label)
                    attack_instance['sustained_hit'] = sustained_val
            # Don't return yet - we may need to apply Conversion logic below

        # Normal hit resolution (if not already determined by baseline critical)
        if not baseline_critical:
            hit_result['hit'] = self.skill > 0 and dice_roll >= final_needed

        # CONVERSION: Upgrade to critical hit if conditions are met
        # Must happen AFTER hit success is determined
        # Conversion grants critical hits on unmodified successful hit rolls of 4+
        # when the target is more than the specified distance from the bearer
        if attack_instance.get('conversion_active', False) and hit_result['hit']:
            unmod = hit_result.get('unmodified_roll', dice_roll)
            conversion_threshold = self.get_conversion_crit_threshold()  # Always 4
            # Only upgrade if not already a critical and unmodified roll meets threshold
            if unmod >= conversion_threshold and not attack_instance.get('crit_hit', False):
                # Upgrade to critical hit
                attack_instance['crit_hit'] = True
                hit_result['special_effects'].append(
                    f"Conversion: Critical Hit (unmodified {unmod}+ successful hit)"
                )
                if bonus_precision_on_crit:
                    attack_instance["bonus_precision"] = True
                    hit_result['special_effects'].append("Precision")

                # Apply ALL critical hit effects (same logic as baseline critical section)
                # This includes weapon-native AND unit/ability-based Lethal/Sustained hits

                # Apply Lethal Hits from all sources (same as baseline critical)
                if self.is_lethal_hits() or blessings_lethal or dark_pacts_lethal or martial_katah_lethal or bondsman_lethal or pact_lethal or exquisite_lethal or pain_lethal or leading_lethal or bonus_lethal:
                    hit_result['special_effects'].append("Lethal Hits")
                    attack_instance['lethal_hit'] = True

                # Apply Sustained Hits from all sources (same as baseline critical)
                if self.is_sustained_hits() or blessings_sustained or dark_pacts_sustained or martial_katah_sustained or bondsman_sustained or bondsman_sustained_ranged or pact_sustained or exquisite_sustained or empowered_sustained or pain_sustained or bearer_unit_sustained or war_horde_sustained or bonus_sustained or blitzing_grants_sustained:
                    # Support Sustained Hits X / Sustained Hits D3 / etc. Roll per critical hit.
                    if self.is_sustained_hits():
                        try:
                            sh = self.get_sustained_hits_bonus()
                            sh_val = int(sh.resolve())
                            hit_result['special_effects'].append(f"Sustained Hits {sh} (+{sh_val})")
                            attack_instance['sustained_hit'] = sh_val
                        except Exception:
                            hit_result['special_effects'].append("Sustained Hits (+1)")
                            attack_instance['sustained_hit'] = 1
                    else:
                        label = "Sustained Hits (+1)"
                        if blessings_sustained:
                            label += " [Blessings of Khorne]"
                        elif dark_pacts_sustained:
                            label += " [Dark Pacts]"
                        elif martial_katah_sustained:
                            label += " [Martial Ka'tah]"
                        elif bondsman_sustained or bondsman_sustained_ranged:
                            label += " [Bondsman]"
                        elif pact_sustained:
                            label += " [Pact Points]"
                        elif exquisite_sustained:
                            label += " [Exquisite Swordsmanship]"
                        elif empowered_sustained:
                            label += " [Daemonic Empowerment]"
                        elif pain_sustained:
                            label += " [Power from Pain]"
                        elif bearer_unit_sustained:
                            if bearer_unit_sustained_value > 1:
                                label = f"Sustained Hits (+{bearer_unit_sustained_value}) [Bearer Unit]"
                            else:
                                label += " [Bearer Unit]"
                        elif war_horde_sustained:
                            if war_horde_sustained_value > 1:
                                label = f"Sustained Hits (+{war_horde_sustained_value}) [War Horde]"
                            else:
                                label += " [War Horde]"
                        elif bonus_sustained:
                            if bonus_sustained_value > 1:
                                if bonus_sustained_label:
                                    label = f"Sustained Hits (+{bonus_sustained_value}) [{bonus_sustained_label}]"
                                else:
                                    label = f"Sustained Hits (+{bonus_sustained_value})"
                            else:
                                if bonus_sustained_label:
                                    label += f" [{bonus_sustained_label}]"
                                else:
                                    label += ""
                        elif blitzing_grants_sustained:
                            label += " [Blitzing Firepower]"
                        hit_result['special_effects'].append(label)
                        sustained_vals = [1]
                        if bearer_unit_sustained:
                            sustained_vals.append(int(bearer_unit_sustained_value or 0))
                        if pain_sustained:
                            sustained_vals.append(int(pain_sustained_value or 0))
                        if war_horde_sustained:
                            sustained_vals.append(int(war_horde_sustained_value or 0))
                        if bonus_sustained:
                            sustained_vals.append(int(bonus_sustained_value or 0))
                        attack_instance['sustained_hit'] = max(sustained_vals)

        # Ork charge-related keywords: track hits against MONSTER/VEHICLE units.
        if hit_result.get("hit"):
            if hasattr(target, "has_keyword"):
                is_monster_or_vehicle = bool(target.has_keyword("Monster") or target.has_keyword("Vehicle"))
            else:
                is_monster_or_vehicle = bool(getattr(target, "is_monster", False) or getattr(target, "is_vehicle", False))

            if is_monster_or_vehicle:
                unit = getattr(attacker, "parent_unit", None)
                army = unit.get_parent_army() if unit is not None and hasattr(unit, "get_parent_army") else None
                player = getattr(army, "player", None) if army is not None else None
                game = getattr(player, "game", None) if player is not None else None

                if self.is_harpooned():
                    attack_instance["harpooned_target"] = True
                    hit_result["special_effects"].append("Harpooned (charge bonus)")
                    if unit is not None and hasattr(unit, "register_wargear_charge_keyword_hit"):
                        updated = unit.register_wargear_charge_keyword_hit(
                            target,
                            "harpooned",
                            no_overwatch=False,
                            game=game,
                        )
                        if updated and player is not None:
                            append_action(player, f"{unit.name}: Harpooned hit on {target.name} (+2 charge)")
                if self.is_hooked():
                    attack_instance["hooked_target"] = True
                    hit_result["special_effects"].append("Hooked (charge bonus + no Overwatch)")
                    if unit is not None and hasattr(unit, "register_wargear_charge_keyword_hit"):
                        updated = unit.register_wargear_charge_keyword_hit(
                            target,
                            "hooked",
                            no_overwatch=True,
                            game=game,
                        )
                        if updated and player is not None:
                            append_action(
                                player,
                                f"{unit.name}: Hooked hit on {target.name} (+2 charge, no Overwatch)",
                            )
                if self.is_impaled():
                    attack_instance["impaled_target"] = True
                    hit_result["special_effects"].append("Impaled (charge bonus)")
                    if unit is not None and hasattr(unit, "register_wargear_charge_keyword_hit"):
                        updated = unit.register_wargear_charge_keyword_hit(
                            target,
                            "impaled",
                            no_overwatch=False,
                            game=game,
                        )
                        if updated and player is not None:
                            append_action(player, f"{unit.name}: Impaled hit on {target.name} (+2 charge)")
                if self.is_snagged():
                    attack_instance["snagged_target"] = True
                    hit_result["special_effects"].append("Snagged (charge bonus + no Overwatch)")
                    if unit is not None and hasattr(unit, "register_wargear_charge_keyword_hit"):
                        updated = unit.register_wargear_charge_keyword_hit(
                            target,
                            "snagged",
                            no_overwatch=True,
                            game=game,
                        )
                        if updated and player is not None:
                            append_action(
                                player,
                                f"{unit.name}: Snagged hit on {target.name} (+2 charge, no Overwatch)",
                            )

        return hit_result

    def _wound_target_with_tracking(
        self, 
        target: 'Unit', 
        attacker: 'Model', 
        attack_instance: Dict,
        *,
        roll_value: Optional[int] = None,
        allow_rerolls: bool = True,
        log_roll: bool = True,
    ) -> Dict:
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
        rerolls_allowed = bool(allow_rerolls)
        
        if attack_instance.get('lethal_hit', False):
            wound_result['wound'] = True
            wound_result['special_effects'].append("Lethal Hit (auto-wound)")
            return wound_result

        strength = self.strength
        try:
            if self.parent_wargear and isinstance(strength, int):
                bonus, reasons = getattr(attacker, "get_temporary_weapon_strength_bonus", lambda _n: (0, []))(
                    getattr(self.parent_wargear, "name", "")
                )
                if bonus:
                    strength = strength + int(bonus)
                    if reasons:
                        wound_result.setdefault("modifiers", []).extend(list(reasons))
                    else:
                        wound_result.setdefault("modifiers", []).append(
                            f"Ability +{bonus}S ({getattr(self.parent_wargear, 'name', 'weapon')}) [temporary]"
                        )
        except Exception:
            pass
        try:
            sr = getattr(attacker.parent_unit, "special_rules", None)
            bonuses = list(sr.get("daemonic_allegiance_weapon_bonuses", []) or []) if isinstance(sr, dict) else []
            if bonuses and self.parent_wargear and isinstance(strength, int):
                unit = getattr(attacker, "parent_unit", None)
                weapon_name = str(getattr(self.parent_wargear, "name", "") or getattr(self, "name", "") or "")
                for bonus in bonuses:
                    try:
                        names = list(bonus.get("weapon_names", []) or [])
                    except Exception:
                        names = []
                    if names and unit is not None and hasattr(unit, "_weapon_name_matches"):
                        if not unit._weapon_name_matches(names, weapon_name):
                            continue
                    try:
                        s_bonus = int(bonus.get("strength_bonus", 0) or 0)
                    except Exception:
                        s_bonus = 0
                    if s_bonus:
                        strength = strength + int(s_bonus)
                        source = str(bonus.get("source", "") or "Daemonic Allegiance").strip() or "Daemonic Allegiance"
                        wound_result.setdefault("modifiers", []).append(f"{source} +{s_bonus}S ({weapon_name})")
        except Exception:
            pass
        try:
            sonic_bonus = int(attack_instance.get("sonic_destruction_bonus", 0) or 0)
        except Exception:
            sonic_bonus = 0
        if sonic_bonus and isinstance(strength, int):
            strength = strength + int(sonic_bonus)
            wound_result.setdefault("modifiers", []).append(f"+{int(sonic_bonus)}S from Sonic Destruction")
        # Drukhari: Power from Pain (Macro-steroids) set melee Strength.
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                set_val = int(getattr(attacker.parent_unit, "special_rules", {}).get("pain_melee_strength_set", 0) or 0)
                if set_val and isinstance(strength, int):
                    strength = int(set_val)
                    wound_result.setdefault("modifiers", []).append(f"Set Strength {set_val} from Power from Pain (melee)")
        except Exception:
            pass
        # Enhancement: improve melee weapons' Strength by X (bearer enhancement).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                s_bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("enhancement_melee_strength_bonus", 0) or 0)
                if s_bonus and isinstance(strength, int):
                    strength = strength + s_bonus
                    wound_result.setdefault("modifiers", []).append(f"+{s_bonus}S from Enhancement (melee)")
        except Exception:
            pass
        if self.parent_wargear and self.parent_wargear.is_melee() and isinstance(strength, int):
            sr = self._unit_special_rules(attacker)
            bearer_s_bonus = int(sr.get("enhancement_bearer_melee_strength_bonus", 0) or 0)
            if bearer_s_bonus and self._attacker_is_enhancement_bearer(attacker, sr):
                strength = strength + bearer_s_bonus
                wound_result.setdefault("modifiers", []).append(
                    f"+{bearer_s_bonus}S from Enhancement bearer (melee)"
                )
        # Aura: add Strength to weapons for nearby friendly units.
        try:
            from ..utility.aura_effects import get_aura_strength_bonus
            aura_s, aura_reasons = get_aura_strength_bonus(attacker.parent_unit, self)
            if aura_s and isinstance(strength, int):
                strength = strength + int(aura_s)
                wound_result.setdefault("modifiers", []).extend(list(aura_reasons or ()))
        except Exception:
            pass
        # Detachment ability: Relentless Rage (World Eaters - Berzerker Warband)
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                s_bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("relentless_rage_melee_strength_bonus", 0) or 0)
                if s_bonus and isinstance(strength, int):
                    strength = strength + s_bonus
                    wound_result.setdefault("modifiers", []).append(f"+{s_bonus}S from Relentless Rage (melee)")
        except Exception:
            pass
        # Rage-cursed Onslaught: Limb from Limb (+1 Strength to melee weapons this phase).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                sr = getattr(attacker.parent_unit, "special_rules", None)
                s_bonus = int(sr.get("limb_from_limb_melee_strength_bonus", 0) or 0) if isinstance(sr, dict) else 0
                if s_bonus and isinstance(strength, int):
                    apply_bonus = True
                    exp = str(sr.get("limb_from_limb_expires_phase", "") or "").strip().upper() if isinstance(sr, dict) else ""
                    if exp:
                        try:
                            army = attacker.parent_unit.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                            pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            pname = ""
                        if pname and pname != exp:
                            apply_bonus = False
                    if apply_bonus:
                        strength = strength + s_bonus
                        wound_result.setdefault("modifiers", []).append(f"+{s_bonus}S from Limb from Limb")
        except Exception:
            pass
        # Tyranids: Synapse (+1 Strength in melee while within Synapse Range).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                army = attacker.parent_unit.get_parent_army()
                mgr = getattr(army, "synapse", None) if army is not None else None
                if mgr is not None and mgr.unit_in_synapse_range(attacker.parent_unit):
                    if isinstance(strength, int):
                        strength = strength + 1
                        wound_result.setdefault("modifiers", []).append("+1S from Synapse (melee)")
        except Exception:
            pass
        # Orks: Waaagh! (+1 Strength to melee weapons).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                unit = getattr(attacker, "parent_unit", None)
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "waaagh", None) if army is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr is not None and mgr.unit_is_affected(unit, game=game):
                    if isinstance(strength, int):
                        strength = strength + 1
                        wound_result.setdefault("modifiers", []).append("+1S from Waaagh! (melee)")
        except Exception:
            pass
        # Drukhari: Power from Pain (Brides of Death).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                s_bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("pain_melee_strength_bonus", 0) or 0)
                if s_bonus and isinstance(strength, int):
                    strength = strength + s_bonus
                    wound_result.setdefault("modifiers", []).append(f"+{s_bonus}S from Power from Pain (melee)")
        except Exception:
            pass
        # Drukhari: Combat Drugs (Grave Lotus).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                unit = getattr(attacker, "parent_unit", None)
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
                if mgr is not None:
                    game = getattr(getattr(army, "player", None), "game", None)
                    keys = mgr.get_active_combat_drug_keys_for_model(attacker, game=game)
                    if "GRAVE_LOTUS" in keys and isinstance(strength, int):
                        strength = strength + 1
                        wound_result.setdefault("modifiers", []).append("Combat Drugs: Grave Lotus +1S (melee)")
        except Exception:
            pass
        # Emperor's Children: Sensational Performance (+1 Strength to melee weapons this phase).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("sensational_performance_active"):
                    apply_bonus = True
                    exp = str(sr.get("sensational_performance_expires_phase", "") or "").strip().upper()
                    if exp:
                        try:
                            army = attacker.parent_unit.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                            pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            pname = ""
                        if pname and pname != exp:
                            apply_bonus = False
                    if apply_bonus:
                        s_bonus = int(sr.get("sensational_performance_strength_bonus", 0) or 0)
                        if s_bonus and isinstance(strength, int):
                            strength = strength + s_bonus
                            wound_result.setdefault("modifiers", []).append(f"+{s_bonus}S from Sensational Performance")
        except Exception:
            pass
        # Charge bonus: improve Strength/Damage for melee attacks after a Charge move.
        if self.parent_wargear and self.parent_wargear.is_melee():
            s_bonus, _d_bonus, s_reasons, _d_reasons = self._get_charge_melee_strength_damage_bonus(attacker, attack_instance)
            if s_bonus and isinstance(strength, int):
                strength = strength + int(s_bonus)
                if s_reasons:
                    wound_result.setdefault("modifiers", []).extend(list(s_reasons))
        # Bondsman: Magaera's Duty (+1S vs closest target for ranged attacks).
        try:
            if self._bondsman_magaera_bonus_applies(attacker, target):
                if isinstance(strength, int):
                    strength = strength + 1
                    wound_result.setdefault("modifiers", []).append("+1S from Bondsman (Magaera's Duty)")
        except Exception:
            pass

        # Attached units can still be valid targets even if bodyguard models are gone (leaders remain)
        try:
            alloc = target.get_models_for_wound_allocation()
        except Exception:
            alloc = list(getattr(target, "models", []) or [])
        if not alloc:
            wound_result['special_effects'].append("No valid targets")
            return wound_result

        target_toughness = attack_instance.get("target_toughness_override", None)
        if target_toughness is None:
            target_toughness = target.toughness

        # Aura cache (shared with hit resolution for the same attack_instance)
        aura_mods = attack_instance.get("_aura_attack_mods")
        if aura_mods is None:
            from ..utility.aura_effects import get_aura_attack_modifiers
            aura_mods = get_aura_attack_modifiers(attacker.parent_unit, target, self)
            attack_instance["_aura_attack_mods"] = aura_mods

        # Enemy-targeted aura debuffs affecting target characteristics (e.g. Nurgle's Gift (Aura): -1T)
        try:
            dt = int(getattr(aura_mods, "target_toughness_delta", 0) or 0)
            if dt:
                target_toughness = int(target_toughness) + dt
                wound_result['modifiers'].extend(list(getattr(aura_mods, "target_toughness_reasons", ()) or ()))
        except Exception:
            pass

        wound_result['target_toughness'] = target_toughness
        # Provide reroll callback for wound
        def _reroll_wound():
            new_roll = get_roll("D6")
            if log_roll:
                try:
                    weapon_name_for_log = getattr(self, 'parent_wargear', None).name if getattr(self, 'parent_wargear', None) else getattr(self, 'name', 'Weapon')
                    append_dice(attacker.parent_unit.get_parent_army().player, f"Wound re-roll: {new_roll} vs T{target_toughness} by {attacker.name} with {weapon_name_for_log}")
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
            bondsman_lance = False
            try:
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("bondsman_lance"):
                    bondsman_lance = True
            except Exception:
                bondsman_lance = False
            blood_tithe_lance = False
            try:
                unit = getattr(attacker, "parent_unit", None)
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                if mgr is not None and getattr(mgr, "blood_tithe_daemonic_rage_applies", None):
                    if mgr.blood_tithe_daemonic_rage_applies(unit):
                        blood_tithe_lance = True
            except Exception:
                blood_tithe_lance = False
            daemonic_fury_lance = False
            try:
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("daemonic_fury_lance_active") is True:
                    daemonic_fury_lance = True
                    owner = str(sr.get("daemonic_fury_lance_turn_owner", "") or "")
                    turn = int(sr.get("daemonic_fury_lance_turn", 0) or 0)
                    if owner or turn:
                        try:
                            army = attacker.parent_unit.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                        except Exception:
                            game = None
                        if game is None:
                            daemonic_fury_lance = False
                        else:
                            cur_turn = int(getattr(game, "turn", 0) or 0)
                            cur_player = getattr(game, "get_current_player", lambda: None)()
                            cur_owner = str(getattr(cur_player, "id", "") or "")
                            if owner and owner != cur_owner:
                                daemonic_fury_lance = False
                            if turn and turn != cur_turn:
                                daemonic_fury_lance = False
            except Exception:
                daemonic_fury_lance = False
            goretrack_lance = False
            try:
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("goretrack_onslaught_active") is True:
                    goretrack_lance = True
                    owner = str(sr.get("goretrack_onslaught_turn_owner", "") or "")
                    turn = int(sr.get("goretrack_onslaught_turn", 0) or 0)
                    if owner or turn:
                        try:
                            army = attacker.parent_unit.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                        except Exception:
                            game = None
                        if game is None:
                            goretrack_lance = False
                        else:
                            cur_turn = int(getattr(game, "turn", 0) or 0)
                            cur_player = getattr(game, "get_current_player", lambda: None)()
                            cur_owner = str(getattr(cur_player, "id", "") or "")
                            if owner and owner != cur_owner:
                                goretrack_lance = False
                            if turn and turn != cur_turn:
                                goretrack_lance = False
            except Exception:
                goretrack_lance = False
            bonus_lance = bool(attack_instance.get("bonus_lance"))
            bonus_lance_source = str(attack_instance.get("bonus_lance_source") or "")
            if is_melee and (self.is_lance() or bondsman_lance or blood_tithe_lance or daemonic_fury_lance or goretrack_lance or bonus_lance):
                charged = bool(getattr(attacker.parent_unit.round_state, "charged_this_round", False))
                if charged:
                    dice_modifier += 1
                    if bonus_lance and not self.is_lance():
                        if bonus_lance_source:
                            wound_result['modifiers'].append(f"+1 to wound from Lance ({bonus_lance_source})")
                        else:
                            wound_result['modifiers'].append("+1 to wound from Lance (objective target)")
                    elif bondsman_lance and not self.is_lance():
                        wound_result['modifiers'].append("+1 to wound from Lance (Bondsman)")
                    elif blood_tithe_lance and not self.is_lance():
                        wound_result['modifiers'].append("+1 to wound from Lance (Blood Tithe)")
                    elif daemonic_fury_lance and not self.is_lance():
                        wound_result['modifiers'].append("+1 to wound from Lance (Daemonic Fury)")
                    elif goretrack_lance and not self.is_lance():
                        wound_result['modifiers'].append("+1 to wound from Lance (Goretrack Onslaught)")
                    else:
                        wound_result['modifiers'].append("+1 to wound from Lance (charged)")
        except Exception:
            pass

        # Templar Vows: Accept Any Challenge, No Matter the Odds.
        try:
            is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
            if is_melee:
                army = attacker.parent_unit.get_parent_army()
                mgr = getattr(army, "templar_vows", None) if army is not None else None
                if mgr is not None and mgr.melee_wound_bonus_applies(
                    attacker.parent_unit,
                    target,
                    strength=strength,
                    target_toughness=target_toughness,
                ):
                    dice_modifier += 1
                    wound_result['modifiers'].append("+1 to wound from Accept Any Challenge")
        except Exception:
            pass

        # Oath of Moment: +1 to wound vs the selected target (Codex: Space Marines detachment only).
        try:
            army = attacker.parent_unit.get_parent_army()
            mgr = getattr(army, "oath_of_moment", None) if army is not None else None
            if mgr is not None and mgr.wound_bonus_applies(attacker.parent_unit, target):
                dice_modifier += 1
                wound_result['modifiers'].append("+1 to wound from Oath of Moment")
        except Exception:
            pass
        # Movement phase selected target wound bonus (e.g., Aeldari).
        try:
            attacker_unit = getattr(attacker, "parent_unit", None)
            army = attacker_unit.get_parent_army() if attacker_unit is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            bonus, reason = target.get_movement_phase_visible_wound_bonus(attacker_unit, game=game)
            if bonus:
                dice_modifier += int(bonus)
                wound_result['modifiers'].append(reason or f"+{int(bonus)} to wound from Movement phase bonus")
        except Exception:
            pass
        # Dark Ritual (once per battle): +1 to wound until end of turn.
        try:
            attacker_unit = getattr(attacker, "parent_unit", None)
            if attacker_unit is not None and hasattr(attacker_unit, "get_dark_ritual_bonuses"):
                army = attacker_unit.get_parent_army() if attacker_unit is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                _hit_bonus, wound_bonus, source = attacker_unit.get_dark_ritual_bonuses(game=game)
                if wound_bonus:
                    dice_modifier += int(wound_bonus)
                    wound_result['modifiers'].append(f"+{int(wound_bonus)} to wound from {source}")
        except Exception:
            pass
        # Thousand Sons: Grand Coven (Psychic Maelstrom).
        try:
            army = attacker.parent_unit.get_parent_army()
            mgr = getattr(army, "thousand_sons_detachments", None) if army is not None else None
            if mgr is not None and callable(getattr(mgr, "grand_coven_psychic_wound_bonus", None)):
                game = getattr(getattr(army, "player", None), "game", None)
                bonus = int(mgr.grand_coven_psychic_wound_bonus(attacker, self, game=game) or 0)
                if bonus:
                    dice_modifier += bonus
                    wound_result['modifiers'].append(f"+{bonus} to wound from Psychic Maelstrom")
        except Exception:
            pass
        # Adepta Sororitas: The Blood of Martyrs (Hallowed Martyrs).
        unit = getattr(attacker, "parent_unit", None)
        army = (
            unit.get_parent_army()
            if unit is not None and hasattr(unit, "get_parent_army") and hasattr(unit, "parent_army")
            else None
        )
        mgr = getattr(army, "adepta_sororitas_detachments", None) if army is not None else None
        bonus_fn = getattr(mgr, "blood_of_martyrs_wound_bonus", None) if mgr is not None else None
        if callable(bonus_fn):
            bonus, reason = bonus_fn(attacker, unit)
            if bonus:
                dice_modifier += int(bonus)
                wound_result['modifiers'].append(
                    reason or f"+{int(bonus)} to wound from The Blood of Martyrs"
                )
        # Adeptus Custodes: Against All Odds (+1 to wound when isolated).
        unit = getattr(attacker, "parent_unit", None)
        army = None
        if unit is not None and hasattr(unit, "get_parent_army") and hasattr(unit, "parent_army"):
            army = unit.get_parent_army()
        mgr = getattr(army, "adeptus_custodes_detachments", None) if army is not None else None
        if mgr is not None and callable(getattr(mgr, "against_all_odds_wound_bonus", None)):
            game = getattr(getattr(army, "player", None), "game", None)
            game_map = getattr(game, "map", None) if game is not None else None
            if game_map is None:
                game_map = self._get_game_map_from_model(attacker)
            bonus = int(mgr.against_all_odds_wound_bonus(attacker, target, game=game, game_map=game_map) or 0)
            if bonus:
                dice_modifier += bonus
                wound_result['modifiers'].append(f"+{bonus} to wound from Against All Odds")
        # Drukhari: Power from Pain (Sculptor of Torments).
        try:
            is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
            if is_melee:
                w_bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("pain_melee_wound_bonus", 0) or 0)
                if w_bonus:
                    dice_modifier += w_bonus
                    wound_result['modifiers'].append(f"+{w_bonus} to wound from Power from Pain (melee)")
        except Exception:
            pass
        # Drukhari: Power from Pain (Deadly Retinue) - defensive wound penalty.
        try:
            is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
            if is_melee:
                tsr = getattr(target, "special_rules", None)
                if isinstance(tsr, dict):
                    mod = int(tsr.get("pain_melee_wound_roll_defense_mod", 0) or 0)
                    if mod:
                        dice_modifier += int(mod)
                        wound_result['modifiers'].append(f"{mod} to wound from Power from Pain (defense)")
        except Exception:
            pass
        # Harbingers of Dread: Doom (+1 to wound vs Battle-shocked targets).
        try:
            army = attacker.parent_unit.get_parent_army()
            mgr = getattr(army, "harbingers_of_dread", None) if army is not None else None
            if mgr is not None:
                from ..rules.harbingers_of_dread import DOOM
                if mgr.is_dread_active(DOOM.key, unit=attacker.parent_unit):
                    try:
                        if target.is_battle_shocked():
                            dice_modifier += 1
                            wound_result['modifiers'].append("+1 to wound from Doom (Harbingers of Dread)")
                    except Exception:
                        pass
        except Exception:
            pass
        # Leagues of Votann: Prioritised Efficiency (Fortify Takeover -1 to wound vs non-vehicle).
        try:
            target_army = target.get_parent_army()
            mgr = getattr(target_army, "prioritised_efficiency", None) if target_army is not None else None
            if mgr is not None:
                delta, reason = mgr.wound_roll_penalty(target, strength=strength, toughness=target_toughness)
                if delta:
                    dice_modifier += int(delta)
                    if reason:
                        wound_result['modifiers'].append(reason)
        except Exception:
            pass
        # Necrons: Merciless Reclamation (+1 to wound vs targets within objective range).
        try:
            unit = getattr(attacker, "parent_unit", None)
            root = unit.get_attached_unit_root() if unit is not None and hasattr(unit, "get_attached_unit_root") else unit
            sr = getattr(root, "special_rules", None) if root is not None else None
            if isinstance(sr, dict) and sr.get("merciless_reclamation_active"):
                apply_bonus = True
                exp = str(sr.get("merciless_reclamation_expires_phase", "") or "").strip().upper()
                if exp:
                    try:
                        army = root.get_parent_army()
                        game = getattr(getattr(army, "player", None), "game", None)
                        pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    except Exception:
                        pname = ""
                    if pname and pname != exp:
                        apply_bonus = False
                if apply_bonus:
                    game = None
                    try:
                        army = root.get_parent_army()
                        game = getattr(getattr(army, "player", None), "game", None)
                    except Exception:
                        game = None
                    game_map = getattr(game, "map", None) if game is not None else None
                    try:
                        if callable(getattr(root, "_target_within_objective_range", None)):
                            if root._target_within_objective_range(target, game_map):
                                dice_modifier += 1
                                wound_result['modifiers'].append("+1 to wound from Merciless Reclamation")
                    except Exception:
                        pass
        except Exception:
            pass

        # Friendly aura roll modifiers (e.g. "Beacons of Rage (Aura)")
        if getattr(aura_mods, "wound", 0):
            dice_modifier += int(aura_mods.wound)
            wound_result['modifiers'].extend(list(getattr(aura_mods, "wound_reasons", ()) or ()))

        # Attached leader leading bonuses (e.g., leading melee/ranged wound buffs)
        lead_mods = None
        unit_wound_mods = None
        try:
            unit = attacker.parent_unit
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
            attack_type = "melee" if is_melee else "ranged"
            lead_mods = root.get_leading_attack_roll_modifiers(attack_type, target=target)
            if isinstance(lead_mods, dict) and int(lead_mods.get("wound", 0) or 0):
                bonus = int(lead_mods.get("wound", 0) or 0)
                dice_modifier += bonus
                wound_result['modifiers'].extend(list(lead_mods.get("wound_reasons", ()) or ()))
            unit_wound_mods = unit.get_unit_wound_reroll_modifiers(attack_type, target=target)
            if isinstance(unit_wound_mods, dict) and int(unit_wound_mods.get("wound", 0) or 0):
                bonus = int(unit_wound_mods.get("wound", 0) or 0)
                dice_modifier += bonus
                wound_result['modifiers'].extend(list(unit_wound_mods.get("wound_reasons", ()) or ()))
        except Exception:
            lead_mods = None
            unit_wound_mods = None

        # Model-specific: attack roll modifiers from parsed ability text.
        try:
            model_attack_mods = attack_instance.get("_model_attack_mods")
            if model_attack_mods is None:
                unit = attacker.parent_unit
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                attack_type = "melee" if is_melee else "ranged"
                model_attack_mods = unit.model_attack_roll_modifiers_vs_weakened_target(
                    attacker,
                    attack_type=attack_type,
                    target=target,
                )
                attack_instance["_model_attack_mods"] = model_attack_mods
            if isinstance(model_attack_mods, dict) and int(model_attack_mods.get("wound", 0) or 0):
                bonus = int(model_attack_mods.get("wound", 0) or 0)
                dice_modifier += bonus
                wound_result['modifiers'].extend(list(model_attack_mods.get("wound_reasons", ()) or ()))
        except Exception:
            pass

        crit_wound_threshold = None
        crit_wound_reasons: list[str] = []
        try:
            if aura_mods is not None and getattr(aura_mods, "crit_wound_threshold", None):
                crit_wound_threshold = int(aura_mods.crit_wound_threshold)
                crit_wound_reasons.extend(list(getattr(aura_mods, "crit_wound_reasons", ()) or ()))
        except Exception:
            pass
        try:
            if isinstance(lead_mods, dict) and lead_mods.get("crit_wound_threshold"):
                val = int(lead_mods.get("crit_wound_threshold"))
                crit_wound_threshold = val if crit_wound_threshold is None else min(int(crit_wound_threshold), val)
                crit_wound_reasons.extend(list(lead_mods.get("crit_wound_reasons", ()) or ()))
        except Exception:
            pass
        try:
            if isinstance(unit_wound_mods, dict) and unit_wound_mods.get("crit_wound_threshold"):
                val = int(unit_wound_mods.get("crit_wound_threshold"))
                crit_wound_threshold = val if crit_wound_threshold is None else min(int(crit_wound_threshold), val)
                crit_wound_reasons.extend(list(unit_wound_mods.get("crit_wound_reasons", ()) or ()))
        except Exception:
            pass
        try:
            if isinstance(unit_wound_mods, dict):
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                if is_melee:
                    unit = attacker.parent_unit
                    root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
                    sr = getattr(root, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("daemonic_patrons_active"):
                        exp = str(sr.get("daemonic_patrons_expires_phase", "") or "").strip().upper()
                        pname = ""
                        try:
                            game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                            pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            pname = ""
                        if not exp or (pname and pname == exp):
                            val = int(sr.get("daemonic_patrons_crit_wound_threshold", 0) or 0)
                            if val:
                                crit_wound_threshold = val if crit_wound_threshold is None else min(int(crit_wound_threshold), val)
                                src = str(sr.get("daemonic_patrons_source", "") or "Daemonic Patrons").strip()
                                crit_wound_reasons.append(f"{src}: critical wound on {val}+")
        except Exception:
            pass

        wound_result["crit_threshold"] = int(crit_wound_threshold or 6)

        # Space Marines: Dutiful Tenacity (Wrath of the Rock) -1 to wound if Strength > Toughness.
        target_army = target.get_parent_army() if target is not None and hasattr(target, "get_parent_army") else None
        mgr = getattr(target_army, "space_marines_detachments", None) if target_army is not None else None
        if mgr is not None and hasattr(mgr, "dutiful_tenacity_wound_roll_penalty"):
            penalty, reason = mgr.dutiful_tenacity_wound_roll_penalty(
                target,
                strength=strength,
                target_toughness=target_toughness,
            )
            if penalty:
                dice_modifier -= int(penalty)
                label = reason or "Dutiful Tenacity"
                wound_result['modifiers'].append(f"-{int(penalty)} to wound from {label}")

        # First Prince of Chaos (Shadow Legion Nurgle): -1 to wound if Strength > Toughness.
        try:
            if hasattr(target, "has_first_prince_nurgle_defense") and target.has_first_prince_nurgle_defense():
                if isinstance(strength, int) and isinstance(target_toughness, int) and strength > target_toughness:
                    dice_modifier -= 1
                    wound_result['modifiers'].append("-1 to wound from First Prince of Chaos (Nurgle)")
        except Exception:
            pass

        # Defensive reaction stratagems: -1 to wound (generic template).
        try:
            try:
                troot = target.get_attached_unit_root()
            except Exception:
                troot = target
            attack_type = "melee" if (self.parent_wargear and self.parent_wargear.is_melee()) else "ranged"
            attacker_key = attack_instance.get("attacker_key")
            if not attacker_key:
                try:
                    attacker_unit = getattr(attacker, "parent_unit", None)
                    if attacker_unit is not None:
                        attacker_root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
                        attacker_key = get_entity_id(attacker_root)
                except Exception:
                    attacker_key = None
            phase_key = self._resolve_phase_key(attacker_unit=getattr(attacker, "parent_unit", None), target_unit=troot)
            for entry in self._iter_defensive_entries(
                troot,
                "defensive_wound_mods",
                attacker_key=attacker_key,
                attack_type=attack_type,
                phase_key=phase_key,
            ):
                try:
                    if entry.get("requires_strength_gt_toughness"):
                        if not (isinstance(strength, int) and isinstance(target_toughness, int) and strength > target_toughness):
                            continue
                except Exception:
                    pass
                penalty = int(entry.get("value", 0) or 0)
                if penalty:
                    dice_modifier -= penalty
                    src = entry.get("source") or "Defensive stratagem"
                    wound_result['modifiers'].append(f"-{penalty} to wound from {src}")
        except Exception:
            pass

        dice_modifier = min(max(dice_modifier, -1), 1)

        dice_roll = None
        miracle_used = False
        if roll_value is not None:
            try:
                dice_roll = int(roll_value)
            except Exception:
                dice_roll = None
        if dice_roll is None:
            try:
                unit = attacker.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr is not None and mgr.can_use_act_of_faith(unit, game=game):
                    final_needed = None
                    try:
                        if isinstance(strength, int) and isinstance(target_toughness, int):
                            if strength >= 2 * target_toughness:
                                final_needed = 2
                            elif strength > target_toughness:
                                final_needed = 3
                            elif strength == target_toughness:
                                final_needed = 4
                            elif strength * 2 <= target_toughness:
                                final_needed = 6
                            else:
                                final_needed = 5
                            final_needed = int(final_needed) - int(dice_modifier)
                            final_needed = min(max(final_needed, 2), 6)
                    except Exception:
                        final_needed = None
                    dice_roll, _dice, miracle_used = mgr.resolve_roll(
                        unit,
                        roll_type="wound",
                        game=game,
                        dice_count=1,
                        die_faces=6,
                        needed=final_needed,
                    )
            except Exception:
                dice_roll = None
                miracle_used = False
        if dice_roll is None:
            dice_roll = get_roll("D6")
        if log_roll:
            try:
                weapon_name_for_log = getattr(self, 'parent_wargear', None).name if getattr(self, 'parent_wargear', None) else getattr(self, 'name', 'Weapon')
                if miracle_used:
                    append_dice(attacker.parent_unit.get_parent_army().player, f"Miracle die used for Wound roll: {dice_roll} vs T{target_toughness} by {attacker.name} with {weapon_name_for_log}")
                else:
                    append_dice(attacker.parent_unit.get_parent_army().player, f"Wound roll: {dice_roll} vs T{target_toughness} by {attacker.name} with {weapon_name_for_log}")
            except Exception:
                pass
        if miracle_used:
            wound_result['special_effects'].append("Miracle die")

        # Value-based and full rerolls from aura/leading/unit rules.
        reroll_used = False
        reroll_wound_values = set()
        reroll_value_reasons: list[str] = []
        reroll_full_reasons: list[str] = []
        try:
            if aura_mods is not None:
                for v in list(getattr(aura_mods, "reroll_wound_values", ()) or ()):
                    try:
                        reroll_wound_values.add(int(v))
                    except Exception:
                        continue
                if bool(getattr(aura_mods, "reroll_wound_ones", False)):
                    reroll_wound_values.add(1)
                reroll_value_reasons.extend(list(getattr(aura_mods, "reroll_wound_reasons", ()) or ()))
                if bool(getattr(aura_mods, "reroll_wound_full", False)):
                    reroll_full_reasons.extend(list(getattr(aura_mods, "reroll_wound_full_reasons", ()) or ()))
        except Exception:
            pass
        try:
            if isinstance(lead_mods, dict):
                for v in list(lead_mods.get("reroll_wound_values", ()) or ()):
                    try:
                        reroll_wound_values.add(int(v))
                    except Exception:
                        continue
                if bool(lead_mods.get("reroll_wound_ones", False)):
                    reroll_wound_values.add(1)
                reroll_value_reasons.extend(list(lead_mods.get("reroll_wound_reasons", ()) or ()))
                if bool(lead_mods.get("reroll_wound_full", False)):
                    reroll_full_reasons.extend(list(lead_mods.get("reroll_wound_full_reasons", ()) or ()))
        except Exception:
            pass
        try:
            if isinstance(unit_wound_mods, dict):
                for v in list(unit_wound_mods.get("reroll_wound_values", ()) or ()):
                    try:
                        reroll_wound_values.add(int(v))
                    except Exception:
                        continue
                if bool(unit_wound_mods.get("reroll_wound_ones", False)):
                    reroll_wound_values.add(1)
                reroll_value_reasons.extend(list(unit_wound_mods.get("reroll_wound_reasons", ()) or ()))
                if bool(unit_wound_mods.get("reroll_wound_full", False)):
                    reroll_full_reasons.extend(list(unit_wound_mods.get("reroll_wound_full_reasons", ()) or ()))
        except Exception:
            pass
        try:
            unit = attacker.parent_unit
            model_wound_mods = attack_instance.get("_model_wound_reroll_mods")
            if model_wound_mods is None:
                model_wound_mods = unit.get_model_wound_reroll_modifiers(attacker, attack_type=attack_type, target=target)
                attack_instance["_model_wound_reroll_mods"] = model_wound_mods
            if isinstance(model_wound_mods, dict):
                for v in list(model_wound_mods.get("reroll_wound_values", ()) or ()):
                    try:
                        reroll_wound_values.add(int(v))
                    except Exception:
                        continue
                reroll_value_reasons.extend(list(model_wound_mods.get("reroll_wound_reasons", ()) or ()))
                if bool(model_wound_mods.get("reroll_wound_full", False)):
                    reroll_full_reasons.extend(list(model_wound_mods.get("reroll_wound_full_reasons", ()) or ()))
        except Exception:
            pass
        try:
            unit = getattr(attacker, "parent_unit", None)
            army = unit.get_parent_army() if unit is not None else None
            mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
            if mgr is not None and callable(getattr(mgr, "methodical_annihilation_reroll_wound_ones", None)):
                game_map = self._get_game_map_from_model(attacker)
                if mgr.methodical_annihilation_reroll_wound_ones(attacker, self, target, game_map=game_map):
                    reroll_wound_values.add(1)
                    reroll_value_reasons.append("Methodical Annihilation: re-roll Wound roll of 1")
        except Exception:
            pass
        # Contextual reroll sources carried on the attack instance (best-effort).
        try:
            rule = attack_instance.get("closest_monster_vehicle_reroll_rule")
            if rule and bool(rule.get("reroll_wound")):
                reason = str(rule.get("source", "") or "Closest eligible MONSTER/VEHICLE").strip() or "Closest eligible MONSTER/VEHICLE"
                reroll_full_reasons.append(reason)
        except Exception:
            pass
        try:
            rule = attack_instance.get("monster_vehicle_reroll_rule")
            if rule and bool(rule.get("reroll_wound")):
                reason = str(rule.get("source", "") or "Monster/Vehicle rerolls").strip() or "Monster/Vehicle rerolls"
                reroll_full_reasons.append(reason)
        except Exception:
            pass
        # Twin-linked grants reroll of wound rolls.
        try:
            twin_linked_active = False
            if self.is_twin_linked():
                twin_linked_active = True
            bonus_twin_linked = bool(attack_instance.get("bonus_twin_linked"))
            if bonus_twin_linked:
                twin_linked_active = True
            # Daemonic Fury twin-linked (melee) special case.
            daemonic_fury_twin_linked = False
            try:
                unit = getattr(attacker, "parent_unit", None)
                sr = getattr(unit, "special_rules", None) if unit is not None else None
                if isinstance(sr, dict) and sr.get("daemonic_fury_twin_linked_active") is True:
                    is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                    if is_melee:
                        expires_phase = str(sr.get("daemonic_fury_twin_linked_expires_phase", "") or "")
                        if expires_phase:
                            phase_key = self._resolve_phase_key(attacker_unit=unit, target_unit=target)
                            if phase_key and expires_phase != phase_key:
                                is_melee = False
                    if is_melee:
                        twin_linked_active = True
                        daemonic_fury_twin_linked = True
            except Exception:
                pass
            if twin_linked_active:
                if daemonic_fury_twin_linked and not self.is_twin_linked():
                    reroll_full_reasons.append("Twin-linked (Daemonic Fury)")
                elif bonus_twin_linked and not self.is_twin_linked():
                    reroll_full_reasons.append("Twin-linked (objective target)")
                else:
                    reroll_full_reasons.append("Twin-linked (re-roll failed wound)")
        except Exception:
            pass

        wound_result["reroll_values"] = list(sorted(reroll_wound_values))
        wound_result["reroll_value_reasons"] = list(reroll_value_reasons)
        wound_result["reroll_full_reasons"] = list(reroll_full_reasons)

        if rerolls_allowed:
            try:
                if rerolls_allowed and dice_roll in reroll_wound_values and "reroll" not in wound_result:
                    rr = _reroll_wound()
                    if reroll_value_reasons:
                        wound_result.setdefault("special_effects", []).extend(reroll_value_reasons)
                    else:
                        wound_result.setdefault("special_effects", []).append("Re-roll Wound roll")
                    if dice_roll == 1:
                        wound_result["reroll_of_one"] = 1
                    wound_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
            except Exception:
                pass

        if rerolls_allowed:
            try:
                if rerolls_allowed and reroll_full_reasons and "reroll" not in wound_result:
                    needed = 0
                    try:
                        s_val = strength
                        t_val = target_toughness
                        if isinstance(s_val, int) and isinstance(t_val, int):
                            if s_val >= 2 * t_val:
                                needed = 2
                            elif s_val > t_val:
                                needed = 3
                            elif s_val == t_val:
                                needed = 4
                            elif s_val * 2 <= t_val:
                                needed = 6
                            else:
                                needed = 5
                    except Exception:
                        needed = 0
                    final_needed = needed
                    try:
                        final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                    except Exception:
                        pass
                    try:
                        success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        unit = attacker.parent_unit
                        game = unit.get_parent_army().player.game
                        player = unit.get_parent_army().player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                    reason = reroll_full_reasons[0] if reroll_full_reasons else "Unit ability"
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="wound",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason=reason,
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll:
                        rr = _reroll_wound()
                        wound_result.setdefault("special_effects", []).extend(reroll_full_reasons)
                        wound_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
            except Exception:
                pass

        # Grey Knights: Fury of Titan (Deep Strike) re-roll Wound rolls of 1.
        try:
            if rerolls_allowed and dice_roll == 1 and "reroll" not in wound_result:
                unit = attacker.parent_unit
                sr = getattr(unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("fury_of_titan_active"):
                    rr = _reroll_wound()
                    wound_result.setdefault("special_effects", []).append("Fury of Titan: re-roll Wound roll of 1")
                    wound_result["reroll_of_one"] = 1
                    wound_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # Closest eligible MONSTER/VEHICLE target: re-roll Wound roll (optional).
        try:
            rule = attack_instance.get("closest_monster_vehicle_reroll_rule")
            if rerolls_allowed and rule and rule.get("reroll_wound") and "reroll" not in wound_result:
                needed = 0
                try:
                    s_val = strength
                    t_val = target_toughness
                    if isinstance(s_val, int) and isinstance(t_val, int):
                        if s_val >= 2 * t_val:
                            needed = 2
                        elif s_val > t_val:
                            needed = 3
                        elif s_val == t_val:
                            needed = 4
                        elif s_val * 2 <= t_val:
                            needed = 6
                        else:
                            needed = 5
                except Exception:
                    needed = 0
                final_needed = needed
                try:
                    final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                except Exception:
                    pass
                try:
                    success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                except Exception:
                    success = False
                do_reroll = False
                try:
                    unit = attacker.parent_unit
                    game = unit.get_parent_army().player.game
                    player = unit.get_parent_army().player
                    is_human = bool(getattr(player, "has_control", lambda: False)())
                    provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                except Exception:
                    is_human = False
                    provider = None
                    player = None
                reason = str(rule.get("source", "") or "").strip() or "Closest eligible MONSTER/VEHICLE"
                if is_human and callable(provider):
                    try:
                        do_reroll = bool(provider(
                            player=player,
                            unit=unit,
                            roll_type="wound",
                            value=dice_roll,
                            dice=None,
                            needed=final_needed,
                            success=success,
                            reason=reason,
                        ))
                    except Exception:
                        do_reroll = False
                else:
                    do_reroll = (not success)
                if do_reroll:
                    rr = _reroll_wound()
                    wound_result.setdefault("special_effects", []).append(
                        f"{reason}: re-roll Wound roll"
                    )
                    wound_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # MONSTER/VEHICLE target: re-roll Wound roll (optional).
        try:
            rule = attack_instance.get("monster_vehicle_reroll_rule")
            if rerolls_allowed and rule and rule.get("reroll_wound") and "reroll" not in wound_result:
                needed = 0
                try:
                    s_val = strength
                    t_val = target_toughness
                    if isinstance(s_val, int) and isinstance(t_val, int):
                        if s_val >= 2 * t_val:
                            needed = 2
                        elif s_val > t_val:
                            needed = 3
                        elif s_val == t_val:
                            needed = 4
                        elif s_val * 2 <= t_val:
                            needed = 6
                        else:
                            needed = 5
                except Exception:
                    needed = 0
                final_needed = needed
                try:
                    final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                except Exception:
                    pass
                try:
                    success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                except Exception:
                    success = False
                do_reroll = False
                try:
                    unit = attacker.parent_unit
                    game = unit.get_parent_army().player.game
                    player = unit.get_parent_army().player
                    is_human = bool(getattr(player, "has_control", lambda: False)())
                    provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                except Exception:
                    is_human = False
                    provider = None
                    player = None
                reason = str(rule.get("source", "") or "").strip() or "Monster/Vehicle rerolls"
                if is_human and callable(provider):
                    try:
                        do_reroll = bool(provider(
                            player=player,
                            unit=unit,
                            roll_type="wound",
                            value=dice_roll,
                            dice=None,
                            needed=final_needed,
                            success=success,
                            reason=reason,
                        ))
                    except Exception:
                        do_reroll = False
                else:
                    do_reroll = (not success)
                if do_reroll:
                    rr = _reroll_wound()
                    wound_result.setdefault("special_effects", []).append(
                        f"{reason}: re-roll Wound roll"
                    )
                    wound_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # Emperor's Children: Pledges to the Dark Prince (3+) re-roll Wound rolls of 1.
        try:
            if rerolls_allowed and dice_roll == 1 and "reroll" not in wound_result:
                unit = attacker.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is not None and mgr.pact_points_at_least(3) and mgr.is_emperors_children_unit(unit):
                    rr = _reroll_wound()
                    wound_result.setdefault("special_effects", []).append("Pledges to the Dark Prince: re-roll Wound roll of 1")
                    wound_result["reroll_of_one"] = 1
                    wound_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # Emperor's Children: Mechanised Murder re-roll Wound rolls of 1.
        try:
            if rerolls_allowed and dice_roll == 1 and "reroll" not in wound_result:
                unit = attacker.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is not None and mgr.mechanised_murder_applies(unit):
                    rr = _reroll_wound()
                    wound_result.setdefault("special_effects", []).append("Mechanised Murder: re-roll Wound roll of 1")
                    wound_result["reroll_of_one"] = 1
                    wound_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # Seductive Gambit: melee attacks can re-roll Wound rolls of 1.
        try:
            if rerolls_allowed and dice_roll == 1 and "reroll" not in wound_result:
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                if is_melee:
                    unit = attacker.parent_unit
                    if hasattr(unit, "_seductive_gambit_active") and unit._seductive_gambit_active():
                        rr = _reroll_wound()
                        wound_result.setdefault("special_effects", []).append("Seductive Gambit: re-roll Wound roll of 1")
                        wound_result["reroll_of_one"] = 1
                        wound_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # Rage-cursed Onslaught: Maddened Ferocity re-roll Wound rolls of 1 (melee).
        try:
            if rerolls_allowed and dice_roll == 1 and "reroll" not in wound_result:
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                if is_melee:
                    unit = attacker.parent_unit
                    army = unit.get_parent_army() if unit is not None else None
                    mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
                    if mgr is not None and getattr(mgr, "is_rage_cursed_onslaught", lambda: False)():
                        if getattr(mgr, "unit_is_adeptus_astartes", lambda _u: False)(unit):
                            rr = _reroll_wound()
                            wound_result.setdefault("special_effects", []).append("Maddened Ferocity: re-roll Wound roll of 1")
                            wound_result["reroll_of_one"] = 1
                            wound_result["reroll"] = rr
                            dice_roll = rr
                            reroll_used = True
        except Exception:
            pass

        pain_objective_reroll = False
        try:
            sr = getattr(attacker.parent_unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_reroll_wound_full_if_objective"):
                try:
                    unit = attacker.parent_unit
                    army = unit.get_parent_army() if unit is not None else None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                except Exception:
                    game = None
                if game is not None and hasattr(game, "_unit_within_range_of_objective"):
                    pain_objective_reroll = bool(game._unit_within_range_of_objective(target))
        except Exception:
            pain_objective_reroll = False

        # Drukhari: Power from Pain (Sadistic Raiders) re-roll Wound roll if target is on an objective (optional).
        try:
            if rerolls_allowed and pain_objective_reroll and "reroll" not in wound_result:
                needed = 0
                try:
                    s_val = strength
                    t_val = target_toughness
                    if isinstance(s_val, int) and isinstance(t_val, int):
                        if s_val >= 2 * t_val:
                            needed = 2
                        elif s_val > t_val:
                            needed = 3
                        elif s_val == t_val:
                            needed = 4
                        elif s_val * 2 <= t_val:
                            needed = 6
                        else:
                            needed = 5
                except Exception:
                    needed = 0
                final_needed = needed
                try:
                    final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                except Exception:
                    pass
                try:
                    success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                except Exception:
                    success = False
                do_reroll = False
                try:
                    unit = attacker.parent_unit
                    game = unit.get_parent_army().player.game
                    player = unit.get_parent_army().player
                    is_human = bool(getattr(player, "has_control", lambda: False)())
                    provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                except Exception:
                    is_human = False
                    provider = None
                    player = None
                if is_human and callable(provider):
                    try:
                        do_reroll = bool(provider(
                            player=player,
                            unit=unit,
                            roll_type="wound",
                            value=dice_roll,
                            dice=None,
                            needed=final_needed,
                            success=success,
                            reason="Power from Pain (Sadistic Raiders)",
                        ))
                    except Exception:
                        do_reroll = False
                else:
                    do_reroll = (not success)
                if do_reroll:
                    rr = _reroll_wound()
                    wound_result.setdefault("special_effects", []).append("Power from Pain: re-roll Wound roll (objective)")
                    wound_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # Drukhari: Power from Pain (Sadistic Raiders) re-roll Wound rolls of 1.
        try:
            if rerolls_allowed and (not pain_objective_reroll) and dice_roll == 1 and "reroll" not in wound_result:
                sr = getattr(attacker.parent_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("pain_reroll_wound_ones"):
                    rr = _reroll_wound()
                    wound_result.setdefault("special_effects", []).append("Power from Pain: re-roll Wound roll of 1")
                    wound_result["reroll_of_one"] = 1
                    wound_result["reroll"] = rr
                    dice_roll = rr
                    reroll_used = True
        except Exception:
            pass

        # Drukhari: Power from Pain (Goaded Savagery) re-roll Wound rolls for non-character melee attacks (optional).
        try:
            if rerolls_allowed and "reroll" not in wound_result:
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                if is_melee and not bool(getattr(attacker, "is_character", False)):
                    sr = getattr(attacker.parent_unit, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("pain_beast_reroll_wound"):
                        needed = 0
                        try:
                            s_val = strength
                            t_val = target_toughness
                            if isinstance(s_val, int) and isinstance(t_val, int):
                                if s_val >= 2 * t_val:
                                    needed = 2
                                elif s_val > t_val:
                                    needed = 3
                                elif s_val == t_val:
                                    needed = 4
                                elif s_val * 2 <= t_val:
                                    needed = 6
                                else:
                                    needed = 5
                        except Exception:
                            needed = 0
                        final_needed = needed
                        try:
                            final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                        except Exception:
                            pass
                        try:
                            success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                        except Exception:
                            success = False
                        do_reroll = False
                        try:
                            unit = attacker.parent_unit
                            game = unit.get_parent_army().player.game
                            player = unit.get_parent_army().player
                            is_human = bool(getattr(player, "has_control", lambda: False)())
                            provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        except Exception:
                            is_human = False
                            provider = None
                            player = None
                        if is_human and callable(provider):
                            try:
                                do_reroll = bool(provider(
                                    player=player,
                                    unit=unit,
                                    roll_type="wound",
                                    value=dice_roll,
                                    dice=None,
                                    needed=final_needed,
                                    success=success,
                                    reason="Power from Pain (Goaded Savagery)",
                                ))
                            except Exception:
                                do_reroll = False
                        else:
                            do_reroll = (not success)
                        if do_reroll:
                            rr = _reroll_wound()
                            wound_result.setdefault("special_effects", []).append("Power from Pain: re-roll Wound roll (beast melee)")
                            wound_result["reroll"] = rr
                            dice_roll = rr
                            reroll_used = True
        except Exception:
            pass

        # Emperor's Children: Internal Rivalries (Favoured Champions) re-roll Wound roll (optional).
        try:
            if rerolls_allowed and "reroll" not in wound_result:
                unit = attacker.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is not None and mgr.is_favoured_champions(unit):
                    needed = 0
                    try:
                        s_val = strength
                        t_val = target_toughness
                        if isinstance(s_val, int) and isinstance(t_val, int):
                            if s_val >= 2 * t_val:
                                needed = 2
                            elif s_val > t_val:
                                needed = 3
                            elif s_val == t_val:
                                needed = 4
                            elif s_val * 2 <= t_val:
                                needed = 6
                            else:
                                needed = 5
                    except Exception:
                        needed = 0
                    final_needed = needed
                    try:
                        final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                    except Exception:
                        pass
                    try:
                        success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        game = army.player.game if army is not None else None
                        player = army.player if army is not None else None
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="wound",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason="Internal Rivalries (Favoured Champions)",
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll:
                        rr = _reroll_wound()
                        wound_result.setdefault("special_effects", []).append("Internal Rivalries: re-roll Wound roll (Favoured Champions)")
                        wound_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # Bondsman: Atrapos's Duty re-roll Wound rolls vs TITANIC/TOWERING targets.
        try:
            if rerolls_allowed and "reroll" not in wound_result:
                unit = attacker.parent_unit
                sr = getattr(unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("bondsman_reroll_hit_wound_vs_titanic"):
                    try:
                        is_big = bool(getattr(target, "is_titanic", False) or getattr(target, "is_towering", False))
                    except Exception:
                        is_big = False
                    if is_big:
                        needed = 0
                        try:
                            s_val = strength
                            t_val = target_toughness
                            if isinstance(s_val, int) and isinstance(t_val, int):
                                if s_val >= 2 * t_val:
                                    needed = 2
                                elif s_val > t_val:
                                    needed = 3
                                elif s_val == t_val:
                                    needed = 4
                                elif s_val * 2 <= t_val:
                                    needed = 6
                                else:
                                    needed = 5
                        except Exception:
                            needed = 0
                        final_needed = needed
                        try:
                            final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                        except Exception:
                            pass
                        try:
                            success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                        except Exception:
                            success = False
                        do_reroll = False
                        try:
                            army = unit.get_parent_army()
                            game = army.player.game
                            player = army.player
                            is_human = bool(getattr(player, "has_control", lambda: False)())
                            provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        except Exception:
                            is_human = False
                            provider = None
                            player = None
                        if is_human and callable(provider):
                            try:
                                do_reroll = bool(provider(
                                    player=player,
                                    unit=unit,
                                    roll_type="wound",
                                    value=dice_roll,
                                    dice=None,
                                    needed=final_needed,
                                    success=success,
                                    reason="Bondsman (Atrapos's Duty)",
                                ))
                            except Exception:
                                do_reroll = False
                        else:
                            do_reroll = (not success)
                        if do_reroll:
                            rr = _reroll_wound()
                            wound_result.setdefault("special_effects", []).append("Bondsman: re-roll Wound roll (Atrapos's Duty)")
                            wound_result["reroll"] = rr
                            dice_roll = rr
                            reroll_used = True
        except Exception:
            pass

        # Bondsman: Mentor re-roll Wound rolls vs this model's quarry.
        try:
            if rerolls_allowed and "reroll" not in wound_result:
                unit = attacker.parent_unit
                sr = getattr(unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("bondsman_reroll_wound_vs_quarry"):
                    quarry_ids = getattr(unit, "_bondsman_quarry_ids", None)
                    if not quarry_ids:
                        quarry_ids = getattr(unit, "_monarch_of_the_hunt_quarry_ids", None)
                    if quarry_ids:
                        try:
                            tid = getattr(target, "_id", None)
                            rid = getattr(target.get_attached_unit_root(), "_id", None)
                        except Exception:
                            tid = getattr(target, "_id", None)
                            rid = None
                        is_quarry = (tid in quarry_ids) or (rid in quarry_ids)
                        if is_quarry:
                            needed = 0
                            try:
                                s_val = strength
                                t_val = target_toughness
                                if isinstance(s_val, int) and isinstance(t_val, int):
                                    if s_val >= 2 * t_val:
                                        needed = 2
                                    elif s_val > t_val:
                                        needed = 3
                                    elif s_val == t_val:
                                        needed = 4
                                    elif s_val * 2 <= t_val:
                                        needed = 6
                                    else:
                                        needed = 5
                            except Exception:
                                needed = 0
                            final_needed = needed
                            try:
                                final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                            except Exception:
                                pass
                            try:
                                success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                            except Exception:
                                success = False
                            do_reroll = False
                            try:
                                army = unit.get_parent_army()
                                game = army.player.game
                                player = army.player
                                is_human = bool(getattr(player, "has_control", lambda: False)())
                                provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                            except Exception:
                                is_human = False
                                provider = None
                                player = None
                            if is_human and callable(provider):
                                try:
                                    do_reroll = bool(provider(
                                        player=player,
                                        unit=unit,
                                        roll_type="wound",
                                        value=dice_roll,
                                        dice=None,
                                        needed=final_needed,
                                        success=success,
                                        reason="Bondsman (Mentor)",
                                    ))
                                except Exception:
                                    do_reroll = False
                            else:
                                do_reroll = (not success)
                            if do_reroll:
                                rr = _reroll_wound()
                                wound_result.setdefault("special_effects", []).append("Bondsman: re-roll Wound roll (Mentor)")
                                wound_result["reroll"] = rr
                                dice_roll = rr
                                reroll_used = True
        except Exception:
            pass

        # Methodical Destruction: re-roll Wound roll vs this model's victim (optional).
        try:
            if rerolls_allowed and "reroll" not in wound_result:
                unit = attacker.parent_unit
                victim_ids = getattr(unit, "_methodical_destruction_victim_ids", None)
                if victim_ids:
                    try:
                        tid = getattr(target, "_id", None)
                        rid = getattr(target.get_attached_unit_root(), "_id", None)
                    except Exception:
                        tid = getattr(target, "_id", None)
                        rid = None
                    is_victim = (tid in victim_ids) or (rid in victim_ids)
                    if is_victim:
                        needed = 0
                        try:
                            s_val = strength
                            t_val = target_toughness
                            if isinstance(s_val, int) and isinstance(t_val, int):
                                if s_val >= 2 * t_val:
                                    needed = 2
                                elif s_val > t_val:
                                    needed = 3
                                elif s_val == t_val:
                                    needed = 4
                                elif s_val * 2 <= t_val:
                                    needed = 6
                                else:
                                    needed = 5
                        except Exception:
                            needed = 0
                        final_needed = needed
                        try:
                            final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                        except Exception:
                            pass
                        try:
                            success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                        except Exception:
                            success = False
                        do_reroll = False
                        try:
                            army = unit.get_parent_army()
                            game = army.player.game
                            player = army.player
                            is_human = bool(getattr(player, "has_control", lambda: False)())
                            provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        except Exception:
                            is_human = False
                            provider = None
                            player = None
                        reason = "Methodical Destruction"
                        if is_human and callable(provider):
                            try:
                                do_reroll = bool(provider(
                                    player=player,
                                    unit=unit,
                                    roll_type="wound",
                                    value=dice_roll,
                                    dice=None,
                                    needed=final_needed,
                                    success=success,
                                    reason=reason,
                                ))
                            except Exception:
                                do_reroll = False
                        else:
                            do_reroll = (not success)
                        if do_reroll:
                            rr = _reroll_wound()
                            wound_result.setdefault("special_effects", []).append(
                                "Methodical Destruction: re-roll Wound roll (victim)"
                            )
                            wound_result["reroll"] = rr
                            dice_roll = rr
                            reroll_used = True
        except Exception:
            pass

        # PREY SELECTION: re-roll Wound roll vs prey (optional).
        try:
            if rerolls_allowed and "reroll" not in wound_result:
                unit = attacker.parent_unit
                prey_ids = getattr(unit, "_prey_selection_prey_ids", None)
                if prey_ids and bool(getattr(unit, "_prey_selection_reroll_wound", False)):
                    melee_only = bool(getattr(unit, "_prey_selection_melee_only", False))
                    is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                    if (not melee_only) or is_melee:
                        try:
                            tid = getattr(target, "_id", None)
                            rid = getattr(target.get_attached_unit_root(), "_id", None)
                        except Exception:
                            tid = getattr(target, "_id", None)
                            rid = None
                        is_prey = (tid in prey_ids) or (rid in prey_ids)
                        if is_prey:
                            needed = 0
                            try:
                                s_val = strength
                                t_val = target_toughness
                                if isinstance(s_val, int) and isinstance(t_val, int):
                                    if s_val >= 2 * t_val:
                                        needed = 2
                                    elif s_val > t_val:
                                        needed = 3
                                    elif s_val == t_val:
                                        needed = 4
                                    elif s_val * 2 <= t_val:
                                        needed = 6
                                    else:
                                        needed = 5
                            except Exception:
                                needed = 0
                            final_needed = needed
                            try:
                                final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                            except Exception:
                                pass
                            try:
                                success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                            except Exception:
                                success = False
                            do_reroll = False
                            try:
                                army = unit.get_parent_army()
                                game = army.player.game
                                player = army.player
                                is_human = bool(getattr(player, "has_control", lambda: False)())
                                provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                            except Exception:
                                is_human = False
                                provider = None
                                player = None
                            reason = str(getattr(unit, "_prey_selection_source", "") or "Prey selection")
                            if is_human and callable(provider):
                                try:
                                    do_reroll = bool(provider(
                                        player=player,
                                        unit=unit,
                                        roll_type="wound",
                                        value=dice_roll,
                                        dice=None,
                                        needed=final_needed,
                                        success=success,
                                        reason=reason,
                                    ))
                                except Exception:
                                    do_reroll = False
                            else:
                                do_reroll = (not success)
                            if do_reroll:
                                rr = _reroll_wound()
                                wound_result.setdefault("special_effects", []).append(
                                    f"{reason}: re-roll Wound roll (prey)"
                                )
                                wound_result["reroll"] = rr
                                dice_roll = rr
                                reroll_used = True
        except Exception:
            pass

        # Code Chivalric: Martial Valour re-roll Wound roll (one per selection).
        try:
            if rerolls_allowed and "reroll" not in wound_result:
                unit = attacker.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "code_chivalric", None) if army is not None else None
                if mgr is not None and mgr.can_use_reroll(attacker, kind="wound"):
                    needed = 0
                    try:
                        s_val = strength
                        t_val = target_toughness
                        if isinstance(s_val, int) and isinstance(t_val, int):
                            if s_val >= 2 * t_val:
                                needed = 2
                            elif s_val > t_val:
                                needed = 3
                            elif s_val == t_val:
                                needed = 4
                            elif s_val * 2 <= t_val:
                                needed = 6
                            else:
                                needed = 5
                    except Exception:
                        needed = 0
                    final_needed = needed
                    try:
                        final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                    except Exception:
                        pass
                    try:
                        success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        game = army.player.game
                        player = army.player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="wound",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason="Code Chivalric",
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll and attacker.consume_code_chivalric_reroll("wound"):
                        rr = _reroll_wound()
                        wound_result.setdefault("special_effects", []).append("Code Chivalric: re-roll Wound roll")
                        wound_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # Selected to shoot: re-roll one Wound roll (one per selection).
        try:
            if rerolls_allowed and "reroll" not in wound_result:
                is_ranged = bool(getattr(self.parent_wargear, "is_ranged", lambda: False)())
                if is_ranged and getattr(attacker, "can_use_selected_to_shoot_reroll", None) and attacker.can_use_selected_to_shoot_reroll("wound"):
                    needed = 0
                    try:
                        s_val = strength
                        t_val = target_toughness
                        if isinstance(s_val, int) and isinstance(t_val, int):
                            if s_val >= 2 * t_val:
                                needed = 2
                            elif s_val > t_val:
                                needed = 3
                            elif s_val == t_val:
                                needed = 4
                            elif s_val * 2 <= t_val:
                                needed = 6
                            else:
                                needed = 5
                    except Exception:
                        needed = 0
                    final_needed = needed
                    try:
                        final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                    except Exception:
                        pass
                    try:
                        success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        unit = attacker.parent_unit
                        game = unit.get_parent_army().player.game
                        player = unit.get_parent_army().player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                        unit = None
                    reason = ""
                    try:
                        reason = str(getattr(attacker, "get_selected_to_shoot_reroll_source", lambda: "")() or "")
                    except Exception:
                        reason = ""
                    label = reason or "Selected to shoot"
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="wound",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason=label,
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll and attacker.consume_selected_to_shoot_reroll("wound"):
                        rr = _reroll_wound()
                        wound_result.setdefault("special_effects", []).append(f"{label}: re-roll Wound roll")
                        wound_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # Selected to shoot or fight: re-roll one Hit roll or one Wound roll (one per selection).
        try:
            if rerolls_allowed and "reroll" not in wound_result:
                is_ranged = bool(getattr(self.parent_wargear, "is_ranged", lambda: False)())
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                action = "shoot" if is_ranged else "fight" if is_melee else ""
                if action and getattr(attacker, "can_use_selected_to_action_reroll", None) and attacker.can_use_selected_to_action_reroll("wound", action):
                    needed = 0
                    try:
                        s_val = strength
                        t_val = target_toughness
                        if isinstance(s_val, int) and isinstance(t_val, int):
                            if s_val >= 2 * t_val:
                                needed = 2
                            elif s_val > t_val:
                                needed = 3
                            elif s_val == t_val:
                                needed = 4
                            elif s_val * 2 <= t_val:
                                needed = 6
                            else:
                                needed = 5
                    except Exception:
                        needed = 0
                    final_needed = needed
                    try:
                        final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                    except Exception:
                        pass
                    try:
                        success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                    except Exception:
                        success = False
                    do_reroll = False
                    try:
                        unit = attacker.parent_unit
                        game = unit.get_parent_army().player.game
                        player = unit.get_parent_army().player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                        unit = None
                    reason = ""
                    try:
                        reason = str(getattr(attacker, "get_selected_to_action_reroll_source", lambda _a=None: "")(action) or "")
                    except Exception:
                        reason = ""
                    default_label = "Selected to shoot" if action == "shoot" else "Selected to fight"
                    label = reason or default_label
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="wound",
                                value=dice_roll,
                                dice=None,
                                needed=final_needed,
                                success=success,
                                reason=label,
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        do_reroll = (not success)
                    if do_reroll and attacker.consume_selected_to_action_reroll("wound", action):
                        rr = _reroll_wound()
                        wound_result.setdefault("special_effects", []).append(f"{label}: re-roll Wound roll")
                        wound_result["reroll"] = rr
                        dice_roll = rr
                        reroll_used = True
        except Exception:
            pass

        # MONARCH OF THE HUNT (Shalaxi): melee vs quarry => optional re-roll of the Wound roll (even if successful),
        # to allow "fishing" for 6s.
        # Note: cannot re-roll a dice more than once, so skip if already rerolled.
        try:
            if rerolls_allowed and "reroll" not in wound_result:
                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                if is_melee:
                    quarry_ids = getattr(attacker.parent_unit, "_monarch_of_the_hunt_quarry_ids", None)
                    if quarry_ids:
                        try:
                            tid = getattr(target, "_id", None)
                            rid = getattr(target.get_attached_unit_root(), "_id", None)
                        except Exception:
                            tid = getattr(target, "_id", None)
                            rid = None
                        is_quarry = (tid in quarry_ids) or (rid in quarry_ids)
                        if is_quarry:
                            # Compute needed (same as in _apply_wound_roll)
                            needed = 0
                            try:
                                s_val = strength
                                t_val = target_toughness
                                if isinstance(s_val, int) and isinstance(t_val, int):
                                    if s_val >= 2 * t_val:
                                        needed = 2
                                    elif s_val > t_val:
                                        needed = 3
                                    elif s_val == t_val:
                                        needed = 4
                                    elif s_val * 2 <= t_val:
                                        needed = 6
                                    else:
                                        needed = 5
                            except Exception:
                                needed = 0
                            final_needed = needed
                            try:
                                final_needed = int(min(max(int(final_needed) - int(dice_modifier), 2), 6))
                            except Exception:
                                pass
                            # Determine "success" at this stage (before _apply_wound_roll handles nat 1/6).
                            try:
                                success = (dice_roll != 1) and (bool(final_needed) and dice_roll >= int(final_needed))
                            except Exception:
                                success = False

                            do_reroll = False
                            try:
                                unit = attacker.parent_unit
                                game = unit.get_parent_army().player.game
                                player = unit.get_parent_army().player
                                provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                            except Exception:
                                provider = None
                                player = None
                                unit = None

                            if callable(provider):
                                try:
                                    do_reroll = bool(provider(
                                        player=player,
                                        unit=unit,
                                        roll_type="wound",
                                        value=dice_roll,
                                        dice=None,
                                        needed=final_needed,
                                        success=success,
                                        reason="Monarch of the Hunt",
                                    ))
                                except Exception:
                                    do_reroll = False

                            if do_reroll:
                                rr = _reroll_wound()
                                wound_result.setdefault("special_effects", []).append("Monarch of the Hunt: re-roll Wound roll (melee vs quarry)")
                                wound_result["reroll"] = rr
                                dice_roll = rr
                                reroll_used = True
        except Exception:
            pass
        wound_result['roll'] = dice_roll
        # Publish roll_made for wound
        if log_roll:
            try:
                unit = attacker.parent_unit
                game = unit.get_parent_army().player.game
                from ..utility.reroll_tracker import prepare_reroll_event
                roll_id, reroll_cb, reroll_locked = prepare_reroll_event(
                    game,
                    _reroll_wound,
                    reroll_used=bool(reroll_used),
                    used_result=dice_roll,
                )
                game.event_system.publish(
                    "roll_made",
                    player=unit.get_parent_army().player,
                    unit=unit,
                    roll_type="wound",
                    value=dice_roll,
                    reroll=reroll_cb,
                    reroll_locked=bool(reroll_locked),
                    roll_id=roll_id,
                    miracle_used=bool(miracle_used),
                )
            except Exception:
                pass

        # Compute needed roll for prompt-driven rules before applying them.
        needed_for_prompt = None
        try:
            if isinstance(strength, int) and isinstance(target_toughness, int):
                if strength >= (target_toughness * 2):
                    base_needed = 2
                elif strength > target_toughness:
                    base_needed = 3
                elif strength == target_toughness:
                    base_needed = 4
                elif strength * 2 <= target_toughness:
                    base_needed = 6
                else:
                    base_needed = 5
                needed_for_prompt = min(max(int(base_needed) - int(dice_modifier), 2), 6)
        except Exception:
            needed_for_prompt = None

        # Leading ability: once per phase, optionally set the roll to an unmodified 6.
        new_roll, decision = self._maybe_apply_leading_unmodified_six(
            attacker,
            target,
            roll_type="wound",
            roll_value=dice_roll,
            needed=needed_for_prompt,
        )
        if new_roll is not None and int(new_roll) != int(dice_roll):
            dice_roll = int(new_roll)
            wound_result['roll'] = dice_roll
            wound_result['special_effects'].append("Leading ability: set roll to 6")

        new_roll, decision = self._maybe_apply_model_unmodified_six(
            attacker,
            roll_type="wound",
            roll_value=dice_roll,
            needed=needed_for_prompt,
            attacker=attacker,
            target=target,
        )
        if new_roll is not None and int(new_roll) != int(dice_roll):
            dice_roll = int(new_roll)
            wound_result['roll'] = dice_roll
            wound_result['special_effects'].append("Ability: set roll to 6")

        # Aspect Shrine Token (Aeldari): optionally set the roll to an unmodified 6.
        new_roll, decision = self._maybe_apply_aspect_shrine_token(
            attacker,
            target,
            roll_type="wound",
            roll_value=dice_roll,
            needed=needed_for_prompt,
        )
        if new_roll is not None and int(new_roll) != int(dice_roll):
            dice_roll = int(new_roll)
            wound_result['roll'] = dice_roll
            wound_result['special_effects'].append("Aspect Shrine Token: set roll to 6")

        def _apply_wound_roll(roll: int) -> bool:
            """Apply wound logic for a given (unmodified) roll; respects dice_modifier."""
            def _devastating_from_blessings() -> bool:
                """Decapitating Strikes: melee vs INFANTRY gains Devastating Wounds."""
                try:
                    is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                except Exception:
                    is_melee = False
                if not is_melee:
                    return False
                try:
                    if not target.has_keyword("Infantry"):
                        return False
                except Exception:
                    return False
                try:
                    unit = getattr(attacker, "parent_unit", None)
                    army = unit.get_parent_army() if unit is not None else None
                    mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
                    game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                    br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                    if mgr is None or br <= 0:
                        return False
                    # Eligibility: attached unit group qualifies if any member has Blessings of Khorne ability
                    try:
                        qualifies = bool(unit.get_attached_unit_root().attached_unit_has_blessings_of_khorne())
                    except Exception:
                        qualifies = False
                    if not qualifies:
                        return False
                    return bool(mgr.is_blessing_active_for_unit("DECAPITATING_STRIKES", unit, battle_round=br))
                except Exception:
                    return False

            def _devastating_from_pain() -> bool:
                """Drukhari: Decapitating Strikes (Pain) melee vs INFANTRY gains Devastating Wounds."""
                try:
                    is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                except Exception:
                    is_melee = False
                if not is_melee:
                    return False
                try:
                    if not target.has_keyword("Infantry"):
                        return False
                except Exception:
                    return False
                try:
                    sr = getattr(attacker.parent_unit, "special_rules", None)
                    return bool(isinstance(sr, dict) and sr.get("pain_devastating_vs_infantry"))
                except Exception:
                    return False

            # Natural 1 always fails
            if roll == 1:
                return False
            # Natural 6 always wounds (critical wound)
            if roll == 6:
                wound_result['special_effects'].append("Natural 6 (auto-wound)")
                attack_instance['crit_wound'] = True
                has_temp_dev = False
                try:
                    has_temp_dev = bool(getattr(attacker, "has_temporary_devastating_wounds_melee", lambda: False)())
                    if has_temp_dev:
                        is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                        has_temp_dev = bool(is_melee)
                except Exception:
                    has_temp_dev = False
                if self.is_devastating_wounds() or _devastating_from_blessings() or _devastating_from_pain() or has_temp_dev or attack_instance.get("bonus_devastating_wounds"):
                    wound_result['special_effects'].append("Devastating Wounds")
                    attack_instance['mortal_wound'] = True
                return True

            # Anti-X can make a roll count as a critical wound.
            # If multiple Anti- instances exist, they are not cumulative; pick the most permissive
            # one that applies to this target (lowest required value).
            try:
                best = None
                anti_specs = list(self.get_anti_specs() or [])
                bonus_specs = list(attack_instance.get("bonus_anti_specs") or [])
                if bonus_specs:
                    anti_specs.extend(bonus_specs)
                for kw, val in anti_specs:
                    try:
                        if not kw:
                            continue
                        applies = False
                        try:
                            applies = bool(target.has_keyword(kw))
                        except Exception:
                            try:
                                applies = bool(target.has_any_keyword(kw))
                            except Exception:
                                applies = False
                        if applies:
                            if best is None or int(val) < int(best[1]):
                                best = (kw, int(val))
                    except Exception:
                        continue
                if best is not None:
                    anti_keyword, anti_value = best[0], int(best[1])
                    if roll >= anti_value:
                        wound_result['special_effects'].append(f"Anti-{anti_keyword} {anti_value}+")
                        attack_instance['crit_wound'] = True
                        has_temp_dev = False
                        try:
                            has_temp_dev = bool(getattr(attacker, "has_temporary_devastating_wounds_melee", lambda: False)())
                            if has_temp_dev:
                                is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                                has_temp_dev = bool(is_melee)
                        except Exception:
                            has_temp_dev = False
                        if self.is_devastating_wounds() or _devastating_from_blessings() or _devastating_from_pain() or has_temp_dev or attack_instance.get("bonus_devastating_wounds"):
                            wound_result['special_effects'].append("Devastating Wounds")
                            attack_instance['mortal_wound'] = True
                        return True
            except Exception:
                pass

            # Determine base wound threshold based on S vs T
            base_needed = None
            strength_comparison = ""
            if strength >= (target_toughness * 2):
                base_needed = 2
                strength_comparison = f"S{strength} >= 2xT{target_toughness}"
            elif strength > target_toughness:
                base_needed = 3
                strength_comparison = f"S{strength} > T{target_toughness}"
            elif strength == target_toughness:
                base_needed = 4
                strength_comparison = f"S{strength} = T{target_toughness}"
            elif strength <= (target_toughness / 2):
                base_needed = 6
                strength_comparison = f"S{strength} <= T{target_toughness}/2"
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
            if crit_wound_threshold is not None:
                try:
                    threshold = int(crit_wound_threshold)
                except Exception:
                    threshold = None
                if threshold is not None and roll >= threshold and roll >= final_needed:
                    wound_result['special_effects'].append(f"Critical wound ({threshold}+)")
                    if crit_wound_reasons:
                        wound_result['special_effects'].extend(list(crit_wound_reasons))
                    attack_instance['crit_wound'] = True
                    has_temp_dev = False
                    try:
                        has_temp_dev = bool(getattr(attacker, "has_temporary_devastating_wounds_melee", lambda: False)())
                        if has_temp_dev:
                            is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                            has_temp_dev = bool(is_melee)
                    except Exception:
                        has_temp_dev = False
                    if self.is_devastating_wounds() or _devastating_from_blessings() or _devastating_from_pain() or has_temp_dev or attack_instance.get("bonus_devastating_wounds"):
                        wound_result['special_effects'].append("Devastating Wounds")
                        attack_instance['mortal_wound'] = True
                    return True
            return roll >= final_needed

        # First attempt
        if dice_roll == 6:
            wound_result['wound'] = True
            wound_result['wound'] = _apply_wound_roll(dice_roll)
        else:
            wound_result['wound'] = _apply_wound_roll(dice_roll)

        # TWIN-LINKED: re-roll failed wound rolls once.
        try:
            daemonic_fury_twin_linked = False
            try:
                unit = getattr(attacker, "parent_unit", None)
                sr = getattr(unit, "special_rules", None) if unit is not None else None
                if isinstance(sr, dict) and sr.get("daemonic_fury_twin_linked_active") is True:
                    is_melee = bool(getattr(self.parent_wargear, "is_melee", lambda: False)())
                    if is_melee:
                        daemonic_fury_twin_linked = True
                        expires_phase = str(sr.get("daemonic_fury_twin_linked_expires_phase", "") or "")
                        if expires_phase:
                            phase_key = self._resolve_phase_key(attacker_unit=unit, target_unit=target)
                            if phase_key and expires_phase != phase_key:
                                daemonic_fury_twin_linked = False
            except Exception:
                daemonic_fury_twin_linked = False
            bonus_twin = bool(attack_instance.get("bonus_twin_linked"))
            if rerolls_allowed and (not wound_result['wound']) and "reroll" not in wound_result and (self.is_twin_linked() or daemonic_fury_twin_linked or bonus_twin):
                reroll = _reroll_wound()
                if daemonic_fury_twin_linked and not self.is_twin_linked():
                    wound_result['special_effects'].append("Twin-linked (Daemonic Fury)")
                elif bonus_twin and not self.is_twin_linked():
                    wound_result['special_effects'].append("Twin-linked (objective target)")
                else:
                    wound_result['special_effects'].append("Twin-linked (re-roll failed wound)")
                wound_result['reroll'] = reroll
                wound_result['wound'] = _apply_wound_roll(reroll)
        except Exception:
            pass

        if dice_roll == 1:
            wound_result['special_effects'].append("Natural 1 (auto-fail)")

        return wound_result

    def _save_with_tracking(
        self,
        target_model: 'Model',
        attack_instance: Dict,
        ap: int,
        *,
        roll_value: Optional[int] = None,
        allow_rerolls: bool = True,
        log_roll: bool = True,
    ) -> Dict:
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
        rerolls_allowed = bool(allow_rerolls)
        shadow_field_active = False
        shadow_field_broken = False
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            if t_unit is not None and hasattr(t_unit, "model_has_shadow_field_ability"):
                shadow_field_active = bool(t_unit.model_has_shadow_field_ability(target_model))
                if shadow_field_active and hasattr(t_unit, "is_shadow_field_broken"):
                    shadow_field_broken = bool(t_unit.is_shadow_field_broken(target_model))
        except Exception:
            shadow_field_active = False
            shadow_field_broken = False
        shadow_field_block_invuln = bool(shadow_field_active and shadow_field_broken)
        
        # Stratagem / rule-driven defensive modifiers that need to be reflected in the attack_instance.
        # - GO TO GROUND: 6++ invulnerable + Benefit of Cover until end of phase.
        # - SMOKESCREEN: Benefit of Cover until end of phase (Stealth handled in hit modifier via Unit.has_stealth()).
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            sr = getattr(t_unit, "special_rules", None) if t_unit is not None else None
            if isinstance(sr, dict) and sr.get("go_to_ground_active") is True:
                attack_instance.setdefault("benefit_of_cover", True)
                attack_instance.setdefault("benefit_of_cover_source", "GO TO GROUND")
                attack_instance.setdefault("inv_save_override", 6)
            if isinstance(sr, dict) and sr.get("smokescreen_active") is True:
                attack_instance.setdefault("benefit_of_cover", True)
                attack_instance.setdefault("benefit_of_cover_source", "SMOKESCREEN")
        except Exception:
            pass
        # Bearer/leading-unit abilities: Benefit of Cover against ranged attacks that target the unit.
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            sr = getattr(t_unit, "special_rules", None) if t_unit is not None else None
            entries = sr.get("bearer_unit_benefit_of_cover") if isinstance(sr, dict) else None
            if entries:
                is_melee = False
                is_ranged = False
                try:
                    if self.parent_wargear is not None:
                        is_melee = bool(self.parent_wargear.is_melee())
                        is_ranged = bool(self.parent_wargear.is_ranged())
                except Exception:
                    is_melee = False
                    is_ranged = False
                if not is_melee and not is_ranged:
                    try:
                        is_ranged = bool(getattr(self, "range", None) and int(getattr(self.range, "max", 0) or 0) > 0)
                    except Exception:
                        is_ranged = False
                if is_ranged:
                    sources = []
                    for entry in entries:
                        requires_objective = False
                        requires_controlled = False
                        if isinstance(entry, dict):
                            atype = str(entry.get("attack_type") or "any").strip().lower()
                            src = str(entry.get("source") or "Bearer unit ability").strip() or "Bearer unit ability"
                            requires_objective = bool(entry.get("requires_objective"))
                            requires_controlled = bool(entry.get("requires_objective_controlled"))
                        elif isinstance(entry, (tuple, list)):
                            atype = str(entry[0] if entry else "any").strip().lower()
                            src = str(entry[1]) if len(entry) > 1 else "Bearer unit ability"
                        else:
                            continue
                        if atype not in ("any", "ranged"):
                            continue
                        if requires_objective or requires_controlled:
                            game_map = None
                            try:
                                attacker_unit = attack_instance.get("attacker_unit")
                            except Exception:
                                attacker_unit = None
                            try:
                                if attacker_unit is not None:
                                    game_map = getattr(getattr(attacker_unit.get_parent_army(), "player", None), "game", None).map
                            except Exception:
                                game_map = None
                            if game_map is None:
                                try:
                                    game_map = getattr(getattr(t_unit.get_parent_army(), "player", None), "game", None).map
                                except Exception:
                                    game_map = None
                            if requires_controlled:
                                if not t_unit._within_controlled_objective_range(game_map=game_map):
                                    continue
                            elif requires_objective:
                                if not t_unit.is_within_any_objective_range(game_map=game_map):
                                    continue
                        sources.append(src)
                    if sources:
                        attack_instance.setdefault("benefit_of_cover", True)
                        if "benefit_of_cover_source" not in attack_instance:
                            uniq = []
                            seen = set()
                            for src in sources:
                                key = src.lower()
                                if key in seen:
                                    continue
                                seen.add(key)
                                uniq.append(src)
                            attack_instance["benefit_of_cover_source"] = ", ".join(uniq) if uniq else "Bearer unit ability"
        except Exception:
            pass
        # Aura abilities: Benefit of Cover against ranged attacks that target the unit.
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            if t_unit is not None:
                is_melee = False
                is_ranged = False
                try:
                    if self.parent_wargear is not None:
                        is_melee = bool(self.parent_wargear.is_melee())
                        is_ranged = bool(self.parent_wargear.is_ranged())
                except Exception:
                    is_melee = False
                    is_ranged = False
                if not is_melee and not is_ranged:
                    try:
                        is_ranged = bool(getattr(self, "range", None) and int(getattr(self.range, "max", 0) or 0) > 0)
                    except Exception:
                        is_ranged = False
                if is_ranged:
                    from ..utility.aura_effects import get_aura_benefit_of_cover
                    has_cover, reasons = get_aura_benefit_of_cover(t_unit)
                    if has_cover:
                        attack_instance.setdefault("benefit_of_cover", True)
                        if "benefit_of_cover_source" not in attack_instance:
                            attack_instance["benefit_of_cover_source"] = ", ".join(reasons) if reasons else "Aura: Benefit of Cover"
                        elif reasons:
                            existing = str(attack_instance.get("benefit_of_cover_source") or "")
                            parts = [p.strip() for p in existing.split(",") if p.strip()]
                            for reason in reasons:
                                if reason not in parts:
                                    parts.append(reason)
                            attack_instance["benefit_of_cover_source"] = ", ".join(parts) if parts else existing
        except Exception:
            pass
        # Orks: Waaagh! (5+ invulnerable save while active).
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            army = t_unit.get_parent_army() if t_unit is not None else None
            mgr = getattr(army, "waaagh", None) if army is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if mgr is not None and t_unit is not None and mgr.unit_is_affected(t_unit, game=game):
                current = attack_instance.get("inv_save_override", None)
                if current is None or int(current) > 5:
                    attack_instance["inv_save_override"] = 5
        except Exception:
            pass
        # World Eaters: Blood Tithe (Boon of Blood) 4++ for BLOOD LEGIONS units.
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            army = t_unit.get_parent_army() if t_unit is not None else None
            mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if mgr is not None and t_unit is not None and getattr(mgr, "blood_tithe_boon_of_blood_applies", None):
                if mgr.blood_tithe_boon_of_blood_applies(t_unit):
                    current = attack_instance.get("inv_save_override", None)
                    if current is None or int(current) > 4:
                        attack_instance["inv_save_override"] = 4
        except Exception:
            pass
        # World Eaters: Idols of Khorne (Idol of Blessed Blood) 4++ for JAKHALS/GOREMONGERS within range.
        t_unit = getattr(target_model, "parent_unit", None)
        get_parent_army = getattr(t_unit, "get_parent_army", None) if t_unit is not None else None
        army = get_parent_army() if callable(get_parent_army) and hasattr(t_unit, "parent_army") else None
        mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        applies_fn = getattr(mgr, "idols_of_khorne_blessed_blood_applies", None) if mgr is not None else None
        if callable(applies_fn) and t_unit is not None:
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            game_map = getattr(game, "map", None) if game is not None else None
            if applies_fn(t_unit, game_map=game_map):
                current = attack_instance.get("inv_save_override", None)
                if current is None or int(current) > 4:
                    attack_instance["inv_save_override"] = 4
                    attack_instance["inv_save_override_reason"] = "Idol of Blessed Blood (Aura)"
        # Wargear abilities (e.g. "The bearer has a 4+ invulnerable save.").
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            if t_unit is not None and hasattr(t_unit, "get_model_invulnerable_save_override"):
                inv_value, inv_reason = t_unit.get_model_invulnerable_save_override(target_model)
                if inv_value:
                    current = attack_instance.get("inv_save_override", None)
                    if current is None or int(current) > int(inv_value):
                        attack_instance["inv_save_override"] = int(inv_value)
                        if inv_reason:
                            attack_instance["inv_save_override_reason"] = str(inv_reason)
        except Exception:
            pass
        # Defensive reaction stratagems: invulnerable save overrides.
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            t_root = t_unit.get_attached_unit_root() if (t_unit is not None and hasattr(t_unit, "get_attached_unit_root")) else t_unit
            attack_type = "melee" if (self.parent_wargear and self.parent_wargear.is_melee()) else "ranged"
            attacker_key = attack_instance.get("attacker_key")
            phase_key = self._resolve_phase_key(
                attacker_unit=attack_instance.get("attacker_unit"),
                target_unit=t_root,
            )
            for entry in self._iter_defensive_entries(
                t_root,
                "defensive_invuln_overrides",
                attacker_key=attacker_key,
                attack_type=attack_type,
                phase_key=phase_key,
            ):
                inv_value = int(entry.get("value", 0) or 0)
                if not inv_value:
                    continue
                current = attack_instance.get("inv_save_override", None)
                if current is None or int(current) > inv_value:
                    attack_instance["inv_save_override"] = inv_value
                    src = entry.get("source")
                    if src:
                        attack_instance["inv_save_override_reason"] = str(src)
        except Exception:
            pass

        # Calculate save value
        save_base = target_model.save
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            if t_unit is not None and hasattr(t_unit, "get_model_save_characteristic_override"):
                save_override, save_reason = t_unit.get_model_save_characteristic_override(target_model)
                if save_override:
                    save_base = int(save_override)
                    save_result["base_save"] = int(save_override)
                    if save_reason:
                        save_result["special_effects"].append(f"Save characteristic set ({save_reason})")
        except Exception:
            save_base = target_model.save

        save_value = save_base - ap
        save_result['final_save'] = save_value
        inv_save, inv_save_condition = target_model.inv_save

        # Invulnerable override (e.g. GO TO GROUND 6++) can grant an invuln save even if the model lacks one.
        try:
            inv_override = attack_instance.get("inv_save_override", None)
            if inv_override is not None and not shadow_field_block_invuln:
                inv_override = int(inv_override)
                if inv_override and inv_override < save_value:
                    save_value = inv_override
                    save_result['save_type'] = 'invulnerable'
                    save_result['final_save'] = save_value
                    inv_reason = attack_instance.get("inv_save_override_reason", None)
                    if inv_reason:
                        save_result['special_effects'].append(f"Invulnerable save {inv_override}+ ({inv_reason})")
                    else:
                        save_result['special_effects'].append(f"Invulnerable save {inv_override}+ (override)")
        except Exception:
            pass
        
        if inv_save and not shadow_field_block_invuln:
            # Check invulnerable save condition (string-based, not callable)
            condition_met = True
            if inv_save_condition and inv_save_condition.strip():
                condition_met = self._check_invulnerable_save_condition(inv_save_condition, attack_instance)
            
            if condition_met and inv_save < save_value:
                save_value = inv_save
                save_result['save_type'] = 'invulnerable'
                save_result['final_save'] = save_value

        shadow_field_no_reroll = False
        if shadow_field_active and not shadow_field_block_invuln:
            if save_result.get("save_type") == "invulnerable":
                shadow_field_no_reroll = True
                save_result['special_effects'].append("Shadow Field: no invulnerable re-rolls")

        # Provide reroll callback for save
        def _reroll_save():
            new_roll = get_roll("D6")
            if log_roll:
                try:
                    append_dice(target_model.parent_unit.get_parent_army().player, f"Save re-roll: {new_roll} (need {save_value}+) for {target_model.name}")
                except Exception:
                    pass
            return new_roll
        dice_roll = None
        miracle_used = False
        if roll_value is not None:
            try:
                dice_roll = int(roll_value)
            except Exception:
                dice_roll = None
        if dice_roll is None:
            try:
                unit = target_model.parent_unit
                army = unit.get_parent_army() if unit is not None else None
                mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr is not None and mgr.can_use_act_of_faith(unit, game=game):
                    dice_roll, _dice, miracle_used = mgr.resolve_roll(
                        unit,
                        roll_type="save",
                        game=game,
                        dice_count=1,
                        die_faces=6,
                        needed=save_value,
                    )
            except Exception:
                dice_roll = None
                miracle_used = False
        if dice_roll is None:
            dice_roll = get_roll("D6")
        if log_roll:
            try:
                if miracle_used:
                    append_dice(target_model.parent_unit.get_parent_army().player, f"Miracle die used for Save roll: {dice_roll} (need {save_value}+) for {target_model.name}")
                else:
                    append_dice(target_model.parent_unit.get_parent_army().player, f"Save roll: {dice_roll} (need {save_value}+) for {target_model.name}")
            except Exception:
                pass
        save_result['roll'] = dice_roll
        save_result['needed'] = save_value
        if miracle_used:
            save_result['special_effects'].append("Miracle die")
        # Publish roll_made for save
        if log_roll:
            try:
                unit = target_model.parent_unit
                game = unit.get_parent_army().player.game
                from ..utility.reroll_tracker import prepare_reroll_event
                roll_id, reroll_cb, reroll_locked = prepare_reroll_event(game, _reroll_save)
                if shadow_field_no_reroll:
                    reroll_locked = True
                game.event_system.publish(
                    "roll_made",
                    player=unit.get_parent_army().player,
                    unit=unit,
                    roll_type="save",
                    value=dice_roll,
                    reroll=reroll_cb,
                    reroll_locked=bool(reroll_locked),
                    roll_id=roll_id,
                    miracle_used=bool(miracle_used),
                )
            except Exception:
                pass

        # Model ability: once per battle, optionally set save roll to an unmodified 6.
        new_roll, decision = self._maybe_apply_model_unmodified_six(
            target_model,
            roll_type="save",
            roll_value=dice_roll,
            needed=save_value,
            attacker=None,
            target=getattr(target_model, "parent_unit", None),
        )
        if new_roll is not None and int(new_roll) != int(dice_roll):
            dice_roll = int(new_roll)
            save_result['roll'] = dice_roll
            save_result['special_effects'].append("Ability: set roll to 6")
        
        if dice_roll == 1:  # unmodified dice roll of 1 is always a fail
            save_result['saved'] = False
            save_result['special_effects'].append("Natural 1 (auto-fail)")
        else:
            from ..utility.modifiers import compute_save_roll_modifier
            dice_modifier, effects = compute_save_roll_modifier(
                target_model,
                attack_instance=attack_instance,
                ap=ap,
                save_type=save_result.get("save_type"),
                weapon_profile=self,
            )
            if effects:
                save_result["special_effects"].extend(list(effects))
            save_result['saved'] = (dice_roll + dice_modifier) >= save_value

            if dice_modifier != 0:
                save_result['special_effects'].append(f"Modifier {dice_modifier:+d}")

        # Shadow Field: on first failed invulnerable save, bearer loses invulnerable save.
        try:
            if shadow_field_active and not shadow_field_broken:
                if save_result.get("save_type") == "invulnerable" and not save_result.get("saved", False):
                    t_unit = getattr(target_model, "parent_unit", None)
                    if t_unit is not None and hasattr(t_unit, "mark_shadow_field_broken"):
                        t_unit.mark_shadow_field_broken(target_model)
                    save_result['special_effects'].append("Shadow Field broken")
        except Exception:
            pass

        # Channeller Stones: first failed save each turn sets Damage to 0.
        try:
            if not save_result.get("saved", False):
                t_unit = getattr(target_model, "parent_unit", None)
                if t_unit is not None and hasattr(t_unit, "get_first_failed_save_damage_zero_sources"):
                    sources = list(t_unit.get_first_failed_save_damage_zero_sources() or [])
                else:
                    sources = []
                if sources:
                    try:
                        root = t_unit.get_attached_unit_root()
                    except Exception:
                        root = t_unit
                    sr = getattr(root, "special_rules", None)
                    if not isinstance(sr, dict):
                        sr = {}
                    owner_id = ""
                    turn = 0
                    try:
                        army = root.get_parent_army()
                        player = getattr(army, "player", None) if army is not None else None
                        owner_id = str(getattr(player, "id", "") or "")
                        game = getattr(player, "game", None) if player is not None else None
                        turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                    except Exception:
                        owner_id = ""
                        turn = 0
                    used_owner = str(sr.get("first_failed_save_damage_zero_turn_owner", "") or "")
                    try:
                        used_turn = int(sr.get("first_failed_save_damage_zero_turn", 0) or 0)
                    except Exception:
                        used_turn = 0
                    already_used = False
                    if used_turn and turn and used_turn == turn:
                        if not used_owner or not owner_id or used_owner == owner_id:
                            already_used = True
                    if not already_used:
                        source = str(sources[0] or "First failed save").strip() or "First failed save"
                        attack_instance["force_damage_zero"] = True
                        attack_instance["force_damage_zero_source"] = source
                        sr["first_failed_save_damage_zero_turn"] = int(turn or 0)
                        if owner_id:
                            sr["first_failed_save_damage_zero_turn_owner"] = owner_id
                        sr["first_failed_save_damage_zero_source"] = source
                        root.special_rules = sr
                        save_result['special_effects'].append(f"{source}: damage set to 0")
        except Exception:
            pass

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
        print(f"WARN: Unknown invulnerable save condition format: '{condition}' - applying save")
        return True

    def _resolve_wounds_cannot_be_ignored(self, attack_instance: Dict) -> bool:
        wounds_cannot_be_ignored = bool(attack_instance.get("wounds_cannot_be_ignored", False))
        if not wounds_cannot_be_ignored:
            try:
                wounds_cannot_be_ignored = bool(self.wounds_cannot_be_ignored())
            except Exception:
                wounds_cannot_be_ignored = False
        return bool(wounds_cannot_be_ignored)

    def _record_damage_result(self, attack_result: AttackResult, damage_result: Dict) -> None:
        if attack_result is None or damage_result is None:
            return
        try:
            attack_result.damage_results.append(damage_result)
            attack_result.total_damage_dealt += int(damage_result.get("damage_applied", 0) or 0)
            if damage_result.get("model_killed"):
                attack_result.models_killed += 1
        except Exception:
            pass

    @staticmethod
    def _pending_mortal_target_key(target_unit: Optional['Unit']) -> str:
        if target_unit is None:
            return ""
        try:
            key = getattr(target_unit, "_id", None)
            if key:
                return str(key)
        except Exception:
            pass
        return get_entity_id(target_unit)

    def _damage_target_with_tracking(
        self,
        target_model: 'Model',
        attacker: 'Model',
        attack_instance: Dict,
        game_map: Optional['Map'] = None,
        *,
        roll_value: Optional[int] = None,
        roll_values: Optional[list[int]] = None,
        allow_rerolls: bool = True,
    ) -> Dict:
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
        rerolls_allowed = bool(allow_rerolls)

        damage_taken_override = 0
        damage_taken_source = ""
        try:
            if target_model is not None and hasattr(target_model, "get_temporary_damage_taken_override"):
                damage_taken_override, damage_taken_source = target_model.get_temporary_damage_taken_override()
        except Exception:
            damage_taken_override = 0
            damage_taken_source = ""

        damage_override = 0
        damage_override_source = ""
        try:
            weapon_name = ""
            if getattr(self, "parent_wargear", None) is not None:
                weapon_name = str(getattr(self.parent_wargear, "name", "") or "")
            if not weapon_name:
                weapon_name = str(getattr(self, "name", "") or "")
            if attacker is not None and hasattr(attacker, "get_temporary_weapon_damage_override"):
                damage_override, damage_override_source = attacker.get_temporary_weapon_damage_override(weapon_name)
        except Exception:
            damage_override = 0
            damage_override_source = ""
        
        # Calculate base Damage characteristic with detailed tracking
        if damage_taken_override:
            try:
                damage_value = int(damage_taken_override)
            except Exception:
                damage_value = 0
            damage_result["damage_expression"] = str(damage_taken_override)
            damage_result["damage_rolled"] = int(damage_value)
            if damage_taken_source:
                damage_result["special_effects"].append(f"{damage_taken_source}: Damage {int(damage_value)}")
            rerolls_allowed = False
        elif damage_override:
            try:
                damage_value = int(damage_override)
            except Exception:
                damage_value = 0
            damage_result["damage_expression"] = str(damage_override)
            damage_result["damage_rolled"] = int(damage_value)
            if damage_override_source:
                damage_result["special_effects"].append(f"{damage_override_source}: Damage {int(damage_value)}")
            rerolls_allowed = False
        elif isinstance(self.damage, DiceCollection):
            # Provide reroll callback for damage
            def _reroll_damage():
                new_val, new_rolls = self.damage.roll_detailed()
                return new_val, new_rolls
            damage_value = None
            dice_rolls = None
            miracle_used = False
            if roll_value is not None:
                try:
                    damage_value = int(roll_value)
                except Exception:
                    damage_value = None
                dice_rolls = list(roll_values or [])
            if damage_value is None:
                try:
                    unit = attacker.parent_unit
                    army = unit.get_parent_army() if unit is not None else None
                    mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if mgr is not None and mgr.can_use_act_of_faith(unit, game=game):
                        damage_value, dice_rolls, miracle_used = mgr.resolve_roll(
                            unit,
                            roll_type="damage",
                            game=game,
                            dice_count=self.damage.number,
                            die_faces=self.damage.die_faces,
                            modifier=self.damage.modifier,
                        )
                except Exception:
                    damage_value = None
                    dice_rolls = None
                    miracle_used = False
            if damage_value is None or dice_rolls is None:
                damage_value, dice_rolls = self.damage.roll_detailed()
            damage_result['damage_dice_rolls'] = dice_rolls
            if miracle_used:
                damage_result['special_effects'].append("Miracle die")
            # Publish roll_made for damage
            try:
                unit = attacker.parent_unit
                game = unit.get_parent_army().player.game
                from ..utility.reroll_tracker import prepare_reroll_event
                roll_id, reroll_cb, reroll_locked = prepare_reroll_event(game, _reroll_damage)
                game.event_system.publish(
                    "roll_made",
                    player=unit.get_parent_army().player,
                    unit=unit,
                    roll_type="damage",
                    value=damage_value,
                    dice=dice_rolls,
                    reroll=reroll_cb,
                    reroll_locked=bool(reroll_locked),
                    roll_id=roll_id,
                    miracle_used=bool(miracle_used),
                )
            except Exception:
                pass
        else:
            damage_value = self.damage
            damage_result['damage_dice_rolls'] = []
        damage_result['damage_rolled'] = damage_value
        try:
            sonic_bonus = int(attack_instance.get("sonic_destruction_bonus", 0) or 0)
        except Exception:
            sonic_bonus = 0
        if sonic_bonus:
            damage_value = int(damage_value) + int(sonic_bonus)
            damage_result['damage_rolled'] = damage_value
            damage_result['special_effects'].append(f"+{int(sonic_bonus)} Damage (Sonic Destruction)")

        # D-cannon: re-roll Damage roll of 1; vs TITANIC you can re-roll the Damage roll instead.
        try:
            if rerolls_allowed and isinstance(self.damage, DiceCollection):
                unit = getattr(attacker, "parent_unit", None)
                rule = None
                if unit is not None and getattr(unit, "get_d_cannon_damage_reroll_rule", None):
                    rule = unit.get_d_cannon_damage_reroll_rule(attacker)
                if rule and "reroll" not in damage_result:
                    weapon_name = ""
                    try:
                        if getattr(self, "parent_wargear", None) is not None:
                            weapon_name = str(getattr(self.parent_wargear, "name", "") or "")
                        else:
                            weapon_name = str(getattr(self, "name", "") or "")
                    except Exception:
                        weapon_name = ""
                    if rule.get("weapon_match") and str(rule.get("weapon_match") or "").lower() not in weapon_name.lower():
                        rule = None
                if rule and "reroll" not in damage_result:
                    is_titanic = False
                    try:
                        target_unit = getattr(target_model, "parent_unit", None)
                        if target_unit is not None:
                            is_titanic = bool(
                                target_unit.has_any_keyword("TITANIC") or target_unit.has_keyword("TITANIC")
                            )
                        else:
                            is_titanic = bool(
                                getattr(target_model, "has_any_keyword", lambda *_a, **_k: False)("TITANIC")
                                or getattr(target_model, "has_keyword", lambda *_a, **_k: False)("TITANIC")
                            )
                    except Exception:
                        is_titanic = False

                    source = str(rule.get("source", "") or "D-cannon").strip() or "D-cannon"
                    if is_titanic and rule.get("reroll_damage_full_vs_titanic"):
                        do_reroll = False
                        try:
                            unit = attacker.parent_unit
                            game = unit.get_parent_army().player.game
                            player = unit.get_parent_army().player
                            is_human = bool(getattr(player, "has_control", lambda: False)())
                            provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        except Exception:
                            is_human = False
                            provider = None
                            player = None
                        if is_human and callable(provider):
                            try:
                                do_reroll = bool(provider(
                                    player=player,
                                    unit=unit,
                                    roll_type="damage",
                                    value=damage_value,
                                    dice=damage_result.get("damage_dice_rolls", None),
                                    reason=source,
                                ))
                            except Exception:
                                do_reroll = False
                        else:
                            try:
                                avg = float(self.damage.stat_average())
                                do_reroll = float(damage_value) < avg
                            except Exception:
                                do_reroll = False
                        if do_reroll:
                            new_val, new_rolls = _reroll_damage()
                            damage_value = new_val
                            damage_result['damage_dice_rolls'] = new_rolls
                            damage_result['damage_rolled'] = new_val
                            damage_result.setdefault('special_effects', []).append(
                                f"{source}: re-roll Damage roll"
                            )
                            damage_result['reroll'] = new_val
                    else:
                        base_roll = None
                        try:
                            rolls = damage_result.get("damage_dice_rolls", None)
                            if isinstance(rolls, list) and len(rolls) == 1:
                                base_roll = int(rolls[0])
                        except Exception:
                            base_roll = None
                        if base_roll == 1:
                            new_val, new_rolls = _reroll_damage()
                            damage_value = new_val
                            damage_result['damage_dice_rolls'] = new_rolls
                            damage_result['damage_rolled'] = new_val
                            damage_result.setdefault('special_effects', []).append(
                                f"{source}: re-roll Damage roll of 1"
                            )
                            damage_result['reroll'] = new_val
                            damage_result['reroll_of_one'] = 1
        except Exception:
            pass

        # Closest eligible MONSTER/VEHICLE target: re-roll Damage roll (optional).
        try:
            rule = attack_instance.get("closest_monster_vehicle_reroll_rule")
            if rerolls_allowed and rule and rule.get("reroll_damage") and isinstance(self.damage, DiceCollection) and "reroll" not in damage_result:
                do_reroll = False
                try:
                    unit = attacker.parent_unit
                    game = unit.get_parent_army().player.game
                    player = unit.get_parent_army().player
                    is_human = bool(getattr(player, "has_control", lambda: False)())
                    provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                except Exception:
                    is_human = False
                    provider = None
                    player = None
                reason = str(rule.get("source", "") or "").strip() or "Closest eligible MONSTER/VEHICLE"
                if is_human and callable(provider):
                    try:
                        do_reroll = bool(provider(
                            player=player,
                            unit=unit,
                            roll_type="damage",
                            value=damage_value,
                            dice=damage_result.get("damage_dice_rolls", None),
                            reason=reason,
                        ))
                    except Exception:
                        do_reroll = False
                else:
                    try:
                        avg = float(self.damage.stat_average())
                        do_reroll = float(damage_value) < avg
                    except Exception:
                        do_reroll = False
                if do_reroll:
                    new_val, new_rolls = _reroll_damage()
                    damage_value = new_val
                    damage_result['damage_dice_rolls'] = new_rolls
                    damage_result['damage_rolled'] = new_val
                    damage_result.setdefault('special_effects', []).append(
                        f"{reason}: re-roll Damage roll"
                    )
                    damage_result['reroll'] = new_val
        except Exception:
            pass

        # MONSTER/VEHICLE target: re-roll Damage roll (optional).
        try:
            rule = attack_instance.get("monster_vehicle_reroll_rule")
            if rerolls_allowed and rule and rule.get("reroll_damage") and isinstance(self.damage, DiceCollection) and "reroll" not in damage_result:
                do_reroll = False
                try:
                    unit = attacker.parent_unit
                    game = unit.get_parent_army().player.game
                    player = unit.get_parent_army().player
                    is_human = bool(getattr(player, "has_control", lambda: False)())
                    provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                except Exception:
                    is_human = False
                    provider = None
                    player = None
                reason = str(rule.get("source", "") or "").strip() or "Monster/Vehicle rerolls"
                if is_human and callable(provider):
                    try:
                        do_reroll = bool(provider(
                            player=player,
                            unit=unit,
                            roll_type="damage",
                            value=damage_value,
                            dice=damage_result.get("damage_dice_rolls", None),
                            reason=reason,
                        ))
                    except Exception:
                        do_reroll = False
                else:
                    try:
                        avg = float(self.damage.stat_average())
                        do_reroll = float(damage_value) < avg
                    except Exception:
                        do_reroll = False
                if do_reroll:
                    new_val, new_rolls = _reroll_damage()
                    damage_value = new_val
                    damage_result['damage_dice_rolls'] = new_rolls
                    damage_result['damage_rolled'] = new_val
                    damage_result.setdefault('special_effects', []).append(
                        f"{reason}: re-roll Damage roll"
                    )
                    damage_result['reroll'] = new_val
        except Exception:
            pass

        # Selected to shoot: re-roll one Damage roll (one per selection).
        try:
            if rerolls_allowed and isinstance(self.damage, DiceCollection) and "reroll" not in damage_result:
                is_ranged = bool(getattr(self.parent_wargear, "is_ranged", lambda: False)())
                if is_ranged and getattr(attacker, "can_use_selected_to_shoot_reroll", None) and attacker.can_use_selected_to_shoot_reroll("damage"):
                    do_reroll = False
                    try:
                        unit = attacker.parent_unit
                        game = unit.get_parent_army().player.game
                        player = unit.get_parent_army().player
                        is_human = bool(getattr(player, "has_control", lambda: False)())
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                    except Exception:
                        is_human = False
                        provider = None
                        player = None
                        unit = None
                    reason = ""
                    try:
                        reason = str(getattr(attacker, "get_selected_to_shoot_reroll_source", lambda: "")() or "")
                    except Exception:
                        reason = ""
                    label = reason or "Selected to shoot"
                    if is_human and callable(provider):
                        try:
                            do_reroll = bool(provider(
                                player=player,
                                unit=unit,
                                roll_type="damage",
                                value=damage_value,
                                dice=damage_result.get("damage_dice_rolls", None),
                                reason=label,
                            ))
                        except Exception:
                            do_reroll = False
                    else:
                        try:
                            avg = float(self.damage.stat_average())
                            do_reroll = float(damage_value) < avg
                        except Exception:
                            do_reroll = False
                    if do_reroll and attacker.consume_selected_to_shoot_reroll("damage"):
                        new_val, new_rolls = _reroll_damage()
                        damage_value = new_val
                        damage_result['damage_dice_rolls'] = new_rolls
                        damage_result['damage_rolled'] = new_val
                        damage_result.setdefault('special_effects', []).append(
                            f"{label}: re-roll Damage roll"
                        )
                        damage_result['reroll'] = new_val
        except Exception:
            pass

        # Leading ability: once per phase, optionally set the roll to an unmodified 6.
        try:
            if isinstance(self.damage, DiceCollection):
                new_roll, decision = self._maybe_apply_leading_unmodified_six(
                    attacker,
                    getattr(target_model, "parent_unit", None),
                    roll_type="damage",
                    roll_value=damage_value,
                    needed=None,
                )
                if new_roll is not None and int(new_roll) != int(damage_value):
                    damage_value = int(new_roll)
                    damage_result['damage_rolled'] = damage_value
                    damage_result.setdefault('special_effects', []).append("Leading ability: set roll to 6")
        except Exception:
            pass

        # Core Rules: Damage characteristic modifiers are cumulative and follow ordering:
        # replace -> DIV -> MUL -> ADD -> SUB, then round up.
        #
        # Also: if a weapon inflicts mortal wounds *in addition* to normal damage, Damage modifiers
        # do not apply to those mortal wounds. (We model this with a future-proof flag.)
        from ..utility.modifiers import Modifier, ModifierOp, apply_numeric_modifiers, apply_characteristic_caps

        damage_mods: list[Modifier] = []
        defensive_damage_entries = []
        allocated_damage_entries = []

        if self.is_melta() and attack_instance.get('below_half_distance', False):
            # Support Melta N / Melta D3 / Melta D6+X, etc.
            try:
                melta = self.get_melta_bonus()
                melta_bonus = int(melta.resolve())
                damage_mods.append(Modifier(ModifierOp.ADD, melta_bonus, source="weapon:melta"))
                damage_result['special_effects'].append(f"Melta +{melta_bonus} ({melta})")
            except Exception as exc:
                print(f"WARN: Melta bonus parsing failed for {self.name}: {exc}")

        # Enhancement: improve melee weapons' Damage by X (bearer enhancement).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                d_bonus = int(getattr(attacker.parent_unit, "special_rules", {}).get("enhancement_melee_damage_bonus", 0) or 0)
                if d_bonus:
                    damage_mods.append(Modifier(ModifierOp.ADD, int(d_bonus), source="enhancement:melee_damage_add"))
                    damage_result['special_effects'].append(f"Enhancement +{d_bonus}D (melee)")
        except Exception:
            pass
        if self.parent_wargear and self.parent_wargear.is_melee():
            sr = self._unit_special_rules(attacker)
            bearer_d_bonus = int(sr.get("enhancement_bearer_melee_damage_bonus", 0) or 0)
            if bearer_d_bonus and self._attacker_is_enhancement_bearer(attacker, sr):
                damage_mods.append(
                    Modifier(ModifierOp.ADD, int(bearer_d_bonus), source="enhancement:bearer_melee_damage_add")
                )
                damage_result['special_effects'].append(f"Enhancement bearer +{bearer_d_bonus}D (melee)")
        if self.parent_wargear and self.parent_wargear.is_melee():
            _s_bonus, d_bonus, _s_reasons, d_reasons = self._get_charge_melee_strength_damage_bonus(attacker, attack_instance)
            if d_bonus:
                damage_mods.append(
                    Modifier(ModifierOp.ADD, int(d_bonus), source="ability:charge_melee_damage_add")
                )
                if d_reasons:
                    damage_result['special_effects'].extend(list(d_reasons))
        # Berzerker Glaive: +1 Damage to melee weapons (excluding Extra Attacks).
        try:
            if self.parent_wargear and self.parent_wargear.is_melee() and not self.is_extra_attacks():
                d_bonus = int(
                    getattr(attacker.parent_unit, "special_rules", {}).get(
                        "enhancement_melee_damage_bonus_no_extra_attacks", 0
                    )
                    or 0
                )
                if d_bonus:
                    damage_mods.append(
                        Modifier(ModifierOp.ADD, int(d_bonus), source="enhancement:melee_damage_add_no_extra")
                    )
                    damage_result['special_effects'].append(f"Berzerker Glaive +{d_bonus}D (melee)")
        except Exception:
            pass

        # Psychic Destroyer: +1 Damage to ranged Psychic weapons.
        try:
            if (
                self.parent_wargear
                and self.parent_wargear.is_ranged()
                and self.is_psychic()
            ):
                d_bonus = int(
                    getattr(attacker.parent_unit, "special_rules", {}).get(
                        "enhancement_psychic_destroyer_damage_bonus", 0
                    )
                    or 0
                )
                if d_bonus:
                    damage_mods.append(
                        Modifier(ModifierOp.ADD, int(d_bonus), source="enhancement:psychic_destroyer_damage_add")
                    )
                    damage_result['special_effects'].append(f"Psychic Destroyer +{d_bonus}D (ranged psychic)")
        except Exception:
            pass

        # Unit ability: +Damage to melee attacks vs MONSTER/VEHICLE.
        try:
            if self.parent_wargear and self.parent_wargear.is_melee():
                t_unit = getattr(target_model, "parent_unit", None)
                target_is_monster = bool(getattr(t_unit, "is_monster", False))
                target_is_vehicle = bool(getattr(t_unit, "is_vehicle", False))
                if not (target_is_monster or target_is_vehicle):
                    try:
                        target_is_monster = bool(t_unit.has_keyword("Monster"))
                        target_is_vehicle = bool(t_unit.has_keyword("Vehicle"))
                    except Exception:
                        target_is_monster = False
                        target_is_vehicle = False
                if target_is_monster or target_is_vehicle:
                    d_bonus = 0
                    unit = getattr(attacker, "parent_unit", None)
                    if unit is not None:
                        fn = getattr(unit, "get_melee_damage_bonus_vs_monster_vehicle", None)
                        if callable(fn):
                            d_bonus = int(fn() or 0)
                        else:
                            sr = getattr(unit, "special_rules", None)
                            if isinstance(sr, dict):
                                d_bonus = int(sr.get("melee_damage_bonus_vs_monster_vehicle", 0) or 0)
                    if d_bonus:
                        damage_mods.append(
                            Modifier(ModifierOp.ADD, int(d_bonus), source="ability:melee_damage_vs_monster_vehicle")
                        )
                        damage_result['special_effects'].append(
                            f"+{d_bonus}D vs MONSTER/VEHICLE (melee)"
                        )
        except Exception:
            pass

        # Enhancement: reduce damage allocated to bearer by X.
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            red = int(getattr(t_unit, "special_rules", {}).get("enhancement_reduce_damage_taken", 0) or 0)
            if red:
                damage_mods.append(Modifier(ModifierOp.SUB, int(red), source="enhancement:reduce_damage_taken"))
        except Exception:
            pass
        # Unit/model abilities: reduce damage allocated to this model.
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            sr = getattr(t_unit, "special_rules", None) if t_unit is not None else None
            entries = list(sr.get("allocated_damage_reductions", []) or []) if isinstance(sr, dict) else []
            if t_unit is not None and hasattr(t_unit, "get_model_allocated_damage_reduction_entries"):
                model_entries = list(t_unit.get_model_allocated_damage_reduction_entries(target_model) or [])
                if model_entries:
                    entries.extend(model_entries)
            if entries:
                attack_type = "melee" if (self.parent_wargear and self.parent_wargear.is_melee()) else "ranged"
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    entry_type = str(entry.get("attack_type") or "any").strip().lower()
                    if entry_type not in ("any", attack_type):
                        continue
                    entry_op = str(entry.get("op") or "sub").strip().lower()
                    if entry_op in ("div", "divide", "halve", "half"):
                        div = int(entry.get("value", 0) or 0) or 2
                        damage_mods.append(Modifier(ModifierOp.DIV, int(div), source="ability:allocated_damage_halving"))
                        allocated_damage_entries.append(
                            {"op": "div", "value": int(div), "source": entry.get("source") or "Damage halving"}
                        )
                    else:
                        red = int(entry.get("value", 0) or 0)
                        if red:
                            damage_mods.append(Modifier(ModifierOp.SUB, int(red), source="ability:allocated_damage_reduction"))
                            allocated_damage_entries.append(
                                {"op": "sub", "value": int(red), "source": entry.get("source") or "Damage reduction"}
                            )
        except Exception:
            pass
        # Bondsman: Defender's Duty reduces damage by 1.
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            red = int(getattr(t_unit, "special_rules", {}).get("bondsman_damage_reduction", 0) or 0)
            if red:
                damage_mods.append(Modifier(ModifierOp.SUB, int(red), source="bondsman:reduce_damage_taken"))
        except Exception:
            pass
        # Stratagem: Frenzied Resilience reduces damage by 1 in Fight phase.
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            sr = getattr(t_unit, "special_rules", None) if t_unit is not None else None
            red = int(sr.get("frenzied_resilience_damage_reduction", 0) or 0) if isinstance(sr, dict) else 0
            if red:
                apply_bonus = True
                exp = str(sr.get("frenzied_resilience_expires_phase", "") or "").strip().upper()
                if exp:
                    try:
                        army = t_unit.get_parent_army()
                        game = getattr(getattr(army, "player", None), "game", None)
                        pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    except Exception:
                        pname = ""
                    if pname and pname != exp:
                        apply_bonus = False
                if apply_bonus:
                    damage_mods.append(Modifier(ModifierOp.SUB, int(red), source="stratagem:frenzied_resilience"))
        except Exception:
            pass
        # Defensive reaction stratagems: reduce damage allocated to target.
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            t_root = t_unit.get_attached_unit_root() if (t_unit is not None and hasattr(t_unit, "get_attached_unit_root")) else t_unit
            attack_type = "melee" if (self.parent_wargear and self.parent_wargear.is_melee()) else "ranged"
            attacker_key = attack_instance.get("attacker_key")
            if not attacker_key:
                try:
                    attacker_unit = getattr(attacker, "parent_unit", None)
                    if attacker_unit is not None:
                        attacker_root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
                        attacker_key = get_entity_id(attacker_root)
                except Exception:
                    attacker_key = None
            phase_key = self._resolve_phase_key(attacker_unit=getattr(attacker, "parent_unit", None), target_unit=t_root)
            for entry in self._iter_defensive_entries(
                t_root,
                "defensive_damage_reductions",
                attacker_key=attacker_key,
                attack_type=attack_type,
                phase_key=phase_key,
            ):
                red = int(entry.get("value", 0) or 0)
                if red:
                    damage_mods.append(Modifier(ModifierOp.SUB, int(red), source="stratagem:defensive_damage"))
                    defensive_damage_entries.append((red, entry.get("source") or "Defensive stratagem"))
        except Exception:
            pass

        # Channeller Stones (or similar): set Damage to 0 after a failed save.
        try:
            if bool(attack_instance.get("force_damage_zero")):
                source = str(attack_instance.get("force_damage_zero_source", "") or "First failed save").strip()
                damage_mods.append(Modifier(ModifierOp.SET, 0, source=source))
                damage_result['special_effects'].append(f"{source}: damage set to 0")
        except Exception:
            pass

        # Apply modifiers unless these are "mortal wounds in addition" (not currently used, but Core Rules require it).
        if attack_instance.get("mortal_wound", False) and attack_instance.get("mortal_wound_in_addition", False):
            final_damage = int(damage_value)
        else:
            final_damage, dbg = apply_numeric_modifiers(int(damage_value), damage_mods, base_raw=getattr(self, "_raw_damage", None))
            final_damage = apply_characteristic_caps(
                "damage",
                int(final_damage),
                allow_damage_zero=bool(dbg.get("had_set_to_zero", False)),
                base_raw=getattr(self, "_raw_damage", None),
            )

        # Apply "min 1" / "allow 0 if set to 0" outcome to the actual damage applied.
        damage_value = int(final_damage)

        # Add a readable effect string for damage reduction when it changed the value.
        try:
            red = int(getattr(getattr(target_model, "parent_unit", None), "special_rules", {}).get("enhancement_reduce_damage_taken", 0) or 0)
            if red and any(m.op == ModifierOp.SUB for m in damage_mods):
                damage_result['special_effects'].append(f"Enhancement -{red}D taken")
        except Exception:
            pass
        try:
            red = int(getattr(getattr(target_model, "parent_unit", None), "special_rules", {}).get("bondsman_damage_reduction", 0) or 0)
            if red and any(m.op == ModifierOp.SUB and "bondsman" in str(getattr(m, "source", "")) for m in damage_mods):
                damage_result['special_effects'].append(f"Bondsman -{red}D taken")
        except Exception:
            pass
        try:
            red = int(getattr(getattr(target_model, "parent_unit", None), "special_rules", {}).get("frenzied_resilience_damage_reduction", 0) or 0)
            if red and any(m.op == ModifierOp.SUB and "frenzied_resilience" in str(getattr(m, "source", "")) for m in damage_mods):
                damage_result['special_effects'].append(f"Frenzied Resilience -{red}D taken")
        except Exception:
            pass
        try:
            for red, src in defensive_damage_entries:
                if red:
                    damage_result['special_effects'].append(f"{src} -{red}D taken")
        except Exception:
            pass
        try:
            for entry in allocated_damage_entries:
                if isinstance(entry, dict):
                    val = int(entry.get("value", 0) or 0)
                    src = entry.get("source") or "Damage modifier"
                    op = str(entry.get("op") or "sub").strip().lower()
                    if op == "div":
                        if val == 2:
                            damage_result['special_effects'].append(f"{src}: Damage halved")
                        elif val:
                            damage_result['special_effects'].append(f"{src}: Damage /{val}")
                    elif val:
                        damage_result['special_effects'].append(f"{src} -{val}D taken")
                elif isinstance(entry, (list, tuple)) and entry:
                    red = int(entry[0])
                    src = entry[1] if len(entry) > 1 else "Damage reduction"
                    if red:
                        damage_result['special_effects'].append(f"{src} -{red}D taken")
        except Exception:
            pass
        
        wounds_cannot_be_ignored = bool(attack_instance.get("wounds_cannot_be_ignored", False))
        if not wounds_cannot_be_ignored:
            try:
                wounds_cannot_be_ignored = bool(self.wounds_cannot_be_ignored())
            except Exception:
                wounds_cannot_be_ignored = False

        # Apply damage with detailed tracking
        was_alive = target_model.is_alive
        damage_result.update(
            self._apply_damage_with_tracking(
                target_model,
                attacker,
                damage_value,
                bool(attack_instance.get("mortal_wound", False)),
                attack_instance=attack_instance,
                game_map=game_map,
                wounds_cannot_be_ignored=wounds_cannot_be_ignored,
            )
        )
        damage_result['model_killed'] = was_alive and not target_model.is_alive
        
        if bool(attack_instance.get('mortal_wound', False)):
            damage_result['special_effects'].append("Mortal Wounds")
        
        return damage_result

    def _apply_damage_with_tracking(
        self,
        target_model: 'Model',
        attacker: 'Model',
        damage_amount: int,
        is_mortal: bool,
        *,
        attack_instance: Optional[Dict] = None,
        game_map: Optional['Map'] = None,
        wounds_cannot_be_ignored: bool = False,
    ) -> Dict:
        """Apply damage with detailed tracking of Feel No Pain saves"""
        from warhammer40k_ai.utility.dice import get_roll
        
        result = {
            'damage_applied': 0,
            'fnp_saves': 0,
            'fnp_rolls': [],
            'excess_damage': 0
        }
        attack_instance = attack_instance if isinstance(attack_instance, dict) else {}
        if target_model is not None:
            target_model._last_damage_weapon_profile = self
            target_model._last_damage_source_kind = "attack"
        
        # Handle Feel No Pain saves
        final_damage = damage_amount
        try:
            fnp_abilities = target_model.parent_unit.has_feel_no_pain(target_model=target_model)
        except Exception:
            fnp_abilities = []
        # Defensive reaction stratagems: temporary Feel No Pain.
        try:
            t_unit = getattr(target_model, "parent_unit", None)
            t_root = t_unit.get_attached_unit_root() if (t_unit is not None and hasattr(t_unit, "get_attached_unit_root")) else t_unit
            attack_type = "melee" if (self.parent_wargear and self.parent_wargear.is_melee()) else "ranged"
            attacker_key = None
            try:
                attacker_unit = getattr(attacker, "parent_unit", None)
                if attacker_unit is not None:
                    attacker_root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
                    attacker_key = get_entity_id(attacker_root)
            except Exception:
                attacker_key = None
            phase_key = self._resolve_phase_key(attacker_unit=getattr(attacker, "parent_unit", None), target_unit=t_root)
            for entry in self._iter_defensive_entries(
                t_root,
                "defensive_fnp_overrides",
                attacker_key=attacker_key,
                attack_type=attack_type,
                phase_key=phase_key,
            ):
                val = int(entry.get("value", 0) or 0)
                if val:
                    fnp_abilities.append((val, None))
        except Exception:
            pass

        if fnp_abilities and not wounds_cannot_be_ignored:
            # Find the best applicable Feel No Pain ability
            attacker_unit = getattr(attacker, "parent_unit", None)
            attack_context = {
                "attack_instance": attack_instance,
                "attacker_unit": attacker_unit,
                "attacker_model": attacker,
            }
            best_fnp = target_model._get_best_applicable_fnp(
                fnp_abilities,
                self,
                is_mortal,
                attack_context=attack_context,
                attacker_unit=attacker_unit,
            )
            
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
        target_has_wounds = hasattr(target_model, "wounds")
        if target_has_wounds:
            try:
                target_model.wounds -= final_damage
            except Exception:
                pass
        
        # Handle model death
        try:
            alive_attr = getattr(target_model, "is_alive", True)
            alive = alive_attr() if callable(alive_attr) else bool(alive_attr)
        except Exception:
            alive = True
        if not alive:
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

            try:
                if hasattr(target_model, "die"):
                    target_model.die(game_map=game_map)
            except Exception:
                pass
            # Calculate excess damage (10th edition: excess damage is lost)
            if is_mortal and target_has_wounds:
                try:
                    if abs(target_model.wounds) > 0:
                        result['excess_damage'] = abs(target_model.wounds)
                except Exception:
                    pass
        
        # Check for damaged profile
        try:
            if hasattr(target_model, "_check_damaged_profile"):
                target_model._check_damaged_profile()
        except Exception:
            pass
        
        return result

    def _resolve_mortal_wound_amount(self, value) -> int:
        if value is None:
            return 0
        if isinstance(value, DiceCollection):
            try:
                return int(value.roll())
            except Exception:
                return 0
        if isinstance(value, Count):
            try:
                return int(value.resolve())
            except Exception:
                return 0
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return 0
            if s.isdigit():
                return int(s)
            try:
                return int(get_roll(s))
            except Exception:
                return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _apply_single_mortal_wound_with_tracking(
        self,
        target_model: 'Model',
        attacker: 'Model',
        attack_instance: Dict,
        game_map: Optional['Map'] = None,
    ) -> Dict:
        damage_result = {
            'damage_rolled': 1,
            'damage_applied': 0,
            'target_model': target_model.name,
            'excess_damage': 0,
            'model_killed': False,
            'fnp_saves': 0,
            'fnp_rolls': [],
            'damage_dice_rolls': [],
            'damage_expression': "1",
            'special_effects': ["Mortal Wounds"],
        }

        wounds_cannot_be_ignored = self._resolve_wounds_cannot_be_ignored(attack_instance)
        was_alive = target_model.is_alive
        damage_result.update(
            self._apply_damage_with_tracking(
                target_model,
                attacker,
                1,
                True,
                attack_instance=attack_instance,
                game_map=game_map,
                wounds_cannot_be_ignored=wounds_cannot_be_ignored,
            )
        )
        damage_result['model_killed'] = was_alive and not target_model.is_alive
        return damage_result

    @staticmethod
    def resolve_pending_mortal_wounds_for_target(
        pending_by_target: Dict,
        target_unit: Optional['Unit'],
        game_map: Optional['Map'] = None,
    ) -> None:
        if not pending_by_target or target_unit is None:
            return
        target_key = WargearProfile._pending_mortal_target_key(target_unit)
        entries = pending_by_target.pop(target_key, [])
        if not entries:
            return

        from ..utility.damage_allocation import DamageAllocationCtx

        for entry in entries:
            weapon_profile = entry.get("weapon_profile")
            attacker = entry.get("attacker")
            attack_instance = entry.get("attack_instance")
            attack_result = entry.get("attack_result")
            target_model = entry.get("target_model")
            no_spill = bool(entry.get("no_spill", False))

            if weapon_profile is None or attacker is None:
                continue
            if not isinstance(attack_instance, dict):
                attack_instance = {}

            if no_spill:
                if target_model is None or not getattr(target_model, "is_alive", True):
                    continue
                damage_result = weapon_profile._damage_target_with_tracking(
                    target_model, attacker, attack_instance, game_map=game_map
                )
                weapon_profile._record_damage_result(attack_result, damage_result)
                continue

            amount = int(entry.get("mortal_wound_amount", 0) or 0)
            if amount <= 0:
                continue

            attacker_unit = getattr(attacker, "parent_unit", None)
            if attacker_unit is None or not hasattr(attacker_unit, "_apply_mortal_wounds_to_unit"):
                continue

            initial_model = None
            if target_model is not None and getattr(target_model, "is_alive", True):
                initial_model = target_model

            try:
                wname = getattr(getattr(weapon_profile, "parent_wargear", None), "name", None) or getattr(
                    weapon_profile, "name", ""
                )
            except Exception:
                wname = ""
            try:
                aname = getattr(attacker, "name", "") or ""
            except Exception:
                aname = ""
            allocation_ctx = DamageAllocationCtx(
                reason="Allocate mortal wound",
                damage_source="attack",
                weapon_name=str(wname or ""),
                attacker_name=str(aname or ""),
            )

            def _apply(model):
                dmg = weapon_profile._apply_single_mortal_wound_with_tracking(
                    model,
                    attacker,
                    attack_instance,
                    game_map=game_map,
                )
                weapon_profile._record_damage_result(attack_result, dmg)

            attacker_unit._apply_mortal_wounds_to_unit(
                target_unit,
                amount,
                game_map=game_map,
                initial_model=initial_model,
                apply_fn=_apply,
                allocation_ctx=allocation_ctx,
                allow_initial_model_outside_candidates=bool(initial_model),
            )

    def _print_attack_summary(self, result: AttackResult) -> None:
        '''Print comprehensive attack summary.'''
        print(f"\nATTACK SUMMARY: {result.weapon_name}")
        print(f"   Attacker: {result.attacker_name} -> Target: {result.target_unit_name}")

        # Attack generation with dice details
        modifiers_str = f" ({', '.join(result.attacks_special_modifiers)})" if result.attacks_special_modifiers else ""
        dice_details = ""
        if result.attacks_dice_rolls:
            dice_str = ", ".join(map(str, result.attacks_dice_rolls))
            dice_details = f" - rolled: [{dice_str}]"
        print(
            f"   Attacks: {result.attacks_rolled} (from {result.attacks_dice_expression}{dice_details}){modifiers_str}"
        )

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

            print(
                f"   Hits: {result.total_hits}/{len(result.hit_results)} - {needed_str} - rolled: [{hit_rolls_str}]"
            )

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

            print(
                f"   Wounds: {result.total_wounds}/{len(result.wound_results)} - {needed_str} - rolled: [{wound_rolls_str}]"
            )

        # Save results with save type and modifiers
        if result.save_results:
            save_rolls = [str(save['roll']) for save in result.save_results]
            save_rolls_str = ", ".join(save_rolls)

            # Show save details - assume all saves are the same type for this attack
            first_save = result.save_results[0]
            save_type_str = "Inv" if first_save['save_type'] == 'invulnerable' else "Armor"

            if first_save['save_type'] == 'armor' and first_save['ap_modifier'] < 0:
                needed_str = (
                    f"needed {first_save['needed']}+ {save_type_str} "
                    f"(base {first_save['base_save']}+ with AP{first_save['ap_modifier']})"
                )
            else:
                needed_str = f"needed {first_save['needed']}+ {save_type_str}"

            failed_saves = len(result.save_results) - sum(1 for s in result.save_results if s['saved'])
            print(
                f"   Saves: {failed_saves}/{len(result.save_results)} failed - {needed_str} - rolled: [{save_rolls_str}]"
            )

        # Damage results with Feel No Pain details
        if result.damage_results:
            damage_summary = []
            for i, dmg in enumerate(result.damage_results):
                effects = f" [{', '.join(dmg['special_effects'])}]" if dmg['special_effects'] else ""
                killed = " (killed)" if dmg['model_killed'] else ""
                fnp_info = ""

                # Add Feel No Pain information
                if dmg['fnp_rolls']:
                    fnp_saves = dmg['fnp_saves']
                    fnp_total = len(dmg['fnp_rolls'])
                    fnp_rolls_str = ", ".join([str(roll['roll']) for roll in dmg['fnp_rolls']])
                    fnp_needed = dmg['fnp_rolls'][0]['needed'] if dmg['fnp_rolls'] else 'N/A'
                    fnp_info = f" FNP: {fnp_saves}/{fnp_total} saved (needed {fnp_needed}+ - rolled: [{fnp_rolls_str}])"

                # Add damage dice roll information
                damage_info = f"{dmg['damage_rolled']}->{dmg['damage_applied']}"
                if dmg['damage_dice_rolls']:
                    dice_rolls_str = ", ".join([str(roll) for roll in dmg['damage_dice_rolls']])
                    damage_info = (
                        f"{dmg['damage_rolled']}->{dmg['damage_applied']} "
                        f"(from {dmg['damage_expression']} - rolled: [{dice_rolls_str}])"
                    )

                damage_summary.append(f"#{i+1}: {damage_info} to {dmg['target_model']}{fnp_info}{effects}{killed}")
            print(f"   Damage: {result.total_damage_dealt} total - {', '.join(damage_summary)}")

        # Hazardous effects
        if result.hazardous_roll is not None:
            modified_hazard_roll = apply_hazardous_roll_modifier(self, result.hazardous_roll)
            hazard_modifier = hazardous_roll_modifier(self)
            hazard_result = "Backfire!" if modified_hazard_roll <= 1 else "Safe"
            if hazard_modifier:
                roll_text = f"{result.hazardous_roll} ({hazard_modifier:+d} -> {modified_hazard_roll})"
            else:
                roll_text = f"{result.hazardous_roll}"
            print(f"   Hazardous: Rolled {roll_text} - {hazard_result}")
            if result.hazardous_damage > 0:
                print(f"      {result.attacker_name} takes {result.hazardous_damage} mortal wounds")

        # Final summary
        if result.models_killed > 0:
            print(f"   Models eliminated: {result.models_killed}")

        print()  # Empty line for readability

    def opponent_wound_allocation(self, target: 'Unit', *, attacker: Optional['Model'] = None, game_map: Optional['Map'] = None) -> Optional['Model']:
        """Allocate wounds to target models (defender chooses only when rules allow)."""
        # Attached units: allocate to bodyguards while any exist; otherwise allocate to leader models.
        try:
            candidates = target.get_models_for_wound_allocation()
        except Exception:
            candidates = [m for m in (getattr(target, "models", []) or []) if getattr(m, "is_alive", True)]
        if not candidates:
            return None

        from ..utility.damage_allocation import DamageAllocationCtx, choose_damage_allocation_model
        try:
            wname = getattr(getattr(self, "parent_wargear", None), "name", None) or getattr(self, "name", "")
        except Exception:
            wname = ""
        try:
            aname = getattr(attacker, "name", "") if attacker is not None else ""
        except Exception:
            aname = ""

        return choose_damage_allocation_model(
            target,
            candidates,
            ctx=DamageAllocationCtx(reason="Allocate wound", damage_source="attack", weapon_name=str(wname or ""), attacker_name=str(aname or "")),
        )

    def _assassins_poisons_applies(self, attacker: 'Model') -> bool:
        try:
            unit = getattr(attacker, "parent_unit", None)
            sr = getattr(unit, "special_rules", None)
            if not (isinstance(sr, dict) and sr.get("pain_assassins_poisons_active")):
                return False
            parent = getattr(self, "parent_wargear", None)
            wname = str(getattr(parent, "name", "") or "").strip().lower()
            for blocked in ("blast pistol", "blaster", "dark lance"):
                if blocked in wname:
                    return False
            return True
        except Exception:
            return False

    ###########################################################################
    ### Wargear profile type checks
    ###########################################################################
    def is_pistol(self) -> bool:
        return 'pistol' in [keyword.lower() for keyword in self.get_keywords()]

    def is_heavy(self) -> bool:
        return 'heavy' in [keyword.lower() for keyword in self.get_keywords()]

    def is_hazardous(self) -> bool:
        return 'hazardous' in [keyword.lower() for keyword in self.get_keywords()]

    def is_overcharge(self) -> bool:
        return 'overcharge' in [keyword.lower() for keyword in self.get_keywords()]

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

    def is_plasma_warhead(self) -> bool:
        """Check if weapon has Plasma Warhead keyword."""
        return 'plasma warhead' in [keyword.lower() for keyword in self.get_keywords()]

    def is_linked_fire(self) -> bool:
        """Check if weapon has Linked Fire keyword."""
        return 'linked fire' in [keyword.lower() for keyword in self.get_keywords()]

    def is_psychic_assassin(self) -> bool:
        """Check if weapon has Psychic Assassin keyword."""
        return 'psychic assassin' in [keyword.lower() for keyword in self.get_keywords()]

    def can_shoot_plasma_warhead(
        self,
        attacker: 'Model',
        *,
        game_map: Optional['Map'] = None,
        out_of_phase: bool = False,
    ) -> Tuple[bool, str]:
        """
        Check if Plasma Warhead weapon can be fired this phase.

        Per wahapedia rule text:
        "The bearer can only shoot with this weapon in your Shooting phase, and only if it
        Remained Stationary this turn and you did not use its Deathstrike Missile ability
        to Designate Target or Adjust Target this phase."

        Returns:
            (can_shoot, reason) tuple
        """
        if not self.is_plasma_warhead():
            return True, "Not a Plasma Warhead weapon"

        unit = getattr(attacker, "parent_unit", None)
        if unit is None:
            return False, "Plasma Warhead requires a parent unit"
        if out_of_phase or not bool(getattr(unit, "_is_controlling_players_shooting_phase", lambda: False)()):
            return False, "Plasma Warhead can only be fired in your Shooting phase"

        # Check Remained Stationary
        if not bool(getattr(getattr(unit, "round_state", None), "remained_stationary_this_round", False)):
            return False, "Plasma Warhead requires unit to Remain Stationary"

        army = getattr(unit, "get_parent_army", lambda: None)()
        deathstrike_mgr = getattr(army, "deathstrike", None)
        if deathstrike_mgr is None:
            return False, "No Deathstrike manager found"

        try:
            from ..utility.entity_ids import get_entity_id
            unit_id = get_entity_id(unit)
        except ValueError:
            return False, "Unit ID not found"

        if not deathstrike_mgr.has_marker(unit_id):
            return False, "No Deathstrike marker placed (use Designate Target first)"

        # Check if Designate/Adjust was used this phase
        if deathstrike_mgr.used_designate_adjust_this_phase(unit_id):
            return False, "Cannot fire Plasma Warhead in same phase as Designate/Adjust"

        return True, "OK"

    def is_conversion(self) -> bool:
        """Check if weapon has Conversion keyword."""
        return 'conversion' in [keyword.lower() for keyword in self.get_keywords()]

    def get_conversion_distance(self, attacker: Optional['Model'] = None) -> float:
        """
        Extract distance threshold from Conversion keyword by parsing the unit's
        Conversion ability description from Datasheets_abilities.json.

        The Conversion ability description contains text like:
        "more than 12\" from the bearer" or "more than 24\" from the bearer"

        Args:
            attacker: Optional Model to get the unit's datasheet abilities from

        Returns:
            Distance threshold in inches (12.0, 18.0, or 24.0). Defaults to 12.0 if parsing fails.
        """
        # Try to parse distance from unit's Conversion ability
        if attacker is not None:
            try:
                unit = getattr(attacker, "parent_unit", None)
                if unit is not None:
                    datasheet = getattr(unit, "datasheet", None)
                    if datasheet is not None:
                        abilities = getattr(datasheet, "datasheets_abilities", [])
                        for ability in abilities:
                            if isinstance(ability, dict) and ability.get("name", "").lower() == "conversion":
                                description = ability.get("description", "")
                                # Parse "more than XX" from description
                                import re
                                match = re.search(r'more than (\d+)"', description)
                                if match:
                                    distance = float(match.group(1))
                                    return distance
            except Exception:
                pass

        # Default to 12.0 if parsing fails or no attacker provided
        return 12.0

    def get_conversion_crit_threshold(self) -> int:
        """Return the unmodified hit roll threshold for Conversion critical hits.

        Per the rules, Conversion always uses 4+ as the threshold for upgrading
        successful hits to critical hits.
        """
        return 4

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

    ###########################################################################
    ### Ork-specific keyword detection methods
    ###########################################################################
    def is_bubblechukka(self) -> bool:
        """Check if this weapon has the Bubblechukka keyword."""
        return 'bubblechukka' in [keyword.lower() for keyword in self.get_keywords()]

    def is_dead_choppy(self) -> bool:
        """Check if this weapon has the Dead Choppy keyword."""
        return 'dead choppy' in [keyword.lower() for keyword in self.get_keywords()]

    def is_harpooned(self) -> bool:
        """Check if this weapon has the Harpooned keyword."""
        return 'harpooned' in [keyword.lower() for keyword in self.get_keywords()]

    def is_hooked(self) -> bool:
        """Check if this weapon has the Hooked keyword."""
        return 'hooked' in [keyword.lower() for keyword in self.get_keywords()]

    def is_impaled(self) -> bool:
        """Check if this weapon has the Impaled keyword."""
        return 'impaled' in [keyword.lower() for keyword in self.get_keywords()]

    def is_snagged(self) -> bool:
        """Check if this weapon has the Snagged keyword."""
        return 'snagged' in [keyword.lower() for keyword in self.get_keywords()]

    def get_bubblechukka_profile_for_roll(self, roll: int) -> Optional['WargearProfile']:
        """
        Get the appropriate Bubblechukka profile based on a D6 roll.

        Args:
            roll: D6 roll result (1-6)

        Returns:
            The appropriate WargearProfile based on the roll:
            - 1-2: big bubble
            - 3-4: wobbly bubble
            - 5-6: dense bubble
            Returns None if this is not a Bubblechukka weapon or roll is invalid.
        """
        if not self.is_bubblechukka():
            return None

        if roll < 1 or roll > 6:
            return None

        if not self.parent_wargear:
            return None

        if roll <= 2:
            profile_name = "big bubble"
        elif roll <= 4:
            profile_name = "wobbly bubble"
        else:
            profile_name = "dense bubble"

        return self.parent_wargear.profiles.get(profile_name, None)

    def get_anti_specs(self) -> list[tuple[str, int]]:
        """Return all Anti-<keyword> <value>+ specs present on this profile (best-effort)."""
        out: list[tuple[str, int]] = []
        for keyword in self.get_keywords():
            try:
                raw = str(keyword or "").strip()
                if not raw:
                    continue
                lower = raw.lower()
                if not lower.startswith("anti-"):
                    continue
                # Format like "Anti-Vehicle 4+" or "Anti-Infantry 2+"
                parts = raw[5:].replace("+", "").split(" ")
                if len(parts) == 2 and parts[1].isdigit():
                    out.append((parts[0].lower(), int(parts[1])))
            except Exception:
                continue
        return out

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



def _split_wargear_name(raw_name: str) -> tuple[str, str]:
    if not raw_name:
        return "", "default"
    cleaned = raw_name.replace("\u2019", "'").replace("\u0192?T", "'")
    for sep in (" \u2013 ", " - ", " \u2014 "):
        if sep in cleaned:
            base, profile = cleaned.split(sep, 1)
            return base.strip(), profile.strip()
    return cleaned.strip(), "default"

class Wargear:
    def __init__(self, wargear_data: Dict):
        self._id = str(uuid.uuid4())
        raw_name = wargear_data.get('name', '') or ''
        self.name, profile_name = _split_wargear_name(raw_name)
        self.type = wargear_data.get('type', '')
        self.profiles = { profile_name: WargearProfile(profile_name, wargear_data, self) }

    @property
    def id(self) -> str:
        return self._id

    def clone(self) -> "Wargear":
        cloned = copy.deepcopy(self)
        cloned._id = str(uuid.uuid4())
        for profile in cloned.profiles.values():
            profile.parent_wargear = cloned
        return cloned
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

    def is_bubblechukka(self) -> bool:
        """Check if this wargear is a Bubblechukka weapon."""
        for profile in self.profiles.values():
            if profile.is_bubblechukka():
                return True
        return False

    def select_bubblechukka_profile(self) -> Optional[WargearProfile]:
        """
        Select a random Bubblechukka profile based on a D6 roll.

        Returns:
            The selected WargearProfile, or None if this is not a Bubblechukka weapon.
        """
        if not self.is_bubblechukka():
            return None

        roll = int(get_roll("D6"))
        first_profile = next(iter(self.profiles.values()))
        selected_profile = first_profile.get_bubblechukka_profile_for_roll(roll)

        if selected_profile:
            print(f"Bubblechukka rolled {roll}: using {selected_profile.name} profile")

        return selected_profile


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
    ending = ending.replace("one of the following:", "one of the following: ")
    ending = ending.replace("up to two of the following:", "up to two of the following: ")

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
        if ";" in ending:
            parts = [item.strip() for item in ending.split(";") if item.strip()]
            return parse_wargear_item(parts), 1
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
        s = (s or "").replace("\u00e2\u0080\u0099", "'").replace("\u2019", "'").lower().strip()
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
        t = text.replace("\u2019", "'").replace("\u2018", "'")
        t = t.replace("\u0192?T", "'")
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
        elif match := re.match(r"^up to (\d+) ([\w\s']+) can each be equipped with (.*)", description):
            # e.g. "Up to 2 models can each be equipped with one of the following: ..."
            assert not is_replacement
            actor, condition = parse_warger_actor_string(match.group(2))
            conditions.append(condition)
            model_limit = Quantity(min=1, max=int(match.group(1)))
            replacement_items, limit = parse_wargear_string_ending(match.group(3))
            item_limit = Quantity(min=1, max=limit)
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
        elif match := re.match(r"^this unit can have (.*)", description):
            replacement_items, limit = parse_wargear_string_ending(match.group(1))
            item_limit = Quantity(min=1, max=limit)
            actor = "unit"
        elif match := re.match(r"^it can have (.*)", description):
            replacement_items, limit = parse_wargear_string_ending(match.group(1))
            item_limit = Quantity(min=1, max=limit)
            actor = "unit"
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
                elif conditional.startswith(f"{search_str} this model's"):
                    new_conditional = conditional[len(f"{search_str} this model's"):].strip()
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
                elif conditional.startswith(f"{search_str} these options cannot be taken on the same model"):
                    # Equivalent mutex phrasing
                    option.conditionals.append("the same model cannot be equipped with more than one of these wargear options")
                elif conditional.startswith(f"{search_str} you cannot select both of these options for the same model"):
                    new_conditional = conditional[len(f"{search_str} "):].strip()
                    option.conditionals.append(new_conditional)
                elif conditional.startswith(f"{search_str} maximum 1 per model") or conditional.startswith(f"{search_str} maximum one per model"):
                    option.conditionals.append("maximum 1 per model")
                elif conditional.startswith(f"{search_str} to a maximum of"):
                    # e.g. "* To a maximum of 1 per 10 models in this unit."
                    option.conditionals.append(conditional[len(f"{search_str} "):].strip())
                elif conditional.startswith(f"{search_str} this weapon cannot be replaced"):
                    # Applies to the starred item(s) in this option
                    option.conditionals.append("lock_selected_items")
                elif conditional.startswith(f"{search_str} this model cannot have duplicates of these pieces of wargear") or conditional.startswith(f"{search_str} each model cannot have duplicates of these pieces of wargear"):
                    option.conditionals.append("no duplicates in choices")
                elif match := re.match(r" excluding the (\D+), you cannot select the same weapon from this list more than once per unit$", conditional[len(search_str):]):
                    new_conditional = conditional[len(f"{search_str} "):].strip()
                    option.conditionals.append(new_conditional)
                elif match := re.match(r" a model can only take one of these options, and if it does so its (\D+) cannot be replaced$", conditional[len(search_str):]):
                    new_conditional = conditional[len(f"{search_str} "):].strip()
                    option.conditionals.append(new_conditional)
                elif match := re.match(r" you cannot select the same weapon more than once per unit unless it contains (\d+) models, in which case you cannot select the same weapon more than twice per unit", conditional[len(search_str):]):
                    option.conditionals.append(match.group(0))
                else:
                    # Do not crash the parser for footnotes; keep the raw text as a conditional.
                    # (This will still show up in the matrix as a remaining gap if we don't enforce it.)
                    if DEBUG:
                        print(f"UNHANDLED POST_CONDITIONAL: {conditional}")
                    option.conditionals.append(conditional[len(f"{search_str} "):].strip() if search_str else conditional.strip())

    return wargear_options
