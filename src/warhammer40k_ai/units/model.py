from typing import List, Dict, Optional, Tuple
from .wargear import Wargear, WargearProfile
from .ability import Ability
from ..utility.count import Count, CountType
from ..utility.dice import get_roll
from ..utility.modifiers import compute_save_roll_modifier
from ..utility.model_base import Base
import uuid
import logging
import re

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..battlefield.map import Map
    from .unit import Unit
    from .wargear import WargearProfile

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class Model:
    """Represents a Warhammer 40k model with its attributes and wargear."""

    def __init__(
        self,
        name: str,
        movement: int,
        toughness: int,
        save: int,
        wounds: int,
        leadership: int,
        objective_control: int,
        model_base: Base,
        inv_save: Optional[int] = None,
        inv_save_condition: Optional[str] = None,
        *,
        movement_raw: Optional[str] = None,
        toughness_raw: Optional[str] = None,
        save_raw: Optional[str] = None,
        wounds_raw: Optional[str] = None,
        leadership_raw: Optional[str] = None,
        objective_control_raw: Optional[str] = None,
        inv_save_raw: Optional[str] = None,
    ):
        self.name = name.split(' \u2013 ')[0]
        # Model attributes have a base value, but can be modified by wargear, strategems, etc
        # We need to track base value and current value separately
        self._base_movement = movement
        self._movement = movement
        self._movement_raw = movement_raw
        self._base_toughness = toughness
        self._toughness = toughness
        self._toughness_raw = toughness_raw
        self._base_save = save
        self._save = save
        self._save_raw = save_raw
        self._inv_save = inv_save # nothing can modify this
        self._inv_save_condition = inv_save_condition
        self._inv_save_raw = inv_save_raw
        self._base_wounds = wounds
        self._wounds = wounds
        self._wounds_raw = wounds_raw
        self._base_leadership = leadership
        self._leadership = leadership
        self._leadership_raw = leadership_raw
        self._base_objective_control = objective_control
        self._objective_control = objective_control
        self._objective_control_raw = objective_control_raw

        self.model_base = model_base
        self.wargear: List[Wargear] = []
        self.abilities: Dict[Ability] = {}
        self.optional_wargear: List[str] = []

        # Gameplay related attributes
        self._id = str(uuid.uuid4())  # Generate a unique ID for each model
        self.parent_unit = None
        self.last_move_path = []
        # Rule usage / temporary buffs
        self._once_per_battle_used: set[str] = set()
        # Temporary effects keyed by effect id; each value is a small dict
        self._temporary_effects: dict[str, dict] = {}

    @property
    def id(self) -> str:
        """Return the unique ID of the model."""
        return self._id

    @property
    def is_alive(self) -> bool:
        """Return whether the model is alive."""
        return self.wounds > 0

    @property
    def is_character(self) -> bool:
        pu = getattr(self, "parent_unit", None)
        if pu is None:
            return False
        try:
            fn = getattr(pu, "has_keyword_local", None)
            if callable(fn):
                return bool(fn("Character"))
        except Exception:
            pass
        try:
            if not hasattr(pu, "keywords"):
                return bool(getattr(pu, "is_character", False))
            kws = getattr(pu, "keywords", []) or []
            return "character" in [str(k).lower() for k in kws]
        except Exception:
            pass
        return bool(getattr(pu, "is_character", False))

    @property
    def has_circular_base(self) -> bool:
        """Return whether the model has a circular base."""
        return self.model_base.has_circular_base

    @property
    def base_size(self) -> float:
        """Return the base size of the model."""
        return self.model_base.base_size

    @property
    def facing(self) -> float:
        """Return the facing of the model."""
        return self.model_base.facing

    @property
    def is_max_health(self) -> bool:
        """Return whether the model is at full health."""
        return self.wounds == self._base_wounds

    @property
    def health_percent(self) -> float:
        """Return the health percent of the model."""
        return (self.wounds / self._base_wounds) * 100

    def add_wargear(self, wargear: Wargear) -> None:
        """Add wargear to the model."""
        print(f"Appending: {type(wargear)}")
        self.wargear.append(wargear)
    
    def add_optional_wargear(self, wargear: str) -> None:
        """Add optional wargear to the model."""
        self.optional_wargear.append(wargear)

    def get_optional_wargear_by_name(self, wargear_name: str) -> Optional[Ability]:
        for wargear in self.optional_wargear:
            if wargear.lower() == wargear_name.lower():
                for ability in self.parent_unit.possible_abilities:
                    if ability.name.lower() == wargear_name.lower():
                        return ability
        return None

    def add_ability(self, ability: Ability) -> None:
        """Add ability to the model."""
        self.abilities[ability.name] = ability

    # ---------------- Once-per-battle / temporary rules helpers ----------------

    def has_used_once_per_battle(self, key: str) -> bool:
        k = (key or "").strip().lower()
        if not k:
            return False
        return k in (self._once_per_battle_used or set())

    def mark_used_once_per_battle(self, key: str) -> None:
        k = (key or "").strip().lower()
        if not k:
            return
        if not isinstance(getattr(self, "_once_per_battle_used", None), set):
            self._once_per_battle_used = set()
        self._once_per_battle_used.add(k)

    def activate_possessed_lord(self) -> bool:
        """
        Possessed Lord (Slaughterbound / similar):
        Once per battle, at the start of the Fight phase, this model can use this ability.
        If it does, until the end of the phase:
        - add 3 to the Attacks characteristic of melee weapons equipped by this model
        - those weapons have [DEVASTATING WOUNDS]

        Engine note: we expose this as an explicit activation API. A controller can call it at the appropriate timing.
        """
        key = "possessed_lord"
        if self.has_used_once_per_battle(key):
            return False
        # Install effect until end of Fight phase
        self._temporary_effects["possessed_lord"] = {
            "melee_attacks_bonus": 3,
            "devastating_wounds_melee": True,
            "expires_phase": "FIGHT_PHASE",
        }
        self.mark_used_once_per_battle(key)
        return True

    def get_temporary_melee_attacks_bonus(self) -> int:
        eff = getattr(self, "_temporary_effects", {}) or {}
        try:
            v = eff.get("possessed_lord", {})
            return int(v.get("melee_attacks_bonus", 0) or 0)
        except Exception:
            return 0

    def has_temporary_devastating_wounds_melee(self) -> bool:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict):
            return False
        for v in eff.values():
            try:
                if bool(v.get("devastating_wounds_melee", False)):
                    return True
            except Exception:
                continue
        return False

    # ---------------- Code Chivalric helpers ----------------

    def grant_code_chivalric_rerolls(self) -> None:
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        self._temporary_effects["code_chivalric_rerolls"] = {
            "hit_remaining": 1,
            "wound_remaining": 1,
        }

    def clear_code_chivalric_rerolls(self) -> None:
        try:
            eff = getattr(self, "_temporary_effects", None)
            if isinstance(eff, dict):
                eff.pop("code_chivalric_rerolls", None)
        except Exception:
            pass

    def can_use_code_chivalric_reroll(self, kind: str) -> bool:
        eff = getattr(self, "_temporary_effects", {}) or {}
        data = eff.get("code_chivalric_rerolls", {})
        if not isinstance(data, dict):
            return False
        key = "hit_remaining" if str(kind or "").strip().lower() == "hit" else "wound_remaining"
        try:
            return int(data.get(key, 0) or 0) > 0
        except Exception:
            return False

    def consume_code_chivalric_reroll(self, kind: str) -> bool:
        eff = getattr(self, "_temporary_effects", {}) or {}
        data = eff.get("code_chivalric_rerolls", {})
        if not isinstance(data, dict):
            return False
        key = "hit_remaining" if str(kind or "").strip().lower() == "hit" else "wound_remaining"
        try:
            remaining = int(data.get(key, 0) or 0)
        except Exception:
            remaining = 0
        if remaining <= 0:
            return False
        data[key] = remaining - 1
        eff["code_chivalric_rerolls"] = data
        return True

    def on_phase_end(self, phase) -> None:
        """Clear temporary effects that expire at end of the provided phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if not pname:
            return
        eff = getattr(self, "_temporary_effects", None)
        if not isinstance(eff, dict) or not eff:
            return
        to_del = []
        for k, v in list(eff.items()):
            try:
                if str(v.get("expires_phase", "") or "").strip().upper() == pname:
                    to_del.append(k)
            except Exception:
                continue
        for k in to_del:
            try:
                del eff[k]
            except Exception:
                pass

    def set_parent_unit(self, unit_ptr) -> None:
        """Set the parent unit of the model."""
        self.parent_unit = unit_ptr

    def set_location(self, x: float, y: float, z: float, facing: float) -> None:
        """Set the location and facing of the model."""
        self.model_base.x = x
        self.model_base.y = y
        self.model_base.z = z
        self.model_base.set_facing(facing)

    def get_location(self) -> Tuple[float, float, float, float]:
        """Get the location and facing of the model."""
        return self.model_base.x, self.model_base.y, self.model_base.z, self.model_base.facing

    ################
    ### Modifiers
    ################
    def take_damage(
        self,
        amount: int = 0,
        is_mortal: bool = False,
        weapon_profile: Optional['WargearProfile'] = None,
        game_map: Optional['Map'] = None,
        wounds_cannot_be_ignored: bool = False,
        is_psychic_attack: bool = False,
        attack_context: Optional[dict] = None,
    ) -> int:
        if not wounds_cannot_be_ignored and weapon_profile is not None:
            wcni_fn = getattr(weapon_profile, "wounds_cannot_be_ignored", None)
            if callable(wcni_fn):
                wounds_cannot_be_ignored = bool(wcni_fn())

        try:
            fnp_abilities = self.parent_unit.has_feel_no_pain()
        except Exception:
            fnp_abilities = []
        if fnp_abilities and not wounds_cannot_be_ignored:
            # Find the best applicable Feel No Pain ability (lowest dice value)
            best_fnp = self._get_best_applicable_fnp(
                fnp_abilities,
                weapon_profile,
                is_mortal,
                is_psychic_attack=is_psychic_attack,
                attack_context=attack_context,
            )
            
            if best_fnp:
                fnp_value, fnp_condition = best_fnp
                # Roll D6 for each point of damage to see if Feel No Pain saves it
                fnp_saves = 0
                condition_text = f" ({fnp_condition})" if fnp_condition else ""
                for i in range(amount):
                    fnp_roll = get_roll("D6")
                    if fnp_roll >= fnp_value:
                        fnp_saves += 1
                        print(f"{self.name} Feel No Pain{condition_text} save: rolled {fnp_roll}, needed {fnp_value}+ - SAVED")
                    else:
                        print(f"{self.name} Feel No Pain{condition_text} save: rolled {fnp_roll}, needed {fnp_value}+ - FAILED")
                
                # Reduce damage by the number of successful FNP saves
                amount -= fnp_saves
                if fnp_saves > 0:
                    print(f"{self.name} prevented {fnp_saves} damage with Feel No Pain{condition_text}")
            else:
                print(f"{self.name} has Feel No Pain abilities but none apply to this damage source")
        
        self.wounds -= amount
        print(f"{self.name} takes {amount} damage. It is {'Alive' if self.is_alive else 'Dead'}")
        excess_damage = 0
        if not self.is_alive:
            self.die(game_map=game_map)
            # below is left-over from 9th edition - excess damage is lost in 10th edition
            if is_mortal and abs(self.wounds) > 0:
                excess_damage = abs(self.wounds)
        self._check_damaged_profile()
        return excess_damage

    def _get_best_applicable_fnp(
        self,
        fnp_abilities: List[Tuple[int, Optional[str]]],
        weapon_profile: Optional['WargearProfile'],
        is_mortal: bool,
        *,
        is_psychic_attack: bool = False,
        attack_context: Optional[dict] = None,
        attacker_unit: Optional['Unit'] = None,
    ) -> Optional[Tuple[int, Optional[str]]]:
        """Find the best applicable Feel No Pain ability (lowest dice value) for the current damage source.
        
        Args:
            fnp_abilities: List of (dice_value, condition) tuples for all FNP abilities
            weapon_profile: The weapon profile that caused the damage (None for non-weapon damage)
            is_mortal: Whether the damage is mortal wounds
            
        Returns:
            Optional[Tuple[int, Optional[str]]]: The best applicable FNP ability, or None if none apply
        """
        applicable_fnp = []
        
        for dice_value, condition in fnp_abilities:
            if self._check_fnp_condition(
                condition,
                weapon_profile,
                is_mortal,
                is_psychic_attack=is_psychic_attack,
                attack_context=attack_context,
                attacker_unit=attacker_unit,
            ):
                applicable_fnp.append((dice_value, condition))
        
        if not applicable_fnp:
            return None
        
        # Return the FNP with the lowest dice value (best chance to save)
        return min(applicable_fnp, key=lambda x: x[0])

    def _check_fnp_condition(
        self,
        condition: Optional[str],
        weapon_profile: Optional['WargearProfile'],
        is_mortal: bool,
        *,
        is_psychic_attack: bool = False,
        attack_context: Optional[dict] = None,
        attacker_unit: Optional['Unit'] = None,
    ) -> bool:
        """Check if Feel No Pain condition is met for the current weapon profile.
        
        Args:
            condition: The FNP condition string (e.g., "against psychic attacks", "against mortal wounds")
            weapon_profile: The weapon profile that caused the damage (None for non-weapon damage)
            is_mortal: Whether the damage is mortal wounds
            
        Returns:
            bool: True if the FNP condition is met and should apply
        """
        if not condition:
            return True  # No condition means FNP always applies

        condition = condition.lower().strip()
        if not condition:
            return True

        if condition in ("against that attack", "against that attack instead"):
            return True

        requires_leading = "while leading" in condition
        if requires_leading:
            unit = getattr(self, "parent_unit", None)
            if not (unit and getattr(unit, "is_attached_leader", False)):
                return False
            condition = condition.replace("while leading a unit", "")
            condition = condition.replace("while leading", "")
            condition = condition.strip(" ,")
            if not condition:
                return True

        atk_ctx = attack_context if isinstance(attack_context, dict) else {}
        atk_instance = atk_ctx.get("attack_instance")
        if not isinstance(atk_instance, dict):
            atk_instance = {}

        if attacker_unit is None:
            attacker_unit = atk_ctx.get("attacker_unit")
        if attacker_unit is None:
            attacker_model = atk_ctx.get("attacker_model")
            if attacker_model is not None:
                attacker_unit = getattr(attacker_model, "parent_unit", None)

        def _coerce_int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        is_psychic = bool(is_psychic_attack)
        if weapon_profile is not None:
            is_psychic_fn = getattr(weapon_profile, "is_psychic", None)
            if callable(is_psychic_fn) and is_psychic_fn():
                is_psychic = True

        is_melee = False
        is_ranged = False
        parent = getattr(weapon_profile, "parent_wargear", None) if weapon_profile is not None else None
        if parent is not None:
            is_melee_fn = getattr(parent, "is_melee", None)
            if callable(is_melee_fn):
                is_melee = bool(is_melee_fn())
            is_ranged_fn = getattr(parent, "is_ranged", None)
            if callable(is_ranged_fn):
                is_ranged = bool(is_ranged_fn())

        weapon_keywords: list[str] = []
        if weapon_profile is not None:
            get_keywords = getattr(weapon_profile, "get_keywords", None)
            if callable(get_keywords):
                weapon_keywords = [str(keyword).lower() for keyword in get_keywords() if str(keyword or "").strip()]

        damage_char = None
        dmg_val = atk_instance.get("damage_characteristic") if isinstance(atk_instance, dict) else None
        if dmg_val is None and weapon_profile is not None:
            dmg_val = getattr(weapon_profile, "damage", None)
        if isinstance(dmg_val, Count) and dmg_val.ctype == CountType.FLAT:
            damage_char = _coerce_int(dmg_val.value)
        elif isinstance(dmg_val, int):
            damage_char = dmg_val
        elif isinstance(dmg_val, str):
            s = dmg_val.strip()
            if s.isdigit():
                damage_char = int(s)

        is_devastating = False
        if weapon_profile is not None:
            is_dev_fn = getattr(weapon_profile, "is_devastating_wounds", None)
            if callable(is_dev_fn):
                is_devastating = bool(is_dev_fn())

        crit_wound = bool(atk_instance.get("crit_wound", False))

        clauses = [c.strip() for c in re.split(r"\s*(?:,|\band\b|\bor\b)\s*", condition) if c.strip()]
        if not clauses:
            clauses = [condition]

        def _clause_matches(clause: str) -> bool:
            text = clause.strip()
            if text.startswith(("against ", "while ", "when ")):
                text = text.split(" ", 1)[1].strip()

            if "mortal wound" in text and is_mortal:
                return True
            if "psychic" in text and is_psychic:
                return True
            if "battle-shocked" in text or "battleshocked" in text:
                if "attack" in text or "attacker" in text:
                    if attacker_unit is None:
                        return False
                    is_bs_fn = getattr(attacker_unit, "is_battle_shocked", None)
                    if callable(is_bs_fn):
                        return bool(is_bs_fn())
                    return False
            if "damage characteristic" in text:
                if damage_char is not None and re.search(r"damage characteristic(?: of)?\s+1", text):
                    return int(damage_char) == 1
            if "devastating wounds" in text:
                if is_devastating and crit_wound:
                    return True
            if "melee" in text and is_melee:
                return True
            if "ranged" in text and is_ranged:
                return True

            for keyword in weapon_keywords:
                if keyword and keyword in text:
                    return True

            return False

        for clause in clauses:
            if _clause_matches(clause):
                return True

        return False  # Condition not met

    def die(self, game_map: Optional['Map'] = None) -> None:
        # Suppress print for comprehensive attack summary
        # print(f"{self.name} [{self.id}] has Died!!!")
        #self.callbacks[hook_events.ENEMY_MODEL_KILLED].append(self)
        # Trigger on-death abilities (before the model is removed from its unit)
        try:
            if getattr(self, "parent_unit", None) is not None:
                self.parent_unit._handle_model_destroyed(model=self, game_map=game_map)
        except Exception:
            # Never let reactive abilities crash core death/removal.
            pass

        self.parent_unit.remove_model(self, False, game_map=game_map)

    # Fleeing is like dying but does not trigger any rules of when a "model is destroyed"
    def flee(self, game_map: Optional['Map'] = None) -> None:
        logger.info(f"{self.name} [{self.id}] has Fled!!!")
        self.parent_unit.remove_model(self, True, game_map=game_map)

    def heal(self, amount: int = 0) -> None:
        self.wounds = min(self._base_wounds, self.wounds + amount)
        logger.info(f"{self.name} is healed for {amount} damage")
        self._check_damaged_profile()

    def _check_damaged_profile(self) -> None:
        """
        Apply or clear damaged-profile effects.

        Note: damaged profiles are primarily used by single-model units (Vehicles/Monsters),
        so we apply them at the parent-unit level.
        """
        if not (self.parent_unit and getattr(self.parent_unit, "damaged_profile", None) and getattr(self.parent_unit, "damaged_profile_desc", None)):
            return

        try:
            active = bool(self.is_alive and (self.wounds in self.parent_unit.damaged_profile))
        except Exception:
            active = False

        try:
            if active:
                # Unit-level handler parses and applies a supported subset.
                if hasattr(self.parent_unit, "_apply_damaged_profile_effects"):
                    self.parent_unit._apply_damaged_profile_effects(self.parent_unit.damaged_profile_desc)
                else:
                    self._apply_damaged_profile(self.parent_unit.damaged_profile_desc)
            else:
                if hasattr(self.parent_unit, "_clear_damaged_profile_effects"):
                    self.parent_unit._clear_damaged_profile_effects()
        except Exception:
            # Never let degraded-profile parsing break damage application.
            pass

    def _apply_damaged_profile(self, profile: str) -> None:
        # Implement the logic to apply the damaged profile
        # This could involve updating various attributes of the model
        logger.info(f"Applying damaged profile to {self.name}: {profile}")
        # Need string parsing to handle the profile

    ################
    ### Utility Math
    ################
    def edge_to_edge_distance(self, other: "Model") -> float:
        return self.model_base.edge_to_edge_distance(other.model_base)

    def vertical_distance(self, other: "Model") -> float:
        return self.model_base.vertical_distance(other.model_base)

    def collides_with(self, other: "Model") -> bool:
        return self.model_base.collides_with(other.model_base)

    def return_closest_model_in_unit(self, unit: 'Unit') -> 'Model':
        closest_model = None
        closest_dist = float('inf')
        from ..utility.aura_utils import distance_between_models_bases_3d
        models = unit.get_attached_unit_models()
        for model in models:
            dist = float(distance_between_models_bases_3d(self, model))
            if dist < closest_dist:
                closest_dist = dist
                closest_model = model
        return closest_model, closest_dist

    def find_targets_in_range(self, game_map: 'Map', wargear_item: Optional[Wargear] = None, wargear_profile: Optional[WargearProfile] = None) -> List['Unit']:
        targets = []
        enemy_units = game_map.get_enemy_units(self.parent_unit)
        for enemy_unit in enemy_units:
            closest_model, closest_dist = self.return_closest_model_in_unit(enemy_unit)
            if closest_model and closest_dist < self.maximum_range(wargear_item, wargear_profile):
                # Check Lone Operative restriction
                if enemy_unit.has_lone_operative():
                    # Lone Operative units can only be targeted if the attacking model is within 12 inches
                    if closest_dist > 12.0:
                        continue  # Skip this target due to Lone Operative restriction
                # Wreathed in Shadows (Belakor Shadow Form): 18" ranged targeting restriction.
                try:
                    from ..rules.shadow_form import target_unit_has_wreathed_in_shadows
                    if target_unit_has_wreathed_in_shadows(enemy_unit, game_map=game_map):
                        if closest_dist > 18.0:
                            continue
                except Exception:
                    pass
                targets.append(enemy_unit)
        return targets

    ################
    ### Properties
    ################
    @property
    def movement(self) -> int:
        # Core Rules modifier ordering is enforced by the unit modifier pipeline.
        try:
            if self.parent_unit and hasattr(self.parent_unit, "get_effective_model_characteristic"):
                return int(self.parent_unit.get_effective_model_characteristic(self, "movement"))
        except Exception:
            pass
        return int(self._movement)

    @movement.setter
    def movement(self, value: int) -> None:
        self._movement = value

    @property
    def toughness(self) -> int:
        try:
            if self.parent_unit and hasattr(self.parent_unit, "get_effective_model_characteristic"):
                return int(self.parent_unit.get_effective_model_characteristic(self, "toughness"))
        except Exception:
            pass
        return int(self._toughness)

    @toughness.setter
    def toughness(self, value: int) -> None:
        self._toughness = value

    @property
    def save(self) -> int:
        try:
            if self.parent_unit and hasattr(self.parent_unit, "get_effective_model_characteristic"):
                return int(self.parent_unit.get_effective_model_characteristic(self, "save"))
        except Exception:
            pass
        return int(self._save)

    @save.setter
    def save(self, value: int) -> None:
        self._save = value

    @property
    def inv_save(self) -> Tuple[Optional[int], Optional[str]]:
        return self._inv_save, self._inv_save_condition

    @property
    def wounds(self) -> int:
        return self._wounds

    @wounds.setter
    def wounds(self, value: int) -> None:
        self._wounds = value

    @property
    def leadership(self) -> int:
        try:
            if self.parent_unit and hasattr(self.parent_unit, "get_effective_model_characteristic"):
                return int(self.parent_unit.get_effective_model_characteristic(self, "leadership"))
        except Exception:
            pass
        return int(self._leadership)

    @leadership.setter
    def leadership(self, value: int) -> None:
        self._leadership = value

    @property
    def objective_control(self) -> int:
        try:
            if self.parent_unit and hasattr(self.parent_unit, "get_effective_model_characteristic"):
                return int(self.parent_unit.get_effective_model_characteristic(self, "objective_control"))
        except Exception:
            pass
        return int(self._objective_control)

    @objective_control.setter
    def objective_control(self, value: int) -> None:
        self._objective_control = value

    ################
    ### Location
    ################
    @property
    def x(self) -> float:
        return self.model_base.x

    @property
    def y(self) -> float:
        return self.model_base.y

    @property
    def z(self) -> float:
        return self.model_base.z

    @property
    def facing(self) -> float:
        return self.model_base.facing

    ################
    ### Battle Related
    ################
    def maximum_range(self, wargear_item: Optional[Wargear] = None, wargear_profile: Optional[WargearProfile] = None) -> int:
        max_range = 0
        if wargear_profile:
            return wargear_profile.range.max
        elif wargear_item:
            if wargear_item.is_ranged():
                max_range = max(max_range, wargear_item.maximum_range())
        else:
            for wargear in self.wargear:
                if wargear.is_ranged():
                    max_range = max(max_range, wargear.maximum_range())
        return max_range

    def ranged_attack(self, target: 'Unit', wargear_profile: WargearProfile) -> None:
        self.attack(target, wargear_profile)

    def melee_attack(self, target: 'Unit', wargear_profile: WargearProfile) -> None:
        self.attack(target, wargear_profile)

    def attack(self, target: 'Unit', wargear_profile: WargearProfile) -> None:
        assert target is not None
        assert wargear_profile is not None
        wargear_profile.attack(target, self)

    def passed_saving_throw(self, attack_instance: Dict, attacking_ap: int = 0) -> bool:
        assert attacking_ap <= 0
        atk = attack_instance if isinstance(attack_instance, dict) else {}
        save_value = self.save - attacking_ap
        save_type = "armor"
        inv_override = atk.get("inv_save_override", None)
        try:
            inv_override_val = int(inv_override) if inv_override is not None else None
        except (TypeError, ValueError):
            inv_override_val = None
        if inv_override_val is not None and inv_override_val > 0 and inv_override_val < save_value:
            save_value = inv_override_val
            save_type = "invulnerable"
        inv_save, inv_save_condition = self.inv_save
        if inv_save:
            # Check invulnerable save condition (string-based, not callable)
            condition_met = True
            if inv_save_condition and inv_save_condition.strip():
                condition_met = self._check_invulnerable_save_condition(inv_save_condition, atk)
            
            if condition_met and inv_save < save_value:
                save_value = min(save_value, inv_save)
                save_type = "invulnerable"

        dice_roll = get_roll("D6")
        if dice_roll == 1:  # unmodified dice roll of 1 is always a fail
            # Suppress print for comprehensive attack summary
            # print(f"Saving Throw: dice_roll == 1, returning False")
            return False

        dice_modifier, _effects = compute_save_roll_modifier(
            self,
            attack_instance=atk,
            ap=attacking_ap,
            save_type=save_type,
            weapon_profile=atk.get("weapon_profile"),
        )
        # Suppress print for comprehensive attack summary
        # print(f"Saving Throw: dice_roll: {dice_roll}, dice_modifier: {dice_modifier}, save_value: {save_value}")
        return (dice_roll + dice_modifier) >= save_value

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
            
            # Get weapon profile from attack_instance if available
            weapon_profile = attack_instance.get('weapon_profile')
            if not weapon_profile:
                # If no weapon profile available, default to applying the save
                return True
            
            # Check if the attacking weapon has this keyword
            weapon_keywords = [kw.lower() for kw in weapon_profile.get_keywords()]
            
            # Special case mappings for common keywords
            if keyword_to_check == "psychic":
                return "psychic" in weapon_keywords
            elif keyword_to_check == "melee":
                return weapon_profile.parent_wargear and weapon_profile.parent_wargear.is_melee()
            elif keyword_to_check == "ranged":
                return weapon_profile.parent_wargear and weapon_profile.parent_wargear.is_ranged()
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

    def failed_saving_throw(self, attack_instance: Dict, attacking_ap: int = 0) -> bool:
        return not self.passed_saving_throw(attack_instance, attacking_ap)

    ################
    ### String Representation
    ################
    def __str__(self) -> str:
        return (f"{self.name} (M:{self.movement}\", T:{self.toughness}, Sv:{self.save}+, "
                f"InvSv:{self.inv_save or '-'}+, W:{self.wounds}, Ld:{self.leadership}+, "
                f"OC:{self.objective_control}\nbase_size:{self.model_base}\n"
                f"wargear:{self.wargear}\noptional_wargear:{self.optional_wargear}\n"
                f"abilities:{self.abilities.keys()}\nid:{self.id})")

    def __repr__(self) -> str:
        return (f"Model(id='{self.id}', name='{self.name}', M={self.movement}, "
                f"T={self.toughness}, Sv={self.save}, InvSv={self.inv_save}, "
                f"W={self.wounds}, Ld={self.leadership}, OC={self.objective_control}\n"
                f"base_size={self.model_base}\nwargear={self.wargear}\n"
                f"optional_wargear={self.optional_wargear})\n"
                f"abilities={self.abilities.keys()})")

    def __eq__(self, other: "Model") -> bool:
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
