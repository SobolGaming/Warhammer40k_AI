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
        keywords: Optional[List[str]] = None,
        faction_keywords: Optional[List[str]] = None,
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

        # Per-model keywords (initialized from datasheet)
        self.keywords: List[str] = list(keywords or [])
        self.faction_keywords: List[str] = list(faction_keywords or [])

        # Gameplay related attributes
        self._id = str(uuid.uuid4())  # Generate a unique ID for each model
        self.parent_unit = None
        self.last_move_path = []
        # Rule usage / temporary buffs
        self._once_per_battle_used: set[str] = set()
        self._once_per_battle_use_count: dict[str, int] = {}
        self._once_per_battle_extra_uses: dict[str, int] = {}
        self._once_per_battle_last_phase: dict[str, str] = {}
        self._once_per_battle_round_used: dict[str, int] = {}
        # Temporary effects keyed by effect id; each value is a small dict
        self._temporary_effects: dict[str, dict] = {}
        # Pending placement (e.g., reanimation/split) and model-specific tags
        self._pending_placement: bool = False
        self._pending_placement_source: Optional[str] = None
        self._horrors_kind: Optional[str] = None
        # Last damage context (best-effort)
        self._last_damage_source_kind: Optional[str] = None
        self._last_damage_weapon_profile = None

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
        except (AttributeError, TypeError, ValueError):
            logger.debug("Model.is_character failed has_keyword_local lookup.", exc_info=True)
        try:
            if not hasattr(pu, "keywords"):
                return bool(getattr(pu, "is_character", False))
            kws = getattr(pu, "keywords", []) or []
            return "character" in [str(k).lower() for k in kws]
        except (AttributeError, TypeError, ValueError):
            logger.debug("Model.is_character failed keyword list fallback.", exc_info=True)
        return bool(getattr(pu, "is_character", False))

    def has_keyword(self, keyword: str) -> bool:
        """Check if this model has the specified keyword (case-insensitive)."""
        kw = (keyword or "").lower().strip()
        if not kw:
            return False
        try:
            return kw in [k.lower() for k in (self.keywords or [])]
        except Exception:
            return False

    def has_any_keyword(self, keyword: str) -> bool:
        """Check if this model has the specified keyword in keywords or faction_keywords (case-insensitive)."""
        kw = (keyword or "").lower().strip()
        if not kw:
            return False
        try:
            if kw in [k.lower() for k in (self.keywords or [])]:
                return True
        except (AttributeError, TypeError):
            logger.debug("Model.has_any_keyword failed keywords lookup.", exc_info=True)
        try:
            if kw in [k.lower() for k in (self.faction_keywords or [])]:
                return True
        except (AttributeError, TypeError):
            logger.debug("Model.has_any_keyword failed faction_keywords lookup.", exc_info=True)
        return False

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
        logger.info(f"Appending: {type(wargear)}")
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

    @staticmethod
    def _normalize_phase_name(phase_name: object) -> str:
        if phase_name is None:
            return ""
        if hasattr(phase_name, "name"):
            phase_name = getattr(phase_name, "name", "")
        text = str(phase_name or "").strip()
        if not text:
            return ""
        return text.upper().replace(" ", "_")

    def _resolve_game(self):
        unit = getattr(self, "parent_unit", None)
        if unit is None or not hasattr(unit, "get_parent_army"):
            return None
        army = unit.get_parent_army()
        if army is None:
            return None
        player = getattr(army, "player", None)
        if player is None:
            return None
        return getattr(player, "game", None)

    def _current_phase_info(self, phase_name: object = None) -> tuple[str, str, object]:
        game = self._resolve_game()
        phase_key = self._normalize_phase_name(phase_name)
        phase_label = ""
        if game is not None:
            if not phase_key:
                phase_key = self._normalize_phase_name(getattr(game, "phase", None))
            label_fn = getattr(game, "_current_phase_label", None)
            if callable(label_fn):
                phase_label = str(label_fn() or "")
        if not phase_label and phase_key:
            phase_label = phase_key.replace("_", " ").title()
        return phase_key, phase_label, game

    def _allowed_once_per_battle_uses(self, k: str) -> int:
        extra = int((getattr(self, "_once_per_battle_extra_uses", {}) or {}).get(k, 0) or 0)
        if extra < 0:
            extra = 0
        return 1 + extra

    def remaining_once_per_battle_uses(self, key: str, *, phase_name: object = None) -> int:
        k = (key or "").strip().lower()
        if not k:
            return 0
        phase_key, _, _ = self._current_phase_info(phase_name)
        used_count = int((getattr(self, "_once_per_battle_use_count", {}) or {}).get(k, 0) or 0)
        allowed = self._allowed_once_per_battle_uses(k)
        remaining = max(0, allowed - used_count)
        if remaining <= 0:
            return 0
        if phase_key and used_count > 0:
            last_phase = str((getattr(self, "_once_per_battle_last_phase", {}) or {}).get(k, "") or "")
            if last_phase and last_phase == phase_key:
                used_by_round = getattr(self, "_once_per_battle_round_used", None)
                if not isinstance(used_by_round, dict):
                    return 0
                current_round = self._current_battle_round()
                if current_round <= 0:
                    return 0
                try:
                    last_round = int(used_by_round.get(k, 0) or 0)
                except Exception:
                    return 0
                if int(last_round) == int(current_round):
                    return 0
        return remaining

    def has_used_once_per_battle(self, key: str, *, phase_name: object = None) -> bool:
        return self.remaining_once_per_battle_uses(key, phase_name=phase_name) <= 0

    def grant_once_per_battle_extra_use(self, key: str, *, uses: int = 1) -> bool:
        k = (key or "").strip().lower()
        if not k:
            return False
        add = int(uses or 0)
        if add <= 0:
            return False
        extra = getattr(self, "_once_per_battle_extra_uses", None)
        if not isinstance(extra, dict):
            extra = {}
            self._once_per_battle_extra_uses = extra
        extra[k] = int(extra.get(k, 0) or 0) + add
        return True

    def mark_used_once_per_battle(
        self,
        key: str,
        *,
        phase_name: object = None,
        ability_name: str = "",
        source: str = "datasheet",
        publish_event: bool = True,
    ) -> bool:
        k = (key or "").strip().lower()
        if not k:
            return False
        phase_key, phase_label, game = self._current_phase_info(phase_name)
        if self.has_used_once_per_battle(k, phase_name=phase_key):
            return False
        used_set = getattr(self, "_once_per_battle_used", None)
        if not isinstance(used_set, set):
            used_set = set()
            self._once_per_battle_used = used_set
        used_set.add(k)
        counts = getattr(self, "_once_per_battle_use_count", None)
        if not isinstance(counts, dict):
            counts = {}
            self._once_per_battle_use_count = counts
        counts[k] = int(counts.get(k, 0) or 0) + 1
        last_phase = getattr(self, "_once_per_battle_last_phase", None)
        if not isinstance(last_phase, dict):
            last_phase = {}
            self._once_per_battle_last_phase = last_phase
        if phase_key:
            last_phase[k] = phase_key
        br = self._current_battle_round()
        if br > 0:
            used_round = getattr(self, "_once_per_battle_round_used", None)
            if not isinstance(used_round, dict):
                used_round = {}
                self._once_per_battle_round_used = used_round
            used_round[k] = int(br)
        if not publish_event or game is None:
            return True
        event_system = getattr(game, "event_system", None)
        if event_system is None or not hasattr(event_system, "publish"):
            return True
        unit = getattr(self, "parent_unit", None)
        if unit is None or not hasattr(unit, "get_parent_army"):
            return True
        army = unit.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return True
        ability_label = str(ability_name or "").strip() or k.replace("_", " ").title()
        event_system.publish(
            "once_per_battle_ability_used",
            player=player,
            game=game,
            unit=unit,
            model=self,
            ability_key=k,
            ability_name=ability_label,
            phase_key=phase_key,
            phase_name=phase_label,
            source=str(source or "").strip().lower() or "datasheet",
        )
        return True

    def _current_battle_round(self, battle_round: Optional[int] = None) -> int:
        if battle_round is not None:
            try:
                return int(battle_round)
            except Exception:
                return int(battle_round or 0)
        game = self._resolve_game()
        if game is None:
            return 0
        try:
            return int(getattr(game, "turn", 0) or 0)
        except Exception:
            return 0

    def has_used_once_per_battle_round(self, key: str, *, battle_round: Optional[int] = None) -> bool:
        k = (key or "").strip().lower()
        if not k:
            return False
        br = self._current_battle_round(battle_round)
        if br <= 0:
            return False
        used = getattr(self, "_once_per_battle_round_used", None)
        if not isinstance(used, dict):
            return False
        try:
            return int(used.get(k, 0) or 0) == br
        except Exception:
            return False

    def mark_used_once_per_battle_round(
        self,
        key: str,
        *,
        battle_round: Optional[int] = None,
        ability_name: str = "",
        source: str = "datasheet",
    ) -> bool:
        k = (key or "").strip().lower()
        if not k:
            return False
        br = self._current_battle_round(battle_round)
        if br <= 0:
            return False
        if self.has_used_once_per_battle_round(k, battle_round=br):
            return False
        used = getattr(self, "_once_per_battle_round_used", None)
        if not isinstance(used, dict):
            used = {}
            self._once_per_battle_round_used = used
        used[k] = int(br)
        return True

    def _activate_once_per_battle_melee_buff(
        self,
        *,
        key: str,
        ability_name: str,
        attacks_bonus: int = 0,
        ap_bonus: int = 0,
        strength_bonus: int = 0,
        damage_bonus: int = 0,
        devastating_wounds: bool = False,
    ) -> bool:
        key = str(key or "").strip().lower()
        if not key:
            return False
        if self.has_used_once_per_battle(key):
            return False
        effects = getattr(self, "_temporary_effects", None)
        if not isinstance(effects, dict):
            effects = {}
            self._temporary_effects = effects
        entry = {"expires_phase": "FIGHT_PHASE"}
        if attacks_bonus:
            entry["melee_attacks_bonus"] = int(attacks_bonus)
        if ap_bonus:
            entry["melee_ap_bonus"] = int(ap_bonus)
        if strength_bonus:
            entry["melee_strength_bonus"] = int(strength_bonus)
            entry["melee_strength_bonus_source"] = str(ability_name or "").strip() or "Melee strength bonus"
        if damage_bonus:
            entry["melee_damage_bonus"] = int(damage_bonus)
            entry["melee_damage_bonus_source"] = str(ability_name or "").strip() or "Melee damage bonus"
        if devastating_wounds:
            entry["devastating_wounds_melee"] = True
        effects[key] = entry
        self.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet")
        return True

    def activate_possessed_lord(self) -> bool:
        """
        Possessed Lord (Slaughterbound / similar):
        Once per battle, at the start of the Fight phase, this model can use this ability.
        If it does, until the end of the phase:
        - add 3 to the Attacks characteristic of melee weapons equipped by this model
        - those weapons have [DEVASTATING WOUNDS]

        Engine note: we expose this as an explicit activation API. A controller can call it at the appropriate timing.
        """
        return self._activate_once_per_battle_melee_buff(
            key="possessed_lord",
            ability_name="Possessed Lord",
            attacks_bonus=3,
            devastating_wounds=True,
        )

    def activate_fight_phase_melee_ap_boost(
        self,
        *,
        key: str = "fight_phase_melee_ap_boost",
        ability_name: str = "",
    ) -> bool:
        """
        Once per battle, at the start of the Fight phase, this model can use this ability.
        If it does, until the end of the phase:
        - add 3 to the Attacks characteristic of melee weapons equipped by this model
        - improve the Armour Penetration characteristic of those weapons by 1
        """
        label = str(ability_name or "").strip() or "Fight phase melee boost"
        return self._activate_once_per_battle_melee_buff(
            key=key,
            ability_name=label,
            attacks_bonus=3,
            ap_bonus=1,
        )

    def activate_fight_phase_melee_attacks_strength_boost(
        self,
        *,
        key: str,
        ability_name: str,
        attacks_bonus: int = 3,
        strength_bonus: int = 3,
    ) -> bool:
        """
        Once per battle, at the start of the Fight phase, this model can use this ability.
        If it does, until the end of the phase:
        - add to the Attacks characteristic of melee weapons equipped by this model
        - add to the Strength characteristic of melee weapons equipped by this model
        """
        label = str(ability_name or "").strip() or "Fight phase melee attacks/strength boost"
        try:
            attacks_bonus = int(attacks_bonus or 0)
        except Exception:
            attacks_bonus = 0
        try:
            strength_bonus = int(strength_bonus or 0)
        except Exception:
            strength_bonus = 0
        if attacks_bonus <= 0 and strength_bonus <= 0:
            return False
        return self._activate_once_per_battle_melee_buff(
            key=key,
            ability_name=label,
            attacks_bonus=int(attacks_bonus),
            strength_bonus=int(strength_bonus),
        )

    def activate_fight_phase_melee_attacks_devastating_wounds_boost(
        self,
        *,
        key: str,
        ability_name: str,
        attacks_bonus: int = 3,
    ) -> bool:
        """
        Once per battle, at the start of the Fight phase, this model can use this ability.
        If it does, until the end of the phase:
        - add to the Attacks characteristic of melee weapons equipped by this model
        - those weapons have [DEVASTATING WOUNDS]
        """
        label = str(ability_name or "").strip() or "Fight phase melee devastating wounds boost"
        try:
            attacks_bonus = int(attacks_bonus or 0)
        except Exception:
            attacks_bonus = 0
        if attacks_bonus <= 0:
            return False
        return self._activate_once_per_battle_melee_buff(
            key=key,
            ability_name=label,
            attacks_bonus=int(attacks_bonus),
            devastating_wounds=True,
        )

    def activate_fight_phase_melee_full_characteristic_boost(
        self,
        *,
        key: str,
        ability_name: str,
        bonus: int = 1,
    ) -> bool:
        """
        Once per battle, at the start of the Fight phase, this model can use this ability.
        If it does, until the end of the phase, improve the Strength, Attacks, Armour Penetration
        and Damage characteristics of melee weapons equipped by this model by the given bonus.
        """
        label = str(ability_name or "").strip() or "Fight phase melee boost"
        try:
            bonus = int(bonus or 0)
        except Exception:
            bonus = 0
        if bonus == 0:
            return False
        return self._activate_once_per_battle_melee_buff(
            key=key,
            ability_name=label,
            attacks_bonus=bonus,
            ap_bonus=bonus,
            strength_bonus=bonus,
            damage_bonus=bonus,
        )

    def _resolve_weapon_flat_attacks_and_strength(self, weapon_name: str) -> tuple[str, int, int]:
        target = self._normalize_weapon_name(weapon_name)
        if not target:
            return "", 0, 0

        unit = getattr(self, "parent_unit", None)
        match_fn = getattr(unit, "_weapon_name_matches", None) if unit is not None else None

        best_weapon_name = ""
        best_attacks = 0
        best_strength = 0
        best_score = -1

        for wargear in list(getattr(self, "wargear", []) or []):
            if wargear is None:
                continue
            base_name = str(getattr(wargear, "name", "") or "").strip()
            if not base_name:
                continue
            profiles = getattr(wargear, "profiles", None)
            if not isinstance(profiles, dict):
                continue
            for profile_name, profile in sorted(profiles.items(), key=lambda item: str(item[0]).lower()):
                candidate_names = [base_name]
                profile_label = str(profile_name or "").strip()
                if profile_label and profile_label.lower() != "default":
                    candidate_names.append(f"{base_name} - {profile_label}")

                matched = False
                for candidate in candidate_names:
                    candidate_norm = self._normalize_weapon_name(candidate)
                    if not candidate_norm:
                        continue
                    if callable(match_fn) and bool(match_fn([weapon_name], candidate)):
                        matched = True
                        break
                    if candidate_norm == target or candidate_norm in target or target in candidate_norm:
                        matched = True
                        break
                if not matched:
                    continue

                attacks_raw = getattr(profile, "attacks", None)
                if isinstance(attacks_raw, Count):
                    if attacks_raw.ctype is not CountType.FLAT:
                        continue
                    attacks_value = int(attacks_raw.value or 0)
                elif isinstance(attacks_raw, int):
                    attacks_value = int(attacks_raw)
                else:
                    continue

                strength_raw = getattr(profile, "strength", 0)
                strength_value = int(strength_raw) if isinstance(strength_raw, int) else 0
                if attacks_value <= 0 or strength_value <= 0:
                    continue

                score = len(self._normalize_weapon_name(base_name))
                if score > best_score:
                    best_score = score
                    best_weapon_name = str(base_name)
                    best_attacks = int(attacks_value)
                    best_strength = int(strength_value)

        return best_weapon_name, best_attacks, best_strength

    def activate_fight_phase_weapon_attacks_strength_multiplier(
        self,
        *,
        key: str,
        ability_name: str,
        weapon_name: str,
        attacks_multiplier: int = 1,
        strength_multiplier: int = 1,
        crit_wound_threshold: int = 0,
        crit_all_attacks: bool = False,
    ) -> bool:
        """
        Once per battle, at the start of the Fight phase:
        multiply a named weapon's Attacks/Strength and optionally force critical wounds
        on successful wound rolls.
        """
        key = str(key or "").strip().lower()
        if not key:
            return False
        if self.has_used_once_per_battle(key):
            return False

        resolved_weapon_name, base_attacks, base_strength = self._resolve_weapon_flat_attacks_and_strength(weapon_name)
        if not resolved_weapon_name:
            resolved_weapon_name = str(weapon_name or "").strip()
        if not resolved_weapon_name:
            return False

        attacks_multiplier = int(attacks_multiplier or 1)
        strength_multiplier = int(strength_multiplier or 1)
        crit_wound_threshold = int(crit_wound_threshold or 0)

        applied = False
        source_name = str(ability_name or "").strip() or "Fight phase weapon multiplier"

        if attacks_multiplier > 1 and base_attacks > 0:
            self.set_temporary_weapon_attacks_override(
                key=f"{key}:attacks",
                weapon_name=resolved_weapon_name,
                attacks_value=int(base_attacks * attacks_multiplier),
                source=source_name,
                expires_phase="FIGHT_PHASE",
            )
            applied = True

        if strength_multiplier > 1 and base_strength > 0:
            self.set_temporary_weapon_bonus(
                key=f"{key}:strength",
                weapon_name=resolved_weapon_name,
                strength_bonus=int(base_strength * (strength_multiplier - 1)),
                source=source_name,
                expires_phase="FIGHT_PHASE",
            )
            applied = True

        if crit_wound_threshold > 0:
            crit_weapon_names: list[str] = []
            if crit_all_attacks:
                for wargear in list(getattr(self, "wargear", []) or []):
                    if wargear is None:
                        continue
                    is_melee = bool(getattr(wargear, "is_melee", lambda: False)())
                    if not is_melee:
                        continue
                    name = str(getattr(wargear, "name", "") or "").strip()
                    if name and name not in crit_weapon_names:
                        crit_weapon_names.append(name)
            if not crit_weapon_names:
                crit_weapon_names = [resolved_weapon_name]

            for index, crit_weapon_name in enumerate(sorted(crit_weapon_names, key=lambda n: n.lower())):
                self.set_temporary_weapon_wound_crit_bonus(
                    key=f"{key}:crit:{index}",
                    weapon_name=str(crit_weapon_name),
                    crit_wound_threshold=int(crit_wound_threshold),
                    source=source_name,
                    expires_phase="FIGHT_PHASE",
                )
            applied = True

        if not applied:
            return False
        self.mark_used_once_per_battle(key, ability_name=source_name, source="datasheet")
        return True

    def activate_fight_phase_hellforged_attacks_bonus(
        self,
        *,
        key: str,
        ability_name: str,
        weapon_name: str = "hellforged",
        attacks_bonus: int = 3,
    ) -> bool:
        """
        Once per battle, at the start of the Fight phase:
        add Attacks to this model's hellforged weapons until end of phase.
        """
        key = str(key or "").strip().lower()
        if not key:
            return False
        if self.has_used_once_per_battle(key):
            return False
        try:
            attacks_bonus = int(attacks_bonus or 0)
        except Exception:
            attacks_bonus = 0
        if attacks_bonus <= 0:
            return False
        self.set_temporary_weapon_bonus(
            key=key,
            weapon_name=str(weapon_name or "hellforged").strip() or "hellforged",
            attacks_bonus=int(attacks_bonus),
            source=str(ability_name or "").strip() or "Hellforged weapons",
            expires_phase="FIGHT_PHASE",
        )
        self.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet")
        return True

    def activate_movement_phase_move_weapon_bonus(
        self,
        *,
        key: str,
        ability_name: str,
        move_bonus_dice: str = "",
        move_bonus_flat: int = 0,
        weapon_name: str,
        attacks_bonus: int,
    ) -> bool:
        """
        Once per battle, before a Normal move in the Movement phase:
        add Move (dice/flat) and weapon Attacks bonus until end of turn.
        """
        key = str(key or "").strip().lower()
        if not key:
            return False
        if self.has_used_once_per_battle(key):
            return False
        bonus = 0
        move_bonus_dice = str(move_bonus_dice or "").strip().upper()
        if move_bonus_dice:
            try:
                bonus += int(get_roll(move_bonus_dice) or 0)
            except Exception:
                pass
        try:
            move_bonus_flat = int(move_bonus_flat or 0)
        except Exception:
            move_bonus_flat = 0
        if move_bonus_flat > 0:
            bonus += int(move_bonus_flat)
        try:
            attacks_bonus = int(attacks_bonus or 0)
        except Exception:
            attacks_bonus = 0
        if bonus <= 0 and attacks_bonus <= 0:
            return False
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        entry = {"expires_phase": "FIGHT_PHASE"}
        if bonus:
            entry["movement_bonus"] = int(bonus)
            entry["movement_bonus_source"] = str(ability_name or "").strip() or "Movement bonus"
            if move_bonus_dice:
                entry["movement_bonus_dice"] = move_bonus_dice
            if move_bonus_flat > 0:
                entry["movement_bonus_flat"] = int(move_bonus_flat)
        weapon_name = str(weapon_name or "").strip()
        if attacks_bonus:
            source_label = str(ability_name or "").strip() or "Weapon attacks bonus"
            weapon_name_norm = self._normalize_weapon_name(weapon_name)
            if weapon_name_norm and (weapon_name_norm == "melee weapons" or weapon_name_norm == "melee weapon"):
                entry["melee_attacks_bonus"] = int(attacks_bonus)
                entry["melee_attacks_bonus_source"] = source_label
            elif weapon_name:
                entry["weapon_attacks_bonus"] = {weapon_name: int(attacks_bonus)}
                entry["weapon_attacks_bonus_source"] = source_label
        self._temporary_effects[key] = entry
        self.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet")
        return True

    def activate_hand_of_asuryan(
        self,
        *,
        key: str = "hand_of_asuryan",
        ability_name: str = "Hand of Asuryan",
        weapon_name: str = "Bloody Twins",
    ) -> bool:
        """
        Once per battle, when selected to shoot:
        - Bloody Twins has Damage 3
        - Gains [ANTI-INFANTRY 5+] and [DEVASTATING WOUNDS] until end of phase
        """
        key = str(key or "").strip().lower()
        if not key:
            return False
        if self.has_used_once_per_battle(key):
            return False
        weapon_name = str(weapon_name or "").strip()
        if not weapon_name:
            return False
        label = str(ability_name or "").strip() or "Hand of Asuryan"
        self.set_temporary_weapon_keyword_bonuses(
            key=f"{key}:keywords",
            weapon_name=weapon_name,
            keywords=["ANTI-INFANTRY 5+", "DEVASTATING WOUNDS"],
            source=label,
            expires_phase="SHOOTING_PHASE",
            attack_type="ranged",
        )
        self.set_temporary_weapon_damage_override(
            key=f"{key}:damage",
            weapon_name=weapon_name,
            damage_value=3,
            source=label,
            expires_phase="SHOOTING_PHASE",
        )
        self.mark_used_once_per_battle(key, ability_name=label, source="datasheet")
        return True

    def activate_shieldbreaker(
        self,
        *,
        key: str = "shieldbreaker",
        ability_name: str = "Shieldbreaker",
        weapon_name: str = "exitus rifle",
        wound_bonus: int = 1,
    ) -> bool:
        """
        Once per battle, when selected to shoot:
        - selected weapon gains +wound
        - any successful wound roll with that weapon counts as a critical wound
        until end of Shooting phase.
        """
        key = str(key or "").strip().lower()
        if not key:
            return False
        if self.has_used_once_per_battle(key):
            return False
        weapon_name = str(weapon_name or "").strip()
        if not weapon_name:
            return False
        try:
            wound_bonus = int(wound_bonus or 0)
        except Exception:
            wound_bonus = 0
        if wound_bonus <= 0:
            return False
        label = str(ability_name or "").strip() or "Shieldbreaker"
        self.set_temporary_weapon_wound_crit_bonus(
            key=f"{key}:wound_crit",
            weapon_name=weapon_name,
            wound_bonus=int(wound_bonus),
            crit_wound_threshold=2,
            source=label,
            expires_phase="SHOOTING_PHASE",
        )
        self.mark_used_once_per_battle(key, ability_name=label, source="datasheet")
        return True

    def get_temporary_melee_attacks_bonus(self) -> int:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0
        total = 0
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            try:
                total += int(v.get("melee_attacks_bonus", 0) or 0)
            except Exception:
                continue
        return total

    def get_temporary_melee_ap_bonus(self) -> int:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0
        total = 0
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            try:
                total += int(v.get("melee_ap_bonus", 0) or 0)
            except Exception:
                continue
        return total

    def get_temporary_melee_strength_bonus(self) -> tuple[int, list[str]]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, []
        total = 0
        reasons: list[str] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            try:
                bonus = int(v.get("melee_strength_bonus", 0) or 0)
            except Exception:
                bonus = 0
            if bonus:
                total += int(bonus)
                source = str(v.get("melee_strength_bonus_source") or "").strip()
                label = source or "Temporary melee strength bonus"
                reasons.append(f"{label} +{int(bonus)}S (melee)")
        return int(total), reasons

    def get_temporary_melee_damage_bonus(self) -> tuple[int, list[str]]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, []
        total = 0
        reasons: list[str] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            try:
                bonus = int(v.get("melee_damage_bonus", 0) or 0)
            except Exception:
                bonus = 0
            if bonus:
                total += int(bonus)
                source = str(v.get("melee_damage_bonus_source") or "").strip()
                label = source or "Temporary melee damage bonus"
                reasons.append(f"{label} +{int(bonus)}D (melee)")
        return int(total), reasons

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

    def get_temporary_movement_bonus(self) -> int:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0
        total = 0
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            try:
                total += int(v.get("movement_bonus", 0) or 0)
            except Exception:
                continue
        return total

    @staticmethod
    def _normalize_weapon_name(value: str) -> str:
        t = str(value or "").lower()
        t = t.replace("\u2019", "'")
        t = re.sub(r"[^a-z0-9]+", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    def set_temporary_movement_bonus(
        self,
        *,
        key: str,
        movement_bonus: int = 0,
        source: str = "",
        expires_phase: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        effects = self._temporary_effects
        movement_bonus = int(movement_bonus or 0)
        if movement_bonus <= 0:
            effects.pop(key_norm, None)
            return
        effects[key_norm] = {
            "expires_phase": str(expires_phase or "").strip().upper(),
            "movement_bonus": int(movement_bonus),
            "movement_bonus_source": str(source or "").strip() or "Movement bonus",
        }

    def set_temporary_weapon_bonus(
        self,
        *,
        key: str,
        weapon_name: str,
        attacks_bonus: int = 0,
        strength_bonus: int = 0,
        ap_bonus: int = 0,
        damage_bonus: int = 0,
        source: str = "",
        expires_phase: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        effects = self._temporary_effects
        try:
            attacks_bonus = int(attacks_bonus or 0)
        except Exception:
            attacks_bonus = 0
        try:
            strength_bonus = int(strength_bonus or 0)
        except Exception:
            strength_bonus = 0
        try:
            ap_bonus = int(ap_bonus or 0)
        except Exception:
            ap_bonus = 0
        try:
            damage_bonus = int(damage_bonus or 0)
        except Exception:
            damage_bonus = 0
        if attacks_bonus <= 0 and strength_bonus <= 0 and ap_bonus <= 0 and damage_bonus <= 0:
            effects.pop(key_norm, None)
            return
        entry = {"expires_phase": str(expires_phase or "").strip().upper()}
        weapon_name = str(weapon_name or "").strip()
        label = str(source or "").strip() or "Weapon bonus"
        if weapon_name and attacks_bonus:
            entry["weapon_attacks_bonus"] = {weapon_name: int(attacks_bonus)}
            entry["weapon_attacks_bonus_source"] = label
        if weapon_name and strength_bonus:
            entry["weapon_strength_bonus"] = {weapon_name: int(strength_bonus)}
            entry["weapon_strength_bonus_source"] = label
        if weapon_name and ap_bonus:
            entry["weapon_ap_bonus"] = {weapon_name: int(ap_bonus)}
            entry["weapon_ap_bonus_source"] = label
        if weapon_name and damage_bonus:
            entry["weapon_damage_bonus"] = {weapon_name: int(damage_bonus)}
            entry["weapon_damage_bonus_source"] = label
        effects[key_norm] = entry

    def get_temporary_weapon_attacks_bonus(self, weapon_name: str) -> tuple[int, list[str]]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, []
        target = self._normalize_weapon_name(weapon_name)
        if not target:
            return 0, []
        total = 0
        reasons: list[str] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            bonus_map = v.get("weapon_attacks_bonus")
            if not isinstance(bonus_map, dict):
                continue
            source = str(v.get("weapon_attacks_bonus_source") or "").strip()
            for key, bonus in bonus_map.items():
                try:
                    bonus_val = int(bonus or 0)
                except Exception:
                    bonus_val = 0
                if bonus_val == 0:
                    continue
                key_norm = self._normalize_weapon_name(str(key or ""))
                if not key_norm:
                    continue
                if key_norm == target or key_norm in target or target in key_norm:
                    total += int(bonus_val)
                    label = source or str(key or weapon_name)
                    reasons.append(f"{label} +{bonus_val}A ({key_norm}) [temporary]")
        return int(total), reasons

    def get_temporary_weapon_strength_bonus(self, weapon_name: str) -> tuple[int, list[str]]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, []
        target = self._normalize_weapon_name(weapon_name)
        if not target:
            return 0, []
        total = 0
        reasons: list[str] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            bonus_map = v.get("weapon_strength_bonus")
            if not isinstance(bonus_map, dict):
                continue
            source = str(v.get("weapon_strength_bonus_source") or "").strip()
            for key, bonus in bonus_map.items():
                try:
                    bonus_val = int(bonus or 0)
                except Exception:
                    bonus_val = 0
                if bonus_val == 0:
                    continue
                key_norm = self._normalize_weapon_name(str(key or ""))
                if not key_norm:
                    continue
                if key_norm == target or key_norm in target or target in key_norm:
                    total += int(bonus_val)
                    label = source or str(key or weapon_name)
                    reasons.append(f"{label} +{bonus_val}S ({key_norm}) [temporary]")
        return int(total), reasons

    def get_temporary_weapon_ap_bonus(self, weapon_name: str) -> tuple[int, list[str]]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, []
        target = self._normalize_weapon_name(weapon_name)
        if not target:
            return 0, []
        total = 0
        reasons: list[str] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            bonus_map = v.get("weapon_ap_bonus")
            if not isinstance(bonus_map, dict):
                continue
            source = str(v.get("weapon_ap_bonus_source") or "").strip()
            for key, bonus in bonus_map.items():
                try:
                    bonus_val = int(bonus or 0)
                except Exception:
                    bonus_val = 0
                if bonus_val == 0:
                    continue
                key_norm = self._normalize_weapon_name(str(key or ""))
                if not key_norm:
                    continue
                if key_norm == target or key_norm in target or target in key_norm:
                    total += int(bonus_val)
                    label = source or str(key or weapon_name)
                    reasons.append(f"{label} +{bonus_val}AP ({key_norm}) [temporary]")
        return int(total), reasons

    def get_temporary_weapon_damage_bonus(self, weapon_name: str) -> tuple[int, list[str]]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, []
        target = self._normalize_weapon_name(weapon_name)
        if not target:
            return 0, []
        total = 0
        reasons: list[str] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            bonus_map = v.get("weapon_damage_bonus")
            if not isinstance(bonus_map, dict):
                continue
            source = str(v.get("weapon_damage_bonus_source") or "").strip()
            for key, bonus in bonus_map.items():
                try:
                    bonus_val = int(bonus or 0)
                except Exception:
                    bonus_val = 0
                if bonus_val == 0:
                    continue
                key_norm = self._normalize_weapon_name(str(key or ""))
                if not key_norm:
                    continue
                if key_norm == target or key_norm in target or target in key_norm:
                    total += int(bonus_val)
                    label = source or str(key or weapon_name)
                    reasons.append(f"{label} +{bonus_val}D ({key_norm}) [temporary]")
        return int(total), reasons

    @staticmethod
    def _temporary_target_matches_keywords(target, keywords: list[str]) -> bool:
        if target is None:
            return False
        normalized_keywords = [str(keyword or "").strip().lower() for keyword in list(keywords or []) if str(keyword or "").strip()]
        if not normalized_keywords:
            return True
        candidates = [target]
        parent_unit = getattr(target, "parent_unit", None)
        if parent_unit is not None:
            candidates.append(parent_unit)
        for candidate in candidates:
            has_any_keyword = getattr(candidate, "has_any_keyword", None)
            has_keyword = getattr(candidate, "has_keyword", None)
            keywords_iter = list(getattr(candidate, "keywords", []) or [])
            keywords_iter.extend(list(getattr(candidate, "faction_keywords", []) or []))
            keywords_seen = {str(keyword or "").strip().lower() for keyword in keywords_iter if str(keyword or "").strip()}
            for keyword in normalized_keywords:
                if callable(has_any_keyword) and bool(has_any_keyword(keyword)):
                    return True
                if callable(has_keyword) and bool(has_keyword(keyword)):
                    return True
                if keyword in keywords_seen:
                    return True
        return False

    def set_temporary_weapon_wound_crit_bonus(
        self,
        *,
        key: str,
        weapon_name: str,
        wound_bonus: int = 0,
        crit_wound_threshold: int = 0,
        target_keywords_any: Optional[list[str]] = None,
        source: str = "",
        expires_phase: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        effects = self._temporary_effects
        try:
            wound_bonus = int(wound_bonus or 0)
        except Exception:
            wound_bonus = 0
        try:
            crit_wound_threshold = int(crit_wound_threshold or 0)
        except Exception:
            crit_wound_threshold = 0
        weapon_name = str(weapon_name or "").strip()
        if not weapon_name or (wound_bonus <= 0 and crit_wound_threshold <= 0):
            effects.pop(key_norm, None)
            return
        entry = {"expires_phase": str(expires_phase or "").strip().upper()}
        label = str(source or "").strip() or "Weapon wound bonus"
        target_keywords = [
            str(keyword or "").strip().lower()
            for keyword in list(target_keywords_any or [])
            if str(keyword or "").strip()
        ]
        if target_keywords:
            entry["target_keywords_any"] = list(target_keywords)
        if wound_bonus > 0:
            entry["weapon_wound_bonus"] = {weapon_name: int(wound_bonus)}
            entry["weapon_wound_bonus_source"] = label
        if crit_wound_threshold > 0:
            entry["weapon_crit_wound_threshold"] = {weapon_name: int(crit_wound_threshold)}
            entry["weapon_crit_wound_threshold_source"] = label
        effects[key_norm] = entry

    def get_temporary_weapon_wound_bonus(self, weapon_name: str, target=None) -> tuple[int, list[str]]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, []
        weapon_key = self._normalize_weapon_name(weapon_name)
        if not weapon_key:
            return 0, []
        total = 0
        reasons: list[str] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            target_keywords_any = list(v.get("target_keywords_any") or [])
            if target_keywords_any and not self._temporary_target_matches_keywords(target=target, keywords=target_keywords_any):
                continue
            bonus_map = v.get("weapon_wound_bonus")
            if not isinstance(bonus_map, dict):
                continue
            source = str(v.get("weapon_wound_bonus_source") or "").strip()
            for key, bonus in bonus_map.items():
                try:
                    bonus_val = int(bonus or 0)
                except Exception:
                    bonus_val = 0
                if bonus_val == 0:
                    continue
                key_norm = self._normalize_weapon_name(str(key or ""))
                if not key_norm:
                    continue
                if key_norm == weapon_key or key_norm in weapon_key or weapon_key in key_norm:
                    total += int(bonus_val)
                    label = source or str(key or weapon_name)
                    reasons.append(f"{label}: +{int(bonus_val)} to wound")
        return int(total), reasons

    def get_temporary_weapon_crit_wound_threshold(self, weapon_name: str, target=None) -> tuple[int, list[str]]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, []
        weapon_key = self._normalize_weapon_name(weapon_name)
        if not weapon_key:
            return 0, []
        best_threshold = 0
        reasons: list[str] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            target_keywords_any = list(v.get("target_keywords_any") or [])
            if target_keywords_any and not self._temporary_target_matches_keywords(target=target, keywords=target_keywords_any):
                continue
            threshold_map = v.get("weapon_crit_wound_threshold")
            if not isinstance(threshold_map, dict):
                continue
            source = str(v.get("weapon_crit_wound_threshold_source") or "").strip()
            for key, threshold in threshold_map.items():
                try:
                    threshold_val = int(threshold or 0)
                except Exception:
                    threshold_val = 0
                if threshold_val <= 0:
                    continue
                key_norm = self._normalize_weapon_name(str(key or ""))
                if not key_norm:
                    continue
                if key_norm != weapon_key and key_norm not in weapon_key and weapon_key not in key_norm:
                    continue
                if best_threshold <= 0 or threshold_val < best_threshold:
                    best_threshold = int(threshold_val)
                    reasons = []
                label = source or str(key or weapon_name)
                reasons.append(f"{label}: critical wound on {int(threshold_val)}+")
        return int(best_threshold), reasons

    def set_temporary_weapon_damage_override(
        self,
        *,
        key: str,
        weapon_name: str,
        damage_value: int,
        source: str = "",
        expires_phase: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        effects = self._temporary_effects
        try:
            damage_value = int(damage_value or 0)
        except Exception:
            damage_value = 0
        if damage_value <= 0:
            effects.pop(key_norm, None)
            return
        weapon_name = str(weapon_name or "").strip()
        if not weapon_name:
            effects.pop(key_norm, None)
            return
        entry = {"expires_phase": str(expires_phase or "").strip().upper()}
        label = str(source or "").strip() or "Weapon damage override"
        entry["weapon_damage_override"] = {weapon_name: int(damage_value)}
        entry["weapon_damage_override_source"] = label
        effects[key_norm] = entry

    def get_temporary_weapon_damage_override(self, weapon_name: str) -> tuple[int, str]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, ""
        target = self._normalize_weapon_name(weapon_name)
        if not target:
            return 0, ""
        best_val = 0
        best_source = ""
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            bonus_map = v.get("weapon_damage_override")
            if not isinstance(bonus_map, dict):
                continue
            source = str(v.get("weapon_damage_override_source") or "").strip()
            for key, dmg in bonus_map.items():
                key_norm = self._normalize_weapon_name(str(key or ""))
                if not key_norm:
                    continue
                if key_norm != target and key_norm not in target and target not in key_norm:
                    continue
                try:
                    dmg_val = int(dmg or 0)
                except Exception:
                    dmg_val = 0
                if dmg_val > best_val:
                    best_val = int(dmg_val)
                    best_source = source or str(key or weapon_name)
        return int(best_val), best_source

    def set_temporary_weapon_attacks_override(
        self,
        *,
        key: str,
        weapon_name: str,
        attacks_value: int,
        source: str = "",
        expires_phase: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        effects = self._temporary_effects
        try:
            attacks_value = int(attacks_value or 0)
        except Exception:
            attacks_value = 0
        if attacks_value <= 0:
            effects.pop(key_norm, None)
            return
        weapon_name = str(weapon_name or "").strip()
        if not weapon_name:
            effects.pop(key_norm, None)
            return
        entry = {"expires_phase": str(expires_phase or "").strip().upper()}
        label = str(source or "").strip() or "Weapon attacks override"
        entry["weapon_attacks_override"] = {weapon_name: int(attacks_value)}
        entry["weapon_attacks_override_source"] = label
        effects[key_norm] = entry

    def get_temporary_weapon_attacks_override(self, weapon_name: str) -> tuple[int, str]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, ""
        target = self._normalize_weapon_name(weapon_name)
        if not target:
            return 0, ""
        best_val = 0
        best_source = ""
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            bonus_map = v.get("weapon_attacks_override")
            if not isinstance(bonus_map, dict):
                continue
            source = str(v.get("weapon_attacks_override_source") or "").strip()
            for key, att in bonus_map.items():
                key_norm = self._normalize_weapon_name(str(key or ""))
                if not key_norm:
                    continue
                if key_norm != target and key_norm not in target and target not in key_norm:
                    continue
                try:
                    att_val = int(att or 0)
                except Exception:
                    att_val = 0
                if att_val > best_val:
                    best_val = int(att_val)
                    best_source = source or str(key or weapon_name)
        return int(best_val), best_source

    def set_temporary_invulnerable_save(
        self,
        *,
        key: str,
        value: int,
        source: str = "",
        expires_phase: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        effects = self._temporary_effects
        try:
            value = int(value or 0)
        except Exception:
            value = 0
        if value <= 0:
            effects.pop(key_norm, None)
            return
        entry = {"expires_phase": str(expires_phase or "").strip().upper()}
        entry["invulnerable_save_override"] = int(value)
        entry["invulnerable_save_override_source"] = str(source or "").strip() or "Invulnerable save"
        effects[key_norm] = entry

    def get_temporary_invulnerable_save(self) -> tuple[int, str]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, ""
        best_val = 0
        best_source = ""
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            try:
                val = int(v.get("invulnerable_save_override", 0) or 0)
            except Exception:
                val = 0
            if val <= 0:
                continue
            if not best_val or val < best_val:
                best_val = int(val)
                best_source = str(v.get("invulnerable_save_override_source") or "").strip()
        return int(best_val), best_source

    def set_temporary_damage_taken_override(
        self,
        *,
        key: str,
        value: int,
        source: str = "",
        expires_phase: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        effects = self._temporary_effects
        try:
            value = int(value or 0)
        except Exception:
            value = 0
        if value <= 0:
            effects.pop(key_norm, None)
            return
        entry = {"expires_phase": str(expires_phase or "").strip().upper()}
        entry["damage_taken_override"] = int(value)
        entry["damage_taken_override_source"] = str(source or "").strip() or "Damage override"
        effects[key_norm] = entry

    def get_temporary_damage_taken_override(self) -> tuple[int, str]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, ""
        best_val = 0
        best_source = ""
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            if "damage_taken_override" not in v:
                continue
            try:
                val = int(v.get("damage_taken_override", 0) or 0)
            except Exception:
                val = 0
            if val <= 0:
                continue
            source = str(v.get("damage_taken_override_source") or "").strip()
            if best_val == 0 or val < best_val:
                best_val = int(val)
                best_source = source
        return int(best_val), best_source

    def set_temporary_fnp(
        self,
        *,
        key: str,
        value: int,
        source: str = "",
        condition: str | None = None,
        expires_phase: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        effects = self._temporary_effects
        try:
            value = int(value or 0)
        except Exception:
            value = 0
        if value <= 0:
            effects.pop(key_norm, None)
            return
        entry = {"expires_phase": str(expires_phase or "").strip().upper()}
        entry["temporary_fnp_value"] = int(value)
        entry["temporary_fnp_source"] = str(source or "").strip() or "Temporary FNP"
        if condition:
            entry["temporary_fnp_condition"] = str(condition or "").strip()
        effects[key_norm] = entry

    def get_temporary_fnp_entries(self) -> list[tuple[int, str | None]]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return []
        entries: list[tuple[int, str | None]] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            if "temporary_fnp_value" not in v:
                continue
            try:
                val = int(v.get("temporary_fnp_value", 0) or 0)
            except Exception:
                val = 0
            if val <= 0:
                continue
            cond = v.get("temporary_fnp_condition")
            cond = str(cond).strip() if cond else None
            entries.append((int(val), cond))
        return entries

    def set_temporary_weapon_keyword_bonuses(
        self,
        *,
        key: str,
        weapon_name: str,
        keywords: list[str],
        source: str = "",
        expires_phase: str = "",
        attack_type: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        effects = self._temporary_effects
        weapon_name = str(weapon_name or "").strip()
        clean_keywords = [str(k or "").strip() for k in list(keywords or []) if str(k or "").strip()]
        if not weapon_name or not clean_keywords:
            effects.pop(key_norm, None)
            return
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged", "any"):
            atype = "any"
        entry = {
            "expires_phase": str(expires_phase or "").strip().upper(),
            "weapon_keyword_bonuses": {weapon_name: list(clean_keywords)},
            "weapon_keyword_bonuses_source": str(source or "").strip() or "Weapon keyword bonus",
            "weapon_keyword_bonuses_attack_type": atype,
        }
        effects[key_norm] = entry

    def get_temporary_weapon_keyword_bonuses(self, weapon_name: str) -> list[dict]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return []
        target = self._normalize_weapon_name(weapon_name)
        if not target:
            return []
        rules: list[dict] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            bonus_map = v.get("weapon_keyword_bonuses")
            if not isinstance(bonus_map, dict):
                continue
            source = str(v.get("weapon_keyword_bonuses_source") or "").strip()
            atype = str(v.get("weapon_keyword_bonuses_attack_type") or "any").strip().lower()
            if atype not in ("melee", "ranged", "any"):
                atype = "any"
            for key, kw_list in bonus_map.items():
                key_norm = self._normalize_weapon_name(str(key or ""))
                if not key_norm:
                    continue
                if key_norm != target and key_norm not in target and target not in key_norm:
                    continue
                for kw in list(kw_list or []):
                    kw_text = str(kw or "").strip()
                    if not kw_text:
                        continue
                    rules.append({"attack_type": atype, "keyword": kw_text, "source": source or kw_text})
        return rules

    def set_temporary_psychic_attack_bonus(
        self,
        *,
        key: str,
        hit_bonus: int = 0,
        wound_bonus: int = 0,
        source: str = "",
        expires_phase: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        effects = self._temporary_effects
        try:
            hit_bonus = int(hit_bonus or 0)
        except Exception:
            hit_bonus = 0
        try:
            wound_bonus = int(wound_bonus or 0)
        except Exception:
            wound_bonus = 0
        if hit_bonus == 0 and wound_bonus == 0:
            effects.pop(key_norm, None)
            return
        entry = {"expires_phase": str(expires_phase or "").strip().upper()}
        if hit_bonus:
            entry["psychic_attack_hit_bonus"] = int(hit_bonus)
        if wound_bonus:
            entry["psychic_attack_wound_bonus"] = int(wound_bonus)
        entry["psychic_attack_bonus_source"] = str(source or "").strip() or "Psychic attack bonus"
        effects[key_norm] = entry

    def get_temporary_psychic_attack_bonus(self, *, game: Optional[object] = None) -> tuple[int, int, list[str], list[str]]:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return 0, 0, [], []
        if game is None:
            game = self._resolve_game()
        pname = ""
        if game is not None:
            try:
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                pname = ""
        total_hit = 0
        total_wound = 0
        hit_reasons: list[str] = []
        wound_reasons: list[str] = []
        for v in eff.values():
            if not isinstance(v, dict):
                continue
            exp = str(v.get("expires_phase", "") or "").strip().upper()
            if exp and pname and exp != pname:
                continue
            try:
                h_bonus = int(v.get("psychic_attack_hit_bonus", 0) or 0)
            except Exception:
                h_bonus = 0
            try:
                w_bonus = int(v.get("psychic_attack_wound_bonus", 0) or 0)
            except Exception:
                w_bonus = 0
            if h_bonus == 0 and w_bonus == 0:
                continue
            source = str(v.get("psychic_attack_bonus_source", "") or "Psychic attack bonus").strip()
            if h_bonus:
                total_hit += int(h_bonus)
                hit_reasons.append(f"{source}: +{int(h_bonus)} to hit (Psychic)")
            if w_bonus:
                total_wound += int(w_bonus)
                wound_reasons.append(f"{source}: +{int(w_bonus)} to wound (Psychic)")
        return int(total_hit), int(total_wound), hit_reasons, wound_reasons

    def set_temporary_crit_on_successful_hit(
        self,
        *,
        key: str,
        source: str = "",
        expires_turn: Optional[int] = None,
        expires_turn_owner: str = "",
    ) -> None:
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        entry = {
            "crit_on_successful_hit": True,
            "crit_on_successful_hit_source": str(source or "").strip() or "Critical hit on successful hit",
        }
        if expires_turn is not None:
            try:
                entry["crit_on_successful_hit_expires_turn"] = int(expires_turn)
            except Exception:
                entry["crit_on_successful_hit_expires_turn"] = int(expires_turn or 0)
        if expires_turn_owner:
            entry["crit_on_successful_hit_expires_turn_owner"] = str(expires_turn_owner)
        self._temporary_effects[key_norm] = entry

    def has_temporary_crit_on_successful_hit(self, *, game=None) -> bool:
        eff = getattr(self, "_temporary_effects", {}) or {}
        if not isinstance(eff, dict) or not eff:
            return False
        if game is None:
            game = self._resolve_game()
        current_turn = None
        current_owner = ""
        if game is not None:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                current_turn = None
            try:
                current_owner = str(getattr(game.get_current_player(), "id", "") or "")
            except Exception:
                current_owner = ""
        for key, v in list(eff.items()):
            if not isinstance(v, dict):
                continue
            if not bool(v.get("crit_on_successful_hit")):
                continue
            exp_turn = v.get("crit_on_successful_hit_expires_turn")
            exp_owner = str(v.get("crit_on_successful_hit_expires_turn_owner", "") or "")
            if exp_turn is not None and current_turn is not None:
                try:
                    if int(exp_turn) != int(current_turn):
                        continue
                except Exception:
                    continue
            if exp_owner and current_owner and exp_owner != current_owner:
                continue
            return True
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

    # ---------------- Selected-to-shoot reroll helpers ----------------

    def grant_selected_to_shoot_rerolls(self, *, hit: bool, wound: bool, damage: bool, source: str = "") -> None:
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        data = self._temporary_effects.get("selected_to_shoot_rerolls", {})
        if not isinstance(data, dict):
            data = {}
        if hit:
            data["hit_remaining"] = max(int(data.get("hit_remaining", 0) or 0), 1)
        if wound:
            data["wound_remaining"] = max(int(data.get("wound_remaining", 0) or 0), 1)
        if damage:
            data["damage_remaining"] = max(int(data.get("damage_remaining", 0) or 0), 1)
        if source:
            data["source"] = str(source or "")
        self._temporary_effects["selected_to_shoot_rerolls"] = data

    def clear_selected_to_shoot_rerolls(self) -> None:
        try:
            eff = getattr(self, "_temporary_effects", None)
            if isinstance(eff, dict):
                eff.pop("selected_to_shoot_rerolls", None)
        except Exception:
            pass

    def can_use_selected_to_shoot_reroll(self, kind: str) -> bool:
        eff = getattr(self, "_temporary_effects", {}) or {}
        data = eff.get("selected_to_shoot_rerolls", {})
        if not isinstance(data, dict):
            return False
        key = str(kind or "").strip().lower()
        if key == "hit":
            field = "hit_remaining"
        elif key == "wound":
            field = "wound_remaining"
        else:
            field = "damage_remaining"
        try:
            return int(data.get(field, 0) or 0) > 0
        except Exception:
            return False

    def consume_selected_to_shoot_reroll(self, kind: str) -> bool:
        eff = getattr(self, "_temporary_effects", {}) or {}
        data = eff.get("selected_to_shoot_rerolls", {})
        if not isinstance(data, dict):
            return False
        key = str(kind or "").strip().lower()
        if key == "hit":
            field = "hit_remaining"
        elif key == "wound":
            field = "wound_remaining"
        else:
            field = "damage_remaining"
        try:
            remaining = int(data.get(field, 0) or 0)
        except Exception:
            remaining = 0
        if remaining <= 0:
            return False
        data[field] = remaining - 1
        eff["selected_to_shoot_rerolls"] = data
        return True

    def get_selected_to_shoot_reroll_source(self) -> str:
        eff = getattr(self, "_temporary_effects", {}) or {}
        data = eff.get("selected_to_shoot_rerolls", {})
        if not isinstance(data, dict):
            return ""
        return str(data.get("source", "") or "")

    # ---------------- Selected-to-shoot/fight reroll choice helpers ----------------

    def grant_selected_to_action_reroll_choice(
        self,
        *,
        action: str,
        allow_hit: bool,
        allow_wound: bool,
        source: str = "",
        mode: str = "choice",
    ) -> None:
        if not isinstance(getattr(self, "_temporary_effects", None), dict):
            self._temporary_effects = {}
        data = self._temporary_effects.get("selected_to_action_reroll_choice", {})
        if not isinstance(data, dict):
            data = {}
        action_key = str(action or "").strip().lower()
        if not action_key:
            return
        entry = data.get(action_key, {})
        if not isinstance(entry, dict):
            entry = {}
        mode_key = str(mode or "choice").strip().lower()
        if mode_key not in ("choice", "one_each"):
            mode_key = "choice"
        entry["mode"] = mode_key
        if mode_key == "one_each":
            if allow_hit:
                entry["allow_hit"] = True
                entry["hit_remaining"] = max(int(entry.get("hit_remaining", 0) or 0), 1)
            if allow_wound:
                entry["allow_wound"] = True
                entry["wound_remaining"] = max(int(entry.get("wound_remaining", 0) or 0), 1)
        else:
            entry["remaining"] = max(int(entry.get("remaining", 0) or 0), 1)
            if allow_hit:
                entry["allow_hit"] = True
            if allow_wound:
                entry["allow_wound"] = True
        if source:
            entry["source"] = str(source or "")
        data[action_key] = entry
        self._temporary_effects["selected_to_action_reroll_choice"] = data

    def clear_selected_to_action_reroll_choice(self, action: str | None = None) -> None:
        eff = getattr(self, "_temporary_effects", None)
        if not isinstance(eff, dict):
            return
        if action is None:
            eff.pop("selected_to_action_reroll_choice", None)
            return
        data = eff.get("selected_to_action_reroll_choice", {})
        if not isinstance(data, dict):
            return
        action_key = str(action or "").strip().lower()
        if not action_key:
            return
        data.pop(action_key, None)
        if not data:
            eff.pop("selected_to_action_reroll_choice", None)
        else:
            eff["selected_to_action_reroll_choice"] = data

    def can_use_selected_to_action_reroll(self, kind: str, action: str) -> bool:
        eff = getattr(self, "_temporary_effects", {}) or {}
        data = eff.get("selected_to_action_reroll_choice", {})
        if not isinstance(data, dict):
            return False
        action_key = str(action or "").strip().lower()
        entry = data.get(action_key, {})
        if not isinstance(entry, dict):
            return False
        kind_key = str(kind or "").strip().lower()
        mode_key = str(entry.get("mode", "choice") or "choice").strip().lower()
        if mode_key == "one_each":
            if kind_key == "hit":
                try:
                    remaining = int(entry.get("hit_remaining", 0) or 0)
                except Exception:
                    remaining = 0
                return bool(entry.get("allow_hit")) and remaining > 0
            if kind_key == "wound":
                try:
                    remaining = int(entry.get("wound_remaining", 0) or 0)
                except Exception:
                    remaining = 0
                return bool(entry.get("allow_wound")) and remaining > 0
            return False
        try:
            remaining = int(entry.get("remaining", 0) or 0)
        except Exception:
            remaining = 0
        if remaining <= 0:
            return False
        if kind_key == "hit":
            return bool(entry.get("allow_hit"))
        if kind_key == "wound":
            return bool(entry.get("allow_wound"))
        return False

    def consume_selected_to_action_reroll(self, kind: str, action: str) -> bool:
        eff = getattr(self, "_temporary_effects", {}) or {}
        data = eff.get("selected_to_action_reroll_choice", {})
        if not isinstance(data, dict):
            return False
        action_key = str(action or "").strip().lower()
        entry = data.get(action_key, {})
        if not isinstance(entry, dict):
            return False
        kind_key = str(kind or "").strip().lower()
        mode_key = str(entry.get("mode", "choice") or "choice").strip().lower()
        if mode_key == "one_each":
            if kind_key == "hit":
                if not bool(entry.get("allow_hit")):
                    return False
                try:
                    remaining = int(entry.get("hit_remaining", 0) or 0)
                except Exception:
                    remaining = 0
                if remaining <= 0:
                    return False
                entry["hit_remaining"] = remaining - 1
            elif kind_key == "wound":
                if not bool(entry.get("allow_wound")):
                    return False
                try:
                    remaining = int(entry.get("wound_remaining", 0) or 0)
                except Exception:
                    remaining = 0
                if remaining <= 0:
                    return False
                entry["wound_remaining"] = remaining - 1
            else:
                return False
        else:
            try:
                remaining = int(entry.get("remaining", 0) or 0)
            except Exception:
                remaining = 0
            if remaining <= 0:
                return False
            if kind_key == "hit" and not bool(entry.get("allow_hit")):
                return False
            if kind_key == "wound" and not bool(entry.get("allow_wound")):
                return False
            entry["remaining"] = remaining - 1
        data[action_key] = entry
        eff["selected_to_action_reroll_choice"] = data
        return True

    def get_selected_to_action_reroll_source(self, action: str) -> str:
        eff = getattr(self, "_temporary_effects", {}) or {}
        data = eff.get("selected_to_action_reroll_choice", {})
        if not isinstance(data, dict):
            return ""
        action_key = str(action or "").strip().lower()
        entry = data.get(action_key, {})
        if not isinstance(entry, dict):
            return ""
        return str(entry.get("source", "") or "")

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
        old_loc = (self.model_base.x, self.model_base.y, self.model_base.z, self.model_base.facing)
        self.model_base.x = x
        self.model_base.y = y
        self.model_base.z = z
        self.model_base.set_facing(facing)
        if old_loc != (x, y, z, facing):
            self._bump_parent_map_state_generation("model_moved")

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
        damage_source: Optional[str] = None,
    ) -> int:
        try:
            if damage_source is None:
                damage_source = "attack" if weapon_profile is not None else "non_attack"
            self._last_damage_weapon_profile = weapon_profile
            self._last_damage_source_kind = str(damage_source or "")
        except Exception:
            pass
        if not wounds_cannot_be_ignored and weapon_profile is not None:
            wcni_fn = getattr(weapon_profile, "wounds_cannot_be_ignored", None)
            if callable(wcni_fn):
                wounds_cannot_be_ignored = bool(wcni_fn())

        if is_mortal:
            maybe_watcher = getattr(self.parent_unit, "_maybe_activate_watcher_in_the_dark", None)
            if callable(maybe_watcher):
                atk_ctx = attack_context if isinstance(attack_context, dict) else {}
                maybe_watcher(
                    target_model=self,
                    attacker_model=atk_ctx.get("attacker_model"),
                    attacker_unit=atk_ctx.get("attacker_unit"),
                    weapon_profile=weapon_profile,
                    game_map=game_map,
                )
        if is_psychic_attack:
            maybe_null_nodules = getattr(self.parent_unit, "_maybe_activate_null_nodules", None)
            if callable(maybe_null_nodules):
                atk_ctx = attack_context if isinstance(attack_context, dict) else {}
                maybe_null_nodules(
                    target_model=self,
                    attacker_model=atk_ctx.get("attacker_model"),
                    attacker_unit=atk_ctx.get("attacker_unit"),
                    weapon_profile=weapon_profile,
                    game_map=game_map,
                )

        try:
            fnp_abilities = self.parent_unit.has_feel_no_pain(target_model=self)
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
                        logger.info(f"{self.name} Feel No Pain{condition_text} save: rolled {fnp_roll}, needed {fnp_value}+ - SAVED")
                    else:
                        logger.error(f"{self.name} Feel No Pain{condition_text} save: rolled {fnp_roll}, needed {fnp_value}+ - FAILED")
                
                # Reduce damage by the number of successful FNP saves
                amount -= fnp_saves
                if fnp_saves > 0:
                    logger.info(f"{self.name} prevented {fnp_saves} damage with Feel No Pain{condition_text}")
            else:
                logger.info(f"{self.name} has Feel No Pain abilities but none apply to this damage source")

        redirected_amount = 0
        try:
            redirect_fn = getattr(self.parent_unit, "_apply_legion_of_excess_thieves_of_pain_redirect", None)
            if callable(redirect_fn) and int(amount or 0) > 0:
                redirected_amount = int(
                    redirect_fn(
                        int(amount or 0),
                        game_map=game_map,
                        source_model=self,
                        damage_source=str(damage_source or ""),
                    )
                    or 0
                )
        except Exception:
            redirected_amount = 0
        if redirected_amount > 0:
            amount = max(0, int(amount or 0) - int(redirected_amount or 0))
        
        self.wounds -= amount
        logger.info(f"{self.name} takes {amount} damage. It is {'Alive' if self.is_alive else 'Dead'}")
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
                try:
                    ignore_lone_operative = False
                    parent_unit = getattr(self, "parent_unit", None)
                    ignore_lone_operative_fn = (
                        getattr(parent_unit, "_model_can_ignore_lone_operative_when_selecting_targets", None)
                        if parent_unit is not None
                        else None
                    )
                    if callable(ignore_lone_operative_fn):
                        ignore_lone_operative = bool(ignore_lone_operative_fn(self))
                    limit, _sources = enemy_unit.get_ranged_targeting_restriction(
                        game_map=game_map,
                        ignore_lone_operative=ignore_lone_operative,
                    )
                    if limit is not None and closest_dist > float(limit):
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
        old_wounds = getattr(self, "_wounds", None)
        self._wounds = value
        if old_wounds != value:
            self._bump_parent_map_state_generation("model_wounds_changed")

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
            try:
                if hasattr(wargear_profile, "_effective_range_max"):
                    return int(wargear_profile._effective_range_max(self))
            except Exception:
                pass
            return wargear_profile.range.max
        elif wargear_item:
            if wargear_item.is_ranged():
                for profile in wargear_item.profiles.values():
                    try:
                        if hasattr(profile, "_effective_range_max"):
                            max_range = max(max_range, int(profile._effective_range_max(self)))
                        else:
                            max_range = max(max_range, profile.range.max)
                    except Exception:
                        continue
        else:
            for wargear in self.wargear:
                if wargear.is_ranged():
                    for profile in wargear.profiles.values():
                        try:
                            if hasattr(profile, "_effective_range_max"):
                                max_range = max(max_range, int(profile._effective_range_max(self)))
                            else:
                                max_range = max(max_range, profile.range.max)
                        except Exception:
                            continue
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
        condition_lower = condition_lower.lstrip("*•- ").rstrip(".").strip()
        if condition_lower == "model only" or condition_lower.endswith(" model only"):
            return True
        
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
        logger.warning(f"WARN: Unknown invulnerable save condition format: '{condition}' - applying save")
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

    def _bump_parent_map_state_generation(self, reason: str) -> None:
        unit = getattr(self, "parent_unit", None)
        if unit is None:
            return
        get_army = getattr(unit, "get_parent_army", None)
        army = get_army() if callable(get_army) else getattr(unit, "parent_army", None)
        player = getattr(army, "player", None)
        game = getattr(player, "game", None)
        game_map = getattr(game, "map", None)
        bump = getattr(game_map, "bump_state_generation", None)
        if callable(bump):
            bump(reason)
