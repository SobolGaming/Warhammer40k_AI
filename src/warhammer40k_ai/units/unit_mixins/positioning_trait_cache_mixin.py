"""Threat, overwatch, and trait-cache helpers for Unit deployment/runtime queries."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class PositioningTraitCacheMixin:
    def get_overwatch_risk(self, charging_unit: 'Unit', game: 'Game') -> float:
        """Calculate the risk this unit poses in overwatch to a charging unit.
        
        Args:
            charging_unit (Unit): The unit attempting to charge
            game (Game): The game instance for distance calculations
            
        Returns:
            float: Risk value from 0.0 to 1.0, where higher values indicate more risk
        """
        # Base risk on our ranged threat level
        ranged_threat, _ = self.get_threat_level()
        
        # Modify based on distance (closer = more dangerous)
        distance = game.get_distance_between_units(charging_unit, self)
        distance_modifier = 1.0 / max(distance, 1.0)  # Avoid division by zero
        
        # Consider if we've already shot this round
        if self.round_state.shot_this_round:
            ranged_threat *= 0.5  # Reduced effectiveness if already shot
            
        # Consider remaining CP for stratagems
        army = self.get_parent_army()
        if army and army.player:
            cp_modifier = min(1.0, army.player.command_points / 3.0)  # Scale based on available CP
            ranged_threat *= (1.0 + cp_modifier)  # More CP = more potential threats
        
        return ranged_threat * distance_modifier


    def _get_cached_ability_trait_index(self) -> dict:
        """
        Return generation-scoped parsed ability trait index for this attached-unit root.

        The index is parse-once per structure generation and reused for high-frequency
        trait checks and pattern searches.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            root = self
        cache = getattr(root, "_ability_cache", None)
        if not isinstance(cache, dict):
            root._ability_cache = {}
            cache = root._ability_cache

        generation = int(getattr(root, "_ability_structure_generation", 0) or 0)
        cache_key = "ability_trait_index_v1"
        cached = cache.get(cache_key)
        if isinstance(cached, dict) and int(cached.get("generation", -1) or -1) == generation:
            return cached

        entries: list[tuple[str, str]] = []
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            if unit is None:
                continue
            # Unit-level abilities
            for ability in list(getattr(unit, "possible_abilities", []) or []):
                if isinstance(ability, str):
                    entries.append((ability, ability))
                    continue
                entries.append(
                    (
                        str(getattr(ability, "name", "") or ""),
                        str(getattr(ability, "description", "") or ""),
                    )
                )
            # Enhancement text
            enh = getattr(unit, "enhancement", None)
            if enh is not None:
                entries.append(
                    (
                        str(getattr(enh, "name", "") or ""),
                        str(getattr(enh, "description", "") or ""),
                    )
                )
            # Model-level ability objects
            for model in list(getattr(unit, "models", []) or []):
                abilities = getattr(model, "abilities", None)
                if not isinstance(abilities, dict):
                    continue
                for ability in abilities.values():
                    if isinstance(ability, str):
                        entries.append((ability, ability))
                        continue
                    entries.append(
                        (
                            str(getattr(ability, "name", "") or ""),
                            str(getattr(ability, "description", "") or ""),
                        )
                    )

        texts: list[str] = []
        seen: set[str] = set()
        for name, desc in entries:
            for raw in (name, desc):
                text_src = str(raw or "")
                if not text_src:
                    continue
                try:
                    cleaned = self._strip_eligibility_prefix(text_src)
                except Exception:
                    cleaned = text_src
                try:
                    normalized = self._normalize_rules_text(cleaned)
                except Exception:
                    normalized = str(cleaned or "")
                normalized = str(normalized or "").strip().lower()
                if not normalized:
                    continue
                if normalized in seen:
                    continue
                seen.add(normalized)
                texts.append(normalized)

        joined = "\n".join(texts)
        firing_deck_value = 0
        for text in texts:
            match = re.search(r"firing\s+deck\s*\(?(\d+)", str(text or ""), flags=re.IGNORECASE)
            if not match:
                continue
            try:
                firing_deck_value = max(firing_deck_value, int(match.group(1) or 0))
            except Exception:
                continue
        trait_flags = {
            "super_heavy_walker": bool(
                "super-heavy walker" in joined
                or "super-heavy war engine" in joined
                or "super heavy war engine" in joined
            ),
            "flip_belt": bool("flip belt" in joined),
            "kill_team": bool("kill team" in joined),
            "stealth": bool("stealth" in joined),
            "infiltrate": bool("infiltrators" in joined or "infiltrate" in joined),
            "deep_strike": bool("deep strike" in joined or "deepstrike" in joined),
            "firing_deck": bool("firing deck" in joined),
        }

        index = {
            "generation": generation,
            "texts": tuple(texts),
            "joined": joined,
            "trait_flags": trait_flags,
            "trait_values": {"firing_deck": int(firing_deck_value)},
            "pattern_hits": {},
            "pattern_values": {},
        }
        cache[cache_key] = index
        return index


    def _trait_flag(self, key: str, *, default: bool = False) -> bool:
        if not key:
            return bool(default)
        index = self._get_cached_ability_trait_index()
        trait_flags = index.get("trait_flags", {}) if isinstance(index, dict) else {}
        return bool(trait_flags.get(key, default))


    def _trait_value(self, key: str, *, default: int = 0) -> int:
        if not key:
            return int(default)
        index = self._get_cached_ability_trait_index()
        trait_values = index.get("trait_values", {}) if isinstance(index, dict) else {}
        try:
            return int(trait_values.get(key, default) or 0)
        except Exception:
            return int(default)


    def _find_ability_with_patterns(self, patterns: List[str], extract_value: bool = False, value_pattern: str = None) -> Tuple[bool, Optional[str]]:
        r"""
        Helper method to find abilities matching given patterns and optionally extract values.

        Args:
            patterns: List of patterns to search for (case-insensitive)
            extract_value: Whether to extract a value from the matched text
            value_pattern: Regex pattern to extract value (e.g., r'(\d+)' for numbers, r'(\d+|D\d+)' for dice)

        Returns:
            Tuple[bool, Optional[str]]: (found, extracted_value)
        """
        try:
            from ...utility.regex_hotspot_metrics import increment as _increment_regex_hotspot

            _increment_regex_hotspot("positioning_mixin:_find_ability_with_patterns")
        except Exception:
            pass

        pattern_lowers = tuple(
            str(pattern or "").strip().lower()
            for pattern in (patterns or [])
            if str(pattern or "").strip()
        )
        if not pattern_lowers:
            return False, None

        # Fast path: parse-once indexed lookup for known high-frequency traits.
        indexed_patterns = {
            "super-heavy walker",
            "super-heavy war engine",
            "super heavy war engine",
            "flip belt",
            "kill team",
            "firing deck",
        }
        can_use_index = all(pattern in indexed_patterns for pattern in pattern_lowers)
        if can_use_index and (not extract_value or pattern_lowers == ("firing deck",)):
            try:
                index = self._get_cached_ability_trait_index()
                pattern_hits = index.get("pattern_hits", {})
                pattern_values = index.get("pattern_values", {})
                index_key = (pattern_lowers, bool(extract_value), str(value_pattern or ""))
                if index_key in pattern_hits:
                    return bool(pattern_hits.get(index_key)), pattern_values.get(index_key)

                texts = tuple(index.get("texts", ()) or ())
                found = False
                value = None
                if extract_value and value_pattern:
                    matchers = tuple(
                        re.compile(rf"{re.escape(pattern)}\s*\(?{value_pattern}")
                        for pattern in pattern_lowers
                    )
                else:
                    matchers = tuple()
                for text in texts:
                    low = str(text or "").lower()
                    for idx, pattern in enumerate(pattern_lowers):
                        if pattern not in low:
                            continue
                        found = True
                        if not matchers:
                            break
                        match = matchers[idx].search(low)
                        if match:
                            value = match.group(1)
                            break
                    if found and (not matchers or value is not None):
                        break

                # Only commit extract-value indexed hits when value was parsed.
                if found and extract_value and value is None:
                    pass
                else:
                    pattern_hits[index_key] = bool(found)
                    if found and value is not None:
                        pattern_values[index_key] = value
                    elif index_key in pattern_values:
                        pattern_values.pop(index_key, None)
                    index["pattern_hits"] = pattern_hits
                    index["pattern_values"] = pattern_values
                    return bool(found), value
            except Exception:
                pass

        value_matchers: tuple[tuple[str, "re.Pattern"], ...] = tuple()
        if extract_value and value_pattern:
            value_matchers = tuple(
                (pattern, re.compile(rf"{re.escape(pattern)}\s*\(?{value_pattern}"))
                for pattern in pattern_lowers
            )

        def _scan_text(text: str, *, context: str, parameter_text: Optional[str] = None) -> Tuple[bool, Optional[str]]:
            low = str(text or "").lower()
            for idx, pattern in enumerate(pattern_lowers):
                if pattern not in low:
                    continue
                if not value_matchers:
                    return True, None
                matcher = value_matchers[idx][1]
                match = matcher.search(low)
                if match:
                    return True, match.group(1)
                if parameter_text:
                    param_match = re.search(value_pattern, str(parameter_text))
                    if param_match:
                        return True, param_match.group(1)
                raise ValueError(
                    f"{pattern} ability found in {context} but could not extract value for unit '{self.name}'"
                )
            return False, None

        # Check keywords first
        for keyword in (self.keywords or []):
            found, value = _scan_text(str(keyword), context=f"keyword '{keyword}'")
            if found:
                return True, value

        # Check unit-level abilities (possible_abilities)
        for ability in self._iter_active_possible_abilities():
            if isinstance(ability, str):
                for segment in self._iter_conditioned_text_segments(ability):
                    found, value = _scan_text(segment, context=f"ability string '{ability}'")
                    if found:
                        return True, value
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, "name") and ability.name:
                    name_text = str(ability.name)
                    name_low = name_text.lower()
                    ability_name_matched = any(pattern in name_low for pattern in pattern_lowers)
                    if ability_name_matched:
                        parameter_text = str(getattr(ability, "parameter", "") or "")
                        found, value = _scan_text(
                            name_text,
                            context=f"ability name '{ability.name}'",
                            parameter_text=parameter_text,
                        )
                        if found:
                            return True, value

                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, "description") and ability.description:
                    for segment in self._iter_conditioned_text_segments(ability.description):
                        found, value = _scan_text(
                            segment,
                            context=f"ability description '{ability.description}'",
                        )
                        if found:
                            return True, value

        # Check model-level abilities
        for ability in self.abilities:
            try:
                if not self._ability_is_active(ability):
                    continue
            except Exception:
                pass
            if isinstance(ability, str):
                for segment in self._iter_conditioned_text_segments(ability):
                    found, value = _scan_text(segment, context=f"model ability string '{ability}'")
                    if found:
                        return True, value
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, "name") and ability.name:
                    name_text = str(ability.name)
                    name_low = name_text.lower()
                    ability_name_matched = any(pattern in name_low for pattern in pattern_lowers)
                    if ability_name_matched:
                        parameter_text = str(getattr(ability, "parameter", "") or "")
                        found, value = _scan_text(
                            name_text,
                            context=f"model ability name '{ability.name}'",
                            parameter_text=parameter_text,
                        )
                        if found:
                            return True, value

                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, "description") and ability.description:
                    for segment in self._iter_conditioned_text_segments(ability.description):
                        found, value = _scan_text(
                            segment,
                            context=f"model ability description '{ability.description}'",
                        )
                        if found:
                            return True, value

        return False, None


    def has_deep_strike(self) -> bool:
        """Check if the unit has Deep Strike ability."""
        # Use cached result if available
        if 'deep_strike' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['deep_strike']

        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                if (
                    sr.get("bearer_unit_deep_strike")
                    or sr.get("realm_of_chaos_temp_deep_strike")
                    or sr.get("imperialis_fleet_combat_landers_deep_strike")
                ):
                    found = True
                elif sr.get("attached_unit_bodyguard_leader_deep_strike") and bool(
                    getattr(self, "is_attached_leader", False)
                ):
                    found = True
                elif sr.get("enhancement_warp_borne_stalker"):
                    bearer_id = str(
                        sr.get("enhancement_warp_borne_stalker_bearer_model_id", "")
                        or sr.get("enhancement_bearer_model_id", "")
                        or ""
                    ).strip()
                    if not bearer_id:
                        found = True
                    else:
                        for model in list(getattr(self, "models", []) or []):
                            model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "")
                            if model_id != bearer_id:
                                continue
                            alive_attr = getattr(model, "is_alive", True)
                            found = bool(alive_attr() if callable(alive_attr) else alive_attr)
                            break
                elif sr.get("cloudstrike_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("cloudstrike_turn_owner", "") or "")
                    turn = int(sr.get("cloudstrike_turn", 0) or 0)
                    exp_phase = str(sr.get("cloudstrike_expires_phase", "") or "").strip().upper()
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
                        elif exp_phase and cur_phase and exp_phase != cur_phase:
                            found = False
                elif sr.get("death_guard_hidden_amongst_the_dead_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("death_guard_hidden_amongst_the_dead_turn_owner", "") or "")
                    turn = int(sr.get("death_guard_hidden_amongst_the_dead_turn", 0) or 0)
                    exp_phase = str(sr.get("death_guard_hidden_amongst_the_dead_expires_phase", "") or "").strip().upper()
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
                        elif exp_phase and cur_phase and exp_phase != cur_phase:
                            found = False
                elif sr.get("dread_talons_screaming_descent_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("dread_talons_screaming_descent_turn_owner", "") or "")
                    turn = int(sr.get("dread_talons_screaming_descent_turn", 0) or 0)
                    exp_phase = str(sr.get("dread_talons_screaming_descent_phase", "") or "").strip().upper()
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
                        elif exp_phase and cur_phase and exp_phase != cur_phase:
                            found = False
                elif sr.get("dark_apparitions_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("dark_apparitions_turn_owner", "") or "")
                    exp_phase = str(sr.get("dark_apparitions_expires_phase", "") or "").strip().upper()
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif exp_phase and cur_phase and exp_phase != cur_phase:
                            found = False
                elif sr.get("thousand_sons_through_the_veil_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("thousand_sons_through_the_veil_turn_owner", "") or "")
                    turn = int(sr.get("thousand_sons_through_the_veil_turn", 0) or 0)
                    exp_phase = str(sr.get("thousand_sons_through_the_veil_expires_phase", "") or "").strip().upper()
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
                        elif exp_phase and cur_phase and exp_phase != cur_phase:
                            found = False
                elif sr.get("thousand_sons_twisted_mirage_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("thousand_sons_twisted_mirage_turn_owner", "") or "")
                    turn = int(sr.get("thousand_sons_twisted_mirage_turn", 0) or 0)
                    exp_phase = str(sr.get("thousand_sons_twisted_mirage_expires_phase", "") or "").strip().upper()
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
                        elif exp_phase and cur_phase and exp_phase != cur_phase:
                            found = False
                elif sr.get("midgame_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("midgame_temp_deep_strike_turn_owner", "") or "")
                    turn = int(sr.get("midgame_temp_deep_strike_must_arrive_turn", 0) or 0)
                    if game is not None:
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
                elif sr.get("umbralefic_crystal_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("umbralefic_crystal_must_arrive_turn_owner", "") or "")
                    turn = int(sr.get("umbralefic_crystal_must_arrive_turn", 0) or 0)
                    if game is not None:
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
        except Exception:
            pass
        if not found:
            try:
                if self._disciple_of_khorne_active():
                    found = True
            except Exception:
                found = False
        if not found:
            try:
                if self._fury_from_the_delve_active():
                    found = True
            except Exception:
                found = False
        if not found:
            try:
                if self._root_has_attached_unit_deep_strike_grant():
                    found = True
            except Exception:
                found = False
        if not found:
            if (
                self._first_prince_of_chaos_active()
                and self._is_chaos_undivided()
                and self.has_any_keyword("HERETIC ASTARTES")
            ):
                found = True
            else:
                found, _ = self._find_ability_with_patterns(["deep strike", "deepstrike"])

        # Attached units can only Deep Strike if every model has Deep Strike.
        # If an active rule grants Deep Strike to "models in this/that unit",
        # the grant applies across the attached unit and this per-member check is skipped.
        try:
            root_grants_attached_deep_strike = False
            if found:
                try:
                    root_grants_attached_deep_strike = bool(self._root_has_attached_unit_deep_strike_grant())
                except Exception:
                    root_grants_attached_deep_strike = False
            if (
                found
                and not root_grants_attached_deep_strike
                and (not bool(getattr(self, "is_leader", False)) or getattr(self, "attached_to", None) is None)
            ):
                root = self.get_attached_unit_root()
                leaders = list(getattr(root, "attached_leaders", []) or [])
                for leader in leaders:
                    try:
                        if not leader.has_deep_strike():
                            found = False
                            break
                    except Exception:
                        found = False
                        break
        except Exception:
            pass
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['deep_strike'] = found
        
        return found
