"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class LateGameplayMixin:
    def _parse_command_phase_end_leadership_cp_gain_specs_from_text(self, ability_name: str, ability_desc: str) -> List[dict]:
        """Parse end-of-Command-phase Leadership test CP gain abilities."""
        normalized = self._normalize_rules_text(ability_desc)
        if not normalized:
            return []
        norm = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
        norm = norm.lower()
        norm = re.sub(r"'s\b", "s", norm)
        norm = re.sub(r"[^a-z0-9]+", " ", norm)
        norm = re.sub(r"\s+", " ", norm).strip()
        m = self._COMMAND_PHASE_END_LEADERSHIP_CP_GAIN_RE.fullmatch(norm)
        if not m:
            return []
        token = str(m.group("cp") or "").strip().lower()
        try:
            cp = int(token)
        except Exception:
            cp = 1 if token == "one" else 1
        return [
            {
                "type": "command_phase_end_leadership_cp_gain",
                "cp": int(cp),
                "source_ability": ability_name or "",
            }
        ]

    def get_phase_end_leadership_cp_gain_specs(self) -> List[dict]:
        """Return end-of-phase Leadership test CP gain specs for this unit group."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "phase_end_leadership_cp_gain_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        specs: List[dict] = []
        seen = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                parsed = unit._parse_phase_end_leadership_cp_gain_specs_from_text(name, text_src)
                for spec in parsed:
                    key = (spec.get("source_ability", "").lower(), int(spec.get("cp", 1) or 1))
                    if key in seen:
                        continue
                    seen.add(key)
                    specs.append(spec)

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_command_phase_end_leadership_cp_gain_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """Return model-specific end-of-Command-phase Leadership test CP gain specs."""
        if model is None:
            return []
        cache_key = f"model_command_phase_end_leadership_cp_gain:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: List[dict] = []
        seen = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            parsed = self._parse_command_phase_end_leadership_cp_gain_specs_from_text(name, text_src)
            for spec in parsed:
                key = (spec.get("source_ability", "").lower(), int(spec.get("cp", 1) or 1))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(spec)

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def _parse_cp_on_kill_specs_from_text(self, ability_name: str, ability_desc: str) -> List[dict]:
        """Parse partial support for 'gain CP when destroying enemy keyword unit/model' abilities.

        This intentionally focuses on broad, extendible text patterns rather than specific names.
        """
        normalized = self._normalize_rules_text(ability_desc)
        txt = normalized.lower()

        # Must look like a 'destroy' trigger and reference CP gain.
        if "gain" not in txt or "cp" not in txt:
            return []
        if "destroys" not in txt:
            return []

        # Extract CP amount (default 1 if implied)
        cp = 1
        try:
            m = re.search(r"gain\s+(\d+)\s*cp", txt, flags=re.IGNORECASE)
            if m:
                cp = int(m.group(1))
        except Exception:
            cp = 1

        # Keyword extraction (extendible)
        keyword_map = {
            "character": "CHARACTER",
            "epic hero": "EPIC HERO",
            "monster": "MONSTER",
            "vehicle": "VEHICLE",
            "psyker": "PSYKER",
        }

        if "enemy" not in txt:
            has_keyword = any(needle in txt for needle in keyword_map)
            if not has_keyword:
                return []

        # Detect what is being destroyed: unit vs model (defaults to model_destroyed)
        trigger = "model_destroyed"
        try:
            # If text explicitly says "... destroys an enemy <X> unit", use unit_destroyed
            if re.search(r"destroys\s+an?\s+(?:enemy\s+)?\b.*\bunit\b", txt):
                trigger = "unit_destroyed"
            # If it explicitly says model, prefer model_destroyed
            if re.search(r"destroys\s+an?\s+(?:enemy\s+)?\b.*\bmodel\b", txt):
                trigger = "model_destroyed"
        except Exception:
            trigger = "model_destroyed"

        # Restriction extraction (extendible)
        requires_melee = False
        try:
            # e.g. "with a melee attack"
            if "melee attack" in txt or "with a melee" in txt:
                requires_melee = True
        except Exception:
            requires_melee = False
        requires_fight_phase = "fight phase" in txt

        target_keywords = []
        for needle, kw in keyword_map.items():
            if needle in txt:
                target_keywords.append(kw)

        # Determine keyword match mode. If multiple keywords are mentioned and "or" appears,
        # treat as ANY. Otherwise default to ALL.
        target_keyword_mode = "all"
        try:
            if len(target_keywords) > 1 and " or " in txt:
                target_keyword_mode = "any"
        except Exception:
            target_keyword_mode = "all"

        return [{
            "type": "gain_cp_on_destroy",
            "trigger": trigger,
            "cp": cp,
            # empty set means "any target" (e.g. The Great Wolf)
            "target_keywords": set(target_keywords),
            "target_keyword_mode": target_keyword_mode,
            "requires_melee": requires_melee,
            "requires_fight_phase": bool(requires_fight_phase),
            "source_ability": ability_name or "",
        }]

    def _parse_heal_on_kill_specs_from_text(self, ability_name: str, ability_desc: str) -> List[dict]:
        """Parse partial support for 'regain wounds when destroying enemy keyword unit/model' abilities."""
        normalized = self._normalize_rules_text(ability_desc)
        txt = normalized.lower()

        if "destroys" not in txt or "enemy" not in txt:
            return []
        if "regains" not in txt or "lost wounds" not in txt:
            return []

        # Determine trigger (unit vs model). Default to unit_destroyed if "unit" appears near destroy.
        trigger = "model_destroyed"
        try:
            if re.search(r"destroys\s+an?\s+enemy\b.*\bunit\b", txt):
                trigger = "unit_destroyed"
            if re.search(r"destroys\s+an?\s+enemy\b.*\bmodel\b", txt):
                trigger = "model_destroyed"
        except Exception:
            trigger = "unit_destroyed"

        # Parse heal amount expression (e.g. D6, D3, 3)
        heal_expr = None
        try:
            m = re.search(r"regains\s+up\s+to\s+(\d+|d\d+)\s+lost wounds", txt, flags=re.IGNORECASE)
            if m:
                heal_expr = m.group(1).upper()
        except Exception:
            heal_expr = None
        if not heal_expr:
            return []

        requires_melee = False
        try:
            if "melee attack" in txt or "with a melee" in txt:
                requires_melee = True
        except Exception:
            requires_melee = False

        keyword_map = {
            "character": "CHARACTER",
            "epic hero": "EPIC HERO",
            "monster": "MONSTER",
            "vehicle": "VEHICLE",
            "psyker": "PSYKER",
        }
        target_keywords = []
        for needle, kw in keyword_map.items():
            if needle in txt:
                target_keywords.append(kw)

        # If there are no keywords, allow only if the text explicitly references an enemy.
        if not target_keywords:
            if "enemy" not in txt:
                return []

        target_keyword_mode = "all"
        try:
            # Champion Slayer: "CHARACTER or MONSTER"
            if len(target_keywords) > 1 and " or " in txt:
                target_keyword_mode = "any"
        except Exception:
            target_keyword_mode = "all"

        return [{
            "type": "heal_on_destroy",
            "trigger": trigger,
            "heal_expr": heal_expr,
            "target_keywords": set(target_keywords),
            "target_keyword_mode": target_keyword_mode,
            "requires_melee": requires_melee,
            "source_ability": ability_name or "",
        }]

    def _parse_weapon_attacks_bonus_on_kill_specs_from_text(self, ability_name: str, ability_desc: str) -> List[dict]:
        """
        Parse support for abilities that grant persistent weapon Attacks bonuses on kill, e.g.:
        "... destroys an enemy CHARACTER model in the Fight phase ... until the end of the battle,
         add 1 to the Attacks characteristic of its Nemesis force weapon."
        """
        normalized = self._normalize_rules_text(ability_desc)
        txt = normalized.lower().replace("\u2019", "'")

        if "destroys" not in txt or "enemy" not in txt:
            return []
        if "until the end of the battle" not in txt:
            return []
        if "attacks characteristic" not in txt:
            return []

        m_bonus = re.search(r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic", txt, flags=re.IGNORECASE)
        if not m_bonus:
            return []
        try:
            attacks_bonus = int(m_bonus.group(1) or 0)
        except Exception:
            attacks_bonus = 0
        if attacks_bonus <= 0:
            return []

        weapon_name = ""
        m_weapon = re.search(r"of\s+its\s+([a-z0-9 '\-]+?)\s+weapons?\b", txt, flags=re.IGNORECASE)
        if m_weapon:
            weapon_name = str(m_weapon.group(1) or "").strip()
        if not weapon_name:
            return []

        trigger = "model_destroyed"
        try:
            if re.search(r"destroys\s+an?\s+(?:enemy\s+)?\b.*\bunit\b", txt):
                trigger = "unit_destroyed"
            if re.search(r"destroys\s+an?\s+(?:enemy\s+)?\b.*\bmodel\b", txt):
                trigger = "model_destroyed"
        except Exception:
            trigger = "model_destroyed"

        requires_melee = False
        try:
            if "melee attack" in txt or "with a melee" in txt:
                requires_melee = True
        except Exception:
            requires_melee = False
        requires_fight_phase = "fight phase" in txt

        keyword_map = {
            "character": "CHARACTER",
            "epic hero": "EPIC HERO",
            "monster": "MONSTER",
            "vehicle": "VEHICLE",
            "psyker": "PSYKER",
        }
        target_keywords = []
        for needle, kw in keyword_map.items():
            if needle in txt:
                target_keywords.append(kw)
        target_keyword_mode = "all"
        try:
            if len(target_keywords) > 1 and " or " in txt:
                target_keyword_mode = "any"
        except Exception:
            target_keyword_mode = "all"

        return [
            {
                "type": "weapon_attacks_bonus_on_destroy",
                "trigger": trigger,
                "attacks_bonus": int(attacks_bonus),
                "weapon_name": str(weapon_name),
                "target_keywords": set(target_keywords),
                "target_keyword_mode": target_keyword_mode,
                "requires_melee": bool(requires_melee),
                "requires_fight_phase": bool(requires_fight_phase),
                "source_ability": ability_name or "",
            }
        ]

    def get_kill_reward_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """Return parsed 'on destroy' reward specs for this unit (and optionally a specific model).

        Used by the event system to support abilities like Trophy Taker / Feeder Tendrils /
        Skulls for Khorne / The Great Wolf / Feared Interrogator / Champion Slayer (partial support).
        """
        # Cache unit-level specs (model-specific specs are not cached here)
        cache_key = "kill_reward_specs_base"
        if cache_key in getattr(self, "_ability_cache", {}):
            base_specs = self._ability_cache[cache_key]
        else:
            base_specs: List[dict] = []
            for n, d in self._iter_ability_entries_for_rules(model=None):
                base_specs.extend(self._parse_cp_on_kill_specs_from_text(n, d))
                base_specs.extend(self._parse_heal_on_kill_specs_from_text(n, d))
                base_specs.extend(self._parse_weapon_attacks_bonus_on_kill_specs_from_text(n, d))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache[cache_key] = base_specs

        # Add model-specific specs (if any)
        if model is None:
            return list(base_specs)

        model_specs: List[dict] = []
        for n, d in self._iter_ability_entries_for_rules(model=model):
            # Avoid double-counting unit-level entries by only parsing model abilities here.
            # We already parsed unit-level in base_specs.
            if n and any(s.get("source_ability") == n for s in base_specs):
                continue
            model_specs.extend(self._parse_cp_on_kill_specs_from_text(n, d))
            model_specs.extend(self._parse_heal_on_kill_specs_from_text(n, d))
            model_specs.extend(self._parse_weapon_attacks_bonus_on_kill_specs_from_text(n, d))

        return list(base_specs) + model_specs
    

    def is_eligible_to_fight(self, game_map: 'Map') -> bool:
        """Check if the unit is eligible to fight in the Fight Phase.
        
        A unit is eligible to fight if:
        a) it is within engagement range of one or more enemy units, OR
        b) it made a charge move this turn (current player's turn)
        
        Args:
            game_map: The game map to check for enemy units and engagement range
            
        Returns:
            bool: True if the unit is eligible to fight
        """
        if not self.is_alive() or not self.deployed:
            return False
        
        # Check if unit charged this turn - units that charged can always fight
        if self.round_state.charged_this_round:
            return True
        
        # Check if unit is within engagement range of any enemy unit
        enemy_units = game_map.get_enemy_units(self)
        for enemy_unit in enemy_units:
            if not enemy_unit.is_alive():
                continue
            if not game_map.is_within_engagement_range(self, enemy_unit):
                continue
            try:
                if bool(getattr(self, "is_aircraft", False)):
                    if bool(getattr(enemy_unit, "is_flying", False)):
                        return True
                    continue
                if bool(getattr(enemy_unit, "is_aircraft", False)) and not bool(getattr(self, "is_flying", False)):
                    continue
            except Exception:
                pass
            return True
        
        return False

    def has_fight_within_3_ability(self) -> bool:
        """Return True if this unit has a 'fight within 3\"' eligibility ability."""
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("fight_within_3"):
            return True
        return False

    def get_fight_within_3_sources(self) -> list[str]:
        """Return ability names that grant fight-within-3\" eligibility."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return []
        specs = sr.get("fight_within_3", []) or []
        names = []
        for item in specs:
            if isinstance(item, dict):
                name = str(item.get("name", "") or "").strip()
            else:
                name = str(item or "").strip()
            if name:
                names.append(name)
        return names

    def fight_within_3_active(self) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        return bool(sr.get("fight_within_3_active", False))

    def set_fight_within_3_active(self, active: bool, source: str | None = None) -> None:
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        if bool(active):
            sr["fight_within_3_active"] = True
            if source:
                sr["fight_within_3_active_source"] = str(source)
        else:
            if "fight_within_3_active" in sr:
                del sr["fight_within_3_active"]
            if "fight_within_3_active_source" in sr:
                del sr["fight_within_3_active_source"]
        self.special_rules = sr

    def clear_fight_within_3_active(self) -> None:
        self.set_fight_within_3_active(False)

    def _model_within_engagement_range_of_unit(self, model, target_unit) -> bool:
        try:
            from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
            from ...utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
        except Exception:
            return False
        try:
            target_models = list(target_unit.get_models_for_collision() or [])
        except Exception:
            target_models = list(getattr(target_unit, "models", []) or [])
        for tm in target_models:
            try:
                if not getattr(tm, "is_alive", False):
                    continue
            except Exception:
                pass
            try:
                hd = float(horizontal_distance_between_bases_2d(model.model_base, tm.model_base))
                vd = float(vertical_distance_between_bases(model.model_base, tm.model_base))
            except Exception:
                continue
            if hd <= ENGAGEMENT_RANGE_HORIZONTAL and vd <= ENGAGEMENT_RANGE_VERTICAL:
                return True
        return False

    def _model_within_range_of_unit(self, model, target_unit, radius: float) -> bool:
        try:
            from ...utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return False
        try:
            target_models = list(target_unit.get_models_for_collision() or [])
        except Exception:
            target_models = list(getattr(target_unit, "models", []) or [])
        for tm in target_models:
            try:
                if not getattr(tm, "is_alive", False):
                    continue
            except Exception:
                pass
            try:
                if float(distance_between_models_bases_3d(model, tm)) <= float(radius) + 1e-6:
                    return True
            except Exception:
                continue
        return False

    def get_fight_eligible_models_for_target(self, target_unit, game_map: Optional['Map'] = None, *, allow_within_3: Optional[bool] = None) -> list:
        """Return models in this unit eligible to fight the given target unit."""
        try:
            models = list(self.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(self, "models", []) or [])
        models = [m for m in models if bool(getattr(m, "is_alive", True))]
        if not models or target_unit is None:
            return []

        if not self.has_fight_within_3_ability():
            return list(models)

        if game_map is None:
            return list(models)

        try:
            if not game_map.is_within_engagement_range(self, target_unit):
                return []
        except Exception:
            return []

        if allow_within_3 is None:
            allow_within_3 = self.fight_within_3_active()

        eligible = []
        for model in models:
            if self._model_within_engagement_range_of_unit(model, target_unit):
                eligible.append(model)
                continue
            if allow_within_3 and self._model_within_range_of_unit(model, target_unit, 3.0):
                eligible.append(model)
        return eligible

    def _charge_bonus_suppressed_key(self, game=None) -> tuple[int, str]:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
            owner = str(getattr(current_player, "id", "") or "")
        except Exception:
            owner = ""
        return turn, owner

    def mark_charge_bonus_suppressed(self, game=None) -> None:
        turn, owner = self._charge_bonus_suppressed_key(game)
        try:
            self.round_state.charge_bonus_suppressed_turn = int(turn or 0)
        except Exception:
            self.round_state.charge_bonus_suppressed_turn = int(turn or 0)
        try:
            self.round_state.charge_bonus_suppressed_turn_owner = str(owner or "")
        except Exception:
            self.round_state.charge_bonus_suppressed_turn_owner = str(owner or "")

    def charge_bonus_suppressed(self, game=None) -> bool:
        try:
            sup_turn = int(getattr(self.round_state, "charge_bonus_suppressed_turn", 0) or 0)
        except Exception:
            sup_turn = 0
        try:
            sup_owner = str(getattr(self.round_state, "charge_bonus_suppressed_turn_owner", "") or "")
        except Exception:
            sup_owner = ""
        if not sup_turn or not sup_owner:
            return False
        turn, owner = self._charge_bonus_suppressed_key(game)
        return sup_turn == int(turn or 0) and sup_owner == str(owner or "")
    

    def should_fight_first(self) -> bool:
        """Check if this unit should fight in the Fight First stage.
        
        Units fight first if they:
        1. Have an inherent Fight First ability, OR
        2. Charged this turn
        
        Returns:
            bool: True if the unit should fight in the Fight First stage
        """
        if self._seductive_gambit_active():
            return False
        # Units that charged this turn fight first
        game = None
        try:
            game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
        except Exception:
            game = None
        if self.round_state.charged_this_round and not self.charge_bonus_suppressed(game):
            return True
            
        # Units with Fight First abilities fight first
        if self.has_fight_first():
            return True
        
        return False
    

    def has_deadly_demise(self) -> Tuple[bool, DiceCollection]:
        """Check if the unit has Deadly Demise ability and return the damage value.
        
        Returns:
            Tuple[bool, DiceCollection]: A tuple containing:
                - A boolean indicating if the unit has Deadly Demise ability
                - A DiceCollection object representing the damage value (e.g., "3", "D3", "D6") or None if no Deadly Demise ability
        """
        def _apply_violent_demise_override(result: Tuple[bool, DiceCollection]) -> Tuple[bool, DiceCollection]:
            if not result or not bool(result[0]):
                return result
            sr = getattr(self, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_violent_demise"):
                return result
            damage_expr = str(sr.get("enhancement_violent_demise_damage_dice", "") or "D3+1")
            return (True, DiceCollection.from_string(damage_expr))

        # Use cached result if available
        if 'deadly_demise' in getattr(self, '_ability_cache', {}):
            cached = self._ability_cache['deadly_demise']
            return _apply_violent_demise_override(cached)
        
        found, damage_str = self._find_ability_with_patterns(["deadly demise"], extract_value=True, value_pattern=r'(\d+|D\d+)')
        if found:
            try:
                dice_collection = DiceCollection.from_string(damage_str)
                result = (True, dice_collection)
            except ValueError:
                raise ValueError(f"Deadly Demise ability found but could not parse damage value '{damage_str}' for unit '{self.name}'")
        else:
            result = (False, None)
        result = _apply_violent_demise_override(result)
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['deadly_demise'] = result
        
        return result

    def _find_all_abilities_with_patterns(self, patterns: List[str], value_pattern: str) -> List[Tuple[int, Optional[str]]]:
        """
        Helper method to find all instances of abilities matching given patterns and extract values with conditions.
        Used specifically for Feel No Pain which can have multiple instances with conditions.
        
        Args:
            patterns: List of patterns to search for (case-insensitive)
            value_pattern: Regex pattern to extract value and optional condition
        
        Returns:
            List[Tuple[int, Optional[str]]]: List of (dice_value, condition) tuples
        """
        found_abilities = []
        
        # Check keywords first
        for keyword in self.keywords:
            for pattern in patterns:
                if pattern.lower() in keyword.lower():
                    match = re.search(value_pattern, keyword.lower())
                    if match:
                        dice_value = int(match.group(1))
                        condition = match.group(2).strip() if match.group(2) else None
                        found_abilities.append((dice_value, condition))
                    else:
                        raise ValueError(f"{pattern} ability found in keyword '{keyword}' but could not extract dice value for unit '{self.name}'")
        
        # Check unit-level abilities (possible_abilities)
        for ability in self._iter_active_possible_abilities():
            if isinstance(ability, str):
                for pattern in patterns:
                    if pattern.lower() in ability.lower():
                        match = re.search(value_pattern, ability.lower())
                        if match:
                            dice_value = int(match.group(1))
                            condition = match.group(2).strip() if match.group(2) else None
                            found_abilities.append((dice_value, condition))
                        else:
                            raise ValueError(f"{pattern} ability found in ability string '{ability}' but could not extract dice value for unit '{self.name}'")
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, 'name') and ability.name:
                    for pattern in patterns:
                        if pattern.lower() in ability.name.lower():
                            ability_name_matched = True
                            match = re.search(value_pattern, ability.name.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                # Check if ability has a parameter attribute (e.g., "5+")
                                if hasattr(ability, 'parameter') and ability.parameter:
                                    param_match = re.search(r'(\d+)\+', ability.parameter)
                                    if param_match:
                                        dice_value = int(param_match.group(1))
                                        found_abilities.append((dice_value, None))
                                    else:
                                        raise ValueError(f"{pattern} ability found in ability name '{ability.name}' with parameter '{ability.parameter}' but could not extract dice value for unit '{self.name}'")
                                else:
                                    raise ValueError(f"{pattern} ability found in ability name '{ability.name}' but could not extract dice value for unit '{self.name}'")
                
                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, 'description') and ability.description:
                    desc_text = self._normalize_rules_text(ability.description)
                    for pattern in patterns:
                        if pattern.lower() in desc_text.lower():
                            match = re.search(value_pattern, desc_text.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                raise ValueError(f"{pattern} ability found in ability description '{ability.description}' but could not extract dice value for unit '{self.name}'")
        
        # Check model-level abilities
        for ability in self.abilities:
            try:
                if not self._ability_is_active(ability):
                    continue
            except Exception:
                pass
            if isinstance(ability, str):
                for pattern in patterns:
                    if pattern.lower() in ability.lower():
                        match = re.search(value_pattern, ability.lower())
                        if match:
                            dice_value = int(match.group(1))
                            condition = match.group(2).strip() if match.group(2) else None
                            found_abilities.append((dice_value, condition))
                        else:
                            raise ValueError(f"{pattern} ability found in model ability string '{ability}' but could not extract dice value for unit '{self.name}'")
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, 'name') and ability.name:
                    for pattern in patterns:
                        if pattern.lower() in ability.name.lower():
                            ability_name_matched = True
                            match = re.search(value_pattern, ability.name.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                # Check if ability has a parameter attribute (e.g., "5+")
                                if hasattr(ability, 'parameter') and ability.parameter:
                                    param_match = re.search(r'(\d+)\+', ability.parameter)
                                    if param_match:
                                        dice_value = int(param_match.group(1))
                                        found_abilities.append((dice_value, None))
                                    else:
                                        raise ValueError(f"{pattern} ability found in model ability name '{ability.name}' with parameter '{ability.parameter}' but could not extract dice value for unit '{self.name}'")
                                else:
                                    raise ValueError(f"{pattern} ability found in model ability name '{ability.name}' but could not extract dice value for unit '{self.name}'")
                
                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, 'description') and ability.description:
                    desc_text = self._normalize_rules_text(ability.description)
                    for pattern in patterns:
                        if pattern.lower() in desc_text.lower():
                            match = re.search(value_pattern, desc_text.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                raise ValueError(f"{pattern} ability found in model ability description '{ability.description}' but could not extract dice value for unit '{self.name}'")
        
        return found_abilities

    def has_feel_no_pain(self, target_model: Optional['Model'] = None) -> List[Tuple[int, Optional[str]]]:
        """Check if the unit has Feel No Pain abilities and return all of them.
        
        Returns:
            List[Tuple[int, Optional[str]]]: A list of tuples containing:
                - The dice roll needed (e.g., 5 for "5+", 6 for "6+")
                - Optional condition string (e.g., "against psychic attacks", "against mortal wounds") (None if unconditional)
        """
        # Use cached result if available
        cached = None
        if 'feel_no_pain' in getattr(self, '_ability_cache', {}):
            cached = list(self._ability_cache['feel_no_pain'])
        if cached is None:
            cached = self._find_all_abilities_with_patterns(
                ["feel no pain", "fnp"],
                r'(?:feel no pain|fnp)\s*\(?(\d+)\+(?:\)?)(?:\s+(.+))?',
            )
            # Cache the base result (dynamic additions are layered below).
            if not hasattr(self, '_ability_cache'):
                self._ability_cache = {}
            self._ability_cache['feel_no_pain'] = list(cached)

        result = list(cached)
        try:
            sr = getattr(self, "special_rules", None)
            entries = sr.get("bearer_unit_fnp") if isinstance(sr, dict) else None
            if isinstance(entries, list):
                seen = set((int(v), (c or "")) for v, c in result)
                for entry in entries:
                    if isinstance(entry, dict):
                        val = entry.get("value")
                        cond = entry.get("condition")
                    elif isinstance(entry, (list, tuple)):
                        val = entry[0] if entry else None
                        cond = entry[1] if len(entry) > 1 else None
                    else:
                        continue
                    try:
                        val = int(val)
                    except Exception:
                        continue
                    key = (int(val), str(cond or ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    result.append((int(val), cond))
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            entries = sr.get("enhancement_bearer_fnp_entries") if isinstance(sr, dict) else None
            if isinstance(entries, list):
                seen = set((int(v), (c or "")) for v, c in result)
                for entry in entries:
                    if isinstance(entry, dict):
                        val = entry.get("value")
                        cond = entry.get("condition")
                    elif isinstance(entry, (list, tuple)):
                        val = entry[0] if entry else None
                        cond = entry[1] if len(entry) > 1 else None
                    else:
                        continue
                    try:
                        val = int(val)
                    except Exception:
                        continue
                    key = (int(val), str(cond or ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    result.append((int(val), cond))
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            entries = sr.get("attached_character_fnp_entries") if isinstance(sr, dict) else None
            if isinstance(entries, list) and target_model is not None:
                t_unit = getattr(target_model, "parent_unit", None) or self
                if bool(getattr(t_unit, "is_attached_leader", False)) and bool(getattr(target_model, "is_character", False)):
                    t_unit_id = get_entity_id(t_unit)
                    seen = set((int(v), (c or "")) for v, c in result)
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        exclude_id = entry.get("exclude_unit_id")
                        if exclude_id and str(exclude_id) == str(t_unit_id):
                            continue
                        try:
                            val = int(entry.get("value"))
                        except Exception:
                            continue
                        key = (int(val), "")
                        if key in seen:
                            continue
                        seen.add(key)
                        result.append((int(val), None))
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            entries = sr.get("unit_contains_character_fnp_entries") if isinstance(sr, dict) else None
            if isinstance(entries, list) and target_model is not None:
                if bool(getattr(target_model, "is_character", False)):
                    seen = set((int(v), (c or "")) for v, c in result)
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        try:
                            val = int(entry.get("value"))
                        except Exception:
                            continue
                        key = (int(val), "")
                        if key in seen:
                            continue
                        seen.add(key)
                        result.append((int(val), None))
        except Exception:
            pass
        try:
            if target_model is not None and hasattr(target_model, "get_temporary_fnp_entries"):
                entries = list(target_model.get_temporary_fnp_entries() or [])
                if entries:
                    seen = set((int(v), (c or "")) for v, c in result)
                    for val, cond in entries:
                        try:
                            val = int(val)
                        except Exception:
                            continue
                        key = (int(val), str(cond or ""))
                        if key in seen:
                            continue
                        seen.add(key)
                        result.append((int(val), cond))
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "blood_tithe_enraged_abjuration_applies", None):
                if mgr.blood_tithe_enraged_abjuration_applies(self):
                    entry = (5, "against psychic attacks and mortal wounds")
                    if entry not in result:
                        result.append(entry)
        except Exception:
            pass
        try:
            # Truesilver Aegis (Aura): friendly GREY KNIGHTS units wholly within 6" gain FNP 6+ vs mortal wounds.
            if self.has_any_keyword("GREY KNIGHTS"):
                from ...utility.aura_utils import unit_wholly_within_range_of_unit

                army = self.get_parent_army()
                friendly_units = []
                if army is not None:
                    try:
                        game = getattr(getattr(army, "player", None), "game", None)
                        game_map = getattr(game, "map", None) if game is not None else None
                    except Exception:
                        game_map = None
                    if game_map is not None and hasattr(game_map, "get_friendly_units"):
                        try:
                            friendly_units = list(game_map.get_friendly_units(self))
                        except Exception:
                            friendly_units = []
                    if not friendly_units:
                        friendly_units = list(getattr(army, "units", []) or [])

                if friendly_units:
                    seen = set((int(v), (c or "")) for v, c in result)
                    for source in list(friendly_units):
                        if source is None:
                            continue
                        has_aura = getattr(source, "has_truesilver_aegis_aura", None)
                        if not callable(has_aura) or not bool(has_aura()):
                            continue
                        try:
                            if hasattr(source, "is_active_for_rules") and not source.is_active_for_rules():
                                continue
                        except Exception:
                            continue
                        if not unit_wholly_within_range_of_unit(source, self, 6.0, use_attached_aggregate=True):
                            continue
                        key = (6, "against mortal wounds")
                        if key not in seen:
                            seen.add(key)
                            result.append((6, "against mortal wounds"))
                        break
        except Exception:
            pass
        try:
            # Improbable Shield (Aura): friendly LEGIONES DAEMONICA TZEENTCH within 6" gain FNP 4+ vs Psychic/mortal.
            is_tzeentch = False
            is_legiones = False
            try:
                is_tzeentch = bool(self.has_any_keyword("TZEENTCH"))
                is_legiones = bool(self.has_any_keyword("LEGIONES DAEMONICA"))
            except Exception:
                is_tzeentch = False
                is_legiones = False
            if is_tzeentch and is_legiones:
                from ...rules.enhancement_descriptors import get_enhancement_tool_descriptor
                from ...utility.aura_utils import model_within_range_of_unit

                desc = get_enhancement_tool_descriptor(
                    enhancement_id="000009810005",
                    name="Improbable Shield (Aura)",
                )
                try:
                    rng = float(getattr(desc, "range_in", 6.0) or 6.0)
                except Exception:
                    rng = 6.0
                try:
                    params = getattr(desc, "effect_params", {}) if desc is not None else {}
                except Exception:
                    params = {}
                try:
                    fnp_val = int(params.get("fnp", 4) or 4)
                except Exception:
                    fnp_val = 4
                condition = str(params.get("condition", "") or "against psychic attacks and mortal wounds").strip()

                army = self.get_parent_army()
                friendly_units = []
                if army is not None:
                    try:
                        game = getattr(getattr(army, "player", None), "game", None)
                        game_map = getattr(game, "map", None) if game is not None else None
                    except Exception:
                        game_map = None
                    if game_map is not None and hasattr(game_map, "get_friendly_units"):
                        try:
                            friendly_units = list(game_map.get_friendly_units(self))
                        except Exception:
                            friendly_units = []
                    if not friendly_units:
                        friendly_units = list(getattr(army, "units", []) or [])

                if friendly_units:
                    seen = set((int(v), (c or "")) for v, c in result)
                    for source in list(friendly_units):
                        sr = getattr(source, "special_rules", None)
                        if not isinstance(sr, dict) or not sr.get("enhancement_improbable_shield"):
                            continue
                        try:
                            if hasattr(source, "is_active_for_rules") and not source.is_active_for_rules():
                                continue
                        except Exception:
                            continue
                        bearer = None
                        try:
                            get_bearer = getattr(source, "_get_enhancement_bearer_model", None)
                            if callable(get_bearer):
                                bearer = get_bearer()
                        except Exception:
                            bearer = None
                        if bearer is None:
                            continue
                        if not model_within_range_of_unit(bearer, self, rng, use_attached_aggregate=True):
                            continue
                        key = (int(fnp_val), str(condition or ""))
                        if key not in seen:
                            seen.add(key)
                            result.append((int(fnp_val), condition))
                        break
        except Exception:
            pass
        return result

    def get_max_weapon_range(self) -> float:
        """Get the maximum range of all weapons in the unit."""
        max_range = 0
        for model in self.models:
            for weapon in model.wargear:
                # Skip melee weapons
                if weapon.is_melee():
                    continue
                
                # Get the maximum range from all profiles
                for profile in weapon.profiles.values():
                    if hasattr(profile, 'range') and profile.range and hasattr(profile.range, 'max'):
                        effective_max = profile.range.max
                        try:
                            if hasattr(profile, "_effective_range_max"):
                                effective_max = profile._effective_range_max(model)
                        except Exception:
                            effective_max = profile.range.max
                        max_range = max(max_range, effective_max)
        
        return max_range

    ###########################################################################
    ### Reserves System
    ###########################################################################
    # Units arriving from reserves (including Deep Strike) have the following restrictions:
    # - CANNOT move normally or advance (unless special rules allow it)
    # - CAN shoot, charge, and fight normally (this is the default rule)
    # - Only special rules would prevent charging/shooting after arriving from reserves

    def set_reserve_status(self, status: str) -> None:
        """Set the reserve status of the unit.
        
        Args:
            status: 'deployed', 'reserves', 'strategic_reserves'
        """
        valid_statuses = ['deployed', 'reserves', 'strategic_reserves']
        if status not in valid_statuses:
            raise ValueError(f"Invalid reserve status: {status}. Must be one of {valid_statuses}")
        prev_status = getattr(self, "reserve_status", None)
        self.reserve_status = status
        # Note: deployed flag is managed separately by deployment logic
        # deployed=True means deployment decision made, deployed=False means needs decision
        if prev_status != status:
            self._publish_unit_event(
                "unit_reserve_status_changed",
                unit=self,
                previous_status=prev_status,
                reserve_status=status,
            )
            self._publish_unit_event(
                "unit_state_changed",
                unit=self,
                reason="reserve_status_changed",
                previous_status=prev_status,
                reserve_status=status,
            )

        # Attached unit behavior: Leaders follow the Bodyguard's reserve decision.
        try:
            for leader in list(getattr(self, "attached_leaders", []) or []):
                try:
                    leader_prev = getattr(leader, "reserve_status", None)
                    leader.reserve_status = status
                except Exception:
                    continue
                if leader_prev != status:
                    publish_fn = getattr(leader, "_publish_unit_event", None)
                    if callable(publish_fn):
                        publish_fn(
                            "unit_reserve_status_changed",
                            unit=leader,
                            previous_status=leader_prev,
                            reserve_status=status,
                        )
                        publish_fn(
                            "unit_state_changed",
                            unit=leader,
                            reason="reserve_status_changed",
                            previous_status=leader_prev,
                            reserve_status=status,
                        )
        except Exception:
            pass

    def mark_entered_reserves_midgame(self, game=None) -> None:
        """Mark that this unit entered reserves during the battle (not at deployment)."""
        try:
            turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        except Exception:
            turn = 0
        try:
            setattr(self, "_entered_reserves_midgame_round", int(turn))
            setattr(self, "_entered_reserves_midgame", True)
        except Exception:
            pass

    def enter_strategic_reserves_midgame(self, *, game=None, game_map=None, reason: str = "") -> bool:
        """Place this unit (and any attached members) into Strategic Reserves mid-battle."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if game is None:
            try:
                game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        if game_map is None and game is not None:
            try:
                game_map = getattr(game, "map", None)
            except Exception:
                game_map = None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for member in members:
            try:
                member.set_reserve_status("strategic_reserves")
            except Exception:
                try:
                    member.reserve_status = "strategic_reserves"
                except Exception:
                    pass
            try:
                member.mark_entered_reserves_midgame(game=game)
            except Exception:
                pass
            try:
                if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                    if game is not None:
                        member._aircraft_return_turn = int(getattr(game, "turn", 0) or 0) + 1
            except Exception:
                pass
            try:
                member.deployed = True
                member.reserve_turn_deployed = None
                member.arrived_from_reserves_this_turn = False
            except Exception:
                pass
            try:
                if game_map is not None and hasattr(game_map, "units") and member in game_map.units:
                    game_map.units.remove(member)
            except Exception:
                pass

        label = reason or "mid-battle ability"
        try:
            logger.info(f"{root.name} placed into Strategic Reserves ({label})")
        except Exception:
            pass
        return True
        

    def is_in_reserves(self) -> bool:
        """Check if the unit is currently in reserves (any type)."""
        return self.reserve_status in ['reserves', 'strategic_reserves']
    

    def is_in_standard_reserves(self) -> bool:
        """Check if the unit is in standard reserves (Deep Strike, etc.)."""
        return self.reserve_status == 'reserves'
    

    def is_in_strategic_reserves(self) -> bool:
        """Check if the unit is in strategic reserves."""
        return self.reserve_status == 'strategic_reserves'
    

    def can_arrive_from_reserves(self, current_turn: int) -> bool:
        """Check if the unit can arrive from reserves this turn.
        
        Args:
            current_turn: The current battle round number
        
        Returns:
            bool: True if the unit can arrive from reserves this turn
        """
        if not self.is_in_reserves():
            return False

        # Reborn in Blood: only the next Movement phase is eligible.
        try:
            if bool(getattr(self, "_reborn_in_blood_pending", False)):
                allowed_round = getattr(self, "_reborn_in_blood_arrival_round", None)
                if allowed_round is not None and int(current_turn) != int(allowed_round):
                    return False
                try:
                    army = self.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if game is not None:
                        if not getattr(game, "is_movement_phase", lambda: False)():
                            return False
                        if getattr(game, "get_current_player", lambda: None)() is not getattr(army, "player", None):
                            return False
                except Exception:
                    pass
        except Exception:
            pass

        # Umbralefic Crystal: only this turn's Movement phase on the owner's turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("umbralefic_crystal_temp_deep_strike")):
                allowed_round = int(sr.get("umbralefic_crystal_must_arrive_turn", 0) or 0)
                if allowed_round and int(current_turn) != int(allowed_round):
                    return False
                owner_id = str(sr.get("umbralefic_crystal_must_arrive_turn_owner", "") or "")
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if game is not None:
                    if not getattr(game, "is_movement_phase", lambda: False)():
                        return False
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    if owner_id and cur_owner and owner_id != cur_owner:
                        return False
        except Exception:
            pass
        
        allow_turn1 = False
        try:
            allow_turn1 = bool(self._strategic_reserves_round_bonus())
        except Exception:
            allow_turn1 = False
        if not allow_turn1:
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and bool(sr.get("umbralefic_crystal_temp_deep_strike")):
                    allowed_round = int(sr.get("umbralefic_crystal_must_arrive_turn", 0) or 0)
                    if not allowed_round or int(current_turn) == int(allowed_round):
                        allow_turn1 = True
            except Exception:
                pass

        # Units cannot arrive from reserves on Turn 1 unless a rule permits it.
        if current_turn < 2 and not allow_turn1:
            return False

        # AIRCRAFT placed into Strategic Reserves mid-game return next turn.
        try:
            aircraft_return_turn = getattr(self, "_aircraft_return_turn", None)
        except Exception:
            aircraft_return_turn = None
        if aircraft_return_turn is not None:
            try:
                if int(current_turn) < int(aircraft_return_turn):
                    return False
            except Exception:
                return False
        
        # Chapter Approved: the "must arrive by end of battle round 3" restriction applies only to
        # units that STARTED the game in reserves, not units placed into reserves mid-game.
        try:
            started_in_reserves = bool(getattr(self, "_started_in_reserves", False))
        except Exception:
            started_in_reserves = False
        if started_in_reserves and current_turn > 3:
            return False
        
        return True

    def _finalize_reserves_arrival(self, turn: int, game_map: Optional['Map'] = None) -> bool:
        """Finalize state updates for a unit that has been set up from reserves."""
        # Unit position is now determined by model positions
        try:
            pre_reserve_status = str(getattr(self, "reserve_status", "") or "")
        except Exception:
            pre_reserve_status = ""
        try:
            pending_deep_strike = bool(getattr(self, "_pending_reserves_deep_strike", False))
        except Exception:
            pending_deep_strike = False
        try:
            if hasattr(self, "_pending_reserves_deep_strike"):
                delattr(self, "_pending_reserves_deep_strike")
        except Exception:
            pass

        # Update unit status
        self.deployed = True
        self.set_reserve_status("deployed")
        self.reserve_turn_deployed = turn
        self.arrived_from_reserves_this_turn = True
        try:
            if hasattr(self, "_reborn_in_blood_pending"):
                delattr(self, "_reborn_in_blood_pending")
        except Exception:
            pass
        try:
            if hasattr(self, "_reborn_in_blood_arrival_round"):
                delattr(self, "_reborn_in_blood_arrival_round")
        except Exception:
            pass
        try:
            if hasattr(self, "_aircraft_return_turn"):
                delattr(self, "_aircraft_return_turn")
        except Exception:
            pass

        try:
            army = self.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            sr = getattr(self, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if pname:
                sr["voice_of_command_set_up_phase"] = pname
                try:
                    sr["voice_of_command_set_up_round"] = int(getattr(game, "turn", turn) or turn)
                except Exception:
                    sr["voice_of_command_set_up_round"] = int(turn or 0)
            self.special_rules = sr
        except Exception:
            pass

        # Grey Knights: Fury of Titan (Deep Strike arrivals re-roll hit/wound 1s until end of turn).
        try:
            used_deep_strike = bool(pre_reserve_status == "reserves" or pending_deep_strike)
            if used_deep_strike and self.has_deep_strike():
                army = self.get_parent_army()
                mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
                if mgr is not None and getattr(mgr, "fury_of_titan_applies", None):
                    if mgr.fury_of_titan_applies(self, used_deep_strike=True):
                        mgr.apply_fury_of_titan(self)
        except Exception:
            pass

        # Reserves arrivals count as having made a Normal move this turn (reinforced).
        try:
            self.round_state.reinforced_this_round = True
            self.round_state.remained_stationary_this_round = False
        except Exception:
            pass

        # Chapter Approved exception: if the unit was too large to be set up wholly within 6" of an edge
        # and instead used the "base touches edge" placement, it cannot move, charge, or shoot this turn.
        try:
            edge_touch = bool(getattr(self, "_pending_reserves_edge_touch", False))
        except Exception:
            edge_touch = False
        try:
            if hasattr(self, "_pending_reserves_edge_touch"):
                delattr(self, "_pending_reserves_edge_touch")
        except Exception:
            pass
        try:
            setattr(self, "_reserves_edge_touch_this_turn", bool(edge_touch))
        except Exception:
            pass

        # Swooping Descent: if set up within 9" of an enemy, cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            pain_min = float(sr.get("pain_deep_strike_min_distance", 0) or 0) if isinstance(sr, dict) else 0.0
            if pain_min and game_map is not None:
                from ...utility.aura_utils import horizontal_distance_between_bases_2d
                within_nine = False
                for enemy in list(game_map.get_enemy_units(self) or []):
                    try:
                        if not getattr(enemy, "is_alive", lambda: True)():
                            continue
                        if not getattr(enemy, "deployed", True):
                            continue
                    except Exception:
                        continue
                    for em in list(getattr(enemy, "models", []) or []):
                        if not getattr(em, "is_alive", True):
                            continue
                        for m in list(getattr(self, "models", []) or []):
                            if not getattr(m, "is_alive", True):
                                continue
                            if float(horizontal_distance_between_bases_2d(m.model_base, em.model_base)) <= 9.0 + 1e-6:
                                within_nine = True
                                break
                        if within_nine:
                            break
                    if within_nine:
                        break
                if within_nine:
                    try:
                        owner = self.get_parent_army().player.id
                    except Exception:
                        owner = ""
                    sr["pain_swooping_descent_no_charge_turn"] = int(turn or 0)
                    if owner:
                        sr["pain_swooping_descent_no_charge_turn_owner"] = owner
                    self.special_rules = sr
        except Exception:
            pass

        # Clear temporary Deep Strike flags from Realm of Chaos/Denizens of the Warp.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                if sr.get("realm_of_chaos_temp_deep_strike") is True:
                    for key in (
                        "realm_of_chaos_temp_deep_strike",
                        "realm_of_chaos_turn_owner",
                        "realm_of_chaos_turn",
                        "realm_of_chaos_source",
                    ):
                        sr.pop(key, None)
                if "denizens_deep_strike_min_distance" in sr or "denizens_deep_strike_expires_phase" in sr:
                    for key in (
                        "denizens_deep_strike_min_distance",
                        "denizens_deep_strike_turn_owner",
                        "denizens_deep_strike_turn",
                        "denizens_deep_strike_expires_phase",
                        "denizens_deep_strike_source",
                    ):
                        sr.pop(key, None)
                if "rapid_manifestation_deep_strike_min_distance" in sr or "rapid_manifestation_expires_phase" in sr:
                    for key in (
                        "rapid_manifestation_deep_strike_min_distance",
                        "rapid_manifestation_turn_owner",
                        "rapid_manifestation_turn",
                        "rapid_manifestation_expires_phase",
                        "rapid_manifestation_source",
                    ):
                        sr.pop(key, None)
                if "hallowed_beacon_deep_strike_min_distance" in sr or "hallowed_beacon_expires_phase" in sr:
                    for key in (
                        "hallowed_beacon_deep_strike_min_distance",
                        "hallowed_beacon_requires_hallowed_ground",
                        "hallowed_beacon_turn_owner",
                        "hallowed_beacon_turn",
                        "hallowed_beacon_expires_phase",
                        "hallowed_beacon_source",
                    ):
                        sr.pop(key, None)
                if sr.get("umbralefic_crystal_temp_deep_strike") is True or "umbralefic_crystal_must_arrive_turn" in sr:
                    for key in (
                        "umbralefic_crystal_temp_deep_strike",
                        "umbralefic_crystal_must_arrive_turn_owner",
                        "umbralefic_crystal_must_arrive_turn",
                    ):
                        sr.pop(key, None)
                self.special_rules = sr
                if hasattr(self, "_ability_cache") and isinstance(getattr(self, "_ability_cache", None), dict):
                    self._ability_cache.pop("deep_strike", None)
        except Exception:
            pass

        logger.info(f" {self.name} arrived from reserves at turn {turn}")
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if mgr is not None and game is not None:
                mgr.maybe_trigger_setup_maneuver(self, game)
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if game is not None and hasattr(game, "event_system"):
                game.event_system.publish("unit_set_up", unit=self)
        except Exception:
            pass
        return True
    

    def must_arrive_from_reserves(self, current_turn: int) -> bool:
        """Check if the unit must arrive from reserves this turn or be destroyed.
        
        Args:
            current_turn: The current battle round number
        
        Returns:
            bool: True if the unit must arrive this turn or be destroyed
        """
        try:
            if bool(getattr(self, "_reborn_in_blood_pending", False)):
                allowed_round = getattr(self, "_reborn_in_blood_arrival_round", None)
                if allowed_round is None or int(current_turn) != int(allowed_round):
                    return False
                try:
                    army = self.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if game is not None and not getattr(game, "is_movement_phase", lambda: False)():
                        return False
                except Exception:
                    pass
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("umbralefic_crystal_temp_deep_strike")):
                allowed_round = int(sr.get("umbralefic_crystal_must_arrive_turn", 0) or 0)
                if not allowed_round or int(current_turn) != int(allowed_round):
                    return False
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if game is not None and not getattr(game, "is_movement_phase", lambda: False)():
                    return False
                owner_id = str(sr.get("umbralefic_crystal_must_arrive_turn_owner", "") or "")
                if owner_id and game is not None:
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    if cur_owner and cur_owner != owner_id:
                        return False
                return self.is_in_reserves()
        except Exception:
            pass
        # AIRCRAFT returning next turn is mandatory.
        try:
            aircraft_return_turn = getattr(self, "_aircraft_return_turn", None)
        except Exception:
            aircraft_return_turn = None
        if aircraft_return_turn is not None:
            try:
                return self.is_in_reserves() and int(current_turn) >= int(aircraft_return_turn)
            except Exception:
                return self.is_in_reserves()

        try:
            started_in_reserves = bool(getattr(self, "_started_in_reserves", False))
        except Exception:
            started_in_reserves = False
        return self.is_in_reserves() and started_in_reserves and current_turn >= 3
    

    def arrive_from_reserves(self, position: Tuple[float, float, float], turn: int, game_map: Optional['Map'] = None) -> bool:
        """Deploy the unit from reserves at the specified position.
        
        Args:
            position: (x, y, z) coordinates where the unit should be placed
            turn: Current turn number
        
        Returns:
            bool: True if deployment was successful
        """
        if not self.can_arrive_from_reserves(turn):
            return False
        
        # Deploy all models at calculated positions
        try:
            # Use the existing model positioning logic with battlefield edge repulsors
            boundary_repulsors = game_map.get_battlefield_edge_repulsors() if game_map else []
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            model_positions = self.calculate_model_positions(position[0], position[1], game_map, boundary_repulsors=boundary_repulsors, avoid_friendly_units=False)
            
            # Check if formation finding failed
            if model_positions is None:
                logger.warning(f"Could not find valid formation for {self.name} arriving from reserves - using default placement")
                # Default: place all models at the unit position
                for model in self.models:
                    model.set_location(position[0], position[1], position[2], 0.0)
            else:
                for model, model_pos in zip(self.models, model_positions):
                    model.set_location(model_pos[0], model_pos[1], model_pos[2], model_pos[3])
        except Exception as e:
            logger.warning(f"Could not calculate model positions for {self.name} arriving from reserves: {e}")
            # Default: place all models at the unit position
            for model in self.models:
                model.set_location(position[0], position[1], position[2], 0.0)
        
        # Unit position is now determined by model positions
        return self._finalize_reserves_arrival(turn, game_map)
    

    def can_move_after_arriving_from_reserves(self) -> bool:
        """Check if the unit can move normally after arriving from reserves this turn."""
        # Units arriving from reserves cannot move unless they have special rules
        if not self.arrived_from_reserves_this_turn:
            return True
        
        # Check for special abilities that allow movement after arriving from reserves
        for ability in self._iter_active_possible_abilities():
            if hasattr(ability, 'name') and ability.name:
                if "can move after" in ability.name.lower() or "move after arriving" in ability.name.lower():
                    return True
            if hasattr(ability, 'description') and ability.description:
                if "can move after" in ability.description.lower() or "move after arriving" in ability.description.lower():
                    return True
        
        return False
    

    def can_advance_after_arriving_from_reserves(self) -> bool:
        """Check if the unit can advance after arriving from reserves this turn."""
        if not self.arrived_from_reserves_this_turn:
            return True
        
        # Units arriving from reserves cannot advance unless they have special rules
        # Check for special abilities that allow advancing after arriving from reserves
        for ability in self._iter_active_possible_abilities():
            if hasattr(ability, 'name') and ability.name:
                if "can advance after" in ability.name.lower() or "advance after arriving" in ability.name.lower():
                    return True
            if hasattr(ability, 'description') and ability.description:
                if "can advance after" in ability.description.lower() or "advance after arriving" in ability.description.lower():
                    return True
        
        return False
    

    def can_charge_after_arriving_from_reserves(self) -> bool:
        """Check if the unit can charge after arriving from reserves this turn."""
        if not self.arrived_from_reserves_this_turn:
            return True

        # Edge-touch exception: cannot charge this turn.
        try:
            if bool(getattr(self, "_reserves_edge_touch_this_turn", False)):
                return False
        except Exception:
            pass
        
        # Units arriving from reserves CAN charge by default (this is the normal rule)
        # Only special restrictions would prevent charging
        for ability in self._iter_active_possible_abilities():
            if hasattr(ability, 'name') and ability.name:
                if ("cannot charge after" in ability.name.lower() or 
                    "no charge after arriving" in ability.name.lower()):
                    return False
            if hasattr(ability, 'description') and ability.description:
                if ("cannot charge after" in ability.description.lower() or 
                    "no charge after arriving" in ability.description.lower()):
                    return False
        
        return True  # Default: can charge after arriving from reserves

    def take_desperate_escape_test(
        self,
        game_map: Optional['Map'] = None,
        *,
        roll_modifier: int = 0,
        reason: str | None = None,
    ) -> int:
        """
        Take a Desperate Escape Test - rolling D6 for each model, destroying on 1-2.
        This is required for Battle-Shocked units that fall back.
        
        Returns:
            int: Number of models destroyed during the test
        """
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bearer_unit_auto_pass_desperate_escape"):
                logger.info(f"{self.name} automatically passes Desperate Escape tests.")
                return 0
        except Exception:
            pass
        note = str(reason or "").strip()
        if note:
            logger.info(f"{self.name} {note} - taking Desperate Escape Test!")
        else:
            logger.info(f"{self.name} is Battle-Shocked and falling back - taking Desperate Escape Test!")
        
        models_to_test = self.models.copy()  # Copy to avoid modifying list while iterating
        models_destroyed = 0
        mod = int(roll_modifier or 0)
        
        for i, model in enumerate(models_to_test):
            roll = get_roll("D6")
            final_roll = roll + mod
            if final_roll <= 2:
                # Model is destroyed
                if mod:
                    logger.info(f"Model {i+1}: Rolled {roll} ({mod:+d} -> {final_roll}) - DESTROYED! ")
                else:
                    logger.info(f"Model {i+1}: Rolled {roll} - DESTROYED! ")
                self.remove_model(model, fleed=True, game_map=game_map)  # Mark as fled, not killed in combat
                models_destroyed += 1
            else:
                # Model survives
                if mod:
                    logger.info(f"Model {i+1}: Rolled {roll} ({mod:+d} -> {final_roll}) - Survives ")
                else:
                    logger.info(f"Model {i+1}: Rolled {roll} - Survives ")
        
        if models_destroyed > 0:
            logger.info(f"Desperate Escape Test complete: {models_destroyed} model(s) destroyed, {len(self.models)} remain")
        else:
            logger.info(f"Desperate Escape Test complete: All models survived!")
        
        return models_destroyed

    def has_lone_operative(self) -> bool:
        """Check if the unit has Lone Operative ability."""
        # Lone Operative does NOT "leak" into an Attached unit via a Leader.
        # If a Leader with Lone Operative is attached to a Bodyguard unit that does not have Lone Operative,
        # the Attached unit does not benefit from Lone Operative while attached.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                root = self.get_attached_unit_root()
                if root is not None and root is not self:
                    return bool(root.has_lone_operative())
        except Exception:
            pass

        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("enhancement_praesidius_lone_operative"):
            return True
        if isinstance(sr, dict) and sr.get("enhancement_spirit_stone_of_raelyth"):
            try:
                game_map = self.get_parent_army().player.game.map
            except Exception:
                game_map = None
            if game_map is not None:
                try:
                    from ...utility.aura_utils import distance_between_models_bases_3d
                    bearer = self._get_enhancement_bearer_model()
                    if bearer is not None and getattr(bearer, "is_alive", True):
                        for other in list(game_map.get_friendly_units(self)):
                            if other is None or other is self:
                                continue
                            try:
                                if not other.has_any_keyword("AELDARI"):
                                    continue
                                if not other.has_any_keyword("VEHICLE"):
                                    continue
                            except Exception:
                                continue
                            try:
                                models = list(other.get_attached_unit_models() or [])
                            except Exception:
                                models = list(getattr(other, "models", []) or [])
                            for tm in models:
                                try:
                                    if not getattr(tm, "is_alive", True):
                                        continue
                                except Exception:
                                    continue
                                try:
                                    if distance_between_models_bases_3d(bearer, tm) <= 3.0 + 1e-6:
                                        return True
                                except Exception:
                                    continue
                except Exception:
                    pass

        normalize_rules_text = getattr(self, "_normalize_rules_text", None)
        if not callable(normalize_rules_text):
            def normalize_rules_text(value: str) -> str:
                return Unit._normalize_rules_text(self, value)
        else:
            def normalize_rules_text(value: str) -> str:
                return self._normalize_rules_text(value)

        strip_eligibility_prefix = getattr(self, "_strip_eligibility_prefix", None)
        if not callable(strip_eligibility_prefix):
            def strip_eligibility_prefix(value: str) -> str:
                return Unit._strip_eligibility_prefix(value)
        else:
            def strip_eligibility_prefix(value: str) -> str:
                return self._strip_eligibility_prefix(value)

        unit_matches_keyword_phrase = getattr(self, "_unit_matches_keyword_phrase", None)
        if not callable(unit_matches_keyword_phrase):
            def unit_matches_keyword_phrase(unit, phrase: str) -> bool:
                return Unit._unit_matches_keyword_phrase(unit, phrase)
        else:
            def unit_matches_keyword_phrase(unit, phrase: str) -> bool:
                return self._unit_matches_keyword_phrase(unit, phrase)

        def _iter_ability_entries():
            if callable(getattr(self, "_iter_ability_entries_for_rules", None)):
                yield from self._iter_ability_entries_for_rules(model=None)
                return
            for ability in getattr(self, "possible_abilities", []) or []:
                yield getattr(ability, "name", None), getattr(ability, "description", None)

        def _normalize_lo_text(value: str) -> str:
            t = normalize_rules_text(value or "")
            t = t.replace("\u2019", "'").replace("\u0192?T", "'")
            t = re.sub(r"'s\b", "s", t, flags=re.IGNORECASE)
            t = t.lower()
            t = re.sub(r"[^a-z0-9]+", " ", t)
            return re.sub(r"\s+", " ", t).strip()

        # Base Lone Operative (static) and conditional proximity-based Lone Operative.
        cache = getattr(self, "_ability_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._ability_cache = cache
        base_found = cache.get("lone_operative_base")
        conditional_rules = cache.get("lone_operative_conditional_rules")
        if base_found is None or conditional_rules is None:
            base_found = False
            conditional_rules = []
            for name, desc in _iter_ability_entries():
                text_src = strip_eligibility_prefix(desc or name or "")
                norm = _normalize_lo_text(text_src)
                if "lone operative" not in norm:
                    continue
                m = re.search(
                    r"while (?:this model|the bearer|this unit) is within (?P<range>\d+) of one or more "
                    r"(?P<other>other )?friendly (?P<keywords>.+?) units?"
                    r"(?P<exclude> excluding units with the lone operative ability)?"
                    r"(?P<not_attached> if this unit is not an attached unit)? "
                    r"(?:this model|the bearer|this unit|it) has (?:the )?lone operative ability",
                    norm,
                    flags=re.IGNORECASE,
                )
                if m:
                    kw_phrase = str(m.group("keywords") or "").strip()
                    if not kw_phrase:
                        continue
                    keyword_options = [kw_phrase]
                    if " or " in kw_phrase:
                        keyword_options = [part.strip() for part in kw_phrase.split(" or ") if part.strip()]
                        if not keyword_options:
                            keyword_options = [kw_phrase]
                    try:
                        rng = int(m.group("range") or 0)
                    except Exception:
                        rng = 0
                    if rng <= 0:
                        continue
                    conditional_rules.append(
                        {
                            "range": int(rng),
                            "keywords": kw_phrase,
                            "keyword_options": tuple(keyword_options),
                            "requires_other": bool(m.group("other")),
                            "exclude_lone_operative": bool(m.group("exclude")),
                            "requires_not_attached": bool(m.group("not_attached")),
                            "source": str(name or "Lone Operative").strip() or "Lone Operative",
                        }
                    )
                    continue
                base_found = True
            cache["lone_operative_base"] = bool(base_found)
            cache["lone_operative_conditional_rules"] = list(conditional_rules)
        else:
            base_found = bool(base_found)
            conditional_rules = list(conditional_rules or [])

        if conditional_rules:
            def _unit_mentions_lone_operative(unit_obj) -> bool:
                try:
                    iter_entries = getattr(unit_obj, "_iter_ability_entries_for_rules", None)
                    if callable(iter_entries):
                        entries = iter_entries(model=None)
                    else:
                        entries = (
                            (getattr(ability, "name", None), getattr(ability, "description", None))
                            for ability in list(getattr(unit_obj, "possible_abilities", []) or [])
                        )
                    for n_name, n_desc in entries:
                        text = strip_eligibility_prefix(f"{n_name or ''} {n_desc or ''}")
                        if not text:
                            continue
                        if "lone operative" in _normalize_lo_text(text):
                            return True
                except Exception:
                    return False
                return False

            game_map = None
            try:
                game_map = self.get_parent_army().player.game.map
            except Exception:
                game_map = None
            if game_map is not None:
                try:
                    from ...utility.aura_utils import unit_within_range_of_unit
                    for rule in conditional_rules:
                        try:
                            rng = float(rule.get("range", 0) or 0)
                        except Exception:
                            rng = 0.0
                        if rng <= 0:
                            continue
                        if bool(rule.get("requires_not_attached")):
                            is_attached = bool(getattr(self, "attached_to", None))
                            if not is_attached:
                                leaders = list(getattr(self, "attached_leaders", []) or [])
                                is_attached = bool(leaders)
                            if is_attached:
                                continue
                        kw_phrase = str(rule.get("keywords") or "").strip()
                        kw_options = [kw_phrase]
                        try:
                            parsed = tuple(rule.get("keyword_options", ()) or ())
                            if parsed:
                                kw_options = [str(v).strip() for v in parsed if str(v).strip()]
                        except Exception:
                            kw_options = [kw_phrase]
                        requires_other = bool(rule.get("requires_other"))
                        exclude_lone_operative = bool(rule.get("exclude_lone_operative"))
                        for other in list(game_map.get_friendly_units(self)):
                            if other is None:
                                continue
                            if requires_other and other is self:
                                continue
                            if not getattr(other, "is_alive", lambda: True)():
                                continue
                            if exclude_lone_operative and _unit_mentions_lone_operative(other):
                                continue
                            if not any(unit_matches_keyword_phrase(other, option) for option in kw_options):
                                continue
                            if unit_within_range_of_unit(self, other, rng, use_attached_aggregate=True):
                                return True
                except Exception:
                    pass
        # LORD OF MURDER (datasheet rule, not an Aura keyworded ability):
        # While this model is within 3" of one or more friendly WORLD EATERS INFANTRY units,
        # this model has the Lone Operative ability.
        has_lord_of_murder = False
        try:
            for a in getattr(self, "possible_abilities", []) or []:
                nm = str(getattr(a, "name", "") or "")
                if nm.strip().lower() == "lord of murder":
                    has_lord_of_murder = True
                    break
        except Exception:
            has_lord_of_murder = False

        if has_lord_of_murder:
            game_map = None
            try:
                game_map = self.get_parent_army().player.game.map
            except Exception:
                game_map = None
            if game_map is not None:
                try:
                    from ...utility.aura_utils import unit_within_range_of_unit
                    for other in list(game_map.get_friendly_units(self)):
                        if other is self:
                            continue
                        if not getattr(other, "is_alive", lambda: True)():
                            continue
                        if (other.has_any_keyword("WORLD EATERS") and other.has_keyword("Infantry")):
                            if unit_within_range_of_unit(self, other, 3.0, use_attached_aggregate=True):
                                return True
                except Exception:
                    pass

        return bool(base_found)

    def ranged_targeting_restriction_specs(self) -> List[dict]:
        """
        Return specs for abilities that restrict ranged targeting to within a distance.

        Specs contain:
            - source: ability name
            - range: int (max distance for ranged targeting)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "ranged_targeting_restriction_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        def _normalize_segment(text: str) -> str:
            if not text:
                return ""
            norm = root._normalize_rules_text(text)
            norm = norm.replace("\u2019", "'").replace("\u0192?T", "'")
            norm = re.sub(r"'s\b", "s", norm, flags=re.IGNORECASE)
            norm = norm.lower()
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            return re.sub(r"\s+", " ", norm).strip()

        allowed_prefixes = (
            "this unit",
            "that unit",
            "this model s unit",
            "this models unit",
            "the bearer s unit",
            "the bearers unit",
            "models in this unit",
            "models in that unit",
            "models in the bearer s unit",
            "models in the bearers unit",
            "while this model is leading a unit",
            "while the bearer is leading a unit",
        )

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                segments = []
                try:
                    segments = unit._iter_conditioned_text_segments(text_src)
                except Exception:
                    segments = [text_src]
                for segment in segments:
                    if not segment:
                        continue
                    for clause in re.split(r"\band\b", segment, flags=re.IGNORECASE):
                        clause = str(clause or "").strip()
                        if not clause:
                            continue
                        normalized = _normalize_segment(clause)
                        if not normalized:
                            continue
                        if not any(normalized.startswith(prefix) for prefix in allowed_prefixes):
                            continue
                        m = unit._RANGED_TARGETING_RESTRICTION_RE.search(normalized)
                        if not m:
                            continue
                        raw = m.group("range") or m.group("range2") or ""
                        try:
                            rng = int(raw or 0)
                        except Exception:
                            rng = 0
                        if rng <= 0:
                            continue
                        source = str(name or "Ranged targeting restriction").strip() or "Ranged targeting restriction"
                        key = (source.lower(), int(rng))
                        if key in seen:
                            continue
                        seen.add(key)
                        specs.append({"source": source, "range": int(rng)})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def get_ranged_targeting_restriction(self, *, game_map=None) -> tuple[Optional[float], list[str]]:
        """
        Return the strictest ranged targeting distance restriction and sources, if any.

        Returns:
            (distance, sources) where distance is the max allowed distance (inches) for ranged targeting.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        best_dist: Optional[float] = None
        sources: list[str] = []

        def _consider(dist: float, src: str) -> None:
            nonlocal best_dist, sources
            if dist <= 0:
                return
            if best_dist is None or dist < best_dist:
                best_dist = float(dist)
                sources = [str(src or "").strip() or "Ranged targeting restriction"]
            elif best_dist == float(dist):
                src_name = str(src or "").strip() or "Ranged targeting restriction"
                if src_name not in sources:
                    sources.append(src_name)

        try:
            if root.has_lone_operative():
                _consider(12.0, "Lone Operative")
        except Exception:
            pass

        for spec in root.ranged_targeting_restriction_specs():
            try:
                dist = float(spec.get("range", 0) or 0)
            except Exception:
                dist = 0.0
            _consider(dist, spec.get("source", "Ranged targeting restriction"))

        try:
            from ...rules.shadow_form import target_unit_has_wreathed_in_shadows
            if target_unit_has_wreathed_in_shadows(root, game_map=game_map):
                _consider(18.0, "Wreathed in Shadows")
        except Exception:
            pass

        return best_dist, sources

