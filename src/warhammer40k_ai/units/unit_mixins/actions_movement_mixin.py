"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class ActionsMovementMixin:
    def apply_command_abilities(self) -> None:
        """Applies command abilities during the Command phase."""
        for ability in self.abilities.get('command_phase', []):
            ability.activate(self)

    ###########################################################################
    ### Command
    ###########################################################################

    def do_command_action(self, game_map: 'Map', current_turn: int = 1) -> bool:
        """Executes the command action for the unit.
        
        Args:
            game_map: The game map
            current_turn: The current battle round number
        """
        self.initialize_round()
        # Battle-shock expires at the start of *your* next Command phase.
        # Clear Battle-shock before running the step's Battle-shock tests.
        self.clear_battle_shock()

        # Do Battle Shock Test for appropriate units
        if (not self.is_alive()):
            return True
        # If forced to test for being Below Starting Strength, do not also test for being Below Half-strength
        # unless explicitly stated.
        if self.is_below_starting_strength():
            logger.info(f"{self.name} is below starting strength - taking Battle-Shock test")
            self.take_battle_shock_test(current_turn)
        elif self.is_below_half_strength():
            logger.info(f"{self.name} is below half strength - taking Battle-Shock test")
            self.take_battle_shock_test(current_turn)

        return True

    ###########################################################################
    ### Movement
    ###########################################################################

    def do_move_action(self, action: int, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        """Executes the given movement action."""
        return self._execute_action(action, destination, game_map)

    def get_engagement_state(self, game_map: 'Map') -> int:
        """Determine if the unit is in engagement range of any enemy model."""
        enemy_units = game_map.get_enemy_units(self)

        engaged = False
        engaged_non_aircraft = False
        for enemy_unit in enemy_units:
            if not enemy_unit.is_alive():
                continue
            if game_map.is_within_engagement_range(self, enemy_unit):
                engaged = True
                if not bool(getattr(enemy_unit, "is_aircraft", False)):
                    engaged_non_aircraft = True
                    break

        self._engaged_only_by_aircraft = bool(engaged and not engaged_non_aircraft)

        return MovementState.IN_ENGAGEMENT_RANGE if engaged else MovementState.OUT_OF_ENGAGEMENT_RANGE

    def get_available_move_actions(self, state: int) -> List[int]:
        """Get the list of available actions based on the current state."""
        try:
            state_enum = state if isinstance(state, MovementState) else MovementState(state)
        except Exception:
            state_enum = state

        # AIRCRAFT: only Normal moves allowed (no Advance/Fall Back/Remain Stationary).
        if bool(getattr(self, "is_aircraft", False)):
            return [MovementAction.MOVE.value]

        engaged_only_by_aircraft = bool(getattr(self, "_engaged_only_by_aircraft", False))
        if state_enum == MovementState.IN_ENGAGEMENT_RANGE:
            if engaged_only_by_aircraft:
                return [
                    MovementAction.REMAIN_STATIONARY.value,
                    MovementAction.MOVE.value,
                    MovementAction.ADVANCE.value,
                    MovementAction.FALL_BACK.value,
                ]
            return [MovementAction.REMAIN_STATIONARY.value, MovementAction.FALL_BACK.value]
        return [MovementAction.REMAIN_STATIONARY.value, MovementAction.MOVE.value, MovementAction.ADVANCE.value]

    def _execute_action(self, action: int, destination: Tuple[float, float, float], game_map: 'Map', advance_roll: int = None) -> bool:
        """Execute a movement action for the unit."""
        # Transport disembark restrictions: if you disembarked from a moved/destroyed transport,
        # you count as having made a Normal move and cannot move further this turn.
        if getattr(self.round_state, "disembarked_from_moved_transport", False) or getattr(self.round_state, "disembarked_from_destroyed_transport", False):
            if action in (MovementAction.MOVE.value, MovementAction.ADVANCE.value, MovementAction.FALL_BACK.value):
                logger.info(f"{self.name} cannot move further after disembarking this turn")
                return False

        # AIRCRAFT: only Normal moves allowed.
        if bool(getattr(self, "is_aircraft", False)):
            if action in (MovementAction.REMAIN_STATIONARY.value, MovementAction.ADVANCE.value, MovementAction.FALL_BACK.value):
                logger.info(f"{self.name} cannot {('remain stationary' if action == MovementAction.REMAIN_STATIONARY.value else 'advance' if action == MovementAction.ADVANCE.value else 'fall back')} (AIRCRAFT)")
                return False

        # If the unit is currently performing a mission Action and moves (excluding pile-in/consolidation handled elsewhere), cancel the Action
        def _cancel_action_due_to_move():
            if getattr(self.round_state, 'performing_action_name', None):
                logger.info(f"{self.name} moved; cancelling Action '{self.round_state.performing_action_name}'")
                self.round_state.performing_action_name = None
                self.round_state.action_completes_turn = None
                self.round_state.action_locked_until_turn_end = False

        success = False
        # Resolve player/game for events
        _player = getattr(self.get_parent_army(), 'player', None)
        _game = getattr(_player, 'game', None) if _player else None
        def _publish(evt: str, **kwargs):
            try:
                if _game and hasattr(_game, 'event_system'):
                    _game.event_system.publish(evt, **kwargs)
            except Exception:
                pass
        # AELDARI: Battle Focus move-triggered manoeuvres (Swift/Flitting/Star Engines)
        if action in (MovementAction.MOVE.value, MovementAction.ADVANCE.value, MovementAction.FALL_BACK.value):
            try:
                army = self.get_parent_army()
                mgr = getattr(army, "battle_focus", None) if army is not None else None
                if mgr is not None:
                    act_name = ('advance' if action == MovementAction.ADVANCE.value else 'fall_back' if action == MovementAction.FALL_BACK.value else 'move')
                    mgr.maybe_trigger_move_maneuvers(self, act_name, _game)
            except Exception:
                pass

        # Overwatch trigger: movement start
        if action in (MovementAction.MOVE.value, MovementAction.ADVANCE.value, MovementAction.FALL_BACK.value):
            _publish("unit_move_started", unit=self, action=('advance' if action == MovementAction.ADVANCE.value else 'fall_back' if action == MovementAction.FALL_BACK.value else 'move'))
        if action == MovementAction.REMAIN_STATIONARY.value:
            logger.info(f"{self.name} remains stationary")
            success = self.remain_stationary()
        elif action == MovementAction.MOVE.value:
            logger.info(f"{self.name} moves to {destination}")
            success = self.move(destination, game_map)
            if success:
                _cancel_action_due_to_move()
        elif action == MovementAction.ADVANCE.value:
            logger.info(f"{self.name} advances to {destination}")
            success = self.advance(destination, game_map)
            if success:
                _cancel_action_due_to_move()
        elif action == MovementAction.FALL_BACK.value:
            logger.info(f"{self.name} falls back")
            # Provide an empty path list for fall back action
            success = self.fall_back(destination, [], game_map)
            if success:
                _cancel_action_due_to_move()
        else:
            raise ValueError(f"Invalid action: {action}")
        
        # Mark unit as having moved this round if action was successful
        # AND set remained_stationary_this_round to False if the unit actually moved
        if success:
            self.round_state.moved_this_round = True
            # If the unit performed any movement action (not remain stationary), 
            # it did not remain stationary this round
            if action != MovementAction.REMAIN_STATIONARY.value:
                self.round_state.remained_stationary_this_round = False
            # Overwatch trigger: movement end
            if action in (MovementAction.MOVE.value, MovementAction.ADVANCE.value, MovementAction.FALL_BACK.value):
                _publish("unit_move_ended", unit=self, action=('advance' if action == MovementAction.ADVANCE.value else 'fall_back' if action == MovementAction.FALL_BACK.value else 'move'))
        
        return success

    def remain_stationary(self) -> bool:
        if bool(getattr(self, "is_aircraft", False)):
            logger.info(f"{self.name} cannot Remain Stationary (AIRCRAFT)")
            return False
        # Unit explicitly chose to remain stationary, so mark it as such
        self.round_state.remained_stationary_this_round = True
        return True

    # ---------------- Ability helpers (best-effort parsing) ----------------
    _LEADING_ABILITY_PREFIX_RE = re.compile(
        r"^\W*while (?:this (?:model|unit)|(?:the )?bearer) is leading(?:s)?(?: a)?(?: [^.,;:]+?)? unit\b",
        re.IGNORECASE,
    )
    _LEADING_ABILITY_RE = re.compile(
        r"\bwhile (?:this (?:model|unit)|(?:the )?bearer) is leading(?:s)?(?: a)?(?: [^.,;:]+?)? unit\b",
        re.IGNORECASE,
    )
    _NOT_LEADING_ABILITY_RE = re.compile(r"\bif this (?:model|unit) is not leading a unit\b", re.IGNORECASE)
    _LEADING_SPECIFIC_UNIT_RE = re.compile(
        r"\b(?:while|if)\s+(?:this model|this unit|the bearer)\s+is\s+leading(?:s)?\s+an?\s+(?P<unit>[^.,;:]+?)\s+unit\b",
        re.IGNORECASE,
    )
    _ATTACHED_SPECIFIC_UNIT_RE = re.compile(
        r"\bif\s+(?:(?:this model|this unit|the bearer)\s+is\s+)?attached\s+to\s+an?\s+(?P<unit>[^.,;:]+?)\s+unit\b",
        re.IGNORECASE,
    )
    _LED_BY_MODEL_RE = re.compile(
        r"\b(?:while|if)\s+an?\s+(?P<model>[^.,;:]+?)\s+model\s+is\s+leading\s+(?:this|that)\s+unit\b",
        re.IGNORECASE,
    )
    _SEGMENT_SPLIT_RE = re.compile(r"[.;]\s*")
    _COND_SEGMENT_ALWAYS = "always"
    _COND_SEGMENT_LEADING_SPECIFIC = "leading_specific_unit"
    _COND_SEGMENT_ATTACHED_SPECIFIC = "attached_specific_unit"

    @staticmethod
    def _normalize_ascii_alnum_space(value: str) -> str:
        """Normalize text to lowercase ASCII alnum tokens separated by single spaces."""
        text = str(value or "").lower()
        if not text:
            return ""
        text = text.replace("\u2019", "'").replace("\u0192?T", "'")
        out_chars: list[str] = []
        prev_space = True
        for ch in text:
            is_ascii_alnum = ("a" <= ch <= "z") or ("0" <= ch <= "9")
            if is_ascii_alnum:
                out_chars.append(ch)
                prev_space = False
                continue
            if not prev_space:
                out_chars.append(" ")
                prev_space = True
        if out_chars and out_chars[-1] == " ":
            out_chars.pop()
        return "".join(out_chars)

    @staticmethod
    def _ability_name_and_description(ability) -> tuple[str, str]:
        if isinstance(ability, str):
            return "", str(ability or "")
        return (
            str(getattr(ability, "name", "") or ""),
            str(getattr(ability, "description", "") or ""),
        )

    @classmethod
    @lru_cache(maxsize=4096)
    def _parse_ability_condition_metadata(
        cls,
        normalized_text: str,
    ) -> tuple[bool, bool, tuple[str, ...], tuple[str, ...]]:
        """
        Parse ability condition metadata from normalized text.

        This parser is pure and safe to cache globally by text.
        """
        text = str(normalized_text or "")
        if not text:
            return False, False, tuple(), tuple()

        requires_leading = bool(cls._LEADING_ABILITY_RE.search(text))
        requires_not_leading = bool(cls._NOT_LEADING_ABILITY_RE.search(text))

        leading_specific_units: list[str] = []
        for match in cls._LEADING_SPECIFIC_UNIT_RE.finditer(text):
            phrase = str(match.group("unit") or "").strip()
            if phrase:
                leading_specific_units.append(phrase)

        led_by_models: list[str] = []
        for match in cls._LED_BY_MODEL_RE.finditer(text):
            phrase = str(match.group("model") or "").strip()
            if phrase:
                led_by_models.append(phrase)

        return (
            requires_leading,
            requires_not_leading,
            tuple(leading_specific_units),
            tuple(led_by_models),
        )

    @classmethod
    @lru_cache(maxsize=4096)
    def _parse_conditioned_text_segment_guards(
        cls,
        normalized_text: str,
    ) -> tuple[tuple[str, str, str], ...]:
        """
        Parse sentence-like segments with unit-condition guards.

        Output tuple items are `(segment_text, guard_kind, phrase)`.
        This parser is pure and safe to cache globally by text.
        """
        text = str(normalized_text or "")
        if not text:
            return tuple()
        if not cls._LEADING_SPECIFIC_UNIT_RE.search(text) and not cls._ATTACHED_SPECIFIC_UNIT_RE.search(text):
            return ((text, cls._COND_SEGMENT_ALWAYS, ""),)

        parsed: list[tuple[str, str, str]] = []
        for raw in cls._SEGMENT_SPLIT_RE.split(text):
            part = str(raw or "").strip()
            if not part:
                continue
            m_leading = cls._LEADING_SPECIFIC_UNIT_RE.search(part)
            if m_leading:
                phrase = str(m_leading.group("unit") or "").strip()
                parsed.append((part, cls._COND_SEGMENT_LEADING_SPECIFIC, phrase))
                continue
            m_attached = cls._ATTACHED_SPECIFIC_UNIT_RE.search(part)
            if m_attached:
                phrase = str(m_attached.group("unit") or "").strip()
                parsed.append((part, cls._COND_SEGMENT_ATTACHED_SPECIFIC, phrase))
                continue
            parsed.append((part, cls._COND_SEGMENT_ALWAYS, ""))
        return tuple(parsed)

    def _ability_leading_specific_units(self, ability) -> list[str]:
        """Return specific unit phrases for abilities gated by leading a named unit."""
        name, desc = self._ability_name_and_description(ability)
        text = self._strip_eligibility_prefix(f"{name} {desc}".strip())
        text = self._normalize_rules_text(text)
        if not text:
            return []
        meta = self._parse_ability_condition_metadata(text)
        return list(meta[2])

    def _ability_led_by_model_phrases(self, ability) -> list[str]:
        """
        Return model-name/keyword phrases for abilities gated by
        "while a/an <model> model is leading this unit".
        """
        name, desc = self._ability_name_and_description(ability)
        text = self._strip_eligibility_prefix(f"{name} {desc}".strip())
        text = self._normalize_rules_text(text)
        if not text:
            return []
        meta = self._parse_ability_condition_metadata(text)
        return list(meta[3])

    def _attached_leader_matches_phrase(self, phrase: str) -> bool:
        if not str(phrase or "").strip():
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        leaders = list(getattr(root, "attached_leaders", []) or [])
        if not leaders:
            return False

        phrase_name = self._normalize_attached_unit_name(phrase)
        for leader in leaders:
            if leader is None:
                continue
            try:
                if self._unit_matches_keyword_phrase(leader, phrase, use_effective=False):
                    return True
            except Exception:
                pass
            try:
                leader_name = self._normalize_attached_unit_name(getattr(leader, "name", ""))
                if phrase_name and leader_name and (phrase_name in leader_name or leader_name in phrase_name):
                    return True
            except Exception:
                pass
            try:
                if hasattr(leader, "_unit_contains_model_named") and leader._unit_contains_model_named(phrase):
                    return True
            except Exception:
                pass
        return False

    def _attached_unit_matches_phrase(self, phrase: str) -> bool:
        bodyguard = getattr(self, "attached_to", None)
        if bodyguard is None:
            return False
        try:
            if self._unit_matches_keyword_phrase(bodyguard, phrase, use_effective=False):
                return True
        except Exception:
            pass
        try:
            bodyguard_name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
            phrase_name = self._normalize_attached_unit_name(phrase)
            if bodyguard_name and bodyguard_name == phrase_name:
                return True
        except Exception:
            pass
        return False

    def _iter_conditioned_text_segments(self, text: str) -> list[str]:
        """
        Split ability text into sentence-like segments and filter clauses gated
        by leading a specific unit.
        """
        cleaned = self._strip_eligibility_prefix(text or "")
        cleaned = self._normalize_rules_text(cleaned)
        if not cleaned:
            return []
        parsed_segments = self._parse_conditioned_text_segment_guards(cleaned)
        if not parsed_segments:
            return []
        segments: list[str] = []
        for part, guard_kind, phrase in parsed_segments:
            if guard_kind == self._COND_SEGMENT_LEADING_SPECIFIC:
                if phrase and self._attached_unit_matches_phrase(phrase):
                    segments.append(part)
                continue
            if guard_kind == self._COND_SEGMENT_ATTACHED_SPECIFIC:
                if phrase and self._attached_unit_matches_phrase(phrase):
                    segments.append(part)
                    continue
                low = part.lower().replace("\u2019", "'").replace("\u0192?T", "'")
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict):
                    if (
                        sr.get("attached_possessed_formation_bonus")
                        and "attached to a world eaters possessed unit" in low
                    ):
                        segments.append(part)
                        continue
                    if (
                        sr.get("attached_battleline_infiltrators_scouts")
                        and "attached to" in low
                        and "battleline" in low
                        and ("infiltrators" in low or "scout" in low)
                    ):
                        segments.append(part)
            else:
                segments.append(part)
        return segments

    def _ability_requires_leading(self, ability) -> bool:
        """Return True if the ability text is gated by 'While this model is leading a unit'."""
        _, desc = self._ability_name_and_description(ability)
        desc = self._strip_eligibility_prefix(desc)
        text = self._normalize_rules_text(desc)
        if not text:
            return False
        return bool(self._parse_ability_condition_metadata(text)[0])

    def _ability_requires_not_leading(self, ability) -> bool:
        """Return True if the ability text requires the model to NOT be leading a unit."""
        _, desc = self._ability_name_and_description(ability)
        desc = self._strip_eligibility_prefix(desc)
        text = self._normalize_rules_text(desc)
        if not text:
            return False
        return bool(self._parse_ability_condition_metadata(text)[1])

    def _ability_is_active(self, ability) -> bool:
        """Return True if the ability is currently active for this unit."""
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict):
            disabled = list(sr.get("disabled_ability_names", []) or [])
            if disabled:
                if isinstance(ability, str):
                    name = ability
                else:
                    name = getattr(ability, "name", "") or ""
                norm_name = self._normalize_ascii_alnum_space(name)
                disabled_set = {
                    self._normalize_ascii_alnum_space(item)
                    for item in disabled
                }
                if norm_name and norm_name in disabled_set:
                    return False

        led_by_model_phrases = self._ability_led_by_model_phrases(ability)
        if led_by_model_phrases:
            if not any(self._attached_leader_matches_phrase(phrase) for phrase in led_by_model_phrases):
                return False
        if self._ability_requires_leading(ability):
            # Only enforce leading attachment when this unit is actually a Leader datasheet.
            if bool(getattr(self, "is_leader", False)) and not bool(getattr(self, "is_attached_leader", False)):
                return False
            if bool(getattr(self, "is_leader", False)):
                specific_units = self._ability_leading_specific_units(ability)
                if specific_units:
                    if not any(self._attached_unit_matches_phrase(phrase) for phrase in specific_units):
                        return False
        elif self._ability_requires_not_leading(ability):
            if bool(getattr(self, "is_attached_leader", False)):
                return False
        try:
            if self._ability_attached_possessed_formation_bonus_distance(ability) is not None:
                sr = getattr(self, "special_rules", None)
                return bool(isinstance(sr, dict) and sr.get("attached_possessed_formation_bonus"))
        except Exception:
            pass
        try:
            if self._ability_attached_battleline_infiltrators_scouts(ability) is not None:
                sr = getattr(self, "special_rules", None)
                return bool(isinstance(sr, dict) and sr.get("attached_battleline_infiltrators_scouts"))
        except Exception:
            pass
        try:
            if self._ability_attached_unit_bodyguard_leader_scouts(ability) is not None:
                return False
        except Exception:
            pass
        try:
            from ...rules.wrathful_presence import ability_name_to_key, unit_has_active_wrathful_presence
            name = ability if isinstance(ability, str) else getattr(ability, "name", "")
            key = ability_name_to_key(name)
            if key:
                return bool(unit_has_active_wrathful_presence(self, key))
        except Exception:
            pass
        try:
            from ...rules.daemon_primarch_slaanesh import ability_name_to_key, unit_has_active_daemon_primarch
            name = ability if isinstance(ability, str) else getattr(ability, "name", "")
            key = ability_name_to_key(name)
            if key:
                return bool(unit_has_active_daemon_primarch(self, key))
        except Exception:
            pass
        try:
            from ...rules.csm_warmaster import (
                ability_name_to_key,
                unit_has_active_warmaster,
                unit_has_warmaster_ability,
            )
            name = ability if isinstance(ability, str) else getattr(ability, "name", "")
            key = ability_name_to_key(name)
            if key and unit_has_warmaster_ability(self):
                return bool(unit_has_active_warmaster(self, key))
        except Exception:
            pass
        try:
            from ...rules.thousand_sons_crimson_king import (
                ability_name_to_key,
                unit_has_active_crimson_king,
                unit_has_crimson_king_sub_ability,
            )
            name = ability if isinstance(ability, str) else getattr(ability, "name", "")
            key = ability_name_to_key(name)
            if key and unit_has_crimson_king_sub_ability(self):
                return bool(unit_has_active_crimson_king(self, key))
        except Exception:
            pass
        try:
            from ...rules.necrons_voice_of_triarch import (
                ability_name_to_key,
                unit_has_active_voice_of_triarch,
                unit_has_voice_of_triarch_ability,
            )
            name = ability if isinstance(ability, str) else getattr(ability, "name", "")
            key = ability_name_to_key(name)
            if key and unit_has_voice_of_triarch_ability(self):
                return bool(unit_has_active_voice_of_triarch(self, key))
        except Exception:
            pass

        # Power from Pain: pain abilities only apply while the unit is Empowered.
        try:
            name = ""
            if isinstance(ability, str):
                name = ability
            else:
                name = getattr(ability, "name", "") or ""
            if "(pain)" in str(name or "").lower():
                sr = getattr(self, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("pain_empowered")):
                    return False
        except Exception:
            pass

        # Wargear abilities only apply if the wargear is equipped.
        try:
            atype = str(getattr(ability, "type", "") or "").lower()
            if "wargear" in atype:
                return self._has_wargear_named(getattr(ability, "name", ""))
        except Exception:
            pass
        return True

    def _ability_attached_possessed_formation_bonus_distance(self, ability) -> Optional[int]:
        """
        Return the Scouts distance for the "attached to WORLD EATERS POSSESSED" formation bonus ability.
        """
        desc = ""
        name = ""
        try:
            if isinstance(ability, str):
                desc = ability
            else:
                name = str(getattr(ability, "name", "") or "")
                desc = str(getattr(ability, "description", "") or "")
        except Exception:
            desc = ""
        text = self._normalize_rules_text(f"{name} {desc}")
        if not text:
            return None
        low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
        if "declare battle formations" not in low:
            return None
        if "attached to a world eaters possessed unit" not in low:
            return None
        if "deep strike" not in low or "scout" not in low:
            return None
        m = re.search(r"scouts?\s*(\d+)", low)
        if not m:
            return None
        return int(m.group(1))

    def _ability_attached_battleline_infiltrators_scouts(self, ability) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "If this model is attached to an EMPEROR'S CHILDREN BATTLELINE unit during the Declare Battle Formations step,
        this model has the Infiltrators and Scouts 6\" abilities."
        """
        desc = ""
        name = ""
        try:
            if isinstance(ability, str):
                desc = ability
            else:
                name = str(getattr(ability, "name", "") or "")
                desc = str(getattr(ability, "description", "") or "")
        except Exception:
            desc = ""
        text = self._normalize_rules_text(f"{name} {desc}")
        if not text:
            return None
        low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
        if "declare battle formations" not in low:
            return None
        if "attached to" not in low or "battleline" not in low:
            return None
        if "infiltrators" not in low or "scout" not in low:
            return None
        m = re.search(r"attached to an? (?P<keywords>.+?) unit", low)
        if not m:
            return None
        kw_phrase = str(m.group("keywords") or "").strip()
        if not kw_phrase:
            return None
        m = re.search(r"scouts?\s*(\d+)", low)
        if not m:
            return None
        try:
            dist = int(m.group(1))
        except Exception:
            return None
        if dist <= 0:
            return None
        return {"keywords": kw_phrase, "scout_distance": int(dist)}

    def _apply_attached_possessed_formation_bonus(self, bodyguard: 'Unit') -> None:
        """Apply the WORLD EATERS POSSESSED formation bonus for Leaders like LORD OF THE EIGHTBOUND."""
        if bodyguard is None:
            return
        dist = None
        for ab in (getattr(self, "possible_abilities", []) or []):
            dist = self._ability_attached_possessed_formation_bonus_distance(ab)
            if dist is not None:
                break
        if dist is None:
            return
        try:
            if not bodyguard.has_any_keyword_local("WORLD EATERS"):
                return
            if not bodyguard.has_any_keyword_local("POSSESSED"):
                return
        except Exception:
            return
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if not sr.get("attached_possessed_formation_bonus"):
            sr["attached_possessed_formation_bonus"] = True
            sr["attached_possessed_formation_scout_distance"] = int(dist)
            self.special_rules = sr

    def _apply_attached_battleline_infiltrators_scouts(self, bodyguard: 'Unit') -> None:
        """Apply battle formation bonuses that grant Infiltrators + Scouts to the Leader model."""
        if bodyguard is None:
            return
        rule = None
        for ab in (getattr(self, "possible_abilities", []) or []):
            rule = self._ability_attached_battleline_infiltrators_scouts(ab)
            if rule is not None:
                break
        if rule is None:
            return
        try:
            if not self._unit_matches_keyword_phrase(bodyguard, rule.get("keywords", ""), use_effective=False):
                return
        except Exception:
            return
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if not sr.get("attached_battleline_infiltrators_scouts"):
            sr["attached_battleline_infiltrators_scouts"] = True
            sr["attached_battleline_infiltrators_scout_distance"] = int(rule.get("scout_distance", 0) or 0)
            self.special_rules = sr

    def _ability_attached_unit_bodyguard_leader_scouts(self, ability) -> Optional[dict]:
        """
        Return rule info for bodyguard ATTACHED UNIT clauses like:
        "If a MINISTORUM PRIEST or INQUISITOR from your army is attached to this unit
        during the Declare Battle Formations step, that model gains the Scouts 6\" ability."
        """
        desc = ""
        name = ""
        try:
            if isinstance(ability, str):
                desc = ability
            else:
                name = str(getattr(ability, "name", "") or "")
                desc = str(getattr(ability, "description", "") or "")
        except Exception:
            desc = ""
        text = self._normalize_rules_text(f"{name} {desc}")
        if not text:
            return None
        low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
        name_low = str(name).lower()
        if name and "attached unit" not in name_low and "retinue" not in name_low:
            # Allow non-ATTACHED UNIT names when wording explicitly matches
            # "If this unit has a Leader unit attached ... that Leader unit gains Scouts X\"."
            if "if this unit has a leader unit attached to it during the declare battle formations step" not in low:
                return None
        if "scout" not in low:
            return None

        m = re.search(
            r"\bif a (?P<keywords>[^.;]+?)\s+(?:(?:model|unit)\s+)?from your army is attached to this unit during the declare battle formations step,?\s*"
            r"that model gains(?: the)? scouts?\s*(?P<distance>\d+)",
            low,
            flags=re.IGNORECASE,
        )
        if m:
            kw_clause = str(m.group("keywords") or "").strip()
            kw_clause = re.sub(r"\bwith the leader ability\b", " ", kw_clause, flags=re.IGNORECASE)
            leader_keywords = [
                token.strip().upper()
                for token in re.split(r"\bor\b|\band\b|,", kw_clause, flags=re.IGNORECASE)
                if token.strip()
            ]
            if not leader_keywords:
                return None
            try:
                distance = int(m.group("distance"))
            except Exception:
                return None
            if distance <= 0:
                return None
            return {"leader_keywords": tuple(leader_keywords), "scout_distance": int(distance)}

        # Generic retinue-style wording where any attached Leader gains Scouts.
        m = re.search(
            r"\bif this unit has a leader unit attached to it during the declare battle formations step,?\s*"
            r"that leader unit gains(?: the)? scouts?\s*(?P<distance>\d+)",
            low,
            flags=re.IGNORECASE,
        )
        if not m:
            return None
        try:
            distance = int(m.group("distance"))
        except Exception:
            return None
        if distance <= 0:
            return None
        return {"leader_keywords": tuple(), "scout_distance": int(distance)}

    def _clear_attached_unit_bodyguard_leader_scouts(self) -> None:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return
        removed = False
        if "attached_unit_bodyguard_leader_scouts" in sr:
            del sr["attached_unit_bodyguard_leader_scouts"]
            removed = True
        if "attached_unit_bodyguard_leader_scout_distance" in sr:
            del sr["attached_unit_bodyguard_leader_scout_distance"]
            removed = True
        if removed:
            self.special_rules = sr

    def _apply_attached_unit_bodyguard_leader_scouts(self, bodyguard: 'Unit') -> None:
        """Apply ATTACHED UNIT clauses that grant Scouts to the attached Leader model."""
        self._clear_attached_unit_bodyguard_leader_scouts()
        if bodyguard is None:
            return
        max_distance = 0
        for ab in (getattr(bodyguard, "possible_abilities", []) or []):
            rule = self._ability_attached_unit_bodyguard_leader_scouts(ab)
            if rule is None:
                continue
            rule_keywords = list(rule.get("leader_keywords") or ())
            if rule_keywords and not any(self.has_any_keyword(k) for k in rule_keywords):
                continue
            try:
                max_distance = max(max_distance, int(rule.get("scout_distance", 0) or 0))
            except Exception:
                continue
        if max_distance <= 0:
            return
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["attached_unit_bodyguard_leader_scouts"] = True
        sr["attached_unit_bodyguard_leader_scout_distance"] = int(max_distance)
        self.special_rules = sr

    def _get_aspect_shrine_root(self) -> 'Unit':
        try:
            return self.get_attached_unit_root()
        except Exception:
            return self

    def get_aspect_shrine_token_total(self) -> int:
        root = self._get_aspect_shrine_root()
        total = int(getattr(root, "_aspect_shrine_tokens_total", 0) or 0)
        if total <= 0:
            # Fallback to optional wargear count if tokens predate the unit-level counter.
            count = 0
            try:
                for model in list(getattr(root, "models", []) or []):
                    for ow in list(getattr(model, "optional_wargear", []) or []):
                        token_name = Unit._norm_wargear_name(str(ow or ""))
                        if token_name in ("aspect shrine token", "incubi shrine token"):
                            count += 1
            except Exception:
                count = 0
            if count:
                total = count
                try:
                    setattr(root, "_aspect_shrine_tokens_total", int(total))
                except Exception:
                    pass
        return max(0, int(total))

    def get_aspect_shrine_token_used(self) -> int:
        root = self._get_aspect_shrine_root()
        used = int(getattr(root, "_aspect_shrine_tokens_used", 0) or 0)
        return max(0, int(used))

    def get_aspect_shrine_token_remaining(self) -> int:
        return max(0, self.get_aspect_shrine_token_total() - self.get_aspect_shrine_token_used())

    def add_aspect_shrine_tokens(self, count: int = 1) -> None:
        root = self._get_aspect_shrine_root()
        try:
            count = int(count)
        except Exception:
            count = 1
        if count <= 0:
            return
        try:
            current = int(getattr(root, "_aspect_shrine_tokens_total", 0) or 0)
        except Exception:
            current = 0
        try:
            setattr(root, "_aspect_shrine_tokens_total", current + count)
        except Exception:
            pass

    def clear_aspect_shrine_tokens(self) -> None:
        root = self._get_aspect_shrine_root()
        try:
            setattr(root, "_aspect_shrine_tokens_total", 0)
        except Exception:
            pass
        try:
            setattr(root, "_aspect_shrine_tokens_used", 0)
        except Exception:
            pass
        try:
            setattr(root, "_aspect_shrine_prompt_suppressed", False)
        except Exception:
            pass

    def spend_aspect_shrine_token(self, count: int = 1) -> bool:
        root = self._get_aspect_shrine_root()
        try:
            count = int(count)
        except Exception:
            count = 1
        if count <= 0:
            return False
        total = self.get_aspect_shrine_token_total()
        used = self.get_aspect_shrine_token_used()
        if used + count > total:
            return False
        try:
            setattr(root, "_aspect_shrine_tokens_used", used + count)
        except Exception:
            return False
        return True

    def is_aspect_shrine_prompt_suppressed(self) -> bool:
        root = self._get_aspect_shrine_root()
        return bool(getattr(root, "_aspect_shrine_prompt_suppressed", False))

    def set_aspect_shrine_prompt_suppressed(self, suppressed: bool = True) -> None:
        root = self._get_aspect_shrine_root()
        try:
            setattr(root, "_aspect_shrine_prompt_suppressed", bool(suppressed))
        except Exception:
            pass

    def clear_aspect_shrine_prompt_suppression(self) -> None:
        self.set_aspect_shrine_prompt_suppressed(False)

    def _has_wargear_named(self, name: str) -> bool:
        want = Unit._norm_wargear_name(name)
        if not want:
            return False
        if want in ("aspect shrine token", "incubi shrine token"):
            try:
                if self.get_aspect_shrine_token_total() > 0:
                    return True
            except Exception:
                pass
        for model in list(getattr(self, "models", []) or []):
            try:
                for wg in list(getattr(model, "wargear", []) or []):
                    if wg and Unit._norm_wargear_name(getattr(wg, "name", "")) == want:
                        return True
            except Exception:
                pass
            try:
                for ow in list(getattr(model, "optional_wargear", []) or []):
                    if Unit._norm_wargear_name(str(ow or "")) == want:
                        return True
            except Exception:
                continue
        return False

    def _model_has_wargear_named(self, model: Optional['Model'], name: str) -> bool:
        if model is None:
            return False
        want = Unit._norm_wargear_name(name)
        if not want:
            return False
        try:
            for wg in list(getattr(model, "wargear", []) or []):
                if wg and Unit._norm_wargear_name(getattr(wg, "name", "")) == want:
                    return True
        except Exception:
            pass
        try:
            for ow in list(getattr(model, "optional_wargear", []) or []):
                if Unit._norm_wargear_name(str(ow or "")) == want:
                    return True
        except Exception:
            pass
        return False

    def _parse_bearer_invulnerable_save(self, text: str) -> Optional[int]:
        if not text:
            return None
        normalized = self._normalize_rules_text(text)
        if not normalized:
            return None
        normalized = normalized.replace("\u2019", "'")
        normalized = re.sub(r"\s+([.])", r"\1", normalized).strip()
        m = self._BEARER_INVULNERABLE_SAVE_RE.match(normalized)
        if not m:
            m = self._BEARER_INVULNERABLE_SAVE_WITH_ALLOCATED_DAMAGE_RE.match(normalized)
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def _parse_bearer_allocated_damage_reductions(self, text: str) -> list[dict]:
        if not text:
            return []
        normalized = self._normalize_rules_text(text)
        if not normalized:
            return []
        normalized = normalized.replace("\u2019", "'")
        normalized = re.sub(r"\s+([.])", r"\1", normalized).strip()
        tl = normalized.lower()
        entries: list[dict] = []

        m = self._BEARER_ALLOCATED_DAMAGE_REDUCTION_RE.search(tl)
        if m:
            try:
                val = int(m.group("val"))
            except Exception:
                val = 0
            if val:
                atype = (m.group("atype") or "any").strip().lower()
                entries.append(
                    {
                        "value": int(val),
                        "attack_type": atype,
                        "op": "sub",
                    }
                )

        m = self._BEARER_ALLOCATED_DAMAGE_HALVING_RE.search(tl)
        if not m:
            m = self._BEARER_ALLOCATED_DAMAGE_HALVING_ALT_RE.search(tl)
        if m:
            atype = (m.group("atype") or "any").strip().lower()
            entries.append(
                {
                    "value": 2,
                    "attack_type": atype,
                    "op": "div",
                }
            )

        return entries

    def _parse_bearer_save_characteristic(self, text: str) -> Optional[int]:
        if not text:
            return None
        normalized = self._normalize_rules_text(text)
        if not normalized:
            return None
        normalized = normalized.replace("\u2019", "'")
        normalized = re.sub(r"\s+([.])", r"\1", normalized).strip()
        m = self._BEARER_SAVE_CHARACTERISTIC_RE.match(normalized)
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def get_model_invulnerable_save_override(self, model: Optional['Model'] = None) -> tuple[Optional[int], Optional[str]]:
        """
        Return (invulnerable_save_value, source_name) for bearer-only invuln wargear abilities.
        """
        if model is None:
            return None, None
        sr = getattr(self, "special_rules", None)
        aegis_active = bool(isinstance(sr, dict) and sr.get("aegis_eternal_active"))
        archons_dynamic = bool(isinstance(sr, dict) and str(sr.get("archons_will_objective_id", "") or "").strip())
        army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
        tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        synaptic_dynamic = False
        active_synaptic_fn = getattr(tyr_mgr, "get_active_synaptic_imperative", None) if tyr_mgr is not None else None
        if callable(active_synaptic_fn):
            try:
                synaptic_dynamic = active_synaptic_fn(game=game) is not None
            except Exception:
                synaptic_dynamic = False
        try:
            temp_val, temp_source = getattr(model, "get_temporary_invulnerable_save", lambda: (0, ""))()
            if temp_val:
                return int(temp_val), temp_source or "Temporary invulnerable save"
        except Exception:
            pass
        cache_key = f"model_invulnerable_save:{get_entity_id(model)}"
        if not aegis_active and not archons_dynamic and not synaptic_dynamic and cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        best_value: Optional[int] = None
        best_source: Optional[str] = None
        archons_active_fn = getattr(self, "archons_will_effects_active", None)
        if callable(archons_active_fn):
            try:
                archons_active = bool(archons_active_fn())
            except Exception:
                archons_active = False
        else:
            archons_active = False

        # Model-level abilities (if any)
        try:
            for ab in getattr(model, "abilities", {}).values():
                try:
                    desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or "")
                    name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "Model ability")
                except Exception:
                    desc = ""
                    name = "Model ability"
                val = self._parse_bearer_invulnerable_save(desc)
                if val is None:
                    continue
                if best_value is None or val < best_value:
                    best_value = val
                    best_source = str(name or "Model ability")
        except Exception:
            pass

        # Wargear abilities tied to equipped items.
        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                atype = str(getattr(ab, "type", "") or "").lower()
                if "wargear" not in atype:
                    continue
                name = getattr(ab, "name", "") or ""
                if not name:
                    continue
                if not self._model_has_wargear_named(model, name):
                    continue
                desc = getattr(ab, "description", "") or ""
                val = self._parse_bearer_invulnerable_save(desc)
                if val is None:
                    continue
                if best_value is None or val < best_value:
                    best_value = val
                    best_source = str(name)
            except Exception:
                continue

        # Leading/bearer unit abilities that grant an invulnerable save to the unit.
        try:
            sr = getattr(self, "special_rules", None)
            entries = sr.get("bearer_unit_invulnerable_save") if isinstance(sr, dict) else None
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        val = entry.get("value")
                        source = entry.get("source")
                    elif isinstance(entry, (list, tuple)):
                        val = entry[0] if entry else None
                        source = entry[1] if len(entry) > 1 else None
                    else:
                        continue
                    try:
                        val = int(val)
                    except Exception:
                        continue
                    source_text = str(source or "").strip()
                    source_norm = source_text.lower().replace("\u2019", "'")
                    if ("archon's will" in source_norm or "archons will" in source_norm) and not archons_active:
                        continue
                    if best_value is None or val < best_value:
                        best_value = int(val)
                        best_source = source_text or "Bearer unit ability"
        except Exception:
            pass

        # Archon's Will: active only while this unit is in range of the selected objective and not Battle-shocked.
        if archons_active and (best_value is None or 5 < best_value):
            best_value = 5
            best_source = "Archon's Will"

        # AEGIS ETERNAL: models wholly within Hallowed Ground gain a 4+ invulnerable save.
        if isinstance(sr, dict) and sr.get("aegis_eternal_active"):
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            player = getattr(army, "player", None) if army is not None else None
            game = getattr(player, "game", None) if player is not None else None
            owner_id = str(sr.get("aegis_eternal_turn_owner", "") or "")
            effect_turn = int(sr.get("aegis_eternal_turn", 0) or 0)
            expires_phase = str(sr.get("aegis_eternal_expires_phase", "") or "").strip().upper()
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
            current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            current_owner = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "") if game is not None else ""
            if (not owner_id or owner_id == str(getattr(player, "id", "") or "")) and (not owner_id or owner_id != current_owner):
                if (not effect_turn or effect_turn == current_turn) and (not expires_phase or expires_phase == phase_name):
                    gk_mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
                    model_in_hallowed_ground = bool(
                        gk_mgr is not None
                        and getattr(gk_mgr, "is_warpbane_task_force", lambda: False)()
                        and getattr(gk_mgr, "model_wholly_within_hallowed_ground", lambda *_a, **_k: False)(model, game=game)
                    )
                    if model_in_hallowed_ground and (best_value is None or 4 < best_value):
                        best_value = 4
                        best_source = str(sr.get("aegis_eternal_source", "") or "Aegis Eternal")

        # Tyranids: Warrior Bioform Onslaught (Leader-beasts): 5+ invulnerable save.
        try:
            inv_fn = getattr(tyr_mgr, "leader_beasts_invulnerable_save", None) if tyr_mgr is not None else None
            if callable(inv_fn):
                inv_value, inv_source = inv_fn(model, unit=self)
                inv_value = int(inv_value or 0)
                if inv_value > 0 and (best_value is None or inv_value < best_value):
                    best_value = int(inv_value)
                    best_source = str(inv_source or "Leader-beasts").strip() or "Leader-beasts"
            synaptic_inv_fn = getattr(tyr_mgr, "synaptic_imperatives_invulnerable_save", None) if tyr_mgr is not None else None
            if callable(synaptic_inv_fn):
                inv_value, inv_source = synaptic_inv_fn(model, unit=self, game=game)
                inv_value = int(inv_value or 0)
                if inv_value > 0 and (best_value is None or inv_value < best_value):
                    best_value = int(inv_value)
                    best_source = str(inv_source or "Synaptic Imperatives").strip() or "Synaptic Imperatives"
        except Exception:
            pass

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        if not aegis_active and not archons_dynamic and not synaptic_dynamic:
            self._ability_cache[cache_key] = (best_value, best_source)
        return best_value, best_source

    def get_model_save_characteristic_override(self, model: Optional['Model'] = None) -> tuple[Optional[int], Optional[str]]:
        """
        Return (save_value, source_name) for bearer-only save characteristic overrides.
        """
        if model is None:
            return None, None
        cache_key = f"model_save_characteristic:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        best_value: Optional[int] = None
        best_source: Optional[str] = None

        # Model-level abilities (if any)
        try:
            for ab in getattr(model, "abilities", {}).values():
                try:
                    desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or "")
                    name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "Model ability")
                except Exception:
                    desc = ""
                    name = "Model ability"
                val = self._parse_bearer_save_characteristic(desc)
                if val is None:
                    continue
                if best_value is None or val < best_value:
                    best_value = val
                    best_source = str(name or "Model ability")
        except Exception:
            pass

        # Wargear abilities tied to equipped items.
        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                atype = str(getattr(ab, "type", "") or "").lower()
                if "wargear" not in atype:
                    continue
                name = getattr(ab, "name", "") or ""
                if not name:
                    continue
                if not self._model_has_wargear_named(model, name):
                    continue
                desc = getattr(ab, "description", "") or ""
                val = self._parse_bearer_save_characteristic(desc)
                if val is None:
                    continue
                if best_value is None or val < best_value:
                    best_value = val
                    best_source = str(name)
            except Exception:
                continue

        # Unit-level abilities on single-model units.
        try:
            if len(list(getattr(self, "models", []) or [])) == 1:
                for ab in list(getattr(self, "possible_abilities", []) or []):
                    try:
                        desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or "")
                        name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "Unit ability")
                    except Exception:
                        desc = ""
                        name = "Unit ability"
                    val = self._parse_bearer_save_characteristic(desc)
                    if val is None:
                        continue
                    if best_value is None or val < best_value:
                        best_value = val
                        best_source = str(name or "Unit ability")
        except Exception:
            pass

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = (best_value, best_source)
        return best_value, best_source

    def get_model_allocated_damage_reduction_entries(self, model: Optional['Model'] = None) -> list[dict]:
        """
        Return allocated-damage modifier entries that apply only to the specified model (bearer-only rules).
        """
        if model is None:
            return []
        cache_key = f"model_allocated_damage_reductions:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        entries: list[dict] = []

        def _add_entries(found: list[dict], source: str) -> None:
            for entry in found:
                if not isinstance(entry, dict):
                    continue
                merged = dict(entry)
                if source and not merged.get("source"):
                    merged["source"] = str(source)
                entries.append(merged)

        # Model-level abilities (if any)
        try:
            for ab in getattr(model, "abilities", {}).values():
                try:
                    desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or "")
                    name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "Model ability")
                except Exception:
                    desc = ""
                    name = "Model ability"
                found = self._parse_bearer_allocated_damage_reductions(desc)
                if found:
                    _add_entries(found, str(name or "Model ability"))
        except Exception:
            pass

        # Wargear abilities tied to equipped items.
        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                atype = str(getattr(ab, "type", "") or "").lower()
                if "wargear" not in atype:
                    continue
                name = getattr(ab, "name", "") or ""
                if not name:
                    continue
                if not self._model_has_wargear_named(model, name):
                    continue
                desc = getattr(ab, "description", "") or ""
                found = self._parse_bearer_allocated_damage_reductions(desc)
                if found:
                    _add_entries(found, str(name))
            except Exception:
                continue

        # Unit-level abilities on single-model units can apply to "this model" wording.
        try:
            models = list(getattr(self, "models", []) or [])
            if len(models) == 1 and models[0] is model:
                for ab in list(getattr(self, "possible_abilities", []) or []):
                    try:
                        desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or "")
                        name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "Unit ability")
                    except Exception:
                        desc = ""
                        name = "Unit ability"
                    found = self._parse_bearer_allocated_damage_reductions(desc)
                    if found:
                        _add_entries(found, str(name or "Unit ability"))
        except Exception:
            pass

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = entries
        return entries

    def _iter_active_possible_abilities(self):
        """Yield unit-level abilities that are currently active for this unit."""
        for ab in (getattr(self, "possible_abilities", []) or []):
            try:
                if not self._ability_is_active(ab):
                    continue
            except Exception:
                continue
            yield ab

    def _iter_active_abilities(self):
        """Yield unit + model abilities that are currently active for this unit."""
        for ab in self._iter_active_possible_abilities():
            yield ab
        for ab in (list(getattr(self, "abilities", []) or []) or []):
            try:
                if not self._ability_is_active(ab):
                    continue
            except Exception:
                continue
            yield ab

    def _iter_active_ability_texts(self):
        """Yield name/description strings for active abilities (used by text scanners)."""
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    for seg in self._iter_conditioned_text_segments(ab):
                        if seg:
                            yield seg
                    continue
                nm = str(getattr(ab, "name", "") or "")
                ds = str(getattr(ab, "description", "") or "")
                if nm:
                    yield nm
                if ds:
                    for seg in self._iter_conditioned_text_segments(ds):
                        if seg:
                            yield seg
            except Exception:
                continue

    def _iter_attached_leader_leading_abilities(self):
        """Yield (ability, leader_unit) for attached leaders with leading-only abilities."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is not self:
            for item in root._iter_attached_leader_leading_abilities():
                yield item
            return
        leaders = list(getattr(root, "attached_leaders", []) or [])
        for leader in leaders:
            if leader is None:
                continue
            try:
                abilities = list(getattr(leader, "possible_abilities", []) or [])
            except Exception:
                abilities = []
            for ab in abilities:
                try:
                    if not leader._ability_requires_leading(ab):
                        continue
                    if not leader._ability_is_active(ab):
                        continue
                except Exception:
                    continue
                yield ab, leader

    def _iter_attached_leader_ability_texts(self):
        """Yield name/description strings for attached leader leading abilities."""
        for ab, _leader in self._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    if ab:
                        yield ab
                    continue
                nm = str(getattr(ab, "name", "") or "")
                ds = str(getattr(ab, "description", "") or "")
                if nm:
                    yield nm
                if ds:
                    yield ds
            except Exception:
                continue

    def leading_battle_focus_token_refund_specs(self) -> list[dict]:
        """
        Leading ability: refund Battle Focus tokens on Agile Manoeuvre spend.

        Returns list of specs with keys:
            - source: ability name
            - threshold: int (D6 roll needed)
            - refund_tokens: optional int (defaults to 1)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "leading_battle_focus_token_refund_specs"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        specs: list[dict] = []
        seen: set[tuple] = set()

        for ab, leader in root._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    name = str(ab or "")
                    desc = str(ab or "")
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text_src = leader._strip_eligibility_prefix(desc or "")
            normalized = leader._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._BATTLE_FOCUS_TOKEN_REFUND_ON_AGILE_MANEUVER_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                threshold = int(m.group("threshold") or 3)
            except Exception:
                threshold = 3
            if threshold <= 0:
                threshold = 3
            source = str(name or "Battle Focus token refund").strip() or "Battle Focus token refund"
            key = (source.lower(), threshold)
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "threshold": int(threshold),
                }
            )

        # Eldritch Raiders - Pirate Prince enhancement:
        # attached leader refunds Battle Focus tokens when the led unit spends one.
        for leader in list(getattr(root, "attached_leaders", []) or []):
            if leader is None:
                continue
            try:
                if hasattr(leader, "is_alive") and not bool(leader.is_alive()):
                    continue
            except Exception:
                continue
            sr = getattr(leader, "special_rules", None)
            if not (isinstance(sr, dict) and bool(sr.get("enhancement_pirate_prince"))):
                continue
            try:
                threshold = int(sr.get("enhancement_pirate_prince_refund_roll_threshold", 3) or 3)
            except Exception:
                threshold = 3
            if threshold <= 0:
                threshold = 3
            try:
                refund_tokens = int(sr.get("enhancement_pirate_prince_refund_tokens", 1) or 1)
            except Exception:
                refund_tokens = 1
            refund_tokens = max(1, int(refund_tokens))
            source = str(sr.get("enhancement_pirate_prince_source", "") or "").strip()
            if not source:
                source = str(getattr(getattr(leader, "enhancement", None), "name", "") or "Pirate Prince").strip() or "Pirate Prince"
            key = (source.lower(), int(threshold), int(refund_tokens))
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "threshold": int(threshold), "refund_tokens": int(refund_tokens)})

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = list(specs)
        root._ability_cache = cache
        return list(specs)

    def leading_leadership_reroll_sources(self) -> list[str]:
        """Leading ability: re-roll Leadership tests taken for the attached unit."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "leading_leadership_reroll_sources"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        sources: list[str] = []
        seen: set[str] = set()

        for ab, leader in root._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    name = str(ab or "")
                    desc = str(ab or "")
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text_src = leader._strip_eligibility_prefix(desc or "")
            normalized = leader._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._LEADING_LEADERSHIP_REROLL_RE.fullmatch(normalized):
                continue
            source = str(name or "Leadership re-roll").strip() or "Leadership re-roll"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            sources.append(source)

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = list(sources)
        root._ability_cache = cache
        return list(sources)

    def dark_pacts_leadership_reroll_sources(self) -> list[str]:
        """Bearer ability: re-roll Leadership tests taken for Dark Pacts."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "dark_pacts_leadership_reroll_sources"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        sources: list[str] = []
        seen: set[str] = set()

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not self._DARK_PACTS_LEADERSHIP_REROLL_RE.fullmatch(normalized):
                    continue
                source = str(name or "Dark Pacts re-roll").strip() or "Dark Pacts re-roll"
                key = source.lower()
                if key in seen:
                    continue
                seen.add(key)
                sources.append(source)

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = list(sources)
        root._ability_cache = cache
        return list(sources)

    def leading_unmodified_six_specs(self) -> list[dict]:
        """
        Leading ability: once per phase, change one hit/wound/damage roll to an unmodified 6.

        Returns list of specs with keys:
            - source: ability name
            - exclude_support_weapon: bool
            - leader: Unit (leader)
            - leader_id: str
            - ability_key: str (stable key for per-phase tracking)
            - usage_limit: "phase" | "turn"
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "leading_unmodified_six_specs"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        specs: list[dict] = []
        seen: set[tuple] = set()

        for ab, leader in root._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    name = str(ab or "")
                    desc = str(ab or "")
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text_src = leader._strip_eligibility_prefix(desc or "")
            normalized = leader._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._LEADING_UNMODIFIED_SIX_ROLL_RE.fullmatch(normalized)
            if not m:
                continue
            exclude_support = False
            try:
                exclude_support = bool(m.group("exclude"))
            except Exception:
                exclude_support = "excluding support weapon" in normalized
            source = str(name or "Leading ability").strip() or "Leading ability"
            try:
                leader_id = str(get_entity_id(leader) or "")
            except Exception:
                leader_id = ""
            source_key = re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")
            ability_key = f"leading_unmodified_six:{leader_id}:{source_key}:{'exclude_support' if exclude_support else 'all'}"
            key = (leader_id, source_key, exclude_support)
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "exclude_support_weapon": bool(exclude_support),
                    "leader": leader,
                    "leader_id": leader_id,
                    "ability_key": ability_key,
                    "usage_limit": "phase",
                    "allowed_roll_types": ("hit", "wound", "damage"),
                }
            )

        # Enhancement: Pledge of Unholy Fortune (Coterie of the Conceited).
        # Once per turn, after a hit/wound/save roll for bearer's unit, if bearer is not Battle-shocked,
        # treat that roll as an unmodified 6.
        holders = [root]
        holders.extend(list(getattr(root, "attached_leaders", []) or []))
        for holder in holders:
            sr = getattr(holder, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_pledge_of_unholy_fortune"):
                continue
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            if not bearer_id:
                continue
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            bearer_unit = None
            for member in members:
                if member is None:
                    continue
                for model in list(getattr(member, "models", []) or []):
                    if str(get_entity_id(model) or "") != bearer_id:
                        continue
                    bearer_unit = member
                    break
                if bearer_unit is not None:
                    break
            if bearer_unit is None:
                continue
            leader_id = str(get_entity_id(bearer_unit) or "")
            source = "Pledge of Unholy Fortune"
            source_key = "pledge_of_unholy_fortune"
            ability_key = f"leading_unmodified_six:{bearer_id}:{source_key}:turn"
            key = (leader_id, source_key, False, "turn")
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "exclude_support_weapon": False,
                    "leader": bearer_unit,
                    "leader_id": leader_id,
                    "ability_key": ability_key,
                    "usage_limit": "turn",
                    "requires_bearer_not_battle_shocked": True,
                    "allowed_roll_types": ("hit", "wound", "save"),
                }
            )

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = list(specs)
        root._ability_cache = cache
        return list(specs)

    def model_once_per_battle_unmodified_six_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: once per battle (or once per battle round), after making a hit/wound/save roll,
        change it to an unmodified 6.

        Returns list of specs with keys:
            - source: ability name
            - key: usage tracking key
            - limit: "battle" | "battle_round"
        """
        if model is None:
            return []
        cache_key = f"model_once_per_battle_unmodified_six_specs:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            limit = ""
            yield_points_cost = 0
            if self._MODEL_ONCE_PER_BATTLE_ROUND_UNMODIFIED_SIX_RE.fullmatch(normalized):
                limit = "battle_round"
            elif (
                "once per turn" in normalized
                and "change the result of one hit roll one wound roll or one saving throw made for this model to an unmodified 6"
                in normalized
            ):
                limit = "battle_round"
                m_cost = re.search(r"spend\s+(\d+)\s*yp", normalized)
                if m_cost:
                    try:
                        yield_points_cost = int(m_cost.group(1) or 0)
                    except Exception:
                        yield_points_cost = 0
            elif self._MODEL_ONCE_PER_BATTLE_UNMODIFIED_SIX_RE.fullmatch(normalized):
                limit = "battle"
            if not limit:
                continue
            source = str(name or "Unmodified 6").strip() or "Unmodified 6"
            key_seed = self._normalize_keyword_phrase(source) or "model_unmodified_six"
            key = f"model_unmodified_six:{key_seed}:{limit}"
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "key": key,
                    "limit": limit,
                    "yield_points_cost": int(max(0, int(yield_points_cost or 0))),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_allocated_damage_zero_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: when an attack is allocated to this model, change Damage to 0.

        Returns list of specs with keys:
            - source: ability name
            - key: deterministic usage tracking key
            - usage: "battle" | "battle_round"
            - optional: whether the rules text uses optional wording ("you can ...")
        """
        if model is None:
            return []
        cache_key = f"model_allocated_damage_zero_specs:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            usage = ""
            if self._MODEL_ONCE_PER_BATTLE_ROUND_ALLOCATED_DAMAGE_ZERO_RE.fullmatch(normalized):
                usage = "battle_round"
            elif self._MODEL_ONCE_PER_BATTLE_ALLOCATED_DAMAGE_ZERO_RE.fullmatch(normalized):
                usage = "battle"
            if not usage:
                continue
            is_optional = bool(re.search(r"\byou can change\b", normalized))
            source = str(name or "Damage set to 0").strip() or "Damage set to 0"
            key_seed = self._normalize_keyword_phrase(source) or "allocated_damage_zero"
            key = f"model_allocated_damage_zero:{key_seed}:{usage}"
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "key": key,
                    "usage": usage,
                    "optional": bool(is_optional),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def leading_tactical_acumen_specs(self) -> list[dict]:
        """
        Leading ability: after this unit has shot, it can make a Normal move of up to X", then cannot charge.

        Returns list of specs with keys:
            - source: ability name
            - range: int
            - leader: Unit (leader)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "leading_tactical_acumen_specs"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        specs: list[dict] = []
        seen: set[tuple[str, int, int, str]] = set()

        for ab, leader in root._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    name = str(ab or "")
                    desc = str(ab or "")
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text_src = leader._strip_eligibility_prefix(desc or "")
            normalized = leader._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._TACTICAL_ACUMEN_RE.fullmatch(normalized)
            if not m:
                if str(name or "").strip().lower() != "tactical acumen":
                    continue
            try:
                rng = int(m.group("range") or 6) if m else 6
            except Exception:
                rng = 6
            if rng <= 0:
                rng = 6
            source = str(name or "Tactical Acumen").strip() or "Tactical Acumen"
            key = (source.lower(), int(rng))
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "range": int(rng), "leader": leader})

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = list(specs)
        root._ability_cache = cache
        return list(specs)

    def leading_weapon_attacks_bonus_specs(self) -> list[dict]:
        """
        Leading ability: while this model is leading a unit, add to the Attacks characteristic
        of named weapons equipped by models in that unit.

        Returns list with keys:
            - leader: leader unit object
            - source: ability name
            - weapon_name: target weapon phrase
            - attacks_bonus: int
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "leading_weapon_attacks_bonus_specs"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        specs: list[dict] = []
        seen: set[tuple[str, str, int]] = set()
        for ab, leader in root._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    name = str(ab or "")
                    desc = str(ab or "")
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text_src = leader._strip_eligibility_prefix(desc or "")
            normalized = leader._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._LEADING_WEAPON_ATTACKS_BONUS_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                bonus = int(m.group("bonus") or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            weapon_name = str(m.group("weapon") or "").strip()
            if not weapon_name:
                continue
            source = str(name or "Leading weapon attacks bonus").strip() or "Leading weapon attacks bonus"
            key = (source.lower(), weapon_name.lower(), int(bonus))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "leader": leader,
                    "source": source,
                    "weapon_name": weapon_name,
                    "attacks_bonus": int(bonus),
                }
            )

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = list(specs)
        root._ability_cache = cache
        return list(specs)

    def leading_weapon_attacks_bonus_for_weapon(self, weapon_name: str, attacker_model=None) -> tuple[int, list[str]]:
        """Return (total_bonus, reasons) for leading weapon Attacks bonuses on the named weapon."""
        if not weapon_name:
            return 0, []
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return 0, []
        if attacker_model is not None:
            try:
                model_unit = getattr(attacker_model, "parent_unit", None)
                model_root = model_unit.get_attached_unit_root() if model_unit is not None else None
                if model_root is not None and model_root is not root:
                    return 0, []
            except Exception:
                pass
        specs = root.leading_weapon_attacks_bonus_specs() if hasattr(root, "leading_weapon_attacks_bonus_specs") else []
        if not specs:
            return 0, []
        total = 0
        reasons: list[str] = []
        for spec in list(specs or []):
            leader = spec.get("leader")
            if leader is None:
                continue
            try:
                if not bool(getattr(leader, "is_attached_leader", False)):
                    continue
                alive_fn = getattr(leader, "is_alive", None)
                if callable(alive_fn) and not alive_fn():
                    continue
            except Exception:
                continue
            weapon_phrase = str(spec.get("weapon_name", "") or "").strip()
            if not weapon_phrase:
                continue
            try:
                if hasattr(root, "_weapon_name_matches") and callable(getattr(root, "_weapon_name_matches")):
                    if not root._weapon_name_matches([weapon_phrase], weapon_name):
                        continue
                else:
                    wn = str(weapon_name or "").strip().lower()
                    wp = str(weapon_phrase or "").strip().lower()
                    if not wn or not wp or (wp not in wn and wn not in wp):
                        continue
            except Exception:
                continue
            try:
                bonus = int(spec.get("attacks_bonus", 0) or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            total += int(bonus)
            source = str(spec.get("source", "") or "Leading weapon attacks bonus").strip() or "Leading weapon attacks bonus"
            reasons.append(f"{source} +{int(bonus)}A ({weapon_phrase})")
        return int(total), reasons

    def unit_post_shoot_reactive_move_no_charge_specs(self) -> list[dict]:
        """
        Unit ability: after this unit has shot, it can make a Normal move up to X";
        if it does, it cannot declare a charge this turn.

        Returns list of specs with keys:
            - source: ability name
            - range: int (max distance for placement generation; D6 resolves to 6 here)
            - range_roll: str (e.g. "D6") or ""
            - requires_not_engaged: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_reactive_move_no_charge_specs"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        specs: list[dict] = []
        seen: set[tuple[str, int, bool]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for member in members:
            if member is None:
                continue
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = member._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = member._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = member._POST_SHOOT_REACTIVE_MOVE_NO_CHARGE_RE.fullmatch(normalized)
                if not m:
                    continue
                range_expr = str(m.group("range_expr") or "").strip().upper()
                range_roll = ""
                rng = 0
                if range_expr == "D6":
                    range_roll = "D6"
                    rng = 6
                else:
                    try:
                        rng = int(range_expr or 0)
                    except Exception:
                        rng = 0
                if rng <= 0:
                    continue
                source = str(name or "Post-shoot reactive move").strip() or "Post-shoot reactive move"
                requires_not_engaged = "not within engagement range" in normalized
                key = (source.lower(), int(rng), str(range_roll), bool(requires_not_engaged))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(rng),
                        "range_roll": str(range_roll),
                        "requires_not_engaged": bool(requires_not_engaged),
                    }
                )

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = list(specs)
        root._ability_cache = cache
        return list(specs)

    def leading_once_per_battle_advance_and_charge_specs(self) -> list[dict]:
        """
        Unit ability: once per battle, this unit can declare a charge after advancing.

        Returns list of specs with keys:
            - source: ability name
            - ability_key: str (stable once-per-battle key)
            - owner_id: str (unit that provides the ability)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "leading_once_per_battle_advance_and_charge_specs"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        specs: list[dict] = []
        seen: set[tuple[str, str]] = set()

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for member in members:
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = member._strip_eligibility_prefix(text_src)
                normalized = member._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not self._ONCE_PER_BATTLE_ADVANCE_AND_CHARGE_RE.fullmatch(normalized):
                    continue
                source = str(name or "Advance and Charge").strip() or "Advance and Charge"
                try:
                    owner_id = str(get_entity_id(member) or "")
                except Exception:
                    owner_id = ""
                if not owner_id:
                    owner_id = str(get_entity_id(root) or "")
                source_key = re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_") or "advance_and_charge"
                ability_key = f"advance_and_charge_once:{owner_id}:{source_key}"
                key = (owner_id, ability_key)
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "ability_key": ability_key,
                        "owner_id": owner_id,
                    }
                )

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = list(specs)
        root._ability_cache = cache
        return list(specs)

    def leading_harvester_of_souls_specs(self) -> list[dict]:
        """
        Leading ability: Harvester of Souls (roll D6s on target/nearby units; mortals after shooting).

        Returns list of specs with keys:
            - source: ability name
            - leader: Unit (leader)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "leading_harvester_of_souls_specs"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        specs: list[dict] = []
        seen: set[str] = set()

        for ab, leader in root._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    name = str(ab or "")
                    desc = str(ab or "")
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text_src = leader._strip_eligibility_prefix(desc or "")
            normalized = leader._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._HARVESTER_OF_SOULS_RE.fullmatch(normalized)
            if not m:
                if str(name or "").strip().lower() != "harvester of souls":
                    continue
            source = str(name or "Harvester of Souls").strip() or "Harvester of Souls"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "leader": leader})

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = list(specs)
        root._ability_cache = cache
        return list(specs)

    def leading_word_of_phoenix_specs(self) -> list[dict]:
        """
        Leading ability: Word of the Phoenix (Command phase bodyguard returns).

        Returns list of specs with keys:
            - source: ability name
            - leader: Unit (leader)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "leading_word_of_phoenix_specs"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        specs: list[dict] = []
        seen: set[str] = set()

        for ab, leader in root._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    name = str(ab or "")
                    desc = str(ab or "")
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text_src = leader._strip_eligibility_prefix(desc or "")
            normalized = leader._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._WORD_OF_PHOENIX_RE.fullmatch(normalized):
                if str(name or "").strip().lower() != "word of the phoenix (psychic)" and str(name or "").strip().lower() != "word of the phoenix":
                    continue
            source = str(name or "Word of the Phoenix").strip() or "Word of the Phoenix"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "leader": leader})

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = list(specs)
        root._ability_cache = cache
        return list(specs)

    def _iter_reroll_scan_texts(self):
        """Yield ability texts for reroll detection."""
        iter_active = getattr(self, "_iter_active_ability_texts", None)
        if callable(iter_active):
            for t in iter_active():
                yield t
        iter_leader = getattr(self, "_iter_attached_leader_ability_texts", None)
        if callable(iter_leader):
            for t in iter_leader():
                yield t

    def _iter_attached_unit_reroll_texts(self):
        """Yield normalized ability texts for attached unit reroll rules (includes leaders)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        seen = set()
        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text = u._normalize_rules_text(desc or name or "")
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                text = Unit._strip_eligibility_prefix(text)
                if "leading a unit" in text.lower() and "bearer's unit" not in text.lower():
                    text = re.sub(r"\bthat unit\b", "the bearer's unit", text, flags=re.IGNORECASE)
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                yield text

    def _iter_attack_roll_rule_texts(self, text: str) -> list[str]:
        """Extract attack-roll rule clauses from a rules text (best-effort)."""
        if not text:
            return []
        cleaned = self._normalize_rules_text(text)
        if not cleaned:
            return []
        cleaned = Unit._strip_eligibility_prefix(cleaned)
        cleaned = re.sub(r";\s*", ". ", cleaned)
        leading_prefix = None
        aura_prefix = None
        m = re.match(r"^(while this model is leading (?:a|this) unit)", cleaned, flags=re.IGNORECASE)
        if m:
            leading_prefix = m.group(1)
        else:
            m = re.match(
                r'^(while a (?:friendly|enemy) .+? unit is within \d+" of this (?:unit|model))',
                cleaned,
                flags=re.IGNORECASE,
            )
            if m:
                aura_prefix = m.group(1)
        prefix = leading_prefix or aura_prefix
        prefix_lower = prefix.lower() if prefix else ""
        sentences = [part.strip() for part in re.split(r"\.\s*", cleaned) if part.strip()]
        if not sentences:
            return []
        candidates: list[str] = []

        def _effect_start(value: str) -> bool:
            return bool(re.match(r"^(?:if|add|subtract|you can|reroll|re-?roll|a successful|an unmodified|a critical)\b", value, flags=re.IGNORECASE))

        for idx, sentence in enumerate(sentences):
            sl = sentence.lower()
            if "each time" not in sl or "attack" not in sl:
                continue
            if not any(k in sl for k in ("hit roll", "wound roll", "critical", "reroll", "re-roll", "subtract", "add")):
                continue
            base_sentence = sentence
            if prefix and not base_sentence.lower().startswith(prefix_lower):
                base_sentence = f"{prefix}, {base_sentence}"
            parts = [base_sentence]
            j = idx + 1
            while j < len(sentences):
                nxt = sentences[j].strip()
                if not nxt:
                    j += 1
                    continue
                if _effect_start(nxt):
                    parts.append(nxt)
                    j += 1
                    continue
                break
            candidates.append(". ".join(parts))

        if not candidates:
            candidates = [cleaned]
        return candidates

    def _parse_attack_roll_rules_from_text(self, text: str):
        """Parse attack-roll rules from text into structured rules."""
        rules = []
        for chunk in self._iter_attack_roll_rule_texts(text):
            try:
                rule = parse_attack_roll_text(chunk)
            except Exception:
                rule = None
            if rule is not None:
                rules.append(rule)
        return rules

    def _get_unit_attack_roll_rules(self):
        """Collect and cache unit-level attack roll rules for this attached unit."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_attack_roll_rules"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]
        rules = []
        seen_names: set[str] = set()
        seen_objective_full_reroll: set[str] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            for name, desc in member._iter_ability_entries_for_rules():
                try:
                    ability_name = str(name or "").replace("\u2019", "'").strip()
                except Exception:
                    ability_name = ""
                name_key = ability_name.lower().strip()
                if name_key and name_key in seen_names:
                    continue
                if name_key:
                    seen_names.add(name_key)
                text_src = desc or name or ""
                for rule in self._parse_attack_roll_rules_from_text(text_src):
                    if rule.scope != "unit":
                        continue
                    if rule.subject not in ("model_in_this_unit", "model_in_that_unit"):
                        continue
                    rules.append((rule, ability_name or "Unit ability"))
                # Stand Vigil-style clause: while within a controlled objective, full wound re-roll.
                try:
                    norm = self._normalize_rules_text(text_src)
                except Exception:
                    norm = str(text_src or "")
                if norm:
                    norm = norm.replace("\u2019", "'").replace("\u0192?T", "'")
                    sentences = [part.strip() for part in re.split(r"\.\s*", norm) if part.strip()]
                    for sentence in sentences:
                        s_norm = sentence.lower()
                        s_norm = re.sub(r"'s\b", "s", s_norm)
                        s_norm = re.sub(r"[^a-z0-9]+", " ", s_norm)
                        s_norm = re.sub(r"\s+", " ", s_norm).strip()
                        if not s_norm:
                            continue
                        if not self._UNIT_OBJECTIVE_CONTROLLED_FULL_WOUND_REROLL_RE.fullmatch(s_norm):
                            continue
                        source = ability_name or "Unit ability"
                        key = f"{source.lower()}|objective_controlled_full_wound_reroll"
                        if key in seen_objective_full_reroll:
                            continue
                        seen_objective_full_reroll.add(key)
                        rules.append(
                            (
                                AttackRollRule(
                                    scope="unit",
                                    subject="model_in_this_unit",
                                    attack_type="any",
                                    effects=(
                                        AttackRollEffect(
                                            roll="wound",
                                            kind="reroll",
                                            reroll_full=True,
                                            condition=AttackRollCondition(attacker_within_objective_controlled=True),
                                        ),
                                    ),
                                ),
                                source,
                            )
                        )
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rules
        return rules

    def _target_is_afflicted(self, target, *, source_unit=None) -> bool:
        if target is None:
            return False
        try:
            t_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
        except Exception:
            t_root = target
        if t_root is None:
            return False
        try:
            sr = getattr(t_root, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("post_shoot_afflicted_active")):
                return True
        except Exception:
            pass
        try:
            from ...rules.nurgles_gift import NurglesGiftManager
        except Exception:
            return False
        source = source_unit or self
        try:
            source_root = source.get_attached_unit_root() if hasattr(source, "get_attached_unit_root") else source
        except Exception:
            source_root = source
        try:
            source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
        except Exception:
            source_army = None
        source_player = getattr(source_army, "player", None) if source_army is not None else None
        game = getattr(source_player, "game", None) if source_player is not None else None
        game_map = getattr(game, "map", None) if game is not None else None
        try:
            return bool(NurglesGiftManager.get_afflicted_plague_for_unit(t_root, game=game, game_map=game_map) is not None)
        except Exception:
            return False

    def _attack_condition_met(self, condition: Optional[AttackRollCondition], *, target=None, source_unit=None) -> bool:
        """Evaluate attack-roll conditions against the current unit/target."""
        if condition is None:
            return True
        unit = source_unit or self
        try:
            unit = unit.get_attached_unit_root()
        except Exception:
            pass
        if condition.attacker_below_starting_strength:
            try:
                if not unit.is_below_starting_strength():
                    return False
            except Exception:
                return False
        if condition.attacker_below_half_strength:
            try:
                if not unit.is_below_half_strength():
                    return False
            except Exception:
                return False
        if condition.attacker_charged_this_turn:
            try:
                if not bool(getattr(unit.round_state, "charged_this_round", False)):
                    return False
            except Exception:
                return False
        if condition.attacker_contains_model_keywords_any:
            matched = False
            for kw in condition.attacker_contains_model_keywords_any:
                if not kw:
                    continue
                try:
                    if hasattr(unit, "_unit_contains_model_with_keyword") and unit._unit_contains_model_with_keyword(kw):
                        matched = True
                        break
                except Exception:
                    pass
                try:
                    if hasattr(unit, "_unit_contains_model_named") and unit._unit_contains_model_named(kw):
                        matched = True
                        break
                except Exception:
                    pass
            if not matched:
                return False
        if condition.attacker_within_objective_controlled:
            try:
                if not unit._attacker_within_objective_controlled():
                    return False
            except Exception:
                return False
        if condition.target_battleshocked:
            try:
                if not (target is not None and target.is_battle_shocked()):
                    return False
            except Exception:
                return False
        if condition.target_within_objective:
            try:
                if not self._target_within_objective_range(target):
                    return False
            except Exception:
                return False
        if condition.target_within_objective_not_controlled:
            try:
                if not self._target_within_uncontrolled_objective_range(target):
                    return False
            except Exception:
                return False
        if condition.target_within_range is not None:
            try:
                from ...utility.aura_utils import unit_within_range_of_unit
                t_unit = target
                if t_unit is not None and not hasattr(t_unit, "get_attached_unit_root"):
                    t_unit = getattr(t_unit, "parent_unit", t_unit)
                if t_unit is None:
                    return False
                game = None
                try:
                    game = getattr(getattr(unit.get_parent_army(), "player", None), "game", None)
                except Exception:
                    game = None
                if game is None:
                    try:
                        game = getattr(getattr(t_unit.get_parent_army(), "player", None), "game", None)
                    except Exception:
                        game = None
                game_map = getattr(game, "map", None) if game is not None else None
                if game_map is not None:
                    placed = list(getattr(game_map, "units", []) or [])
                    try:
                        s_root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
                    except Exception:
                        s_root = unit
                    try:
                        t_root = t_unit.get_attached_unit_root() if hasattr(t_unit, "get_attached_unit_root") else t_unit
                    except Exception:
                        t_root = t_unit
                    if s_root not in placed or t_root not in placed:
                        return False
                if not unit_within_range_of_unit(unit, t_unit, float(condition.target_within_range), use_attached_aggregate=True):
                    return False
            except Exception:
                return False
        if condition.target_isolated_within is not None:
            try:
                from ...utility.aura_utils import unit_within_range_of_unit
                t_unit = target
                if t_unit is not None and not hasattr(t_unit, "get_attached_unit_root"):
                    t_unit = getattr(t_unit, "parent_unit", t_unit)
                if t_unit is None:
                    return False
                game = None
                try:
                    game = getattr(getattr(unit.get_parent_army(), "player", None), "game", None)
                except Exception:
                    game = None
                if game is None:
                    try:
                        game = getattr(getattr(t_unit.get_parent_army(), "player", None), "game", None)
                    except Exception:
                        game = None
                game_map = getattr(game, "map", None) if game is not None else None
                if game_map is None:
                    return False
                placed = list(getattr(game_map, "units", []) or [])
                try:
                    t_root = t_unit.get_attached_unit_root() if hasattr(t_unit, "get_attached_unit_root") else t_unit
                except Exception:
                    t_root = t_unit
                if t_root not in placed:
                    return False
                try:
                    enemies = list(game_map.get_enemy_units(unit) or [])
                except Exception:
                    return False
                if not enemies:
                    return False
                try:
                    from ...utility.entity_ids import get_entity_id
                except Exception:
                    get_entity_id = None
                seen = set()
                for enemy in enemies:
                    try:
                        root = enemy.get_attached_unit_root() if hasattr(enemy, "get_attached_unit_root") else enemy
                    except Exception:
                        root = enemy
                    if root is None or root is t_root:
                        continue
                    if get_entity_id is not None:
                        try:
                            rid = get_entity_id(root)
                        except Exception:
                            rid = None
                        if rid:
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
                    if unit_within_range_of_unit(root, t_root, float(condition.target_isolated_within), use_attached_aggregate=True):
                        return False
            except Exception:
                return False
        if condition.target_can_fly is not None:
            try:
                can_fly = bool(getattr(target, "is_flying", False))
            except Exception:
                can_fly = False
            if not can_fly:
                try:
                    can_fly = bool(target.has_keyword("FLY") or target.has_any_keyword("FLY"))
                except Exception:
                    can_fly = False
            if bool(condition.target_can_fly) != bool(can_fly):
                return False
        if condition.target_below_starting_strength:
            try:
                if not (target is not None and target.is_below_starting_strength()):
                    return False
            except Exception:
                return False
        if condition.target_below_half_strength:
            try:
                if not (target is not None and target.is_below_half_strength()):
                    return False
            except Exception:
                return False

        def _target_has_keyword(keyword: str) -> bool:
            if target is None:
                return False
            kw = str(keyword or "").strip()
            if not kw:
                return False
            kw_norm = kw.lower()
            if kw_norm == "afflicted":
                return bool(self._target_is_afflicted(target, source_unit=unit))
            try:
                return bool(target.has_keyword(kw.upper()))
            except Exception:
                try:
                    return bool(target.has_any_keyword(kw.upper()))
                except Exception:
                    return False

        if condition.target_keywords_any:
            if not any(_target_has_keyword(k) for k in condition.target_keywords_any):
                return False
        if condition.target_keywords_all:
            if not all(_target_has_keyword(k) for k in condition.target_keywords_all):
                return False
        if condition.target_exclude_keywords_any:
            if any(_target_has_keyword(k) for k in condition.target_exclude_keywords_any):
                return False
        return True

    def get_leading_attack_roll_modifiers(self, attack_type: str, *, target=None) -> dict:
        """
        Return leading-only attack roll modifiers from attached leaders for the attached unit.

        Supports strict patterns parsed by attack_roll_parser (full clause matching).
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        cache_key = "leading_attack_roll_rules"
        if cache_key in getattr(root, "_ability_cache", {}):
            rules = root._ability_cache[cache_key]
        else:
            rules = []
            seen_names: set[str] = set()
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    name = str(getattr(ab, "name", "") or "Leading ability").replace("\u2019", "'")
                    desc = str(getattr(ab, "description", "") or "")
                except Exception:
                    name = "Leading ability"
                    desc = ""
                name_key = name.strip().lower()
                if name_key and name_key != "leading ability" and name_key in seen_names:
                    continue
                if name_key and name_key != "leading ability":
                    seen_names.add(name_key)
                text_src = desc or name or ""
                for rule in self._parse_attack_roll_rules_from_text(text_src):
                    if rule.scope != "leading":
                        continue
                    if rule.subject not in ("model_in_that_unit", "model_in_this_unit"):
                        continue
                    rules.append((rule, name or "Leading ability"))
            if not hasattr(root, "_ability_cache"):
                root._ability_cache = {}
            root._ability_cache[cache_key] = rules

        mods = {
            "hit": 0,
            "wound": 0,
            "reroll_hit_ones": False,
            "reroll_wound_ones": False,
            "reroll_hit_values": (),
            "reroll_wound_values": (),
            "reroll_hit_full": False,
            "reroll_wound_full": False,
            "crit_hit_threshold": None,
            "crit_wound_threshold": None,
            "hit_reasons": (),
            "wound_reasons": (),
            "reroll_hit_reasons": (),
            "reroll_wound_reasons": (),
            "reroll_hit_full_reasons": (),
            "reroll_wound_full_reasons": (),
            "crit_hit_reasons": (),
            "crit_wound_reasons": (),
        }

        hit_reasons: list[str] = []
        wound_reasons: list[str] = []
        reroll_hit_reasons: list[str] = []
        reroll_wound_reasons: list[str] = []
        reroll_hit_full_reasons: list[str] = []
        reroll_wound_full_reasons: list[str] = []
        crit_hit_reasons: list[str] = []
        crit_wound_reasons: list[str] = []
        reroll_hit_values: set[int] = set()
        reroll_wound_values: set[int] = set()
        crit_hit_threshold = None
        crit_wound_threshold = None

        def _cond_suffix(cond: Optional[AttackRollCondition]) -> str:
            if not cond:
                return ""
            parts = []
            if cond.target_battleshocked:
                parts.append("vs Battle-shocked targets")
            if cond.attacker_below_starting_strength:
                parts.append("while below Starting Strength")
            if cond.attacker_below_half_strength:
                parts.append("while below Half-strength")
            if cond.attacker_charged_this_turn:
                parts.append("after making a Charge move this turn")
            if cond.attacker_contains_model_keywords_any:
                kw = "/".join(k.upper() for k in cond.attacker_contains_model_keywords_any)
                parts.append(f"while containing {kw} model")
            if cond.attacker_within_objective_controlled:
                parts.append("while within a controlled objective")
            if cond.target_within_objective:
                parts.append("vs targets within objective range")
            if cond.target_within_objective_not_controlled:
                parts.append("vs targets within objective range you do not control")
            if cond.target_within_range is not None:
                parts.append(f"vs targets within {cond.target_within_range}\"")
            if cond.target_isolated_within is not None:
                parts.append(f"vs isolated targets (no other enemy units within {cond.target_isolated_within}\")")
            if cond.target_can_fly is True:
                parts.append("vs FLY targets")
            if cond.target_can_fly is False:
                parts.append("vs non-FLY targets")
            if cond.target_keywords_any:
                if set(cond.target_keywords_any) == {"character"}:
                    parts.append("vs CHARACTER targets")
                elif set(cond.target_keywords_any) == {"monster", "vehicle"}:
                    parts.append("vs MONSTER/VEHICLE targets")
            if cond.target_below_starting_strength:
                parts.append("vs targets below Starting Strength")
            if cond.target_below_half_strength:
                parts.append("vs targets below Half-strength")
            if cond.target_exclude_keywords_any:
                parts.append("excluding " + ", ".join(cond.target_exclude_keywords_any))
            if not parts:
                return ""
            return " (" + "; ".join(parts) + ")"

        for rule, name in list(rules or []):
            if atype != "any" and rule.attack_type not in ("any", atype):
                continue
            for eff in rule.effects:
                if not self._attack_condition_met(eff.condition, target=target, source_unit=root):
                    continue
                label = name or "Leading ability"
                if eff.kind in ("add", "sub") and eff.roll in ("hit", "wound"):
                    val = int(eff.value or 0)
                    if eff.kind == "sub":
                        val = -val
                    if eff.roll == "hit":
                        mods["hit"] += val
                        hit_reasons.append(f"{val:+d} to hit from {label}{_cond_suffix(eff.condition)}")
                    else:
                        mods["wound"] += val
                        wound_reasons.append(f"{val:+d} to wound from {label}{_cond_suffix(eff.condition)}")
                elif eff.kind == "reroll":
                    if eff.roll == "hit":
                        if eff.reroll_full:
                            mods["reroll_hit_full"] = True
                            reroll_hit_full_reasons.append(f"Leading: re-roll Hit roll from {label}{_cond_suffix(eff.condition)}")
                        if eff.reroll_values:
                            reroll_hit_values.update(int(v) for v in eff.reroll_values)
                            reroll_hit_reasons.append(
                                f"Leading: re-roll Hit rolls of {', '.join(str(v) for v in sorted(eff.reroll_values))} from {label}{_cond_suffix(eff.condition)}"
                            )
                    elif eff.roll == "wound":
                        if eff.reroll_full:
                            mods["reroll_wound_full"] = True
                            reroll_wound_full_reasons.append(f"Leading: re-roll Wound roll from {label}{_cond_suffix(eff.condition)}")
                        if eff.reroll_values:
                            reroll_wound_values.update(int(v) for v in eff.reroll_values)
                            reroll_wound_reasons.append(
                                f"Leading: re-roll Wound rolls of {', '.join(str(v) for v in sorted(eff.reroll_values))} from {label}{_cond_suffix(eff.condition)}"
                            )
                elif eff.kind == "crit" and eff.critical_threshold:
                    if eff.roll == "hit":
                        crit_hit_threshold = eff.critical_threshold if crit_hit_threshold is None else min(crit_hit_threshold, eff.critical_threshold)
                        crit_hit_reasons.append(f"Leading: critical hit on {eff.critical_threshold}+ from {label}{_cond_suffix(eff.condition)}")
                    elif eff.roll == "wound":
                        crit_wound_threshold = eff.critical_threshold if crit_wound_threshold is None else min(crit_wound_threshold, eff.critical_threshold)
                        crit_wound_reasons.append(f"Leading: critical wound on {eff.critical_threshold}+ from {label}{_cond_suffix(eff.condition)}")

        mods["reroll_hit_values"] = tuple(sorted(reroll_hit_values))
        mods["reroll_wound_values"] = tuple(sorted(reroll_wound_values))
        mods["reroll_hit_ones"] = bool(1 in reroll_hit_values)
        mods["reroll_wound_ones"] = bool(1 in reroll_wound_values)
        mods["crit_hit_threshold"] = crit_hit_threshold
        mods["crit_wound_threshold"] = crit_wound_threshold
        mods["hit_reasons"] = tuple(hit_reasons)
        mods["wound_reasons"] = tuple(wound_reasons)
        mods["reroll_hit_reasons"] = tuple(reroll_hit_reasons)
        mods["reroll_wound_reasons"] = tuple(reroll_wound_reasons)
        mods["reroll_hit_full_reasons"] = tuple(reroll_hit_full_reasons)
        mods["reroll_wound_full_reasons"] = tuple(reroll_wound_full_reasons)
        mods["crit_hit_reasons"] = tuple(crit_hit_reasons)
        mods["crit_wound_reasons"] = tuple(crit_wound_reasons)
        return mods

    def _path_of_warrior_choice(self, *, game=None) -> str:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        choice = str(sr.get("path_of_warrior_choice", "") or "").strip().upper()
        if not choice:
            return ""
        exp = str(sr.get("path_of_warrior_expires_phase", "") or "").strip().upper()
        if exp:
            if game is None:
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
            if game is not None:
                pname = str(getattr(getattr(game, "phase", None), "name", "") or getattr(game, "phase", "") or "").strip().upper()
                if pname and pname != exp:
                    return ""
        return choice

    def _dance_of_death_choice(self, *, game=None) -> str:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        if bool(sr.get("serpents_brood_fangs_of_the_brood_active")):
            active = True
            exp = str(sr.get("serpents_brood_fangs_of_the_brood_expires_phase", "") or "").strip().upper()
            try:
                effect_turn = int(sr.get("serpents_brood_fangs_of_the_brood_turn", 0) or 0)
            except (TypeError, ValueError):
                effect_turn = 0
            if game is None:
                try:
                    army = root.get_parent_army()
                except (AttributeError, TypeError, ValueError):
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except (AttributeError, TypeError, ValueError):
                    game = None
            if game is not None:
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or getattr(game, "phase", "") or "").strip().upper()
                if exp and phase_name and phase_name != exp:
                    active = False
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if effect_turn and current_turn and effect_turn != current_turn:
                    active = False
            if active:
                return "ALL"
        choice = str(sr.get("dance_of_death_choice", "") or "").strip().upper()
        if not choice:
            return ""
        exp = str(sr.get("dance_of_death_expires_phase", "") or "").strip().upper()
        if exp:
            if game is None:
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
            if game is not None:
                pname = str(getattr(getattr(game, "phase", None), "name", "") or getattr(game, "phase", "") or "").strip().upper()
                if pname and pname != exp:
                    return ""
        return choice

    def _needgaard_huntrs_mark_active_for_shooting(self, *, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("needgaard_huntrs_mark_active"):
            return False
        owner_id = str(sr.get("needgaard_huntrs_mark_owner", "") or "")
        try:
            effect_turn = int(sr.get("needgaard_huntrs_mark_turn", 0) or 0)
        except Exception:
            effect_turn = 0
        if game is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game is None:
            return True
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name and phase_name != "SHOOTING_PHASE":
            return False
        if owner_id:
            try:
                current = game.get_current_player()
            except Exception:
                current = None
            current_id = str(getattr(current, "id", "") or "") if current is not None else ""
            if current_id and current_id != owner_id:
                return False
        if effect_turn:
            try:
                if int(getattr(game, "turn", 0) or 0) != effect_turn:
                    return False
            except Exception:
                return False
        return True

    def _needgaard_ordered_retreat_active_this_turn(self, *, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("needgaard_ordered_retreat_active"):
            return False
        owner_id = str(sr.get("needgaard_ordered_retreat_turn_owner", "") or "")
        try:
            effect_turn = int(sr.get("needgaard_ordered_retreat_turn", 0) or 0)
        except Exception:
            effect_turn = 0
        if game is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game is None:
            return True
        if owner_id:
            try:
                current = game.get_current_player()
            except Exception:
                current = None
            current_id = str(getattr(current, "id", "") or "") if current is not None else ""
            if current_id and current_id != owner_id:
                return False
        if effect_turn:
            try:
                if int(getattr(game, "turn", 0) or 0) != effect_turn:
                    return False
            except Exception:
                return False
        return True

    def _thousand_sons_rubricae_stratagem_active(
        self,
        *,
        active_key: str,
        owner_key: str,
        turn_key: str,
        expires_phase_key: str = "",
        game=None,
    ) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(active_key)):
            return False
        owner_id = str(sr.get(owner_key, "") or "")
        try:
            effect_turn = int(sr.get(turn_key, 0) or 0)
        except Exception:
            effect_turn = 0
        if game is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game is None:
            return True
        if owner_id:
            try:
                current = game.get_current_player()
            except Exception:
                current = None
            current_id = str(getattr(current, "id", "") or "") if current is not None else ""
            if current_id and current_id != owner_id:
                return False
        if effect_turn:
            try:
                if int(getattr(game, "turn", 0) or 0) != effect_turn:
                    return False
            except Exception:
                return False
        if expires_phase_key:
            exp = str(sr.get(expires_phase_key, "") or "").strip().upper()
            if exp:
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                if phase_name and phase_name != exp:
                    return False
        return True

    def get_unit_hit_reroll_modifiers(self, attack_type: str, *, target=None, attacker_model=None) -> dict:
        """
        Return unit-level hit modifiers for this attached unit, parsed via attack_roll_parser.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        rules = self._get_unit_attack_roll_rules()

        mods = {
            "hit": 0,
            "reroll_hit_ones": False,
            "reroll_hit_values": (),
            "reroll_hit_full": False,
            "crit_hit_threshold": None,
            "hit_reasons": (),
            "reroll_hit_reasons": (),
            "reroll_hit_full_reasons": (),
            "crit_hit_reasons": (),
        }

        hit_reasons: list[str] = []
        reroll_hit_reasons: list[str] = []
        reroll_hit_full_reasons: list[str] = []
        crit_hit_reasons: list[str] = []
        reroll_hit_values: set[int] = set()
        crit_hit_threshold = None

        def _cond_suffix(cond: Optional[AttackRollCondition]) -> str:
            if not cond:
                return ""
            parts = []
            if cond.target_battleshocked:
                parts.append("vs Battle-shocked targets")
            if cond.attacker_below_starting_strength:
                parts.append("while below Starting Strength")
            if cond.attacker_below_half_strength:
                parts.append("while below Half-strength")
            if cond.attacker_charged_this_turn:
                parts.append("after making a Charge move this turn")
            if cond.attacker_contains_model_keywords_any:
                kw = "/".join(k.upper() for k in cond.attacker_contains_model_keywords_any)
                parts.append(f"while containing {kw} model")
            if cond.attacker_within_objective_controlled:
                parts.append("while within a controlled objective")
            if cond.target_within_objective:
                parts.append("vs targets within objective range")
            if cond.target_within_objective_not_controlled:
                parts.append("vs targets within objective range you do not control")
            if cond.target_within_range is not None:
                parts.append(f"vs targets within {cond.target_within_range}\"")
            if cond.target_isolated_within is not None:
                parts.append(f"vs isolated targets (no other enemy units within {cond.target_isolated_within}\")")
            if cond.target_can_fly is True:
                parts.append("vs FLY targets")
            if cond.target_can_fly is False:
                parts.append("vs non-FLY targets")
            if cond.target_keywords_any:
                if set(cond.target_keywords_any) == {"character"}:
                    parts.append("vs CHARACTER targets")
                elif set(cond.target_keywords_any) == {"monster", "vehicle"}:
                    parts.append("vs MONSTER/VEHICLE targets")
            if cond.target_below_starting_strength:
                parts.append("vs targets below Starting Strength")
            if cond.target_below_half_strength:
                parts.append("vs targets below Half-strength")
            if cond.target_exclude_keywords_any:
                parts.append("excluding " + ", ".join(cond.target_exclude_keywords_any))
            if not parts:
                return ""
            return " (" + "; ".join(parts) + ")"

        for rule, name in list(rules or []):
            if atype != "any" and rule.attack_type not in ("any", atype):
                continue
            for eff in rule.effects:
                if not self._attack_condition_met(eff.condition, target=target, source_unit=root):
                    continue
                if eff.roll != "hit":
                    continue
                label = name or "Unit ability"
                if eff.kind in ("add", "sub"):
                    val = int(eff.value or 0)
                    if eff.kind == "sub":
                        val = -val
                    mods["hit"] += val
                    hit_reasons.append(f"{val:+d} to hit from {label}{_cond_suffix(eff.condition)}")
                elif eff.kind == "reroll":
                    if eff.reroll_full:
                        mods["reroll_hit_full"] = True
                        reroll_hit_full_reasons.append(f"{label}: re-roll Hit roll{_cond_suffix(eff.condition)}")
                    if eff.reroll_values:
                        reroll_hit_values.update(int(v) for v in eff.reroll_values)
                        reroll_hit_reasons.append(
                            f"{label}: re-roll Hit rolls of {', '.join(str(v) for v in sorted(eff.reroll_values))}{_cond_suffix(eff.condition)}"
                        )
                elif eff.kind == "crit" and eff.critical_threshold:
                    crit_hit_threshold = eff.critical_threshold if crit_hit_threshold is None else min(crit_hit_threshold, eff.critical_threshold)
                    crit_hit_reasons.append(f"{label}: critical hit on {eff.critical_threshold}+{_cond_suffix(eff.condition)}")

        choice = ""
        try:
            choice_fn = getattr(self, "_path_of_warrior_choice", None)
            if callable(choice_fn):
                choice = choice_fn()
        except Exception:
            choice = ""
        if choice in ("HIT", "BOTH"):
            reroll_hit_values.add(1)
            reroll_hit_reasons.append("Path of the Warrior: re-roll Hit rolls of 1")

        choice = ""
        try:
            choice_fn = getattr(self, "_dance_of_death_choice", None)
            if callable(choice_fn):
                choice = choice_fn()
        except Exception:
            choice = ""
        if choice in ("HERO", "ALL"):
            reroll_hit_values.add(1)
            reroll_hit_reasons.append("Dance of Death (Hero's Prowess): re-roll Hit rolls of 1")

        # Angelic Inheritors: Carmine Wrath (character units) re-roll Hit rolls of 1.
        try:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if sm_mgr is not None and getattr(sm_mgr, "legacy_of_the_angel_carmine_wrath_applies", None):
                if sm_mgr.legacy_of_the_angel_carmine_wrath_applies(root):
                    reroll_hit_values.add(1)
                    reroll_hit_reasons.append("Carmine Wrath: re-roll Hit rolls of 1")
        except Exception:
            pass

        # Bastion Task Force: Interlocking Tactics re-roll Hit rolls of 1 vs auspex scanned units.
        try:
            if target is not None:
                army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
                if sm_mgr is not None and getattr(sm_mgr, "interlocking_tactics_target_is_auspex_scanned_for", None):
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if sm_mgr.interlocking_tactics_target_is_auspex_scanned_for(root, target, game=game):
                        reroll_hit_values.add(1)
                        reroll_hit_reasons.append("Interlocking Tactics: re-roll Hit rolls of 1 vs auspex scanned units")
        except Exception:
            pass

        # Needgaard Oathband: HUNTR'S MARK grants ranged re-roll Hit rolls of 1.
        try:
            active_fn = getattr(root, "_needgaard_huntrs_mark_active_for_shooting", None)
            if atype in ("any", "ranged") and callable(active_fn) and active_fn():
                reroll_hit_values.add(1)
                reroll_hit_reasons.append("HUNTR'S MARK: re-roll Hit rolls of 1")
        except Exception:
            pass

        # Rad-Zone Corps: PRE-CALIBRATED PURGE SOLUTION grants ranged full hit re-rolls
        # against targets in the opponent deployment zone this phase.
        if atype in ("any", "ranged") and target is not None:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("rad_zone_pre_calibrated_purge_solution_active"):
                source = (
                    str(
                        sr.get("rad_zone_pre_calibrated_purge_solution_source", "")
                        or "PRE-CALIBRATED PURGE SOLUTION"
                    ).strip()
                    or "PRE-CALIBRATED PURGE SOLUTION"
                )
                get_parent_army = getattr(root, "get_parent_army", None)
                army = get_parent_army() if callable(get_parent_army) else None
                player = getattr(army, "player", None) if army is not None else None
                game_local = getattr(player, "game", None) if player is not None else None
                attacker_owner = str(getattr(player, "id", "") or "")
                effect_owner = str(sr.get("rad_zone_pre_calibrated_purge_solution_turn_owner", "") or "")
                effect_phase = str(sr.get("rad_zone_pre_calibrated_purge_solution_expires_phase", "") or "").strip().upper()
                current_phase = str(getattr(getattr(game_local, "phase", None), "name", "") or "").strip().upper()
                effect_turn = int(sr.get("rad_zone_pre_calibrated_purge_solution_turn", 0) or 0)
                current_turn = int(getattr(game_local, "turn", 0) or 0) if game_local is not None else 0
                effect_active = True
                if effect_owner and attacker_owner and effect_owner != attacker_owner:
                    effect_active = False
                if effect_active and effect_phase and current_phase and effect_phase != current_phase:
                    effect_active = False
                if effect_active and effect_turn and current_turn and effect_turn != current_turn:
                    effect_active = False
                if effect_active and game_local is not None:
                    enemy_player_id = str(sr.get("rad_zone_pre_calibrated_purge_solution_enemy_player_id", "") or "")
                    if not enemy_player_id and player is not None:
                        for other_player in list(getattr(game_local, "players", []) or []):
                            if other_player is not None and other_player is not player:
                                enemy_player_id = str(getattr(other_player, "id", "") or "")
                                break
                    if enemy_player_id:
                        target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                        in_enemy_zone = False
                        adm_mgr = getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None
                        zone_check = getattr(adm_mgr, "unit_within_player_deployment_zone", None) if adm_mgr is not None else None
                        if callable(zone_check):
                            in_enemy_zone = bool(
                                zone_check(
                                    target_root,
                                    enemy_player_id,
                                    game=game_local,
                                )
                            )
                        if in_enemy_zone:
                            mods["reroll_hit_full"] = True
                            reroll_hit_full_reasons.append(
                                f"{source}: re-roll Hit roll vs targets in opponent deployment zone"
                            )

        army = None
        get_parent_army = getattr(root, "get_parent_army", None)
        if callable(get_parent_army):
            army = get_parent_army()
        mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        bonus_fn = getattr(mgr, "ruthless_discipline_reroll_hit_ones", None) if mgr is not None else None
        if callable(bonus_fn) and bonus_fn(root):
            reroll_hit_values.add(1)
            reroll_hit_reasons.append("Ruthless Discipline: re-roll Hit rolls of 1 while ordered")

        # Hallowed Martyrs: RIGHTEOUS VENGEANCE (melee hit re-rolls this phase).
        try:
            if atype in ("any", "melee"):
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("righteous_vengeance_active"):
                    active = True
                    owner_id = str(sr.get("righteous_vengeance_turn_owner", "") or "")
                    source = str(sr.get("righteous_vengeance_source", "") or "RIGHTEOUS VENGEANCE").strip() or "RIGHTEOUS VENGEANCE"
                    game_local = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    phase_name = str(getattr(getattr(game_local, "phase", None), "name", "") or "").strip().upper()
                    expires_phase = str(sr.get("righteous_vengeance_expires_phase", "") or "").strip().upper()
                    if expires_phase and phase_name and expires_phase != phase_name:
                        active = False
                    try:
                        effect_turn = int(sr.get("righteous_vengeance_turn", 0) or 0)
                    except Exception:
                        effect_turn = 0
                    try:
                        current_turn = int(getattr(game_local, "turn", 0) or 0)
                    except Exception:
                        current_turn = 0
                    if effect_turn and current_turn and effect_turn != current_turn:
                        active = False
                    attacker_owner = str(getattr(getattr(army, "player", None), "id", "") or "") if army is not None else ""
                    if owner_id and attacker_owner and owner_id != attacker_owner:
                        active = False
                    if active:
                        mods["reroll_hit_full"] = True
                        reroll_hit_full_reasons.append(f"{source}: re-roll Hit roll (melee)")
        except Exception:
            pass

        # Target debuffs: post-shoot critical hit thresholds (e.g. Whispering Web).
        try:
            if target is not None:
                t_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                sr = getattr(t_root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("post_shoot_crit_hit_threshold_active"):
                    owner_id = str(sr.get("post_shoot_crit_hit_threshold_owner", "") or "")
                    try:
                        turn = int(sr.get("post_shoot_crit_hit_threshold_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    game = None
                    try:
                        game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                    except Exception:
                        game = None
                    if game is not None and owner_id:
                        try:
                            if int(getattr(game, "turn", 0) or 0) != turn or str(getattr(game.get_current_player(), "id", "") or "") != owner_id:
                                for k in (
                                    "post_shoot_crit_hit_threshold_active",
                                    "post_shoot_crit_hit_threshold_owner",
                                    "post_shoot_crit_hit_threshold_turn",
                                    "post_shoot_crit_hit_threshold_source",
                                    "post_shoot_crit_hit_threshold_keyword",
                                    "post_shoot_crit_hit_threshold_value",
                                    "post_shoot_crit_hit_threshold_expires_phase",
                                ):
                                    sr.pop(k, None)
                                t_root.special_rules = sr
                                sr = None
                        except Exception:
                            pass
                    if isinstance(sr, dict) and sr.get("post_shoot_crit_hit_threshold_active"):
                        keyword = str(sr.get("post_shoot_crit_hit_threshold_keyword", "") or "").strip()
                        applies = True
                        if keyword:
                            try:
                                applies = bool(root.has_any_keyword(keyword) or root.has_keyword(keyword))
                            except Exception:
                                applies = False
                        if applies:
                            try:
                                thresh_val = int(sr.get("post_shoot_crit_hit_threshold_value", 6) or 6)
                            except Exception:
                                thresh_val = 6
                            if thresh_val:
                                crit_hit_threshold = (
                                    thresh_val if crit_hit_threshold is None else min(int(crit_hit_threshold), int(thresh_val))
                                )
                                source = str(sr.get("post_shoot_crit_hit_threshold_source", "") or "Post-shoot crit bonus").strip()
                                crit_hit_reasons.append(f"{source}: critical hit on {int(thresh_val)}+")
        except Exception:
            pass

        # Inflamed Infections: selected model scores critical hits on 5+ (or 4+ vs Below Half-strength) against marked target.
        try:
            if target is not None and attacker_model is not None:
                game_local = None
                try:
                    game_local = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                except Exception:
                    game_local = None
                target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                tsr = getattr(target_root, "special_rules", None)
                if isinstance(tsr, dict) and tsr.get("inflamed_infections_active"):
                    exp_phase = str(tsr.get("inflamed_infections_expires_phase", "") or "").strip().upper()
                    phase_name = str(getattr(getattr(game_local, "phase", None), "name", "") or "").strip().upper()
                    if not exp_phase or exp_phase == phase_name:
                        try:
                            marked_turn = int(tsr.get("inflamed_infections_turn", 0) or 0)
                        except Exception:
                            marked_turn = 0
                        try:
                            current_turn = int(getattr(game_local, "turn", 0) or 0)
                        except Exception:
                            current_turn = 0
                        if not (marked_turn and current_turn and marked_turn != current_turn):
                            owner_id = str(tsr.get("inflamed_infections_owner", "") or "")
                            try:
                                attacker_owner = str(getattr(getattr(root.get_parent_army(), "player", None), "id", "") or "")
                            except Exception:
                                attacker_owner = ""
                            if owner_id and attacker_owner == owner_id:
                                source_model_id = str(tsr.get("inflamed_infections_model_id", "") or "")
                                attacker_model_id = str(get_entity_id(attacker_model) or "")
                                if source_model_id and attacker_model_id and source_model_id == attacker_model_id:
                                    try:
                                        threshold = int(tsr.get("inflamed_infections_crit_hit_threshold", 5) or 5)
                                    except Exception:
                                        threshold = 5
                                    is_below_half = False
                                    try:
                                        is_below_half = bool(getattr(target_root, "is_below_half_strength", lambda: False)())
                                    except Exception:
                                        is_below_half = False
                                    if is_below_half:
                                        try:
                                            threshold = int(tsr.get("inflamed_infections_crit_hit_threshold_below_half", 4) or 4)
                                        except Exception:
                                            threshold = 4
                                    threshold = max(2, min(6, int(threshold)))
                                    crit_hit_threshold = threshold if crit_hit_threshold is None else min(int(crit_hit_threshold), threshold)
                                    source = str(tsr.get("inflamed_infections_source", "") or "Inflamed Infections").strip() or "Inflamed Infections"
                                    crit_hit_reasons.append(f"{source}: critical hit on {int(threshold)}+")
        except Exception:
            pass

        # Target buffs: Symphony of Pain (re-roll Hit rolls vs marked target).
        try:
            if target is not None:
                t_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                sr = getattr(t_root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("symphony_of_pain_active"):
                    owner_id = str(sr.get("symphony_of_pain_owner", "") or "")
                    try:
                        turn = int(sr.get("symphony_of_pain_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    game = None
                    try:
                        game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                    except Exception:
                        game = None
                    if game is not None and owner_id:
                        try:
                            current_id = str(getattr(game.get_current_player(), "id", "") or "")
                        except Exception:
                            current_id = ""
                        try:
                            if int(getattr(game, "turn", 0) or 0) != turn or (current_id and current_id != owner_id):
                                for k in (
                                    "symphony_of_pain_active",
                                    "symphony_of_pain_owner",
                                    "symphony_of_pain_turn",
                                    "symphony_of_pain_source",
                                    "symphony_of_pain_keywords",
                                ):
                                    sr.pop(k, None)
                                t_root.special_rules = sr
                                sr = None
                        except Exception:
                            pass
                    if isinstance(sr, dict) and sr.get("symphony_of_pain_active"):
                        applies = True
                        if owner_id:
                            try:
                                army = root.get_parent_army()
                                player = getattr(army, "player", None) if army is not None else None
                            except Exception:
                                player = None
                            if player is not None and str(getattr(player, "id", "") or "") != owner_id:
                                applies = False
                        keywords = list(sr.get("symphony_of_pain_keywords", []) or [])
                        if applies and keywords:
                            for kw in keywords:
                                try:
                                    if not root.has_any_keyword(str(kw or "")):
                                        applies = False
                                        break
                                except Exception:
                                    applies = False
                                    break
                        if applies:
                            source = str(sr.get("symphony_of_pain_source", "") or "Symphony of Pain").strip() or "Symphony of Pain"
                            mods["reroll_hit_full"] = True
                            reroll_hit_full_reasons.append(f"{source}: re-roll Hit roll")
        except Exception:
            pass

        # Despoilers: re-roll Hit rolls after making a Dark Pact (until end of phase).
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and sr.get("despoilers_active"):
            apply_bonus = True
            exp = str(sr.get("despoilers_expires_phase", "") or "").strip().upper()
            if exp:
                army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if game is not None:
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if pname and pname != exp:
                        apply_bonus = False
            if apply_bonus:
                source = str(sr.get("despoilers_source", "") or "Despoilers").strip() or "Despoilers"
                mods["reroll_hit_full"] = True
                reroll_hit_full_reasons.append(f"{source}: re-roll Hit roll")

        # Devoted of Ynnead: Emissaries of Ynnead (Fight phase melee hit rerolls).
        try:
            if atype in ("any", "melee"):
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("aeldari_emissaries_of_ynnead_active"):
                    applies = True
                    owner_id = str(sr.get("aeldari_emissaries_of_ynnead_owner", "") or "")
                    army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                    player = getattr(army, "player", None) if army is not None else None
                    attacker_owner = str(getattr(player, "id", "") or "") if player is not None else ""
                    game_local = getattr(player, "game", None) if player is not None else None
                    if owner_id and attacker_owner and owner_id != attacker_owner:
                        applies = False
                    exp_phase = str(sr.get("aeldari_emissaries_of_ynnead_expires_phase", "") or "").strip().upper()
                    phase_name = str(getattr(getattr(game_local, "phase", None), "name", "") or "").strip().upper()
                    if applies and exp_phase and phase_name and exp_phase != phase_name:
                        applies = False
                    try:
                        marked_turn = int(sr.get("aeldari_emissaries_of_ynnead_turn", 0) or 0)
                    except Exception:
                        marked_turn = 0
                    try:
                        current_turn = int(getattr(game_local, "turn", 0) or 0)
                    except Exception:
                        current_turn = 0
                    if applies and marked_turn and current_turn and marked_turn != current_turn:
                        applies = False
                    if applies:
                        source = str(sr.get("aeldari_emissaries_of_ynnead_source", "") or "EMISSARIES OF YNNEAD").strip()
                        source = source or "EMISSARIES OF YNNEAD"
                        below_starting = False
                        try:
                            below_starting = bool(root.is_below_starting_strength())
                        except Exception:
                            below_starting = False
                        if below_starting:
                            mods["reroll_hit_full"] = True
                            reroll_hit_full_reasons.append(f"{source}: re-roll Hit roll (below Starting Strength)")
                        else:
                            reroll_hit_values.add(1)
                            reroll_hit_reasons.append(f"{source}: re-roll Hit rolls of 1")
        except Exception:
            pass

        # Virulent Vectorium: selected unit gains ranged hit rerolls vs Afflicted targets this phase.
        try:
            if atype in ("any", "ranged") and target is not None:
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("creeping_blight_active"):
                    applies = True
                    owner_id = str(sr.get("creeping_blight_owner", "") or "")
                    army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                    player = getattr(army, "player", None) if army is not None else None
                    attacker_owner = str(getattr(player, "id", "") or "") if player is not None else ""
                    game_local = getattr(player, "game", None) if player is not None else None
                    if owner_id and attacker_owner and owner_id != attacker_owner:
                        applies = False
                    exp_phase = str(sr.get("creeping_blight_expires_phase", "") or "").strip().upper()
                    phase_name = str(getattr(getattr(game_local, "phase", None), "name", "") or "").strip().upper()
                    if applies and exp_phase and phase_name and exp_phase != phase_name:
                        applies = False
                    try:
                        marked_turn = int(sr.get("creeping_blight_turn", 0) or 0)
                    except Exception:
                        marked_turn = 0
                    try:
                        current_turn = int(getattr(game_local, "turn", 0) or 0)
                    except Exception:
                        current_turn = 0
                    if applies and marked_turn and current_turn and marked_turn != current_turn:
                        applies = False
                    if applies and self._target_is_afflicted(target, source_unit=root):
                        source = str(sr.get("creeping_blight_source", "") or "Creeping Blight").strip() or "Creeping Blight"
                        mods["reroll_hit_full"] = True
                        reroll_hit_full_reasons.append(f"{source}: re-roll Hit roll vs Afflicted target")
        except Exception:
            pass

        # Steeped in Suffering: +1 to hit vs targets below Starting Strength.
        try:
            has_steeped = bool(
                self._attached_unit_has_active_enhancement(
                    "enhancement_steeped_in_suffering",
                    enhancement_id="000009998002",
                    enhancement_name="Steeped in Suffering",
                )
            )
            if has_steeped and target is not None:
                target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                if target_root is not None and bool(target_root.is_below_starting_strength()):
                    mods["hit"] += 1
                    hit_reasons.append("+1 to hit from Steeped in Suffering (vs targets below Starting Strength)")
        except Exception:
            pass
        try:
            applies, source = self._court_prideful_superiority_active(target=target)
            if applies:
                mods["reroll_hit_full"] = True
                reroll_hit_full_reasons.append(f"{source}: re-roll Hit roll vs CHARACTER target")
        except Exception:
            pass
        try:
            applies, source = self._coterie_martial_perfection_active()
            if applies:
                mods["reroll_hit_full"] = True
                reroll_hit_full_reasons.append(f"{source}: re-roll Hit roll")
        except Exception:
            pass

        mods["reroll_hit_values"] = tuple(sorted(reroll_hit_values))
        mods["reroll_hit_ones"] = bool(1 in reroll_hit_values)
        mods["crit_hit_threshold"] = crit_hit_threshold
        mods["hit_reasons"] = tuple(hit_reasons)
        mods["reroll_hit_reasons"] = tuple(reroll_hit_reasons)
        mods["reroll_hit_full_reasons"] = tuple(reroll_hit_full_reasons)
        mods["crit_hit_reasons"] = tuple(crit_hit_reasons)
        return mods

    def _gsc_primed_and_readied_context(self, *, game=None) -> Optional[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("gsc_primed_and_readied_active")):
            return None
        source = str(sr.get("gsc_primed_and_readied_source", "") or "PRIMED AND READIED").strip() or "PRIMED AND READIED"
        try:
            threshold = int(sr.get("gsc_primed_and_readied_crit_threshold", 5) or 5)
        except Exception:
            threshold = 5
        threshold = max(2, min(6, int(threshold)))
        if game is None:
            return {"crit_threshold": threshold, "source": source}

        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        expected_phase = str(sr.get("gsc_primed_and_readied_expires_phase", "") or "").strip().upper()
        if expected_phase and phase_name and expected_phase != phase_name:
            return None
        try:
            effect_turn = int(sr.get("gsc_primed_and_readied_turn", 0) or 0)
        except Exception:
            effect_turn = 0
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if effect_turn and current_turn and effect_turn != current_turn:
            return None
        effect_owner = str(sr.get("gsc_primed_and_readied_turn_owner", "") or "")
        if effect_owner:
            try:
                current_owner = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "")
            except Exception:
                current_owner = ""
            if current_owner and effect_owner != current_owner:
                return None
        return {"crit_threshold": threshold, "source": source}

    def _gsc_coordinated_trap_context(self, *, game=None) -> Optional[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("gsc_coordinated_trap_active")):
            return None
        target_id = str(sr.get("gsc_coordinated_trap_target_id", "") or "")
        if not target_id:
            return None
        try:
            wound_bonus = int(sr.get("gsc_coordinated_trap_wound_bonus", 1) or 1)
        except Exception:
            wound_bonus = 1
        source = str(sr.get("gsc_coordinated_trap_source", "") or "COORDINATED TRAP").strip() or "COORDINATED TRAP"
        if game is None:
            return {
                "target_id": target_id,
                "wound_bonus": int(wound_bonus),
                "target_lock": bool(sr.get("gsc_coordinated_trap_target_lock", True)),
                "source": source,
            }

        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        expected_phase = str(sr.get("gsc_coordinated_trap_expires_phase", "") or "").strip().upper()
        if expected_phase and phase_name and expected_phase != phase_name:
            return None
        try:
            effect_turn = int(sr.get("gsc_coordinated_trap_turn", 0) or 0)
        except Exception:
            effect_turn = 0
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if effect_turn and current_turn and effect_turn != current_turn:
            return None
        effect_owner = str(sr.get("gsc_coordinated_trap_turn_owner", "") or "")
        if effect_owner:
            try:
                current_owner = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "")
            except Exception:
                current_owner = ""
            if current_owner and effect_owner != current_owner:
                return None
        return {
            "target_id": target_id,
            "wound_bonus": int(wound_bonus),
            "target_lock": bool(sr.get("gsc_coordinated_trap_target_lock", True)),
            "source": source,
        }

    def _gsc_coordinated_trap_target_locked_to(self, target_unit, *, game=None) -> bool:
        context = self._gsc_coordinated_trap_context(game=game)
        if not isinstance(context, dict):
            return True
        if not bool(context.get("target_lock", True)):
            return True
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        current_target_id = str(get_entity_id(target_root) or "")
        expected_target_id = str(context.get("target_id", "") or "")
        if expected_target_id and current_target_id and expected_target_id != current_target_id:
            return False
        return True

    def get_unit_wound_reroll_modifiers(self, attack_type: str, *, target=None) -> dict:
        """
        Return unit-level wound modifiers for this attached unit, parsed via attack_roll_parser.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        rules = self._get_unit_attack_roll_rules()

        mods = {
            "wound": 0,
            "reroll_wound_ones": False,
            "reroll_wound_values": (),
            "reroll_wound_full": False,
            "crit_wound_threshold": None,
            "wound_reasons": (),
            "reroll_wound_reasons": (),
            "reroll_wound_full_reasons": (),
            "crit_wound_reasons": (),
        }

        wound_reasons: list[str] = []
        reroll_wound_reasons: list[str] = []
        reroll_wound_full_reasons: list[str] = []
        crit_wound_reasons: list[str] = []
        reroll_wound_values: set[int] = set()
        crit_wound_threshold = None

        def _cond_suffix(cond: Optional[AttackRollCondition]) -> str:
            if not cond:
                return ""
            parts = []
            if cond.target_battleshocked:
                parts.append("vs Battle-shocked targets")
            if cond.attacker_below_starting_strength:
                parts.append("while below Starting Strength")
            if cond.attacker_below_half_strength:
                parts.append("while below Half-strength")
            if cond.attacker_charged_this_turn:
                parts.append("after making a Charge move this turn")
            if cond.attacker_contains_model_keywords_any:
                kw = "/".join(k.upper() for k in cond.attacker_contains_model_keywords_any)
                parts.append(f"while containing {kw} model")
            if cond.attacker_within_objective_controlled:
                parts.append("while within a controlled objective")
            if cond.target_within_objective:
                parts.append("vs targets within objective range")
            if cond.target_within_objective_not_controlled:
                parts.append("vs targets within objective range you do not control")
            if cond.target_within_range is not None:
                parts.append(f"vs targets within {cond.target_within_range}\"")
            if cond.target_isolated_within is not None:
                parts.append(f"vs isolated targets (no other enemy units within {cond.target_isolated_within}\")")
            if cond.target_can_fly is True:
                parts.append("vs FLY targets")
            if cond.target_can_fly is False:
                parts.append("vs non-FLY targets")
            if cond.target_keywords_any:
                if set(cond.target_keywords_any) == {"character"}:
                    parts.append("vs CHARACTER targets")
                elif set(cond.target_keywords_any) == {"monster", "vehicle"}:
                    parts.append("vs MONSTER/VEHICLE targets")
            if cond.target_below_starting_strength:
                parts.append("vs targets below Starting Strength")
            if cond.target_below_half_strength:
                parts.append("vs targets below Half-strength")
            if cond.target_exclude_keywords_any:
                parts.append("excluding " + ", ".join(cond.target_exclude_keywords_any))
            if not parts:
                return ""
            return " (" + "; ".join(parts) + ")"

        for rule, name in list(rules or []):
            if atype != "any" and rule.attack_type not in ("any", atype):
                continue
            for eff in rule.effects:
                if not self._attack_condition_met(eff.condition, target=target, source_unit=root):
                    continue
                if eff.roll != "wound":
                    continue
                label = name or "Unit ability"
                if eff.kind in ("add", "sub"):
                    val = int(eff.value or 0)
                    if eff.kind == "sub":
                        val = -val
                    mods["wound"] += val
                    wound_reasons.append(f"{val:+d} to wound from {label}{_cond_suffix(eff.condition)}")
                elif eff.kind == "reroll":
                    if eff.reroll_full:
                        mods["reroll_wound_full"] = True
                        reroll_wound_full_reasons.append(f"{label}: re-roll Wound roll{_cond_suffix(eff.condition)}")
                    if eff.reroll_values:
                        reroll_wound_values.update(int(v) for v in eff.reroll_values)
                        reroll_wound_reasons.append(
                            f"{label}: re-roll Wound rolls of {', '.join(str(v) for v in sorted(eff.reroll_values))}{_cond_suffix(eff.condition)}"
                        )
                elif eff.kind == "crit" and eff.critical_threshold:
                    crit_wound_threshold = eff.critical_threshold if crit_wound_threshold is None else min(crit_wound_threshold, eff.critical_threshold)
                    crit_wound_reasons.append(f"{label}: critical wound on {eff.critical_threshold}+{_cond_suffix(eff.condition)}")

        choice = ""
        try:
            choice_fn = getattr(self, "_path_of_warrior_choice", None)
            if callable(choice_fn):
                choice = choice_fn()
        except Exception:
            choice = ""
        if choice in ("WOUND", "BOTH"):
            reroll_wound_values.add(1)
            reroll_wound_reasons.append("Path of the Warrior: re-roll Wound rolls of 1")

        choice = ""
        try:
            choice_fn = getattr(self, "_dance_of_death_choice", None)
            if callable(choice_fn):
                choice = choice_fn()
        except Exception:
            choice = ""
        if choice in ("VILLAIN", "ALL"):
            mods["wound"] += 1
            wound_reasons.append("Dance of Death (Villain's Doom): +1 to wound")

        # Angelic Inheritors: Carmine Wrath (character units) re-roll Wound rolls of 1.
        try:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if sm_mgr is not None and getattr(sm_mgr, "legacy_of_the_angel_carmine_wrath_applies", None):
                if sm_mgr.legacy_of_the_angel_carmine_wrath_applies(root):
                    reroll_wound_values.add(1)
                    reroll_wound_reasons.append("Carmine Wrath: re-roll Wound rolls of 1")
        except Exception:
            pass

        # Hammer of Avernii: Calculated Annihilation (vs Oath target) re-roll Wound rolls of 1.
        try:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            oath_mgr = getattr(army, "oath_of_moment", None) if army is not None else None
            apply_fn = (
                getattr(oath_mgr, "calculated_annihilation_reroll_wound_ones_applies", None)
                if oath_mgr is not None
                else None
            )
            if callable(apply_fn) and apply_fn(root, target):
                reroll_wound_values.add(1)
                reroll_wound_reasons.append("Calculated Annihilation: re-roll Wound rolls of 1")
        except Exception:
            pass

        # Emperor's Shield: Wrath of Dorn (vs Oath target) re-roll Wound rolls of 1;
        # Darnath Lysander units re-roll the Wound roll instead.
        try:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            oath_mgr = getattr(army, "oath_of_moment", None) if army is not None else None
            apply_ones_fn = getattr(oath_mgr, "wrath_of_dorn_reroll_wound_ones_applies", None) if oath_mgr is not None else None
            apply_full_fn = getattr(oath_mgr, "wrath_of_dorn_reroll_wound_full_applies", None) if oath_mgr is not None else None
            if callable(apply_ones_fn) and apply_ones_fn(root, target):
                reroll_wound_values.add(1)
                reroll_wound_reasons.append("Wrath of Dorn: re-roll Wound rolls of 1")
            if callable(apply_full_fn) and apply_full_fn(root, target):
                mods["reroll_wound_full"] = True
                reroll_wound_full_reasons.append("Wrath of Dorn: re-roll Wound roll")
        except Exception:
            pass

        # The Lost Brethren: A Noble Death in Combat (Death Company melee attacks).
        try:
            if atype in ("any", "melee"):
                army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
                mode_fn = getattr(sm_mgr, "a_noble_death_in_combat_reroll_mode", None) if sm_mgr is not None else None
                mode = str(mode_fn(root) if callable(mode_fn) else "").strip().lower()
                if mode == "full":
                    mods["reroll_wound_full"] = True
                    reroll_wound_full_reasons.append("A Noble Death in Combat: re-roll Wound roll")
                elif mode == "ones":
                    reroll_wound_values.add(1)
                    reroll_wound_reasons.append("A Noble Death in Combat: re-roll Wound rolls of 1")
        except Exception:
            pass

        # Needgaard Oathband: HUNTR'S MARK grants ranged re-roll Wound rolls of 1.
        try:
            active_fn = getattr(root, "_needgaard_huntrs_mark_active_for_shooting", None)
            if atype in ("any", "ranged") and callable(active_fn) and active_fn():
                reroll_wound_values.add(1)
                reroll_wound_reasons.append("HUNTR'S MARK: re-roll Wound rolls of 1")
        except Exception:
            pass

        game = None
        army = None
        get_parent_army = getattr(root, "get_parent_army", None)
        if callable(get_parent_army):
            army = get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
        arch_fn = getattr(dg_mgr, "arch_contaminator_reroll_wounds", None) if dg_mgr is not None else None
        if callable(arch_fn) and arch_fn(root, game=game):
            mods["reroll_wound_full"] = True
            reroll_wound_full_reasons.append(
                "Arch Contaminator: re-roll Wound rolls while within a controlled objective"
            )

        # Hallowed Martyrs: RIGHTEOUS VENGEANCE (melee wound re-rolls vs Below Half-strength targets).
        try:
            if atype in ("any", "melee") and target is not None:
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("righteous_vengeance_active"):
                    active = True
                    owner_id = str(sr.get("righteous_vengeance_turn_owner", "") or "")
                    source = str(sr.get("righteous_vengeance_source", "") or "RIGHTEOUS VENGEANCE").strip() or "RIGHTEOUS VENGEANCE"
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
                    expires_phase = str(sr.get("righteous_vengeance_expires_phase", "") or "").strip().upper()
                    if expires_phase and phase_name and expires_phase != phase_name:
                        active = False
                    try:
                        effect_turn = int(sr.get("righteous_vengeance_turn", 0) or 0)
                    except Exception:
                        effect_turn = 0
                    try:
                        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                    except Exception:
                        current_turn = 0
                    if effect_turn and current_turn and effect_turn != current_turn:
                        active = False
                    attacker_owner = str(getattr(getattr(army, "player", None), "id", "") or "") if army is not None else ""
                    if owner_id and attacker_owner and owner_id != attacker_owner:
                        active = False
                    if active:
                        target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                        below_half = False
                        if target_root is not None:
                            below_half_fn = getattr(target_root, "is_below_half_strength", None)
                            if callable(below_half_fn):
                                try:
                                    below_half = bool(below_half_fn())
                                except Exception:
                                    below_half = False
                        if below_half:
                            mods["reroll_wound_full"] = True
                            reroll_wound_full_reasons.append(f"{source}: re-roll Wound roll vs Below Half-strength target")
        except Exception:
            pass

        # Virulent Vectorium: selected unit gains ranged wound rerolls vs Afflicted targets this phase.
        try:
            if atype in ("any", "ranged") and target is not None:
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("creeping_blight_active"):
                    applies = True
                    owner_id = str(sr.get("creeping_blight_owner", "") or "")
                    attacker_owner = str(getattr(getattr(army, "player", None), "id", "") or "") if army is not None else ""
                    if owner_id and attacker_owner and owner_id != attacker_owner:
                        applies = False
                    exp_phase = str(sr.get("creeping_blight_expires_phase", "") or "").strip().upper()
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if applies and exp_phase and phase_name and exp_phase != phase_name:
                        applies = False
                    try:
                        marked_turn = int(sr.get("creeping_blight_turn", 0) or 0)
                    except Exception:
                        marked_turn = 0
                    try:
                        current_turn = int(getattr(game, "turn", 0) or 0)
                    except Exception:
                        current_turn = 0
                    if applies and marked_turn and current_turn and marked_turn != current_turn:
                        applies = False
                    if applies and self._target_is_afflicted(target, source_unit=root):
                        source = str(sr.get("creeping_blight_source", "") or "Creeping Blight").strip() or "Creeping Blight"
                        mods["reroll_wound_full"] = True
                        reroll_wound_full_reasons.append(f"{source}: re-roll Wound roll vs Afflicted target")
        except Exception:
            pass

        # Misfortune: this unit's attacks suffer -1 to wound.
        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("misfortune_active"):
                penalty = int(sr.get("misfortune_penalty", -1) or -1)
                if penalty:
                    mods["wound"] += int(penalty)
                    source = str(sr.get("misfortune_source", "") or "Misfortune").strip() or "Misfortune"
                    wound_reasons.append(f"{int(penalty):+d} to wound from {source}")
        except Exception:
            pass

        # Fight phase: temporary melee wound penalties (e.g., The Eternal Dance).
        try:
            if atype in ("melee", "any"):
                sr = getattr(root, "special_rules", None)
                entries = list(sr.get("fight_phase_melee_wound_penalties", []) or []) if isinstance(sr, dict) else []
                if entries:
                    phase_name = ""
                    current_turn = 0
                    if game is not None:
                        try:
                            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            phase_name = ""
                        try:
                            current_turn = int(getattr(game, "turn", 0) or 0)
                        except Exception:
                            current_turn = 0
                    if phase_name and phase_name != "FIGHT_PHASE":
                        sr.pop("fight_phase_melee_wound_penalties", None)
                        root.special_rules = sr
                    else:
                        kept = []
                        for entry in entries:
                            if not isinstance(entry, dict):
                                continue
                            if current_turn:
                                try:
                                    if int(entry.get("turn", 0) or 0) not in (0, current_turn):
                                        continue
                                except Exception:
                                    pass
                            kept.append(entry)
                            try:
                                pen = int(entry.get("penalty", 0) or 0)
                            except Exception:
                                pen = 0
                            if pen:
                                mods["wound"] -= int(pen)
                                source = str(entry.get("source", "") or "Fight phase melee penalty").strip()
                                wound_reasons.append(f"{-int(pen):+d} to wound from {source}")
                        if isinstance(sr, dict):
                            sr["fight_phase_melee_wound_penalties"] = kept
                            root.special_rules = sr
        except Exception:
            pass

        # Herald of Ynnead: reroll wound rolls of 1 vs marked target (friendly AELDARI only).
        try:
            if target is not None:
                target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                tsr = getattr(target_root, "special_rules", None)
                if isinstance(tsr, dict) and tsr.get("herald_of_ynnead_active"):
                    exp_phase = str(tsr.get("herald_of_ynnead_expires_phase", "") or "").strip().upper()
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if not exp_phase or exp_phase == phase_name:
                        try:
                            marked_turn = int(tsr.get("herald_of_ynnead_turn", 0) or 0)
                        except Exception:
                            marked_turn = 0
                        try:
                            current_turn = int(getattr(game, "turn", 0) or 0)
                        except Exception:
                            current_turn = 0
                        if not (marked_turn and current_turn and marked_turn != current_turn):
                            owner_id = str(tsr.get("herald_of_ynnead_owner", "") or "")
                            try:
                                attacker_owner = str(getattr(getattr(root.get_parent_army(), "player", None), "id", "") or "")
                            except Exception:
                                attacker_owner = ""
                            if owner_id and attacker_owner == owner_id:
                                keyword = str(tsr.get("herald_of_ynnead_keyword", "") or "aeldari").strip().lower()
                                has_keyword = False
                                try:
                                    if keyword and root.has_any_keyword(keyword):
                                        has_keyword = True
                                except Exception:
                                    has_keyword = False
                                if has_keyword:
                                    reroll_wound_values.add(1)
                                    source = str(tsr.get("herald_of_ynnead_source", "") or "Herald of Ynnead").strip() or "Herald of Ynnead"
                                    reroll_wound_reasons.append(f"{source}: re-roll Wound rolls of 1")
        except Exception:
            pass

        # Spirit Thief: reroll wound rolls of 1 vs marked VEHICLE (friendly HERETIC ASTARTES only).
        try:
            if target is not None:
                target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                tsr = getattr(target_root, "special_rules", None)
                if isinstance(tsr, dict) and tsr.get("spirit_thief_active"):
                    exp_phase = str(tsr.get("spirit_thief_expires_phase", "") or "").strip().upper()
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if not exp_phase or exp_phase == phase_name:
                        try:
                            marked_turn = int(tsr.get("spirit_thief_turn", 0) or 0)
                        except Exception:
                            marked_turn = 0
                        try:
                            current_turn = int(getattr(game, "turn", 0) or 0)
                        except Exception:
                            current_turn = 0
                        if not (marked_turn and current_turn and marked_turn != current_turn):
                            owner_id = str(tsr.get("spirit_thief_owner", "") or "")
                            try:
                                attacker_owner = str(getattr(getattr(root.get_parent_army(), "player", None), "id", "") or "")
                            except Exception:
                                attacker_owner = ""
                            if owner_id and attacker_owner == owner_id:
                                keyword = str(tsr.get("spirit_thief_keyword", "") or "heretic astartes").strip().lower()
                                has_keyword = False
                                try:
                                    if keyword and root.has_any_keyword(keyword):
                                        has_keyword = True
                                except Exception:
                                    has_keyword = False
                                if has_keyword:
                                    reroll_wound_values.add(1)
                                    source = str(tsr.get("spirit_thief_source", "") or "Spirit Thief").strip() or "Spirit Thief"
                                    reroll_wound_reasons.append(f"{source}: re-roll Wound rolls of 1")
        except Exception:
            pass

        # Bringers of Change: ranged attacks re-roll wound 1s, or full wound re-rolls
        # vs targets within objective range you do not control.
        has_bringers = bool(getattr(root, "has_bringers_of_change", lambda: False)())
        if atype in ("any", "ranged") and has_bringers:
            source = "Bringers of Change"
            reroll_wound_values.add(1)
            reroll_wound_reasons.append(f"{source}: re-roll Wound rolls of 1 (ranged)")
            if target is not None and bool(self._target_within_uncontrolled_objective_range(target)):
                mods["reroll_wound_full"] = True
                reroll_wound_full_reasons.append(
                    f"{source}: re-roll Wound roll vs targets within objective range you do not control"
                )

        # PIRATES' DUE: melee attacks re-roll Wound rolls of 1; ANHRATHE get full wound re-rolls
        # when targeting enemy units within range of any objective marker.
        try:
            if atype in ("any", "melee"):
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("aeldari_pirates_due_active"):
                    active = True
                    owner_id = str(sr.get("aeldari_pirates_due_turn_owner", "") or "")
                    try:
                        effect_turn = int(sr.get("aeldari_pirates_due_turn", 0) or 0)
                    except Exception:
                        effect_turn = 0
                    expires_phase = str(sr.get("aeldari_pirates_due_expires_phase", "") or "").strip().upper()
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
                    current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                    attacker_owner = str(getattr(getattr(army, "player", None), "id", "") or "") if army is not None else ""
                    if owner_id and attacker_owner and owner_id != attacker_owner:
                        active = False
                    if active and effect_turn and current_turn and effect_turn != current_turn:
                        active = False
                    if active and expires_phase and phase_name and expires_phase != phase_name:
                        active = False
                    if active:
                        source = str(sr.get("aeldari_pirates_due_source", "") or "PIRATES' DUE").strip() or "PIRATES' DUE"
                        reroll_wound_values.add(1)
                        reroll_wound_reasons.append(f"{source}: re-roll Wound rolls of 1")
                        has_anhrathe = False
                        try:
                            has_anhrathe = bool(root.has_any_keyword("ANHRATHE"))
                        except Exception:
                            has_anhrathe = False
                        if has_anhrathe and target is not None:
                            game_map = getattr(game, "map", None) if game is not None else None
                            if bool(self._target_within_objective_range(target, game_map=game_map)):
                                mods["reroll_wound_full"] = True
                                reroll_wound_full_reasons.append(
                                    f"{source}: re-roll Wound roll vs targets within objective range"
                                )
        except Exception:
            pass

        # WARDING SALVOES: re-roll Wound rolls against enemy units within objective range.
        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("aeldari_warding_salvoes_active") and target is not None:
                owner_id = str(sr.get("aeldari_warding_salvoes_turn_owner", "") or "")
                effect_turn = int(sr.get("aeldari_warding_salvoes_turn", 0) or 0)
                expires_phase = str(sr.get("aeldari_warding_salvoes_expires_phase", "") or "").strip().upper()
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
                current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                attacker_owner = str(getattr(getattr(army, "player", None), "id", "") or "") if army is not None else ""
                active = True
                if owner_id and attacker_owner and owner_id != attacker_owner:
                    active = False
                if active and effect_turn and current_turn and effect_turn != current_turn:
                    active = False
                if active and expires_phase and phase_name and expires_phase != phase_name:
                    active = False
                if active:
                    game_map = getattr(game, "map", None) if game is not None else None
                    if bool(self._target_within_objective_range(target, game_map=game_map)):
                        source = str(sr.get("aeldari_warding_salvoes_source", "") or "WARDING SALVOES").strip() or "WARDING SALVOES"
                        mods["reroll_wound_full"] = True
                        reroll_wound_full_reasons.append(f"{source}: re-roll Wound roll vs targets within objective range")
        except Exception:
            pass

        # DEATH FROM ON HIGH: re-roll Wound rolls this phase.
        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("aeldari_death_from_on_high_active"):
                owner_id = str(sr.get("aeldari_death_from_on_high_turn_owner", "") or "")
                effect_turn = int(sr.get("aeldari_death_from_on_high_turn", 0) or 0)
                expires_phase = str(sr.get("aeldari_death_from_on_high_expires_phase", "") or "").strip().upper()
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
                current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                attacker_owner = str(getattr(getattr(army, "player", None), "id", "") or "") if army is not None else ""
                active = True
                if owner_id and attacker_owner and owner_id != attacker_owner:
                    active = False
                if active and effect_turn and current_turn and effect_turn != current_turn:
                    active = False
                if active and expires_phase and phase_name and expires_phase != phase_name:
                    active = False
                if active:
                    source = (
                        str(sr.get("aeldari_death_from_on_high_source", "") or "DEATH FROM ON HIGH").strip()
                        or "DEATH FROM ON HIGH"
                    )
                    mods["reroll_wound_full"] = True
                    reroll_wound_full_reasons.append(f"{source}: re-roll Wound roll")
        except Exception:
            pass

        # Fire Support: disembarked unit re-rolls wound rolls vs marked target.
        try:
            if target is not None:
                transport_id = str(getattr(root.round_state, "disembarked_from_transport_id", "") or "")
                if transport_id:
                    transport = None
                    if game is not None and hasattr(game, "_resolve_unit_by_id"):
                        transport = game._resolve_unit_by_id(transport_id)
                    if transport is None and army is not None:
                        for cand in list(getattr(army, "units", []) or []):
                            if str(getattr(cand, "_id", "")) == transport_id or str(getattr(cand, "id", "")) == transport_id:
                                transport = cand
                                break
                    if transport is not None:
                        tsr = getattr(transport, "special_rules", None)
                        if isinstance(tsr, dict) and tsr.get("post_shoot_disembark_wound_reroll_active"):
                            exp_phase = str(tsr.get("post_shoot_disembark_wound_reroll_expires_phase", "") or "").strip().upper()
                            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                            if not exp_phase or exp_phase == phase_name:
                                try:
                                    marked_turn = int(tsr.get("post_shoot_disembark_wound_reroll_turn", 0) or 0)
                                except Exception:
                                    marked_turn = 0
                                try:
                                    current_turn = int(getattr(game, "turn", 0) or 0)
                                except Exception:
                                    current_turn = 0
                                if not (marked_turn and current_turn and marked_turn != current_turn):
                                    owner_id = str(tsr.get("post_shoot_disembark_wound_reroll_owner", "") or "")
                                    try:
                                        attacker_owner = str(getattr(getattr(root.get_parent_army(), "player", None), "id", "") or "")
                                    except Exception:
                                        attacker_owner = ""
                                    if not (owner_id and attacker_owner and owner_id != attacker_owner):
                                        target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                                        target_id = str(get_entity_id(target_root) or "")
                                        if target_id and str(tsr.get("post_shoot_disembark_wound_reroll_target_id", "") or "") == target_id:
                                            mods["reroll_wound_full"] = True
                                            source = str(tsr.get("post_shoot_disembark_wound_reroll_source", "") or "Fire Support").strip() or "Fire Support"
                                            reroll_wound_full_reasons.append(f"{source}: re-roll Wound roll")
        except Exception:
            pass

        # Target buffs: Symphony of Pain (re-roll Wound rolls vs marked target).
        try:
            if target is not None:
                t_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                sr = getattr(t_root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("symphony_of_pain_active"):
                    owner_id = str(sr.get("symphony_of_pain_owner", "") or "")
                    try:
                        turn = int(sr.get("symphony_of_pain_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    game = None
                    try:
                        game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                    except Exception:
                        game = None
                    if game is not None and owner_id:
                        try:
                            current_id = str(getattr(game.get_current_player(), "id", "") or "")
                        except Exception:
                            current_id = ""
                        try:
                            if int(getattr(game, "turn", 0) or 0) != turn or (current_id and current_id != owner_id):
                                for k in (
                                    "symphony_of_pain_active",
                                    "symphony_of_pain_owner",
                                    "symphony_of_pain_turn",
                                    "symphony_of_pain_source",
                                    "symphony_of_pain_keywords",
                                ):
                                    sr.pop(k, None)
                                t_root.special_rules = sr
                                sr = None
                        except Exception:
                            pass
                    if isinstance(sr, dict) and sr.get("symphony_of_pain_active"):
                        applies = True
                        if owner_id:
                            try:
                                army = root.get_parent_army()
                                player = getattr(army, "player", None) if army is not None else None
                            except Exception:
                                player = None
                            if player is not None and str(getattr(player, "id", "") or "") != owner_id:
                                applies = False
                        keywords = list(sr.get("symphony_of_pain_keywords", []) or [])
                        if applies and keywords:
                            for kw in keywords:
                                try:
                                    if not root.has_any_keyword(str(kw or "")):
                                        applies = False
                                        break
                                except Exception:
                                    applies = False
                                    break
                        if applies:
                            source = str(sr.get("symphony_of_pain_source", "") or "Symphony of Pain").strip() or "Symphony of Pain"
                            mods["reroll_wound_full"] = True
                            reroll_wound_full_reasons.append(f"{source}: re-roll Wound roll")
        except Exception:
            pass

        # Target buffs: post-shoot keyword wound reroll (e.g., Death's Heads).
        try:
            if target is not None:
                t_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                sr = getattr(t_root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("post_shoot_keyword_wound_reroll_active"):
                    owner_id = str(sr.get("post_shoot_keyword_wound_reroll_owner", "") or "")
                    try:
                        turn = int(sr.get("post_shoot_keyword_wound_reroll_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    game = None
                    try:
                        game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                    except Exception:
                        game = None
                    if game is not None and owner_id:
                        try:
                            current_id = str(getattr(game.get_current_player(), "id", "") or "")
                        except Exception:
                            current_id = ""
                        try:
                            if int(getattr(game, "turn", 0) or 0) != turn or (current_id and current_id != owner_id):
                                for k in (
                                    "post_shoot_keyword_wound_reroll_active",
                                    "post_shoot_keyword_wound_reroll_owner",
                                    "post_shoot_keyword_wound_reroll_turn",
                                    "post_shoot_keyword_wound_reroll_source",
                                    "post_shoot_keyword_wound_reroll_phrase",
                                ):
                                    sr.pop(k, None)
                                t_root.special_rules = sr
                                sr = None
                        except Exception:
                            pass
                    if isinstance(sr, dict) and sr.get("post_shoot_keyword_wound_reroll_active"):
                        applies = True
                        if owner_id:
                            try:
                                army = root.get_parent_army()
                                player = getattr(army, "player", None) if army is not None else None
                            except Exception:
                                player = None
                            if player is not None and str(getattr(player, "id", "") or "") != owner_id:
                                applies = False
                        phrase = str(sr.get("post_shoot_keyword_wound_reroll_phrase", "") or "").strip()
                        if applies and phrase:
                            try:
                                if not self._unit_matches_keyword_phrase(root, phrase, use_effective=True):
                                    applies = False
                            except Exception:
                                applies = False
                        if applies:
                            source = str(sr.get("post_shoot_keyword_wound_reroll_source", "") or "Post-shoot Wound reroll").strip()
                            mods["reroll_wound_full"] = True
                            reroll_wound_full_reasons.append(f"{source}: re-roll Wound roll")
        except Exception:
            pass

        # SANCTIFIED KILL ZONE: wound re-rolls in current phase.
        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("sanctified_kill_zone_active"):
                owner_id = str(sr.get("sanctified_kill_zone_turn_owner", "") or "")
                effect_turn = int(sr.get("sanctified_kill_zone_turn", 0) or 0)
                expires_phase = str(sr.get("sanctified_kill_zone_expires_phase", "") or "").strip().upper()
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
                current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                attacker_owner = str(getattr(getattr(army, "player", None), "id", "") or "") if army is not None else ""
                active = True
                if owner_id and attacker_owner and owner_id != attacker_owner:
                    active = False
                if active and effect_turn and current_turn and effect_turn != current_turn:
                    active = False
                if active and expires_phase and phase_name and expires_phase != phase_name:
                    active = False
                if active:
                    source = str(sr.get("sanctified_kill_zone_source", "") or "Sanctified Kill Zone").strip()
                    if bool(sr.get("sanctified_kill_zone_reroll_full")):
                        mods["reroll_wound_full"] = True
                        reroll_wound_full_reasons.append(f"{source}: re-roll Wound roll")
                    else:
                        reroll_wound_values.add(1)
                        reroll_wound_reasons.append(f"{source}: re-roll Wound rolls of 1")
        except Exception:
            pass

        # Oathbound Speculator: bearer's unit re-rolls wound rolls of 1; optional +1 to wound until end of phase.
        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_oathbound_speculator"):
                bearer = getattr(root, "_get_enhancement_bearer_model", lambda: None)()
                if bearer is not None:
                    source = (
                        str(sr.get("enhancement_oathbound_speculator_source", "") or "Oathbound Speculator").strip()
                        or "Oathbound Speculator"
                    )
                    reroll_wound_values.add(1)
                    reroll_wound_reasons.append(f"{source}: re-roll Wound rolls of 1")
                    if bool(sr.get("enhancement_oathbound_speculator_wound_bonus_active")):
                        owner_id = str(sr.get("enhancement_oathbound_speculator_turn_owner", "") or "")
                        effect_turn = int(sr.get("enhancement_oathbound_speculator_turn", 0) or 0)
                        expires_phase = str(sr.get("enhancement_oathbound_speculator_expires_phase", "") or "").strip().upper()
                        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
                        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                        attacker_owner = (
                            str(getattr(getattr(army, "player", None), "id", "") or "") if army is not None else ""
                        )
                        active = True
                        if owner_id and attacker_owner and owner_id != attacker_owner:
                            active = False
                        if active and effect_turn and current_turn and effect_turn != current_turn:
                            active = False
                        if active and expires_phase and phase_name and expires_phase != phase_name:
                            active = False
                        if active:
                            bonus = int(sr.get("enhancement_oathbound_speculator_wound_bonus", 1) or 1)
                            if bonus:
                                mods["wound"] += int(bonus)
                                wound_reasons.append(f"{int(bonus):+d} to wound from {source}")
        except Exception:
            pass

        # Steeped in Suffering: +1 to wound vs targets below Half-strength.
        try:
            has_steeped = bool(
                self._attached_unit_has_active_enhancement(
                    "enhancement_steeped_in_suffering",
                    enhancement_id="000009998002",
                    enhancement_name="Steeped in Suffering",
                )
            )
            if has_steeped and target is not None:
                target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                if target_root is not None and bool(target_root.is_below_half_strength()):
                    mods["wound"] += 1
                    wound_reasons.append("+1 to wound from Steeped in Suffering (vs targets below Half-strength)")
        except Exception:
            pass
        try:
            applies, source = self._court_prideful_superiority_active(target=target, game=game)
            if applies:
                mods["reroll_wound_full"] = True
                reroll_wound_full_reasons.append(f"{source}: re-roll Wound roll vs CHARACTER target")
        except Exception:
            pass
        try:
            applies, source = self._imperial_agents_prime_target_active(game=game)
            if applies and target is not None:
                try:
                    target_root = target.get_attached_unit_root()
                except Exception:
                    target_root = target
                if target_root is not None and self._entity_has_keyword_for_empyric(target_root, "CHARACTER"):
                    reroll_wound_values.add(1)
                    reroll_wound_reasons.append(f"{source}: re-roll Wound rolls of 1 vs CHARACTER target")
        except Exception:
            pass

        # Host of Ascension: Coordinated Trap (+1 to wound, target locked to marked enemy).
        try:
            if target is not None:
                context = self._gsc_coordinated_trap_context(game=game)
                if isinstance(context, dict):
                    target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                    target_id = str(get_entity_id(target_root) or "")
                    expected_target_id = str(context.get("target_id", "") or "")
                    if target_id and expected_target_id and target_id == expected_target_id:
                        bonus = int(context.get("wound_bonus", 0) or 0)
                        if bonus:
                            mods["wound"] += int(bonus)
                            source = str(context.get("source", "") or "COORDINATED TRAP").strip() or "COORDINATED TRAP"
                            wound_reasons.append(f"{int(bonus):+d} to wound from {source}")
        except Exception:
            pass

        mods["reroll_wound_values"] = tuple(sorted(reroll_wound_values))
        mods["reroll_wound_ones"] = bool(1 in reroll_wound_values)
        mods["crit_wound_threshold"] = crit_wound_threshold
        mods["wound_reasons"] = tuple(wound_reasons)
        mods["reroll_wound_reasons"] = tuple(reroll_wound_reasons)
        mods["reroll_wound_full_reasons"] = tuple(reroll_wound_full_reasons)
        mods["crit_wound_reasons"] = tuple(crit_wound_reasons)
        return mods

    def get_melee_damage_bonus_vs_monster_vehicle(self) -> int:
        """
        Return bonus Damage for melee attacks that target MONSTER or VEHICLE units.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "melee_damage_bonus_vs_monster_vehicle"
        if cache_key in getattr(root, "_ability_cache", {}):
            return int(root._ability_cache[cache_key] or 0)

        bonus = 0
        seen: set[tuple[str, str]] = set()

        def _monster_vehicle_only_condition(cond: Optional[AttackRollCondition]) -> bool:
            if cond is None:
                return False
            if cond.attacker_below_starting_strength or cond.attacker_below_half_strength:
                return False
            if cond.attacker_contains_model_keywords_any:
                return False
            if cond.target_below_starting_strength:
                return False
            if cond.target_battleshocked or cond.target_within_objective or cond.target_within_objective_not_controlled:
                return False
            if cond.target_within_range is not None:
                return False
            if cond.target_can_fly is not None:
                return False
            if cond.target_below_half_strength:
                return False
            if cond.target_keywords_all or cond.target_exclude_keywords_any:
                return False
            kw_any = {k.strip().lower() for k in (cond.target_keywords_any or ()) if k}
            return bool({"monster", "vehicle"}.issubset(kw_any))

        def _scan(text: str, name: str = "") -> int:
            if not text:
                return 0
            norm = self._normalize_rules_text(text)
            if not norm:
                return 0
            key = (str(name or "").strip().lower(), norm.lower())
            if key in seen:
                return 0
            seen.add(key)
            total = 0
            for rule in self._parse_attack_roll_rules_from_text(text):
                if rule.scope not in ("unit", "leading"):
                    continue
                if rule.subject not in ("model_in_this_unit", "model_in_that_unit", "this_model"):
                    continue
                if rule.attack_type not in ("melee", "any"):
                    continue
                for eff in rule.effects:
                    if eff.roll != "damage" or eff.kind != "add":
                        continue
                    if not _monster_vehicle_only_condition(eff.condition):
                        continue
                    try:
                        val = int(eff.value or 0)
                    except Exception:
                        val = 0
                    if val:
                        total += val
            return total

        for ab in root._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    bonus += _scan(ab, "")
                else:
                    desc = str(getattr(ab, "description", "") or "")
                    name = str(getattr(ab, "name", "") or "")
                    if desc:
                        bonus += _scan(desc, name)
                    else:
                        bonus += _scan(name, name)
            except Exception:
                continue

        try:
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    if isinstance(ab, str):
                        bonus += _scan(ab, "")
                    else:
                        desc = str(getattr(ab, "description", "") or "")
                        name = str(getattr(ab, "name", "") or "")
                        if desc:
                            bonus += _scan(desc, name)
                        else:
                            bonus += _scan(name, name)
                except Exception:
                    continue
        except Exception:
            pass

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = int(bonus or 0)
        return int(bonus or 0)

    def get_melee_charge_strength_damage_entries(self) -> list[dict]:
        """
        Return Strength/Damage bonuses for melee attacks after making a Charge move this turn.

        Supported pattern:
        "Each time a model in this unit makes a melee attack, if this unit made a Charge move this turn,
         improve the Strength and Damage characteristics of that attack by X."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "melee_charge_strength_damage_entries"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key] or [])

        entries: list[dict] = []
        seen: set[tuple[str, int]] = set()

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for member in members:
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = member._strip_eligibility_prefix(text_src)
                normalized = member._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = self._MELEE_CHARGE_STRENGTH_DAMAGE_RE.fullmatch(normalized)
                damage_bonus = None
                model_keyword = ""
                if m:
                    try:
                        val = int(m.group("val") or 0)
                    except Exception:
                        val = 0
                    if val <= 0:
                        continue
                    damage_bonus = int(val)
                else:
                    m = self._MELEE_CHARGE_STRENGTH_ONLY_RE.fullmatch(normalized)
                    if m:
                        try:
                            val = int(m.group("val") or 0)
                        except Exception:
                            val = 0
                        if val <= 0:
                            continue
                        damage_bonus = 0
                    else:
                        m = self._MELEE_CHARGE_DAMAGE_ONLY_MODEL_KEYWORD_RE.fullmatch(normalized)
                        if not m:
                            continue
                        try:
                            val = int(m.group("val") or 0)
                        except Exception:
                            val = 0
                        if val <= 0:
                            continue
                        damage_bonus = int(val)
                        try:
                            kw_raw = str(m.group("keyword") or "").strip()
                        except Exception:
                            kw_raw = ""
                        model_keyword = member._normalize_keyword_phrase(kw_raw) or kw_raw.lower()
                        val = 0

                source = str(name or "Charge melee strength/damage").strip() or "Charge melee strength/damage"
                key = (source.lower(), int(val), int(damage_bonus), str(model_keyword))
                if key in seen:
                    continue
                seen.add(key)
                entry = {"strength_bonus": int(val), "damage_bonus": int(damage_bonus), "source": source}
                if model_keyword:
                    entry["model_keyword"] = str(model_keyword)
                entries.append(entry)

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(entries)
        return list(entries)

    def _was_set_up_this_turn(self, *, game=None) -> bool:
        try:
            if bool(getattr(self, "arrived_from_reserves_this_turn", False)):
                return True
        except Exception:
            pass
        try:
            if bool(getattr(self.round_state, "reinforced_this_round", False)):
                return True
        except Exception:
            pass
        try:
            if game is None:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            if turn and int(getattr(self, "reserve_turn_deployed", 0) or 0) == turn:
                return True
        except Exception:
            pass
        return False

    def _target_within_objective_range(self, target_unit=None, game_map=None) -> bool:
        if target_unit is None:
            return False
        if game_map is None:
            try:
                game_map = getattr(getattr(self.get_parent_army(), "player", None), "game", None).map
            except Exception:
                game_map = None
        objectives = list(getattr(game_map, "objectives", []) or []) if game_map is not None else []
        if not objectives:
            return False
        try:
            if bool(getattr(target_unit, "is_embarked", False)) or target_unit.is_in_reserves():
                return False
        except Exception:
            pass
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None:
                loc = obj
            try:
                if target_unit.is_within_objective_range(loc):
                    return True
            except Exception:
                continue
            try:
                models = list(target_unit.get_models_for_collision() or [])
            except Exception:
                models = list(getattr(target_unit, "models", []) or [])
            models = [m for m in models if bool(getattr(m, "is_alive", True))]
            if not models:
                continue
            try:
                from shapely.geometry import Point as _ShPoint
                area = _ShPoint(loc.x, loc.y).buffer(float(getattr(loc, "control_radius", 0.0) or 0.0))
            except Exception:
                area = None
            for model in models:
                try:
                    if area is not None:
                        base = model.model_base.get_base_shape()
                        if base.intersects(area):
                            return True
                except Exception:
                    pass
                try:
                    pos = model.get_location()
                except Exception:
                    pos = None
                if not pos:
                    continue
                try:
                    dx = float(pos[0]) - float(getattr(loc, "x", 0.0))
                    dy = float(pos[1]) - float(getattr(loc, "y", 0.0))
                    radius = float(getattr(loc, "control_radius", 0.0) or 0.0)
                    base_r = float(getattr(model.model_base, "get_radius", lambda: 1.0)())
                    if (dx * dx + dy * dy) ** 0.5 <= (radius + base_r):
                        return True
                except Exception:
                    continue
        return False

    def _target_within_uncontrolled_objective_range(self, target_unit=None, game_map=None) -> bool:
        if target_unit is None:
            return False
        if game_map is None:
            try:
                game_map = getattr(getattr(self.get_parent_army(), "player", None), "game", None).map
            except Exception:
                game_map = None
        objectives = list(getattr(game_map, "objectives", []) or []) if game_map is not None else []
        if not objectives:
            return False
        try:
            attacker_player = getattr(self.get_parent_army(), "player", None)
        except Exception:
            attacker_player = None
        try:
            if bool(getattr(target_unit, "is_embarked", False)) or target_unit.is_in_reserves():
                return False
        except Exception:
            pass
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None:
                loc = obj
            controller = getattr(loc, "controlling_player", None)
            if attacker_player is not None and controller is attacker_player:
                continue
            try:
                if target_unit.is_within_objective_range(loc):
                    return True
            except Exception:
                continue
        return False

    def _objective_in_range(self, game_map=None):
        """Return the first objective marker this unit is within range of, if any."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return None
        try:
            if root.is_in_reserves() or root.is_embarked:
                return None
        except Exception:
            pass
        if game_map is None:
            try:
                game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
            game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return None
        objectives = list(getattr(game_map, "objectives", []) or [])
        if not objectives:
            return None
        for obj in objectives:
            loc = getattr(obj, "location", None) or obj
            if loc is None:
                continue
            try:
                if bool(getattr(loc, "removed", False)):
                    continue
            except Exception:
                pass
            try:
                if root.is_within_objective_range(loc):
                    return obj
            except Exception:
                continue
        return None

    def is_within_any_objective_range(self, game_map=None) -> bool:
        """Return True if this unit is within range of any objective marker."""
        return self._objective_in_range(game_map) is not None

    def _within_controlled_objective_range(self, game_map=None) -> bool:
        """Return True if this unit is within range of an objective marker it controls."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        obj = self._objective_in_range(game_map)
        if obj is None or root is None:
            return False
        loc = getattr(obj, "location", None) or obj
        controller = getattr(loc, "controlling_player", None)
        try:
            return controller is root.get_parent_army().player
        except Exception:
            return False

    def _attacker_within_objective_controlled(self, game_map=None) -> bool:
        """Return True if this unit is within range of an objective marker it controls."""
        return bool(self._within_controlled_objective_range(game_map))

    def can_reroll_advance_roll(self) -> bool:
        """
        Best-effort detection for abilities that allow re-rolling Advance rolls for this unit/model.

        This is intentionally text-based so it can support multiple datasheets without hardcoding.
        """
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if mgr is not None and getattr(mgr, "_army_has_rule", lambda: False)() and getattr(mgr, "_unit_in_army", lambda _u: False)(self):
                if getattr(mgr, "is_hostile_acquisition", lambda: False)():
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is not None and getattr(mgr, "quicksilver_grace_applies", lambda _u: False)(self):
                return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "legacy_of_the_angel_their_appointed_hour_applies", None):
                if mgr.legacy_of_the_angel_their_appointed_hour_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "righteous_fervour_reroll_advance_applies", None):
                if mgr.righteous_fervour_reroll_advance_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "master_of_wolves_reroll_advance_applies", None):
                if mgr.master_of_wolves_reroll_advance_applies(self):
                    return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_reroll_advance"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bondsman_reroll_advance"):
                return True
        except Exception:
            pass
        try:
            if self._aethersails_reroll_active():
                return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
            if mgr is not None:
                skilled_crews = getattr(mgr, "skilled_crews_reroll_advance_applies", None)
                if callable(skilled_crews) and skilled_crews(self):
                    return True
                yriels_own = getattr(mgr, "yriels_own_reroll_advance_applies", None)
                if callable(yriels_own) and yriels_own(self):
                    return True
        except Exception:
            pass
        try:
            for u in list(self.get_attached_unit_members() or []):
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if sr.get("enhancement_reroll_advance") or sr.get("enhancement_reroll_advance_charge"):
                    return True
        except Exception:
            pass
        try:
            iter_fn = getattr(self, "_iter_attached_unit_reroll_texts", None)
            if callable(iter_fn):
                for text in iter_fn():
                    low = text.lower()
                    if self._REROLL_ADVANCE_CHARGE_RE.search(low):
                        return True
                    if ("re-roll" in low or "reroll" in low) and "advance roll" in low:
                        if "bearer's unit" in low or "this model" in low or "that unit" in low:
                            return True
        except Exception:
            pass
        for t in Unit._iter_reroll_scan_texts(self):
            s = str(t or "").lower()
            if "advance" in s and "drukhari" in s and "embarked within this model" in s:
                if self._transport_has_embarked_keyword("DRUKHARI"):
                    return True
                continue
            if ("re-roll" in s or "reroll" in s) and "advance" in s:
                return True
        return False

    def can_reroll_agile_maneuver_rolls(self) -> bool:
        """Return True if this unit can reroll rolls while performing an Agile Manoeuvre."""
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bearer_unit_agile_maneuver_reroll"):
                return True
        except Exception:
            pass
        try:
            for u in list(self.get_attached_unit_members() or []):
                sr = getattr(u, "special_rules", None)
                if isinstance(sr, dict) and sr.get("bearer_unit_agile_maneuver_reroll"):
                    return True
        except Exception:
            pass
        try:
            iter_fn = getattr(self, "_iter_attached_unit_reroll_texts", None)
            if callable(iter_fn):
                for text in iter_fn():
                    if self._BEARER_UNIT_AGILE_MANEUVER_REROLL_RE.search(text):
                        return True
        except Exception:
            pass
        return False

    def _bestial_aspect_unholy_hunger_active(self, *, game_map=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("enhancement_bestial_aspect"):
            return False
        if not sr.get("malefic_surge_unholy_hunger_active"):
            return False
        exp = str(sr.get("malefic_surge_unholy_hunger_expires_phase", "") or "").strip().upper()
        if exp:
            try:
                game = self.get_parent_army().player.game
            except Exception:
                game = None
            if game is None and game_map is not None:
                try:
                    game = getattr(game_map, "game", None)
                except Exception:
                    game = None
            current = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            if current and exp != current:
                return False
        return True

    def _preternatural_agility_ignore_modifiers_active(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("preternatural_agility_ignore_modifiers_active"):
            return False
        try:
            game = self.get_parent_army().player.game
        except Exception:
            game = None
        if game is None:
            return False
        exp = str(sr.get("preternatural_agility_ignore_modifiers_expires_phase", "") or "").strip().upper()
        if exp:
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            if phase_name and phase_name != exp:
                return False
        owner = str(sr.get("preternatural_agility_turn_owner", "") or "")
        try:
            turn = int(sr.get("preternatural_agility_turn", 0) or 0)
        except Exception:
            turn = 0
        if owner:
            cur_player = getattr(game, "get_current_player", lambda: None)()
            if str(getattr(cur_player, "id", "") or "") != owner:
                return False
        if turn:
            if int(getattr(game, "turn", 0) or 0) != int(turn):
                return False
        return True

    def _preternatural_agility_move_through_models_active(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("preternatural_agility_move_through_models_active"):
            return False
        try:
            game = self.get_parent_army().player.game
        except Exception:
            game = None
        if game is None:
            return False
        owner = str(sr.get("preternatural_agility_turn_owner", "") or "")
        try:
            turn = int(sr.get("preternatural_agility_turn", 0) or 0)
        except Exception:
            turn = 0
        if owner:
            cur_player = getattr(game, "get_current_player", lambda: None)()
            if str(getattr(cur_player, "id", "") or "") != owner:
                return False
        if turn:
            if int(getattr(game, "turn", 0) or 0) != int(turn):
                return False
        return True

    def _filter_internal_rivalries_roll_modifiers(self, modifiers, *, kind: str) -> list[tuple[int, str]]:
        if not modifiers:
            return list(modifiers or [])
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is None and army is not None:
                mgr = getattr(army, "emperors_children_detachments", None)
            if mgr is None or not getattr(mgr, "internal_rivalries_applies", lambda _u: False)(self):
                return list(modifiers or [])
        except Exception:
            return list(modifiers or [])
        from ...utility.modifier_choice import (
            CHOICE_KEEP_ALL,
            CHOICE_IGNORE_NEGATIVE,
            CHOICE_IGNORE_POSITIVE,
            CHOICE_IGNORE_ALL,
            filter_signed_modifiers,
        )

        kind_key = str(kind or "").strip().lower()
        try:
            choice = getattr(self.round_state, f"{kind_key}_modifier_choice", None)
        except Exception:
            choice = None
        if not choice:
            choice = CHOICE_KEEP_ALL
        if choice == CHOICE_KEEP_ALL:
            return list(modifiers or [])

        kept, ignored = filter_signed_modifiers(modifiers, str(choice))
        if ignored:
            try:
                sr = getattr(self, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                ignored_sources = tuple(sorted(str(s or "") for _v, s in ignored if str(s or "").strip()))
                kept_sources = tuple(sorted(str(s or "") for _v, s in kept if str(s or "").strip()))
                sig = (ignored_sources, kept_sources, str(choice))
                key = f"internal_rivalries_{kind_key}_mod_signature"
                if sr.get(key) != sig:
                    sr[key] = sig
                    self.special_rules = sr
                    from ...utility.event_bus import append_action

                    pn = self.get_parent_army().player
                    label = "Advance roll" if kind_key == "advance" else "Move roll"
                    ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                    tag = (
                        "negative"
                        if choice == CHOICE_IGNORE_NEGATIVE
                        else "positive"
                        if choice == CHOICE_IGNORE_POSITIVE
                        else "all"
                    )
                    append_action(pn, f"Internal Rivalries: ignored {tag} {label} modifiers ({ignored_text}).")
                    if kept_sources:
                        kept_text = ", ".join(s for s in kept_sources if s)
                        if kept_text:
                            append_action(pn, f"Internal Rivalries: applied {label} modifiers ({kept_text}).")
            except Exception:
                pass

        return kept

    def _filter_driven_by_ultimate_rage_roll_modifiers(self, modifiers, *, kind: str) -> list[tuple[int, str]]:
        if not modifiers:
            return list(modifiers or [])
        try:
            from ...rules.wrathful_presence import driven_by_ultimate_rage_applies
            if not driven_by_ultimate_rage_applies(self):
                return list(modifiers or [])
        except Exception:
            return list(modifiers or [])
        from ...utility.modifier_choice import (
            CHOICE_KEEP_ALL,
            CHOICE_IGNORE_NEGATIVE,
            CHOICE_IGNORE_POSITIVE,
            CHOICE_IGNORE_ALL,
            filter_signed_modifiers,
        )
        kind_key = str(kind or "").strip().lower()
        try:
            choice = getattr(self.round_state, f"{kind_key}_modifier_choice", None)
        except Exception:
            choice = None
        if not choice:
            choice = CHOICE_KEEP_ALL
        if choice == CHOICE_KEEP_ALL:
            return list(modifiers or [])

        kept, ignored = filter_signed_modifiers(modifiers, str(choice))
        if ignored:
            try:
                sr = getattr(self, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                ignored_sources = tuple(sorted(str(s or "") for _v, s in ignored if str(s or "").strip()))
                kept_sources = tuple(sorted(str(s or "") for _v, s in kept if str(s or "").strip()))
                sig = (ignored_sources, kept_sources, str(choice))
                key = f"driven_by_ultimate_rage_{kind_key}_mod_signature"
                if sr.get(key) != sig:
                    sr[key] = sig
                    self.special_rules = sr
                    from ...utility.event_bus import append_action
                    pn = self.get_parent_army().player
                    label = "Advance roll" if kind_key == "advance" else "Charge roll"
                    ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                    tag = (
                        "negative"
                        if choice == CHOICE_IGNORE_NEGATIVE
                        else "positive"
                        if choice == CHOICE_IGNORE_POSITIVE
                        else "all"
                    )
                    append_action(pn, f"Driven by Ultimate Rage: ignored {tag} {label} modifiers ({ignored_text}).")
                    if kept_sources:
                        kept_text = ", ".join(s for s in kept_sources if s)
                        if kept_text:
                            append_action(pn, f"Driven by Ultimate Rage: applied {label} modifiers ({kept_text}).")
            except Exception:
                pass

        return kept

    def _filter_bestial_aspect_roll_modifiers(self, modifiers, *, kind: str) -> list[tuple[int, str]]:
        if not modifiers:
            return list(modifiers or [])
        try:
            if not self._bestial_aspect_unholy_hunger_active():
                return list(modifiers or [])
        except Exception:
            return list(modifiers or [])
        from ...utility.modifier_choice import (
            CHOICE_KEEP_ALL,
            CHOICE_IGNORE_NEGATIVE,
            CHOICE_IGNORE_POSITIVE,
            CHOICE_IGNORE_ALL,
            filter_signed_modifiers,
        )
        kind_key = str(kind or "").strip().lower()
        try:
            choice = getattr(self.round_state, f"{kind_key}_modifier_choice", None)
        except Exception:
            choice = None
        if not choice:
            choice = CHOICE_KEEP_ALL
        if choice == CHOICE_KEEP_ALL:
            return list(modifiers or [])

        kept, ignored = filter_signed_modifiers(modifiers, str(choice))
        if ignored:
            try:
                sr = getattr(self, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                ignored_sources = tuple(sorted(str(s or "") for _v, s in ignored if str(s or "").strip()))
                kept_sources = tuple(sorted(str(s or "") for _v, s in kept if str(s or "").strip()))
                sig = (ignored_sources, kept_sources, str(choice))
                key = f"bestial_aspect_{kind_key}_mod_signature"
                if sr.get(key) != sig:
                    sr[key] = sig
                    self.special_rules = sr
                    from ...utility.event_bus import append_action
                    pn = self.get_parent_army().player
                    label = "Advance roll" if kind_key == "advance" else "Charge roll"
                    ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                    tag = (
                        "negative"
                        if choice == CHOICE_IGNORE_NEGATIVE
                        else "positive"
                        if choice == CHOICE_IGNORE_POSITIVE
                        else "all"
                    )
                    append_action(pn, f"Bestial Aspect: ignored {tag} {label} modifiers ({ignored_text}).")
                    if kept_sources:
                        kept_text = ", ".join(s for s in kept_sources if s)
                        if kept_text:
                            append_action(pn, f"Bestial Aspect: applied {label} modifiers ({kept_text}).")
            except Exception:
                pass

        return kept

    def _filter_preternatural_agility_roll_modifiers(self, modifiers, *, kind: str) -> list[tuple[int, str]]:
        if not modifiers:
            return list(modifiers or [])
        kind_key = str(kind or "").strip().lower()
        if kind_key not in ("advance", "charge"):
            return list(modifiers or [])
        try:
            if not self._preternatural_agility_ignore_modifiers_active():
                return list(modifiers or [])
        except Exception:
            return list(modifiers or [])
        from ...utility.modifier_choice import (
            CHOICE_KEEP_ALL,
            CHOICE_IGNORE_NEGATIVE,
            CHOICE_IGNORE_POSITIVE,
            CHOICE_IGNORE_ALL,
            filter_signed_modifiers,
        )
        try:
            choice = getattr(self.round_state, f"{kind_key}_modifier_choice", None)
        except Exception:
            choice = None
        if not choice:
            choice = CHOICE_KEEP_ALL
        if choice == CHOICE_KEEP_ALL:
            return list(modifiers or [])

        kept, ignored = filter_signed_modifiers(modifiers, str(choice))
        if ignored:
            try:
                sr = getattr(self, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                ignored_sources = tuple(sorted(str(s or "") for _v, s in ignored if str(s or "").strip()))
                kept_sources = tuple(sorted(str(s or "") for _v, s in kept if str(s or "").strip()))
                sig = (ignored_sources, kept_sources, str(choice))
                key = f"preternatural_agility_{kind_key}_mod_signature"
                if sr.get(key) != sig:
                    sr[key] = sig
                    self.special_rules = sr
                    from ...utility.event_bus import append_action
                    pn = self.get_parent_army().player
                    label = "Advance roll" if kind_key == "advance" else "Charge roll"
                    ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                    tag = (
                        "negative"
                        if choice == CHOICE_IGNORE_NEGATIVE
                        else "positive"
                        if choice == CHOICE_IGNORE_POSITIVE
                        else "all"
                    )
                    append_action(pn, f"Preternatural Agility: ignored {tag} {label} modifiers ({ignored_text}).")
                    if kept_sources:
                        kept_text = ", ".join(s for s in kept_sources if s)
                        if kept_text:
                            append_action(pn, f"Preternatural Agility: applied {label} modifiers ({kept_text}).")
            except Exception:
                pass
        return kept

    def _collect_advance_roll_modifiers(self) -> list[tuple[int, str]]:
        if bool(getattr(self, "has_siege_crawler", lambda: False)()):
            return []
        mods: list[tuple[int, str]] = []
        sr = getattr(self, "special_rules", None)
        try:
            bonus = int(sr.get("code_chivalric_advance_bonus", 0) or 0) if isinstance(sr, dict) else 0
        except Exception:
            bonus = 0
        if bonus:
            mods.append((bonus, "Code Chivalric"))
        try:
            army = self.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if sm_mgr is not None and callable(getattr(sm_mgr, "wrathful_procession_advance_roll_bonus", None)):
                bonus, source = sm_mgr.wrathful_procession_advance_roll_bonus(self, game=game)
                if int(bonus or 0):
                    source_name = str(source or "Zealous Litanies").strip() or "Zealous Litanies"
                    mods.append((int(bonus), source_name))
            tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
            synaptic_bonus_fn = getattr(tyr_mgr, "synaptic_imperatives_advance_roll_bonus", None) if tyr_mgr is not None else None
            if callable(synaptic_bonus_fn):
                bonus, source = synaptic_bonus_fn(self, game=game)
                if int(bonus or 0):
                    source_name = str(source or "Synaptic Imperatives").strip() or "Synaptic Imperatives"
                    mods.append((int(bonus), source_name))
        except Exception:
            pass
        if isinstance(sr, dict) and sr.get("ere_we_go_active") is True:
            try:
                ere_active = True
                owner = str(sr.get("ere_we_go_turn_owner", "") or "")
                turn = int(sr.get("ere_we_go_turn", 0) or 0)
                if owner or turn:
                    game = None
                    try:
                        army = self.get_parent_army()
                        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    except Exception:
                        game = None
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        if owner and owner != cur_owner:
                            ere_active = False
                        if turn and turn != cur_turn:
                            ere_active = False
                if ere_active:
                    mods.append((2, "Ere We Go"))
            except Exception:
                pass
        if isinstance(sr, dict):
            try:
                extra = int(sr.get("advance_roll_modifier", 0) or 0)
            except Exception:
                extra = 0
            if extra:
                mods.append((extra, "Advance roll modifier"))
            try:
                extra_list = sr.get("advance_roll_modifiers", None)
            except Exception:
                extra_list = None
            if isinstance(extra_list, list):
                for item in extra_list:
                    try:
                        if isinstance(item, (list, tuple)) and len(item) >= 1:
                            val = int(item[0] or 0)
                            source = str(item[1] if len(item) > 1 else "Advance roll modifier")
                        elif isinstance(item, dict):
                            val = int(item.get("value", 0) or 0)
                            source = str(item.get("source", "") or "Advance roll modifier")
                        else:
                            val = int(item or 0)
                            source = "Advance roll modifier"
                    except Exception:
                        continue
                    if val:
                        mods.append((val, source))
        try:
            from ...utility.aura_effects import get_aura_advance_charge_roll_modifiers
            aura_mods, _ = get_aura_advance_charge_roll_modifiers(self)
            for val, source in list(aura_mods or []):
                if val:
                    mods.append((int(val), source))
        except Exception:
            pass
        return mods

    def _apply_advance_roll_modifiers(self, roll: int) -> int:
        effect = self._get_advance_no_roll_effect()
        if isinstance(effect, dict):
            try:
                dist = int(effect.get("distance", 0) or 0)
            except Exception:
                dist = 0
            if dist > 0:
                return int(dist)
        mods = self._collect_advance_roll_modifiers()
        mods = self._filter_internal_rivalries_roll_modifiers(mods, kind="advance")
        mods = self._filter_driven_by_ultimate_rage_roll_modifiers(mods, kind="advance")
        mods = self._filter_bestial_aspect_roll_modifiers(mods, kind="advance")
        mods = self._filter_preternatural_agility_roll_modifiers(mods, kind="advance")
        for val, source in mods:
            if not val:
                continue
            roll += int(val)
            try:
                if val > 0:
                    logger.info(f"{self.name} advance bonus: +{val}\" ({source})")
                else:
                    logger.info(f"{self.name} advance penalty: {val}\" ({source})")
            except Exception:
                pass
        return int(roll)

    def _is_charge_target_closest_eligible(self, target_unit, *, game_map=None, game=None) -> bool:
        if target_unit is None:
            return False
        if game is None:
            try:
                game = self.get_parent_army().player.game
            except Exception:
                game = None
        if game_map is None:
            try:
                game_map = getattr(game, "map", None)
            except Exception:
                game_map = None
        if game_map is None or game is None:
            return False

        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit

        try:
            if not self.can_declare_charge_against(target_root, game, out_of_turn=True):
                return False
        except Exception:
            return False

        try:
            target_dist = float(game_map.get_distance_between_units(self, target_root))
        except Exception:
            target_dist = None
        if target_dist is None:
            return False

        enemies = None
        try:
            player = self.get_parent_army().player
        except Exception:
            player = None
        if player is not None and game is not None:
            try:
                enemies = list(game.get_enemy_units(player) or [])
            except Exception:
                enemies = None
        if enemies is None:
            try:
                enemies = list(game_map.get_enemy_units(self) or [])
            except Exception:
                enemies = []

        if not enemies:
            return False

        closest = None
        seen = set()
        for enemy_unit in enemies:
            try:
                root = enemy_unit.get_attached_unit_root()
            except Exception:
                root = enemy_unit
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
                if not self.can_declare_charge_against(root, game, out_of_turn=True):
                    continue
            except Exception:
                continue
            try:
                dist = float(game_map.get_distance_between_units(self, root))
            except Exception:
                continue
            if closest is None or dist < closest:
                closest = dist

        if closest is None:
            return False
        return target_dist <= closest + 1e-6

    def get_selected_to_shoot_charge_reroll_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "In your Shooting phase, each time this unit is selected to shoot, if it makes one or more ranged attacks
        and all of those attacks target the same enemy unit, until the end of the turn, each time this unit declares
        a charge, if that enemy unit is a target of that charge, you can re-roll the Charge roll."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "selected_to_shoot_charge_reroll_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        try:
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            for u in members:
                for name, desc in u._iter_ability_entries_for_rules(model=None):
                    text_src = desc or name or ""
                    if not text_src:
                        continue
                    text_src = self._strip_eligibility_prefix(text_src)
                    normalized = self._normalize_rules_text(text_src)
                    normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                    normalized = normalized.lower()
                    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                    normalized = re.sub(r"\s+", " ", normalized).strip()
                    normalized = re.sub(r"\bre roll\b", "reroll", normalized)
                    normalized = re.sub(r"\bre rolls\b", "reroll", normalized)
                    if not normalized:
                        continue
                    if self._SELECTED_TO_SHOOT_CHARGE_REROLL_RE.fullmatch(normalized):
                        source = str(name or "Selected to shoot charge reroll").strip() or "Selected to shoot charge reroll"
                        rule = {"source": source}
                        break
                if rule:
                    break
        except Exception:
            rule = None

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def _selected_to_shoot_charge_reroll_target_ids(self, *, game=None) -> set[str]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return set()
        raw = sr.get("selected_to_shoot_charge_reroll_target_ids")
        if not raw:
            return set()
        if game is not None:
            owner = str(sr.get("selected_to_shoot_charge_reroll_turn_owner", "") or "")
            turn = int(sr.get("selected_to_shoot_charge_reroll_turn", 0) or 0)
            if owner or turn:
                try:
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                except Exception:
                    cur_player = None
                cur_owner = ""
                if cur_player is not None:
                    try:
                        cur_owner = get_entity_id(cur_player)
                    except Exception:
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                cur_turn = int(getattr(game, "turn", 0) or 0)
                if owner and cur_owner and owner != cur_owner:
                    return set()
                if turn and cur_turn and turn != cur_turn:
                    return set()

        if isinstance(raw, dict):
            return {str(k) for k in raw.keys() if k}
        if isinstance(raw, (list, tuple, set)):
            return {str(v) for v in raw if v}
        return {str(raw)}

    def _record_selected_to_shoot_charge_reroll_target(self, target_unit, *, game=None, source: str = "") -> bool:
        if target_unit is None:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
            root.special_rules = sr

        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        if target_root is None:
            return False
        try:
            target_id = get_entity_id(target_root)
        except Exception:
            return False

        owner_id = ""
        turn = 0
        if game is not None:
            try:
                cur_player = getattr(game, "get_current_player", lambda: None)()
            except Exception:
                cur_player = None
            if cur_player is not None:
                try:
                    owner_id = get_entity_id(cur_player)
                except Exception:
                    owner_id = str(getattr(cur_player, "id", "") or "")
            turn = int(getattr(game, "turn", 0) or 0)
        if not owner_id:
            try:
                army = root.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
            except Exception:
                player = None
            if player is not None:
                try:
                    owner_id = get_entity_id(player)
                except Exception:
                    owner_id = str(getattr(player, "id", "") or "")
        if not turn and game is None:
            try:
                turn = int(getattr(getattr(root.get_parent_army(), "player", None), "game", None).turn or 0)
            except Exception:
                turn = 0

        existing_owner = str(sr.get("selected_to_shoot_charge_reroll_turn_owner", "") or "")
        existing_turn = int(sr.get("selected_to_shoot_charge_reroll_turn", 0) or 0)
        targets = set()
        if existing_owner and owner_id and existing_owner != owner_id:
            targets = set()
        elif existing_turn and turn and existing_turn != turn:
            targets = set()
        else:
            raw = sr.get("selected_to_shoot_charge_reroll_target_ids")
            if isinstance(raw, dict):
                targets = {str(k) for k in raw.keys() if k}
            elif isinstance(raw, (list, tuple, set)):
                targets = {str(v) for v in raw if v}
            elif raw:
                targets = {str(raw)}

        targets.add(str(target_id))
        sr["selected_to_shoot_charge_reroll_target_ids"] = sorted(targets)
        if owner_id:
            sr["selected_to_shoot_charge_reroll_turn_owner"] = owner_id
        if turn:
            sr["selected_to_shoot_charge_reroll_turn"] = int(turn)
        if source:
            sr["selected_to_shoot_charge_reroll_source"] = str(source)
        root.special_rules = sr
        return True

    def get_snarling_protector_charge_reroll_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time this model declares a charge that targets an enemy unit within Engagement Range of one or more
        Thousand Sons Psyker units from your army, you can re-roll the Charge roll."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "snarling_protector_charge_reroll_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        seen = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for u in members:
            if u is None:
                continue
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                key = (str(name or "").strip().lower(), u._normalize_rules_text(text_src).lower())
                if key in seen:
                    continue
                seen.add(key)
                normalized = u._normalize_rules_text(u._strip_eligibility_prefix(text_src))
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not u._SNARLING_PROTECTOR_CHARGE_REROLL_RE.search(normalized):
                    continue
                source = str(name or "Snarling Protector").strip() or "Snarling Protector"
                rule = {"source": source}
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def _snarling_protector_charge_reroll_applies(self, *, target_units: list, game_map=None, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        rule = root.get_snarling_protector_charge_reroll_rule()
        if not rule:
            return False
        if not target_units:
            return False
        if game_map is None:
            game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return False

        try:
            army = root.get_parent_army()
            friendly_units = list(getattr(army, "units", []) or []) if army is not None else []
        except Exception:
            friendly_units = []
        seen_friendlies: set[str] = set()
        friendly_psykers: list = []
        for friendly in list(friendly_units or []):
            if friendly is None:
                continue
            try:
                f_root = friendly.get_attached_unit_root()
            except Exception:
                f_root = friendly
            if f_root is None:
                continue
            fid = str(get_entity_id(f_root) or "")
            if fid and fid in seen_friendlies:
                continue
            if fid:
                seen_friendlies.add(fid)
            if f_root is root:
                continue
            try:
                if not f_root.is_alive() or not getattr(f_root, "deployed", True):
                    continue
            except Exception:
                continue
            try:
                if f_root.is_in_reserves() or f_root.is_embarked:
                    continue
            except Exception:
                pass
            try:
                has_ts = bool(f_root.has_any_keyword("THOUSAND SONS"))
            except Exception:
                has_ts = False
            try:
                has_psyker = bool(f_root.has_any_keyword("PSYKER"))
            except Exception:
                has_psyker = False
            if has_ts and has_psyker:
                friendly_psykers.append(f_root)
        if not friendly_psykers:
            return False

        seen_targets: set[str] = set()
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            tid = str(get_entity_id(target_root) or "")
            if tid and tid in seen_targets:
                continue
            if tid:
                seen_targets.add(tid)
            for psyker_unit in friendly_psykers:
                try:
                    if game_map.is_within_engagement_range(psyker_unit, target_root):
                        return True
                except Exception:
                    continue
        return False

    def _court_prideful_superiority_active(self, *, target=None, game=None) -> tuple[bool, str]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None or target is None:
            return (False, "")
        try:
            target_root = target.get_attached_unit_root()
        except Exception:
            target_root = target
        if target_root is None:
            return (False, "")
        if not self._entity_has_keyword_for_empyric(target_root, "CHARACTER"):
            return (False, "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("court_prideful_superiority_active")):
            return (False, "")
        if game is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        phase_name = self._current_phase_name_for_rules(game=game)
        if phase_name and phase_name != "FIGHT_PHASE":
            return (False, "")
        exp_phase = str(sr.get("court_prideful_superiority_expires_phase", "") or "").strip().upper()
        if exp_phase and phase_name and exp_phase != phase_name:
            return (False, "")
        owner_id = str(sr.get("court_prideful_superiority_owner", "") or "")
        if owner_id:
            try:
                army = root.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
            except Exception:
                player = None
            player_id = str(getattr(player, "id", "") or "") if player is not None else ""
            if player_id and owner_id != player_id:
                return (False, "")
        try:
            marked_turn = int(sr.get("court_prideful_superiority_turn", 0) or 0)
        except Exception:
            marked_turn = 0
        if marked_turn:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            except Exception:
                current_turn = 0
            if current_turn and current_turn != marked_turn:
                return (False, "")
        source = str(sr.get("court_prideful_superiority_source", "") or "PRIDEFUL SUPERIORITY").strip() or "PRIDEFUL SUPERIORITY"
        return (True, source)

    def _imperial_agents_prime_target_active(self, *, game=None) -> tuple[bool, str]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return (False, "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("imperial_agents_prime_target_active")):
            return (False, "")
        if game is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        phase_name = self._current_phase_name_for_rules(game=game)
        if phase_name and phase_name not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return (False, "")
        exp_phase = str(sr.get("imperial_agents_prime_target_expires_phase", "") or "").strip().upper()
        if exp_phase and phase_name and exp_phase != phase_name:
            return (False, "")
        owner_id = str(sr.get("imperial_agents_prime_target_owner", "") or "")
        if owner_id:
            try:
                army = root.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
            except Exception:
                player = None
            player_id = str(getattr(player, "id", "") or "") if player is not None else ""
            if player_id and owner_id != player_id:
                return (False, "")
        try:
            marked_turn = int(sr.get("imperial_agents_prime_target_turn", 0) or 0)
        except Exception:
            marked_turn = 0
        if marked_turn:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            except Exception:
                current_turn = 0
            if current_turn and current_turn != marked_turn:
                return (False, "")
        source = str(sr.get("imperial_agents_prime_target_source", "") or "PRIME TARGET").strip() or "PRIME TARGET"
        return (True, source)

    def _coterie_martial_perfection_active(self, *, game=None) -> tuple[bool, str]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return (False, "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("coterie_martial_perfection_active")):
            return (False, "")
        if game is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        phase_name = self._current_phase_name_for_rules(game=game)
        if phase_name and phase_name != "FIGHT_PHASE":
            return (False, "")
        exp_phase = str(sr.get("coterie_martial_perfection_expires_phase", "") or "").strip().upper()
        if exp_phase and phase_name and exp_phase != phase_name:
            return (False, "")
        owner_id = str(sr.get("coterie_martial_perfection_owner", "") or "")
        if owner_id:
            try:
                army = root.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
            except Exception:
                player = None
            player_id = str(getattr(player, "id", "") or "") if player is not None else ""
            if player_id and owner_id != player_id:
                return (False, "")
        try:
            marked_turn = int(sr.get("coterie_martial_perfection_turn", 0) or 0)
        except Exception:
            marked_turn = 0
        if marked_turn:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            except Exception:
                current_turn = 0
            if current_turn and current_turn != marked_turn:
                return (False, "")
        source = str(sr.get("coterie_martial_perfection_source", "") or "MARTIAL PERFECTION").strip() or "MARTIAL PERFECTION"
        return (True, source)

    def _court_euphoric_inspiration_charge_reroll_active(self, *, game=None, game_map=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if not self._entity_has_keyword_for_empyric(root, "EMPEROR'S CHILDREN"):
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        if game is None:
            game = getattr(getattr(army, "player", None), "game", None)
        if game_map is None:
            game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return False
        phase_name = self._current_phase_name_for_rules(game=game)
        if phase_name and phase_name != "CHARGE_PHASE":
            return False
        current_turn = 0
        try:
            current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        except Exception:
            current_turn = 0
        owner_id = str(getattr(getattr(army, "player", None), "id", "") or "")

        seen_sources: set[str] = set()
        for source in list(getattr(army, "units", []) or []):
            if source is None:
                continue
            try:
                source_root = source.get_attached_unit_root()
            except Exception:
                source_root = source
            if source_root is None:
                continue
            sid = str(get_entity_id(source_root) or "")
            if sid and sid in seen_sources:
                continue
            if sid:
                seen_sources.add(sid)
            sr = getattr(source_root, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("court_euphoric_inspiration_aura_active")):
                continue
            exp_phase = str(sr.get("court_euphoric_inspiration_expires_phase", "") or "").strip().upper()
            if exp_phase and phase_name and exp_phase != phase_name:
                continue
            sr_owner = str(sr.get("court_euphoric_inspiration_owner", "") or "")
            if sr_owner and owner_id and sr_owner != owner_id:
                continue
            try:
                marked_turn = int(sr.get("court_euphoric_inspiration_turn", 0) or 0)
            except Exception:
                marked_turn = 0
            if marked_turn and current_turn and marked_turn != current_turn:
                continue
            try:
                if not source_root.is_alive():
                    continue
            except Exception:
                continue
            if not bool(getattr(source_root, "deployed", False)):
                continue
            try:
                if source_root.is_in_reserves():
                    continue
            except Exception:
                pass
            if bool(getattr(source_root, "is_embarked", False)) or getattr(source_root, "embarked_in", None) is not None:
                continue
            try:
                distance = float(game_map.get_distance_between_units(root, source_root))
            except Exception:
                continue
            if distance <= 6.0 + 1e-6:
                return True
        return False

    def can_reroll_charge_roll(self, *, target_unit=None, game_map=None, game=None) -> bool:
        """
        Best-effort detection for abilities that allow re-rolling Charge rolls for this unit/model.
        """
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if mgr is not None and getattr(mgr, "_army_has_rule", lambda: False)() and getattr(mgr, "_unit_in_army", lambda _u: False)(self):
                if getattr(mgr, "is_hostile_acquisition", lambda: False)():
                    return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_charge_reroll"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_reroll_charge"):
                return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "legacy_of_the_angel_their_appointed_hour_applies", None):
                if mgr.legacy_of_the_angel_their_appointed_hour_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "righteous_fervour_reroll_charge_applies", None):
                if mgr.righteous_fervour_reroll_charge_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "master_of_wolves_reroll_charge_applies", None):
                if mgr.master_of_wolves_reroll_charge_applies(self):
                    return True
        except Exception:
            pass
        try:
            if self._spearhead_striker_charge_reroll_active(game=game):
                return True
        except Exception:
            pass
        try:
            if self._court_euphoric_inspiration_charge_reroll_active(game=game, game_map=game_map):
                return True
        except Exception:
            pass
        try:
            if game_map is None and game is not None:
                game_map = getattr(game, "map", None)
        except Exception:
            pass
        try:
            from ...utility.aura_effects import has_aura_charge_reroll

            if has_aura_charge_reroll(self, game_map=game_map):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bondsman_reroll_charge"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("imperial_knights_lancers_sigil_charge_reroll"):
                return True
        except Exception:
            pass
        try:
            enh = getattr(self, "enhancement", None)
            if enh is not None and str(getattr(enh, "name", "") or "").strip().lower() == "battle-lust":
                return True
        except Exception:
            pass
        target_units: list = []
        try:
            if target_unit is None:
                target_units = []
            elif isinstance(target_unit, (list, tuple, set)):
                target_units = [t for t in list(target_unit or []) if t is not None]
            else:
                target_units = [target_unit]
        except Exception:
            target_units = [target_unit] if target_unit is not None else []
        if target_units:
            deduped = []
            seen = set()
            for t in target_units:
                try:
                    root = t.get_attached_unit_root()
                except Exception:
                    root = t
                if root is None:
                    continue
                try:
                    rid = get_entity_id(root)
                except Exception:
                    rid = None
                if rid and rid in seen:
                    continue
                if rid:
                    seen.add(rid)
                deduped.append(root)
            target_units = deduped
        conditional_found = False
        try:
            rule = self.get_selected_to_shoot_charge_reroll_rule()
            if rule:
                conditional_found = True
                active_targets = self._selected_to_shoot_charge_reroll_target_ids(game=game)
                if active_targets and target_units:
                    for t in target_units:
                        try:
                            tid = get_entity_id(t)
                        except Exception:
                            continue
                        if tid in active_targets:
                            return True
        except Exception:
            pass
        try:
            if self.get_snarling_protector_charge_reroll_rule():
                conditional_found = True
                if self._snarling_protector_charge_reroll_applies(
                    target_units=target_units,
                    game_map=game_map,
                    game=game,
                ):
                    return True
        except Exception:
            pass
        try:
            for u in list(self.get_attached_unit_members() or []):
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if sr.get("enhancement_charge_reroll"):
                    return True
                if sr.get("enhancement_charge_reroll_on_setup_turn"):
                    conditional_found = True
                    if self._was_set_up_this_turn(game=game):
                        return True
                if sr.get("enhancement_charge_reroll_if_target_on_objective"):
                    conditional_found = True
                    if any(self._target_within_objective_range(t, game_map) for t in (target_units or [])):
                        return True
        except Exception:
            pass

        try:
            iter_fn = getattr(self, "_iter_attached_unit_reroll_texts", None)
            if callable(iter_fn):
                for text in iter_fn():
                    low = text.lower()
                    if self._REROLL_CHARGE_OBJECTIVE_RE.search(low):
                        conditional_found = True
                        if any(self._target_within_objective_range(t, game_map) for t in (target_units or [])):
                            return True
                        continue
                    if self._REROLL_CHARGE_SETUP_TURN_RE.search(low):
                        conditional_found = True
                        if self._was_set_up_this_turn(game=game):
                            return True
                        continue
                    if self._REROLL_CHARGE_CLOSEST_ELIGIBLE_RE.search(low):
                        conditional_found = True
                        if target_units:
                            for t in target_units:
                                if self._is_charge_target_closest_eligible(
                                    t,
                                    game_map=game_map,
                                    game=game,
                                ):
                                    return True
                        continue
                    if self._REROLL_ADVANCE_CHARGE_RE.search(low):
                        return True
                    if self._REROLL_CHARGE_BEARER_UNIT_RE.search(low):
                        return True
        except Exception:
            pass

        if conditional_found:
            return False

        for t in Unit._iter_reroll_scan_texts(self):
            s = self._normalize_rules_text(str(t or "")).lower()
            if "charge" in s and "drukhari" in s and "embarked within this model" in s:
                if self._transport_has_embarked_keyword("DRUKHARI"):
                    return True
                continue
            if ("re-roll" in s or "reroll" in s) and "charge" in s:
                return True
        return False

    def _charge_roll_target_strength_specs(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "charge_roll_target_strength_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = self._strip_eligibility_prefix(text_src)
                normalized = self._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = self._CHARGE_ROLL_TARGET_STRENGTH_BONUS_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    base_bonus = int(m.group("base") or 0)
                except Exception:
                    base_bonus = 0
                try:
                    half_bonus = int(m.group("half") or 0)
                except Exception:
                    half_bonus = 0
                source = str(name or "Charge roll bonus").strip() or "Charge roll bonus"
                key = (source.lower(), base_bonus, half_bonus)
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"base_bonus": base_bonus, "half_bonus": half_bonus, "source": source})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def get_charge_roll_target_strength_modifiers(self, target_units=None) -> list[tuple[int, str]]:
        specs = self._charge_roll_target_strength_specs()
        if target_units is None:
            return []
        targets = list(target_units) if isinstance(target_units, (list, tuple, set)) else [target_units]
        if not targets:
            return []

        has_below_start = False
        has_below_half = False
        for target in targets:
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if root.is_below_half_strength():
                    has_below_half = True
            except Exception:
                pass
            try:
                if root.is_below_starting_strength():
                    has_below_start = True
            except Exception:
                pass

        modifiers: list[tuple[int, str]] = []
        if has_below_half or has_below_start:
            for spec in specs:
                if has_below_half and int(spec.get("half_bonus", 0) or 0):
                    modifiers.append((int(spec.get("half_bonus", 0) or 0), spec.get("source", "Charge roll bonus")))
                elif has_below_start and int(spec.get("base_bonus", 0) or 0):
                    modifiers.append((int(spec.get("base_bonus", 0) or 0), spec.get("source", "Charge roll bonus")))

        # Space Marines (Lion's Blade Task Force): In The Lion's Claws +2 to charge
        # when a DEATHWING unit charges a target within Engagement Range of friendly RAVENWING.
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            army = root.get_parent_army() if root is not None and hasattr(root, "get_parent_army") else None
        except Exception:
            army = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        bonus_fn = getattr(sm_mgr, "in_the_lions_claws_charge_roll_bonus", None) if sm_mgr is not None else None
        if callable(bonus_fn):
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            try:
                bonus, source = bonus_fn(root, targets, game=game)
            except Exception:
                bonus, source = 0, ""
            if int(bonus or 0):
                modifiers.append((int(bonus or 0), str(source or "In The Lion's Claws")))
        return modifiers

    def _defensive_charge_roll_penalty_specs(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "defensive_charge_roll_penalty_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = self._strip_eligibility_prefix(text_src)
                normalized = self._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = self._DEFENSIVE_CHARGE_ROLL_PENALTY_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    val = int(m.group("val") or 0)
                except Exception:
                    val = 0
                if val <= 0:
                    continue
                source = str(name or "Charge roll penalty").strip() or "Charge roll penalty"
                key = (source.lower(), int(val))
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"value": int(val), "source": source})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def get_defensive_charge_roll_modifiers(self) -> list[tuple[int, str]]:
        specs = self._defensive_charge_roll_penalty_specs()
        modifiers: list[tuple[int, str]] = []
        for spec in specs:
            try:
                val = int(spec.get("value", 0) or 0)
            except Exception:
                val = 0
            if not val:
                continue
            modifiers.append((-abs(val), spec.get("source", "Charge roll penalty")))

        # REPELLING SPHERE: -1 to Charge rolls, or -2 while wholly within Hallowed Ground.
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and sr.get("repelling_sphere_active"):
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            player = getattr(army, "player", None) if army is not None else None
            game = getattr(player, "game", None) if player is not None else None
            owner_id = str(sr.get("repelling_sphere_turn_owner", "") or "")
            effect_turn = int(sr.get("repelling_sphere_turn", 0) or 0)
            expires_phase = str(sr.get("repelling_sphere_expires_phase", "") or "").strip().upper()
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
            current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            current_owner = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "") if game is not None else ""
            active = True
            if owner_id and owner_id != str(getattr(player, "id", "") or ""):
                active = False
            if active and owner_id and owner_id == current_owner:
                active = False
            if active and effect_turn and current_turn and effect_turn != current_turn:
                active = False
            if active and expires_phase and phase_name and expires_phase != phase_name:
                active = False
            if active:
                penalty = 1
                gk_mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
                if gk_mgr is not None and getattr(gk_mgr, "is_warpbane_task_force", lambda: False)():
                    if bool(getattr(gk_mgr, "unit_wholly_within_hallowed_ground", lambda *_a, **_k: False)(root, game=game)):
                        penalty = 2
                source = str(sr.get("repelling_sphere_source", "") or "Repelling Sphere").strip()
                modifiers.append((-int(abs(penalty)), f"{source}: charge roll modifier"))
        return modifiers

    def register_wargear_charge_keyword_hit(
        self,
        target_unit: 'Unit',
        keyword: str,
        *,
        no_overwatch: bool = False,
        game: Optional['Game'] = None,
    ) -> bool:
        """Track charge/Overwatch effects from wargear keyword hits against a target unit."""
        if target_unit is None:
            return False
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
            self.special_rules = sr

        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        target_id = get_entity_id(target_root)

        hits = sr.get("wargear_charge_keyword_hits")
        if not isinstance(hits, dict):
            hits = {}

        entry = dict(hits.get(target_id) or {})
        keywords = set(entry.get("keywords", []) or [])
        key_norm = str(keyword or "").strip().lower()
        if key_norm:
            keywords.add(key_norm)

        updated = False
        prev_bonus = int(entry.get("charge_bonus", 0) or 0)
        if prev_bonus < 2:
            entry["charge_bonus"] = 2
            updated = True
        if no_overwatch and not bool(entry.get("no_overwatch", False)):
            entry["no_overwatch"] = True
            updated = True
        if keywords != set(entry.get("keywords", []) or []):
            entry["keywords"] = sorted(keywords)
            updated = True

        hits[target_id] = entry
        sr["wargear_charge_keyword_hits"] = hits

        owner_id = ""
        if game is not None:
            getter = getattr(game, "get_current_player", None)
            if callable(getter):
                current_player = getter()
                if current_player is not None:
                    owner_id = get_entity_id(current_player)
        if not owner_id:
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            player = getattr(army, "player", None)
            if player is not None:
                owner_id = get_entity_id(player)
        if owner_id:
            sr["wargear_charge_keyword_hits_turn_owner"] = owner_id
        if game is not None:
            sr["wargear_charge_keyword_hits_turn"] = int(getattr(game, "turn", 0) or 0)
        return updated

    def _get_wargear_charge_keyword_effects(self, target_unit: 'Unit', *, game: Optional['Game'] = None) -> Optional[dict]:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        hits = sr.get("wargear_charge_keyword_hits")
        if not isinstance(hits, dict) or target_unit is None:
            return None
        if game is not None:
            owner_id = str(sr.get("wargear_charge_keyword_hits_turn_owner", "") or "")
            if owner_id:
                getter = getattr(game, "get_current_player", None)
                if callable(getter):
                    current = getter()
                    if current is None or get_entity_id(current) != owner_id:
                        return None
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        target_id = get_entity_id(target_root)
        entry = hits.get(target_id)
        if not isinstance(entry, dict):
            return None
        return entry

    def get_wargear_charge_keyword_modifiers(self, target_unit: 'Unit', *, game: Optional['Game'] = None) -> list[tuple[int, str]]:
        entry = self._get_wargear_charge_keyword_effects(target_unit, game=game)
        if not entry:
            return []
        bonus = int(entry.get("charge_bonus", 0) or 0)
        if not bonus:
            return []
        keywords = [str(k) for k in (entry.get("keywords", []) or []) if str(k or "").strip()]
        if keywords:
            label = "/".join([k.title() for k in keywords])
            source = f"{label} (wargear)"
        else:
            source = "Wargear keyword (charge bonus)"
        return [(bonus, source)]

    def _spearhead_striker_charge_reroll_active(self, *, game: Optional['Game'] = None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not sr.get("spearhead_striker_charge_reroll"):
            return False
        if game is None:
            try:
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game is None:
            return True
        owner_id = str(sr.get("spearhead_striker_turn_owner", "") or "")
        if owner_id:
            try:
                current = game.get_current_player()
            except Exception:
                current = None
            if current is None or str(getattr(current, "id", "") or "") != owner_id:
                return False
        try:
            turn = int(sr.get("spearhead_striker_turn", 0) or 0)
        except Exception:
            turn = 0
        if turn:
            try:
                if int(getattr(game, "turn", 0) or 0) != turn:
                    return False
            except Exception:
                return False
        return True

    def _murderous_onslaught_no_overwatch_active(self, *, game: Optional['Game'] = None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not sr.get("murderous_onslaught_no_overwatch"):
            return False
        if game is None:
            try:
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game is None:
            return True
        owner_id = str(sr.get("murderous_onslaught_turn_owner", "") or "")
        if owner_id:
            try:
                current = game.get_current_player()
            except Exception:
                current = None
            if current is None or str(getattr(current, "id", "") or "") != owner_id:
                return False
        try:
            turn = int(sr.get("murderous_onslaught_turn", 0) or 0)
        except Exception:
            turn = 0
        if turn:
            try:
                if int(getattr(game, "turn", 0) or 0) != turn:
                    return False
            except Exception:
                return False
        return True

    def _spearhead_striker_no_overwatch_active(self, *, game: Optional['Game'] = None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not sr.get("spearhead_striker_no_overwatch"):
            return False
        if game is None:
            try:
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game is None:
            return True
        owner_id = str(sr.get("spearhead_striker_turn_owner", "") or "")
        if owner_id:
            try:
                current = game.get_current_player()
            except Exception:
                current = None
            if current is None or str(getattr(current, "id", "") or "") != owner_id:
                return False
        try:
            turn = int(sr.get("spearhead_striker_turn", 0) or 0)
        except Exception:
            turn = 0
        if turn:
            try:
                if int(getattr(game, "turn", 0) or 0) != turn:
                    return False
            except Exception:
                return False
        return True

    def _post_shoot_no_overwatch_active(self, *, game: Optional['Game'] = None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not sr.get("post_shoot_no_overwatch_active"):
            return False
        return True

    def _periapt_of_torments_no_overwatch_active(self, *, target_unit: Optional['Unit'] = None) -> bool:
        try:
            active = bool(
                self._attached_unit_has_active_enhancement(
                    "enhancement_periapt_of_torments",
                    enhancement_id="000010580004",
                    enhancement_name="Periapt of Torments",
                )
            )
        except Exception:
            active = False
        if not active:
            return False
        if target_unit is None:
            return True
        try:
            my_army = self.get_parent_army()
        except Exception:
            my_army = None
        try:
            target_army = target_unit.get_parent_army()
        except Exception:
            target_army = None
        if my_army is None or target_army is None:
            return True
        return my_army is not target_army

    def is_overwatch_prevented_against(self, target_unit: 'Unit', *, game: Optional['Game'] = None) -> bool:
        if self._post_shoot_no_overwatch_active(game=game):
            return True
        if self._murderous_onslaught_no_overwatch_active(game=game):
            return True
        if self._spearhead_striker_no_overwatch_active(game=game):
            return True
        if self._periapt_of_torments_no_overwatch_active(target_unit=target_unit):
            return True
        entry = self._get_wargear_charge_keyword_effects(target_unit, game=game)
        if not entry:
            return False
        return bool(entry.get("no_overwatch", False))

    def has_thrill_seekers(self) -> bool:
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    nm = ab
                else:
                    nm = getattr(ab, "name", "")
                if "thrill seekers" in str(nm or "").lower():
                    return True
            except Exception:
                continue
        return False

    def _is_shadow_legion_detachment(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is not None:
            try:
                return bool(mgr.is_shadow_legion_detachment())
            except Exception:
                return False
        return False

    def _is_legion_of_excess_detachment(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is not None:
            try:
                return bool(mgr.is_legion_of_excess_detachment())
            except Exception:
                return False
        return False

    def _is_daemonic_incursion_detachment(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is not None:
            try:
                return bool(mgr.is_daemonic_incursion_detachment())
            except Exception:
                return False
        return False

    def _first_prince_of_chaos_active(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is not None:
            try:
                return bool(mgr.first_prince_of_chaos_active())
            except Exception:
                return False
        return False

    def _first_prince_has_god_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip()
        if not kw:
            return False
        try:
            if self.has_any_keyword(kw):
                return True
        except Exception:
            pass
        return False

    def has_first_prince_tzeentch_defense(self) -> bool:
        return self._first_prince_of_chaos_active() and self._first_prince_has_god_keyword("TZEENTCH")

    def has_first_prince_nurgle_defense(self) -> bool:
        return self._first_prince_of_chaos_active() and self._first_prince_has_god_keyword("NURGLE")

    def has_first_prince_slaanesh_no_overwatch(self) -> bool:
        return self._first_prince_of_chaos_active() and self._first_prince_has_god_keyword("SLAANESH")

    def _is_belakor(self) -> bool:
        name = str(getattr(self, "name", "") or "").lower().replace("\u2019", "'")
        return "belakor" in name or "be'lakor" in name

    def _is_chaos_undivided(self) -> bool:
        try:
            if (
                self.has_any_keyword("UNDIVIDED")
                or self.has_any_keyword("UNIDIVIDED")
                or self.has_any_keyword("CHAOS UNDIVIDED")
            ):
                return True
        except Exception:
            pass
        return self._is_belakor()

    def has_dark_pacts(self) -> bool:
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    nm = ab
                else:
                    nm = getattr(ab, "name", "")
                if "dark pacts" in str(nm or "").lower():
                    return True
            except Exception:
                continue
        return False

    def has_cabal_of_sorcerers(self) -> bool:
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    nm = ab
                else:
                    nm = getattr(ab, "name", "")
                if "cabal of sorcerers" in str(nm or "").lower():
                    return True
            except Exception:
                continue
        return False

    _EMPYRIC_WELLSPRING_CHOICES = ("LEAPING_WARPFLAME", "MONSTROUS_MANIFESTATION")

    def _is_cabal_of_chaos_detachment(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        if mgr is None:
            return False
        fn = getattr(mgr, "is_cabal_of_chaos", None)
        if not callable(fn):
            return False
        try:
            return bool(fn())
        except Exception:
            return False

    def dark_pacts_requires_empyric_wellspring_choice(self) -> bool:
        return self._is_cabal_of_chaos_detachment()

    def _current_phase_name_for_rules(self, game=None) -> str:
        phase_name = ""
        try:
            if game is None:
                army = self.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
                game = getattr(player, "game", None) if player is not None else None
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase_name = ""
        return phase_name

    def _active_empyric_wellspring_choice(self, *, game=None) -> str:
        if not self.dark_pacts_requires_empyric_wellspring_choice():
            return ""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        choice = str(sr.get("empyric_wellspring_choice", "") or "").strip().upper()
        if choice not in self._EMPYRIC_WELLSPRING_CHOICES:
            return ""
        expires_phase = str(sr.get("empyric_wellspring_expires_phase", "") or "").strip().upper()
        if expires_phase:
            current_phase = self._current_phase_name_for_rules(game=game)
            if current_phase and current_phase != expires_phase:
                return ""
        return choice

    @staticmethod
    def _entity_has_keyword_for_empyric(entity, keyword: str) -> bool:
        kw = str(keyword or "").strip()
        if entity is None or not kw:
            return False
        try:
            has_any = getattr(entity, "has_any_keyword", None)
            if callable(has_any) and bool(has_any(kw)):
                return True
        except Exception:
            pass
        try:
            has_local = getattr(entity, "has_keyword", None)
            if callable(has_local) and bool(has_local(kw)):
                return True
        except Exception:
            pass
        return False

    def _model_matches_empyric_source(self, model, *, choice: str) -> bool:
        parent_unit = getattr(model, "parent_unit", None)
        has_heretic_astartes = self._entity_has_keyword_for_empyric(model, "HERETIC ASTARTES") or self._entity_has_keyword_for_empyric(
            parent_unit, "HERETIC ASTARTES"
        )
        if not has_heretic_astartes:
            return False
        choice_key = str(choice or "").strip().upper()
        if choice_key == "LEAPING_WARPFLAME":
            return self._entity_has_keyword_for_empyric(model, "PSYKER") or self._entity_has_keyword_for_empyric(parent_unit, "PSYKER")
        if choice_key != "MONSTROUS_MANIFESTATION":
            return False
        if (
            self._entity_has_keyword_for_empyric(model, "DAEMON PRINCE")
            or self._entity_has_keyword_for_empyric(parent_unit, "DAEMON PRINCE")
            or self._entity_has_keyword_for_empyric(model, "DAEMON PRINCE WITH WINGS")
            or self._entity_has_keyword_for_empyric(parent_unit, "DAEMON PRINCE WITH WINGS")
        ):
            return True
        text = f"{getattr(model, 'name', '')} {getattr(parent_unit, 'name', '')}".lower().replace("\u2019", "'")
        return ("daemon prince with wings" in text) or ("daemon prince" in text)

    def _friendly_empyric_source_within_range(self, *, choice: str, radius: float = 9.0) -> bool:
        choice_key = str(choice or "").strip().upper()
        if choice_key not in self._EMPYRIC_WELLSPRING_CHOICES:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        try:
            from ...utility.aura_utils import model_within_range_of_unit
        except Exception:
            return False

        seen_roots: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                source_root = unit.get_attached_unit_root()
            except Exception:
                source_root = unit
            if source_root is None:
                continue
            source_id = str(get_entity_id(source_root) or "")
            if source_id:
                if source_id in seen_roots:
                    continue
                seen_roots.add(source_id)
            try:
                if not bool(getattr(source_root, "deployed", True)):
                    continue
                if bool(getattr(source_root, "is_embarked", False)):
                    continue
                if callable(getattr(source_root, "is_in_reserves", None)) and bool(source_root.is_in_reserves()):
                    continue
            except Exception:
                continue
            try:
                if not bool(source_root.is_alive()):
                    continue
            except Exception:
                continue
            try:
                source_models = list(source_root.get_attached_unit_models() or [])
            except Exception:
                source_models = list(getattr(source_root, "models", []) or [])
            for model in list(source_models or []):
                if model is None:
                    continue
                if not bool(getattr(model, "is_alive", True)):
                    continue
                if not self._model_matches_empyric_source(model, choice=choice_key):
                    continue
                try:
                    if model_within_range_of_unit(model, root, float(radius), use_attached_aggregate=True):
                        return True
                except Exception:
                    continue
        return False

    def get_empyric_wellspring_ranged_strength_bonus(self, *, game=None) -> tuple[int, str]:
        choice = self._active_empyric_wellspring_choice(game=game)
        if choice != "LEAPING_WARPFLAME":
            return 0, ""
        if not self._friendly_empyric_source_within_range(choice=choice, radius=9.0):
            return 0, ""
        return 1, "Leaping Warpflame"

    def get_empyric_wellspring_melee_ap_bonus(self, *, game=None) -> tuple[int, str]:
        choice = self._active_empyric_wellspring_choice(game=game)
        if choice != "MONSTROUS_MANIFESTATION":
            return 0, ""
        if not self._friendly_empyric_source_within_range(choice=choice, radius=9.0):
            return 0, ""
        return 1, "Monstrous Manifestation"

    def has_martial_katah(self) -> bool:
        if "martial_katah" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["martial_katah"])

        def _norm(text: str) -> str:
            return str(text or "").replace("\u2019", "'").replace("\u0192?T", "'").lower()

        patterns = ("martial ka'tah", "martial katah")
        found = False
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = getattr(ab, "name", "") or ""
                    desc = getattr(ab, "description", "") or ""
                text = _norm(f"{name} {desc}")
                if any(p in text for p in patterns):
                    found = True
                    break
            except Exception:
                continue

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["martial_katah"] = found
        return found

    def master_of_stances_spec(self) -> Optional[dict]:
        """
        Return spec for Master of the Stances (once per battle, both stances active) if present.

        Spec keys:
            - source: ability name
            - model_id: leader model id (or unit model)
            - ability_key: stable once-per-battle key
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "master_of_stances_spec"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        candidates = [root]
        try:
            candidates.extend(list(getattr(root, "attached_leaders", []) or []))
        except Exception:
            pass
        seen_ids = set()
        spec = None
        for cand in candidates:
            if cand is None:
                continue
            cid = get_entity_id(cand)
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            for name, desc in cand._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = cand._strip_eligibility_prefix(text_src)
                normalized = cand._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not self._MASTER_OF_STANCES_RE.fullmatch(normalized):
                    continue
                try:
                    models = list(getattr(cand, "models", []) or [])
                except Exception:
                    models = []
                model = None
                for m in list(models or []):
                    if getattr(m, "is_alive", True):
                        model = m
                        break
                if model is None:
                    continue
                source = str(name or "Master of the Stances").strip() or "Master of the Stances"
                spec = {
                    "source": source,
                    "model_id": get_entity_id(model),
                    "ability_key": "master_of_stances",
                }
                break
            if spec:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = spec
        return spec

    def model_moment_shackle_spec(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return spec for Moment Shackle (once per battle, start of Fight phase) for a model.

        Spec keys:
            - source: ability name
            - weapon_name: str
            - attacks: int
            - invuln: int
            - ability_key: str
        """
        if model is None:
            return None
        cache_key = f"model_moment_shackle:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]
        spec = None
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9+]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._MOMENT_SHACKLE_RE.fullmatch(normalized)
            if not m:
                if str(name or "").strip().lower() != "moment shackle":
                    continue
                m = None
            weapon_name = ""
            attacks = 0
            invuln = 0
            if m:
                weapon_name = str(m.group("weapon") or "").strip()
                try:
                    attacks = int(m.group("attacks") or 0)
                except Exception:
                    attacks = 0
                try:
                    invuln = int(m.group("invuln") or 0)
                except Exception:
                    invuln = 0
            if not weapon_name:
                weapon_name = "Watcher's Axe"
            if attacks <= 0:
                attacks = 12
            if invuln <= 0:
                invuln = 2
            source = str(name or "Moment Shackle").strip() or "Moment Shackle"
            spec = {
                "source": source,
                "weapon_name": weapon_name,
                "attacks": int(attacks),
                "invuln": int(invuln),
                "ability_key": "moment_shackle",
            }
            break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = spec
        return spec

    def can_use_dark_pacts(self) -> bool:
        has_pacts = self.has_dark_pacts()
        first_prince = self._first_prince_of_chaos_active() and self._is_chaos_undivided()
        if not has_pacts and not first_prince:
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return True
        fid = str(getattr(army, "faction_id", "") or "").strip().upper()
        if fid and fid != "CSM" and not first_prince:
            return False
        return True

    def _auto_pass_dark_pacts_test(self) -> bool:
        return self._first_prince_of_chaos_active() and self._is_belakor()

    def _dark_ascension_aura_applies(self, game_map=None) -> bool:
        """Return True if this unit is affected by Dark Ascension (Aura)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None or not getattr(root, "is_alive", lambda: False)():
            return False
        try:
            if not root.has_any_keyword("HERETIC ASTARTES"):
                return False
        except Exception:
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        try:
            if game_map is None:
                game_map = getattr(getattr(army, "player", None), "game", None).map
        except Exception:
            game_map = None
        try:
            from ...utility.aura_utils import unit_within_range_of_unit
            from ...utility.entity_ids import get_entity_id
        except Exception:
            return False

        seen_roots: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                source_root = unit.get_attached_unit_root()
            except Exception:
                source_root = unit
            if source_root is None:
                continue
            try:
                source_id = str(get_entity_id(source_root) or "")
            except Exception:
                source_id = ""
            if source_id:
                if source_id in seen_roots:
                    continue
                seen_roots.add(source_id)
            if not getattr(source_root, "is_alive", lambda: False)():
                continue
            try:
                if not getattr(source_root, "deployed", True):
                    continue
                if source_root.is_in_reserves() or source_root.is_embarked:
                    continue
            except Exception:
                pass
            has_aura = getattr(source_root, "has_dark_ascension_aura", None)
            if not callable(has_aura) or not bool(has_aura()):
                continue
            try:
                if unit_within_range_of_unit(root, source_root, 6.0, game_map=game_map):
                    return True
            except Exception:
                continue
        return False

    def _maybe_gain_dark_destiny_cp(self, game, *, passed: bool, auto_passed: bool) -> None:
        if not passed or auto_passed:
            return
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return
        try:
            if not root.has_dark_destiny():
                return
        except Exception:
            return
        try:
            modified_roll = int(getattr(root, "_last_leadership_test_modified_roll", 0) or 0)
        except Exception:
            return
        if modified_roll < 7:
            return
        try:
            player = getattr(root.get_parent_army(), "player", None)
        except Exception:
            player = None
        if player is None:
            return
        gain_fn = getattr(player, "gain_command_points", None)
        if not callable(gain_fn):
            return
        try:
            gained = int(gain_fn(1, reason="Dark Destiny") or 0)
        except Exception:
            gained = 0
        if gained <= 0:
            return
        try:
            from ...utility.event_bus import append_action
            append_action(player, f"Dark Destiny: {getattr(root, 'name', 'Unit')} gained {int(gained)} CP.")
        except Exception:
            pass

    def apply_dark_pacts_choice(
        self,
        game,
        *,
        choice: str,
        phase_name: str,
        trigger: str,
        empyric_wellspring_choice: Optional[str] = None,
    ) -> bool:
        trigger_norm = str(trigger or "").strip().lower()
        if trigger_norm not in ("shooting", "fight"):
            return False
        if not self.can_use_dark_pacts():
            return False
        choice_norm = str(choice or "").strip().upper()
        options = ("LETHAL HITS", "SUSTAINED HITS 1")
        if choice_norm not in options:
            return False
        empyric_required = self.dark_pacts_requires_empyric_wellspring_choice()
        empyric_choice_norm = str(empyric_wellspring_choice or "").strip().upper()
        if empyric_required and empyric_choice_norm not in self._EMPYRIC_WELLSPRING_CHOICES:
            return False
        if not empyric_required:
            empyric_choice_norm = ""
        passed = True
        auto_passed = self._auto_pass_dark_pacts_test()
        if not auto_passed:
            try:
                extra_sources = list(self.dark_pacts_leadership_reroll_sources() or [])
            except Exception:
                extra_sources = []
            try:
                if extra_sources:
                    passed = bool(
                        self.pass_leadership_check(
                            extra_reroll_sources=extra_sources,
                            reroll_reason="Dark Pacts re-roll",
                        )
                    )
                else:
                    passed = bool(self.pass_leadership_check())
            except Exception:
                passed = False
            self._maybe_gain_dark_destiny_cp(game, passed=bool(passed), auto_passed=False)
        if not passed:
            try:
                from ...utility.dice import DiceCollection
                dmg_roll, _dice = DiceCollection.from_string("D3").roll_detailed()
                self._apply_mortal_wounds_to_unit(self, int(dmg_roll or 0), game_map=getattr(game, "map", None))
            except Exception:
                pass
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        phase_key = str(phase_name or "").strip().upper() or "FIGHT_PHASE"
        dark_ascension_active = self._dark_ascension_aura_applies(game_map=getattr(game, "map", None))
        sr["dark_pacts_active"] = True
        sr["dark_pacts_choice"] = "BOTH" if dark_ascension_active else choice_norm
        sr["dark_pacts_expires_phase"] = phase_key
        if empyric_required:
            sr["empyric_wellspring_choice"] = empyric_choice_norm
            sr["empyric_wellspring_expires_phase"] = phase_key
            sr["empyric_wellspring_source"] = "Empyric Wellspring"
        else:
            sr.pop("empyric_wellspring_choice", None)
            sr.pop("empyric_wellspring_expires_phase", None)
            sr.pop("empyric_wellspring_source", None)
        if dark_ascension_active:
            sr["dark_ascension_active"] = True
            sr["dark_ascension_expires_phase"] = phase_key
            sr["dark_ascension_source"] = "Dark Ascension (Aura)"
        # Despoilers: re-roll Hit roll after making a Dark Pact.
        if root.has_despoilers():
            sr["despoilers_active"] = True
            sr["despoilers_expires_phase"] = phase_key
            sr["despoilers_source"] = "Despoilers"
        # Unholy Bloodshed: once per battle, gain Devastating Wounds until end of phase.
        if root.has_unholy_bloodshed():
            once_key = "unholy_bloodshed"
            if not root.has_used_unit_once_per_battle(once_key):
                sr["unholy_bloodshed_active"] = True
                sr["unholy_bloodshed_expires_phase"] = phase_key
                sr["unholy_bloodshed_source"] = "Unholy Bloodshed"
                root.mark_unit_once_per_battle_used(once_key, ability_name="Unholy Bloodshed")
        root.special_rules = sr
        return True

    def maybe_trigger_dark_pacts(self, game, *, phase_name: str, trigger: str) -> None:
        trigger_norm = str(trigger or "").strip().lower()
        if trigger_norm not in ("shooting", "fight"):
            return
        if not self.can_use_dark_pacts():
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        try:
            player = self.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return
        try:
            sr = getattr(self, "special_rules", None)
            exp = ""
            if isinstance(sr, dict):
                exp = str(sr.get("dark_pacts_expires_phase", "") or "").strip().upper()
                if sr.get("dark_pacts_active") and exp == str(phase_name or "").strip().upper():
                    return
        except Exception:
            pass
        try:
            from ...engine.decision_kinds import DECISION_CHOOSE_DARK_PACT
            from ...engine.decisions import DecisionOption, DecisionRequest
            from ...utility.entity_ids import get_entity_id
        except Exception:
            return

        unit_id = get_entity_id(self)
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_DARK_PACT:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("unit_id", "")) == str(unit_id) and str(ctx.get("phase_name", "")) == str(phase_name or ""):
                    return

        decision_options = [
            DecisionOption.create(
                "Skip Dark Pact",
                payload={"action": "skip", "unit_id": unit_id, "phase_name": phase_name or "", "trigger": trigger or ""},
            ),
        ]
        base_choices = (
            ("LETHAL HITS", "Lethal Hits"),
            ("SUSTAINED HITS 1", "Sustained Hits 1"),
        )
        empyric_required = bool(self.dark_pacts_requires_empyric_wellspring_choice())
        if empyric_required:
            empyric_choices = (
                (
                    "LEAPING_WARPFLAME",
                    "Leaping Warpflame",
                    "While within 9\" of a friendly HERETIC ASTARTES PSYKER model, improve ranged Strength by 1.",
                ),
                (
                    "MONSTROUS_MANIFESTATION",
                    "Monstrous Manifestation",
                    "While within 9\" of a friendly HERETIC ASTARTES DAEMON PRINCE model, improve melee AP by 1.",
                ),
            )
            for dark_pact_choice, dark_pact_label in base_choices:
                for empyric_choice, empyric_label, empyric_summary in empyric_choices:
                    decision_options.append(
                        DecisionOption.create(
                            f"{dark_pact_label} + {empyric_label}",
                            payload={
                                "choice": dark_pact_choice,
                                "empyric_wellspring_choice": empyric_choice,
                                "summary": f"{dark_pact_label}; {empyric_summary}",
                                "unit_id": unit_id,
                                "phase_name": phase_name or "",
                                "trigger": trigger or "",
                            },
                        )
                    )
        else:
            for dark_pact_choice, dark_pact_label in base_choices:
                decision_options.append(
                    DecisionOption.create(
                        dark_pact_label,
                        payload={
                            "choice": dark_pact_choice,
                            "unit_id": unit_id,
                            "phase_name": phase_name or "",
                            "trigger": trigger or "",
                        },
                    )
                )
        req = DecisionRequest.create(
            DECISION_CHOOSE_DARK_PACT,
            f"Select Dark Pact for {getattr(self, 'name', 'Unit')}",
            player_id=getattr(player, "id", None),
            options=decision_options,
            context={
                "unit_id": unit_id,
                "phase_name": phase_name or "",
                "trigger": trigger or "",
                "empyric_wellspring_required": empyric_required,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)

    def apply_path_of_warrior_choice(self, game, *, choice: str, phase_name: str) -> bool:
        choice_norm = str(choice or "").strip().upper()
        if choice_norm not in ("HIT", "WOUND", "BOTH"):
            return False
        self.set_path_of_warrior_choice(choice_norm, phase_name=str(phase_name or "").strip().upper())
        return True

    def maybe_trigger_path_of_warrior(self, game, *, phase_name: str, trigger: str) -> None:
        trigger_norm = str(trigger or "").strip().lower()
        if trigger_norm not in ("shooting", "fight"):
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        if mgr is None or not getattr(mgr, "path_of_the_warrior_applies", lambda _u: False)(root):
            return

        try:
            leaders = list(getattr(root, "attached_leaders", []) or [])
        except Exception:
            leaders = []
        for leader in leaders:
            sr = getattr(leader, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_mantle_of_wisdom"):
                root.set_path_of_warrior_choice("BOTH", phase_name=str(phase_name or "").strip().upper())
                return

        try:
            from ...engine.decision_kinds import DECISION_CHOOSE_PATH_OF_WARRIOR
            from ...engine.decisions import DecisionOption, DecisionRequest
            from ...utility.entity_ids import get_entity_id
        except Exception:
            return

        unit_id = get_entity_id(root)
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_PATH_OF_WARRIOR:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("unit_id", "")) != str(unit_id):
                    continue
                if str(ctx.get("phase_name", "")) != str(phase_name or ""):
                    continue
                if str(ctx.get("trigger", "")) != str(trigger or ""):
                    continue
                return

        decision_options = [
            DecisionOption.create(
                "Re-roll Hit 1s",
                payload={
                    "choice_key": "HIT",
                    "unit_id": unit_id,
                    "phase_name": phase_name or "",
                    "trigger": trigger or "",
                    "summary": "Re-roll Hit rolls of 1.",
                },
            ),
            DecisionOption.create(
                "Re-roll Wound 1s",
                payload={
                    "choice_key": "WOUND",
                    "unit_id": unit_id,
                    "phase_name": phase_name or "",
                    "trigger": trigger or "",
                    "summary": "Re-roll Wound rolls of 1.",
                },
            ),
        ]
        req = DecisionRequest.create(
            DECISION_CHOOSE_PATH_OF_WARRIOR,
            f"Select Path of the Warrior for {getattr(root, 'name', 'Unit')}",
            player_id=getattr(getattr(army, "player", None), "id", None),
            options=decision_options,
            context={"unit_id": unit_id, "phase_name": phase_name or "", "trigger": trigger or ""},
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)

    def prepare_advance(self) -> Optional[int]:
        """Pre-roll advance dice for UI display. Returns the advance roll."""
        if not hasattr(self.round_state, 'advance_roll') or self.round_state.advance_roll is None:
            advance_roll = None
            miracle_used = False
            fixed_roll = None
            fixed_source = None
            army = None
            player = None
            game = None
            no_roll_effect = self._get_advance_no_roll_effect()
            if isinstance(no_roll_effect, dict):
                try:
                    fixed_roll = int(no_roll_effect.get("distance", 0) or 0)
                except Exception:
                    fixed_roll = None
                if fixed_roll is not None and fixed_roll > 0:
                    fixed_source = "no_roll"
                else:
                    fixed_roll = None
            try:
                if fixed_roll is None:
                    sr = getattr(self, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("chronoshift_active"):
                        exp = str(sr.get("chronoshift_expires_phase", "") or "").strip().upper()
                        apply_bonus = True
                        if exp:
                            try:
                                army = self.get_parent_army()
                                game = getattr(getattr(army, "player", None), "game", None)
                                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                            except Exception:
                                pname = ""
                            if pname and pname != exp:
                                apply_bonus = False
                        if apply_bonus and (not exp or exp == "MOVEMENT_PHASE"):
                            fixed_roll = 6
                            fixed_source = "rule"
            except Exception:
                pass
            try:
                army = self.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
                game = getattr(player, "game", None) if player is not None else None
            except Exception:
                game = None
                player = None
            # Acts of Faith: allow Miracle die selection (no roll needed if used).
            if fixed_roll is None:
                try:
                    mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                    if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                        chosen = mgr.maybe_use_miracle_die(
                            self,
                            roll_type="advance",
                            dice_count=1,
                            die_faces=6,
                            game=game,
                        )
                        if chosen is not None:
                            fixed_roll = int(chosen)
                            fixed_source = "miracle"
                            miracle_used = True
                except Exception:
                    fixed_roll = fixed_roll
                    miracle_used = False

            if game is None or player is None:
                if fixed_roll is not None:
                    try:
                        advance_roll = self._apply_advance_roll_modifiers(int(fixed_roll))
                    except Exception:
                        advance_roll = int(fixed_roll)
                    try:
                        self.round_state.advance_roll = int(advance_roll)
                    except Exception:
                        pass
                    try:
                        from ...utility.event_bus import append_dice
                        if player is not None:
                            append_dice(player, f"Advance roll fixed: {int(advance_roll)} for {self.name}")
                    except Exception:
                        pass
                    return int(advance_roll)
                return None
            if not bool(getattr(game, "is_authoritative", True)):
                return None

            from ...utility.entity_ids import get_entity_id
            from ...engine.roll_utils import command_reroll_available
            reroll_rules = []
            try:
                if fixed_source is None and self.can_reroll_advance_roll():
                    reroll_rules.append(
                        {
                            "action_id": "reroll_advance",
                            "label": "Re-roll Advance roll",
                            "mode": "all",
                            "source": "rule",
                        }
                    )
            except Exception:
                pass
            mgr = getattr(game, "fates_in_flux", None)
            if mgr is not None:
                flux_rule = mgr.build_reroll_rule(game=game, player=player, unit=self, roll_type="advance")
                if flux_rule:
                    reroll_rules.append(flux_rule)
            if fixed_source is None:
                from ...rules.perfectly_adapted import build_perfectly_adapted_reroll_rule

                pa_rule = build_perfectly_adapted_reroll_rule(
                    unit=self,
                    game=game,
                    roll_type="advance",
                )
                if pa_rule:
                    reroll_rules.append(pa_rule)
            command_reroll_ok = False
            if fixed_source is None:
                command_reroll_ok = command_reroll_available(game, player, roll_type="advance")
            spec = {
                "dice_count": 1,
                "faces": 6,
                "reason": f"Advance roll for {self.name}",
                "roll_type": "advance",
                "unit_id": get_entity_id(self),
                "handler_key": "advance_roll",
                "reroll_rules": reroll_rules,
                "command_reroll_allowed": command_reroll_ok,
                "command_reroll_mode": "one",
            }
            if fixed_roll is not None:
                spec["fixed_dice"] = [int(fixed_roll)]
                if fixed_source == "miracle":
                    spec["miracle_used"] = True
            try:
                if bool(getattr(game, "auto_resolve_dice_rolls", False)):
                    if fixed_roll is None:
                        fixed_val = int(get_roll("D6") or 0)
                        spec["fixed_dice"] = [fixed_val]
                    if (reroll_rules or command_reroll_ok) and fixed_source is None:
                        spec["roll_sequence"] = [int(get_roll("D6") or 0)]
            except Exception:
                pass
            req = None
            try:
                req = game.request_dice_roll(player_id=getattr(player, "id", None), spec=spec, prompt=spec["reason"])
            except Exception:
                pass
            try:
                roll_id = None
                if req is not None:
                    roll_id = getattr(req, "context", {}).get("roll_id")
                self.round_state.advance_roll_id = roll_id
            except Exception:
                pass
            if bool(getattr(game, "auto_resolve_dice_rolls", False)):
                return self.round_state.advance_roll
            return None
        return self.round_state.advance_roll

    def get_advance_roll(self) -> int:
        """Get the current advance roll, or None if not rolled yet."""
        return getattr(self.round_state, 'advance_roll', None)

    def _path_crosses_tall_terrain(self, path, game_map, *, height_threshold: float = 4.0) -> bool:
        try:
            from shapely.geometry import LineString
        except Exception:
            return False
        if game_map is None:
            return False
        try:
            terrain_features = list(getattr(game_map, "terrain_features", []) or [])
        except Exception:
            terrain_features = []
        if not terrain_features:
            return False

        for i in range(1, len(path or [])):
            try:
                x0, y0 = float(path[i - 1][0]), float(path[i - 1][1])
                x1, y1 = float(path[i][0]), float(path[i][1])
            except Exception:
                continue
            seg = LineString([(x0, y0), (x1, y1)])
            for terrain in terrain_features:
                footprint = getattr(terrain, "footprint", None)
                if footprint is None:
                    continue
                try:
                    if not seg.intersects(footprint):
                        continue
                except Exception:
                    continue

                walls = getattr(terrain, "walls", None)
                if walls:
                    for wall in list(walls or []):
                        try:
                            poly = wall.get("polygon", None)
                            if poly is None or not seg.intersects(poly):
                                continue
                            z0 = float(wall.get("z_bottom", 0.0) or 0.0)
                            z1 = float(wall.get("z_top", 0.0) or 0.0)
                            if (z1 - z0) > height_threshold:
                                return True
                        except Exception:
                            continue

                feature_height = None
                try:
                    if hasattr(terrain, "height"):
                        feature_height = float(getattr(terrain, "height", 0.0) or 0.0)
                    elif hasattr(terrain, "rim_height"):
                        feature_height = float(getattr(terrain, "rim_height", 0.0) or 0.0)
                    elif hasattr(terrain, "bounding_box") and isinstance(terrain.bounding_box, dict):
                        max_z = float(terrain.bounding_box.get("max", (0.0, 0.0, 0.0))[2] or 0.0)
                        min_z = float(terrain.bounding_box.get("min", (0.0, 0.0, 0.0))[2] or 0.0)
                        feature_height = max_z - min_z
                except Exception:
                    feature_height = None
                if feature_height is not None and feature_height > height_threshold:
                    return True

        return False

    def _apply_super_heavy_walker_terrain_shock(self, game_map, *, action: str) -> None:
        if action not in ("move", "advance", "fall_back"):
            return
        if game_map is None:
            return
        height_threshold = None
        source = "Super-heavy Walker"
        if self.has_super_heavy_walker():
            height_threshold = 4.0
        else:
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("titanic_stride_tall_terrain_height"):
                    height_threshold = float(sr.get("titanic_stride_tall_terrain_height") or 0.0)
                    source = str(sr.get("titanic_stride_source", "") or "Titanic Strides").strip() or "Titanic Strides"
            except Exception:
                height_threshold = None
        if not height_threshold:
            return

        any_crossed = False
        for model in list(getattr(self, "models", []) or []):
            try:
                if not getattr(model, "is_alive", True):
                    continue
            except Exception:
                continue
            path = getattr(model, "last_move_path", None)
            if not path or len(path) < 2:
                continue
            if self._path_crosses_tall_terrain(path, game_map, height_threshold=float(height_threshold)):
                any_crossed = True
                break

        if not any_crossed:
            return

        roll = int(get_roll("D6"))
        try:
            from ...utility.event_bus import append_dice
            pn = self.get_parent_army().player
            append_dice(pn, f"{source} terrain roll: {roll} for {self.name}")
        except Exception:
            pass
        if roll != 1:
            return

        try:
            game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            current_turn = int(getattr(game, "turn", 1) or 1) if game is not None else 1
        except Exception:
            current_turn = 1

        try:
            if not self.is_battle_shocked():
                self.apply_status_effect(BattleShockEffect(current_turn))
        except Exception:
            pass
        logger.info(f"{self.name} is battle-shocked after moving through tall terrain ({source}).")

    def advance(self, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        if bool(getattr(self, "is_aircraft", False)):
            logger.info(f"{self.name} cannot Advance (AIRCRAFT)")
            return False
        # Check if unit can advance after arriving from reserves
        if self.arrived_from_reserves_this_turn and not self.can_advance_after_arriving_from_reserves():
            logger.info(f"{self.name} cannot advance - arrived from reserves this turn")
            return False
        return self.move(destination, game_map, advance=True)

    def _aircraft_normal_move(
        self,
        destination: Tuple[float, float, float],
        game_map: 'Map',
        *,
        pivot_degrees: Optional[float] = None,
    ) -> bool:
        """Resolve AIRCRAFT Normal move (straight line, minimum 20", no max; optional post-move pivot)."""
        if not self.models:
            logger.error(f"Cannot move unit {self.name}: no models in unit")
            return False

        # Check if unit can move after arriving from reserves
        if self.arrived_from_reserves_this_turn and not self.can_move_after_arriving_from_reserves():
            logger.info(f"{self.name} cannot move - arrived from reserves this turn")
            return False

        # Use first alive model as reference
        model = next((m for m in self.models if getattr(m, "is_alive", False)), None)
        if model is None:
            logger.error(f"Cannot move unit {self.name}: no valid models")
            return False

        start_pos = model.get_location()
        if not start_pos:
            logger.error(f"Cannot move unit {self.name}: first model has no position")
            return False

        try:
            dest_x = float(destination[0])
            dest_y = float(destination[1])
        except Exception:
            logger.error(f"Cannot move unit {self.name}: invalid destination")
            return False

        start_x, start_y = float(start_pos[0]), float(start_pos[1])
        start_z = float(start_pos[2]) if len(start_pos) > 2 else 0.0

        facing = float(getattr(model.model_base, "facing", 0.0) or 0.0)
        # Facing 0 points along +Y (consistent with get_angle usage)
        forward_x = math.sin(facing)
        forward_y = math.cos(facing)

        dx = dest_x - start_x
        dy = dest_y - start_y
        forward_dist = (dx * forward_x) + (dy * forward_y)
        # Lateral offset (perpendicular to facing)
        side_dist = (dx * forward_y) - (dy * forward_x)

        # Straight-line requirement
        if forward_dist <= 1e-6:
            logger.info(f"{self.name} must move forward (AIRCRAFT)")
            return False
        if abs(side_dist) > 0.25:
            logger.info(f"{self.name} must move straight forward (AIRCRAFT)")
            return False

        min_move = 20.0

        # Helper: required forward distance for base-to-base >= min_move
        def _required_forward_distance_for_model(m) -> float:
            from ...utility.aura_utils import horizontal_distance_between_bases_2d
            base_start = m.model_base
            # Expand search window until requirement satisfied (should converge quickly)
            hi = max(min_move, 1.0)
            for _ in range(16):
                test_base = self._create_potential_base(
                    base_start.x + forward_x * hi,
                    base_start.y + forward_y * hi,
                    base_start.z,
                    facing,
                    model=m,
                )
                if float(horizontal_distance_between_bases_2d(base_start, test_base)) >= min_move:
                    break
                hi *= 1.5
            lo = 0.0
            for _ in range(20):
                mid = (lo + hi) / 2.0
                test_base = self._create_potential_base(
                    base_start.x + forward_x * mid,
                    base_start.y + forward_y * mid,
                    base_start.z,
                    facing,
                    model=m,
                )
                if float(horizontal_distance_between_bases_2d(base_start, test_base)) >= min_move:
                    hi = mid
                else:
                    lo = mid
            return float(hi)

        # Compute minimum forward distance required for all models (base-to-base >= 20")
        required_forward = 0.0
        for m in self.models:
            if not getattr(m, "is_alive", False):
                continue
            try:
                required_forward = max(required_forward, _required_forward_distance_for_model(m))
            except Exception:
                required_forward = max(required_forward, min_move)

        def _forward_move_within_boundary(dist: float) -> bool:
            if game_map is None:
                return True
            for m in self.models:
                if not getattr(m, "is_alive", False):
                    continue
                new_x = float(m.model_base.x) + forward_x * dist
                new_y = float(m.model_base.y) + forward_y * dist
                if not game_map.is_within_boundary(m, (new_x, new_y)):
                    return False
            return True

        def _send_to_strategic_reserves(reason: str) -> bool:
            try:
                if hasattr(self, "set_reserve_status"):
                    self.set_reserve_status("strategic_reserves")
                else:
                    self.reserve_status = "strategic_reserves"
            except Exception:
                pass
            try:
                if hasattr(self, "mark_entered_reserves_midgame"):
                    game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                    self.mark_entered_reserves_midgame(game=game)
            except Exception:
                pass
            try:
                self.deployed = True
                self.reserve_turn_deployed = None
                self.arrived_from_reserves_this_turn = False
            except Exception:
                pass
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            except Exception:
                current_turn = 0
            try:
                if current_turn > 0:
                    setattr(self, "_aircraft_return_turn", current_turn + 1)
            except Exception:
                pass
            try:
                if game_map is not None and hasattr(game_map, "units") and self in game_map.units:
                    game_map.units.remove(self)
            except Exception:
                pass
            if reason:
                logger.info(f"{self.name} placed into Strategic Reserves ({reason})")
            else:
                logger.info(f"{self.name} placed into Strategic Reserves")
            return True

        # Minimum Move enforcement
        if forward_dist + 1e-6 < required_forward:
            if not _forward_move_within_boundary(required_forward):
                return _send_to_strategic_reserves("minimum move impossible")
            return _send_to_strategic_reserves("minimum move not met")

        # Leaving the battlefield -> Strategic Reserves
        if not _forward_move_within_boundary(forward_dist):
            return _send_to_strategic_reserves("left the battlefield")

        move_dx = forward_x * forward_dist
        move_dy = forward_y * forward_dist

        # Build proposed positions
        proposed = []
        for m in self.models:
            if not getattr(m, "is_alive", False):
                continue
            new_x = float(m.model_base.x) + move_dx
            new_y = float(m.model_base.y) + move_dy
            new_z = game_map.get_height_at_point(new_x, new_y) if game_map else float(m.model_base.z)
            proposed.append((m, new_x, new_y, new_z))

        # Final-position validation: no overlaps, no ending in engagement range
        if game_map is not None:
            for m, nx, ny, _nz in proposed:
                if game_map.check_collision_with_other_friendly_units(m, (nx, ny)):
                    logger.info(f"{self.name} cannot move - {m.name} would overlap a friendly model")
                    return False
                if game_map.check_collision_with_other_enemy_units(m, (nx, ny)):
                    logger.info(f"{self.name} cannot move - {m.name} would overlap an enemy model")
                    return False

            from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
            from ...utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
            for enemy in game_map.get_enemy_units(self):
                if not enemy.is_alive() or not enemy.deployed:
                    continue
                for em in enemy.models:
                    if not getattr(em, "is_alive", False):
                        continue
                    for m, nx, ny, nz in proposed:
                        test_base = self._create_potential_base(nx, ny, nz, facing, model=m)
                        horiz = float(horizontal_distance_between_bases_2d(test_base, em.model_base))
                        vert = float(vertical_distance_between_bases(test_base, em.model_base))
                        if horiz <= ENGAGEMENT_RANGE_HORIZONTAL and vert <= ENGAGEMENT_RANGE_VERTICAL:
                            logger.info(f"{self.name} cannot end within Engagement Range (AIRCRAFT)")
                            return False

        final_facing = facing
        if pivot_degrees is not None:
            try:
                pivot_val = float(pivot_degrees)
            except (TypeError, ValueError):
                pivot_val = 0.0
            pivot_val = max(-90.0, min(90.0, pivot_val))
            final_facing = (facing + math.radians(pivot_val)) % (2.0 * math.pi)

        # Apply movement (pivot after move is optional)
        for m, nx, ny, nz in proposed:
            try:
                m.last_move_path = [
                    (m.model_base.x, m.model_base.y, m.model_base.z, m.model_base.facing),
                    (nx, ny, nz, final_facing),
                ]
            except Exception:
                pass
            m.set_location(nx, ny, nz, final_facing)

        pivot_note = ""
        if pivot_degrees:
            try:
                pivot_note = f", pivot {float(pivot_degrees):.1f}°"
            except (TypeError, ValueError):
                pivot_note = ""
        logger.info(f"{self.name} moved from ({start_x:.1f}, {start_y:.1f}) "
            f"to ({start_x + move_dx:.1f}, {start_y + move_dy:.1f}) "
            f"- distance: {forward_dist:.1f}\"{pivot_note}")
        return True

    def move(
        self,
        destination: Tuple[float, float, float],
        game_map: 'Map',
        advance: bool = False,
        *,
        aircraft_pivot_degrees: Optional[float] = None,
    ) -> bool:
        """
        Moves the unit towards the destination using optimized individual model pathfinding.
        
        This method now uses the new pathfinding system that:
        1. Moves models individually using optimized pathfinding
        2. Validates coherency after all models have moved
        3. If coherency would be broken at the end of the move, the move is NOT allowed and is rolled back
        """
        if bool(getattr(self, "is_aircraft", False)):
            return self._aircraft_normal_move(destination, game_map, pivot_degrees=aircraft_pivot_degrees)
        if not self.models:
            logger.error(f"Cannot move unit {self.name}: no models in unit")
            return False
        
        # Check if unit can move after arriving from reserves
        if self.arrived_from_reserves_this_turn and not self.can_move_after_arriving_from_reserves():
            logger.info(f"{self.name} cannot move - arrived from reserves this turn")
            return False

        # Get starting position from first model for feedback
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot move unit {self.name}: no valid models")
            return False

        first_model = self.models[0]
        if callable(getattr(first_model, "get_location", None)):
            first_model_pos = first_model.get_location()
        else:
            base = getattr(first_model, "model_base", None)
            if base is None:
                logger.error(f"Cannot fall back unit {self.name}: missing model position")
                return False
            first_model_pos = (float(getattr(base, "x", 0.0)), float(getattr(base, "y", 0.0)), float(getattr(base, "z", 0.0)))
        if not first_model_pos:
            logger.error(f"Cannot move unit {self.name}: first model has no position")
            return False

        # Store starting position for feedback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0

        # BACKUP ORIGINAL POSITIONS - Critical for proper rollback on failure
        original_model_positions = []
        for model in self.models:
            original_model_positions.append(model.get_location())

        # Get the movement range from the first model (assuming all models have the same movement)
        movement_range = self.movement

        # If advancing, use stored advance roll or roll new one
        if advance:
            no_roll_distance = None
            effect = self._get_advance_no_roll_effect()
            if isinstance(effect, dict):
                try:
                    no_roll_distance = int(effect.get("distance", 0) or 0)
                except Exception:
                    no_roll_distance = None
                if no_roll_distance is not None and no_roll_distance <= 0:
                    no_roll_distance = None
            chronoshift_fixed = None
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("chronoshift_active"):
                    exp = str(sr.get("chronoshift_expires_phase", "") or "").strip().upper()
                    apply_bonus = True
                    if exp:
                        try:
                            army = self.get_parent_army()
                            game = getattr(getattr(army, "player", None), "game", None)
                            pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            pname = ""
                        if pname and pname != exp:
                            apply_bonus = False
                    if apply_bonus and (not exp or exp == "MOVEMENT_PHASE"):
                        chronoshift_fixed = 6
            except Exception:
                chronoshift_fixed = None

            # Use stored advance roll if available, otherwise roll new one
            if no_roll_distance is not None:
                advance_roll = int(no_roll_distance)
                self.round_state.advance_roll = advance_roll
                try:
                    from ...utility.event_bus import append_dice
                    pn = self.get_parent_army().player
                    append_dice(pn, f"Advance distance fixed: {advance_roll} for {self.name}")
                except Exception:
                    pass
            elif chronoshift_fixed is not None:
                advance_roll = int(chronoshift_fixed)
                try:
                    advance_roll = self._apply_advance_roll_modifiers(int(advance_roll))
                except Exception:
                    pass
                self.round_state.advance_roll = advance_roll
                try:
                    from ...utility.event_bus import append_dice
                    pn = self.get_parent_army().player
                    append_dice(pn, f"Advance roll fixed: {advance_roll} for {self.name} (Chronoshift)")
                except Exception:
                    pass
            elif not hasattr(self.round_state, 'advance_roll') or self.round_state.advance_roll is None:
                advance_roll = None
                miracle_used = False
                try:
                    army = self.get_parent_army()
                    mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                        advance_roll, _dice, miracle_used = mgr.resolve_roll(
                            self,
                            roll_type="advance",
                            game=game,
                            dice_count=1,
                            die_faces=6,
                        )
                except Exception:
                    advance_roll = None
                    miracle_used = False
                if advance_roll is None:
                    advance_roll = get_roll("D6")
                try:
                    from ...utility.event_bus import append_dice
                    pn = self.get_parent_army().player
                    if miracle_used:
                        append_dice(pn, f"Miracle die used for Advance roll: {advance_roll} for {self.name}")
                    else:
                        append_dice(pn, f"Advance roll: {advance_roll} for {self.name}")
                except Exception:
                    pass
                # Optional rule-based reroll prompt (e.g., "re-roll Advance rolls")
                try:
                    _player = getattr(self.get_parent_army(), 'player', None)
                    _game = getattr(_player, 'game', None) if _player else None
                    def _reroll():
                        new_roll = get_roll("D6")
                        self.round_state.advance_roll = new_roll
                        try:
                            from ...utility.event_bus import append_dice as _append
                            _append(_player, f"Advance re-roll: {new_roll} for {self.name}")
                        except Exception:
                            pass
                        return new_roll
                    reroll_used = False
                    provider = getattr(getattr(_game, "map", None), "roll_reroll_provider", None)
                    is_human = self._player_has_local_control(_player)
                    if is_human and callable(provider) and self.can_reroll_advance_roll():
                        if bool(provider(player=_player, unit=self, roll_type="advance", value=advance_roll, dice=None)):
                            advance_roll = _reroll()
                            reroll_used = True
                    # Apply advance roll modifiers (includes Code Chivalric, etc).
                    try:
                        advance_roll = self._apply_advance_roll_modifiers(int(advance_roll))
                    except Exception:
                        pass
                    # Publish roll event (best-effort)
                    if _game is not None and hasattr(_game, "event_system"):
                        from ...utility.reroll_tracker import prepare_reroll_event
                        roll_id, reroll_cb, reroll_locked = prepare_reroll_event(
                            _game,
                            _reroll,
                            reroll_used=bool(reroll_used),
                            used_result=advance_roll,
                        )
                        _game.event_system.publish(
                            "roll_made",
                            player=_player,
                            unit=self,
                            roll_type="advance",
                            value=advance_roll,
                            reroll=reroll_cb,
                            reroll_locked=bool(reroll_locked),
                            roll_id=roll_id,
                            miracle_used=bool(miracle_used),
                        )
                except Exception:
                    pass
                self.round_state.advance_roll = advance_roll
                logger.info(f"Advance roll: {advance_roll}")
            else:
                advance_roll = self.round_state.advance_roll
                logger.info(f"Using stored advance roll: {advance_roll}")
            
            if advance_roll is None:
                logger.error(f"Failed to roll dice for advancing unit {self.name}")
                return False
            movement_range += advance_roll

        from ...utility.calcs import MovementType
        movement_type = MovementType.ADVANCE if advance else MovementType.MOVE
        # Calculate straight-line distance to destination (rules-aware)
        distance_to_destination = measure_direct_distance(
            (start_x, start_y, start_z),
            (destination[0], destination[1], destination[2]),
            self,
            movement_type,
            game_map,
        )

        # Check if destination is within movement range
        if distance_to_destination > movement_range:
            logger.info(f"{self.name} cannot reach destination {distance_to_destination:.1f}\" away (max {'advance' if advance else 'move'}: {movement_range}\")")
            return False

        # Generate potential positions for models with reduced boundary repulsors for better formation finding
        boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
        potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
        
        # Check if formation finding failed
        if potential_positions is None:
            logger.info(f"{self.name} cannot move - no valid formation found at destination")
            return False

        # Use the new individual model pathfinding system
        from ...utility.calcs import get_individual_model_movement_path, process_unit_movement_with_coherency_check
        
        model_movements = []
        successful_moves = 0

        # Move each model individually using optimized pathfinding
        for model_index, (model, model_destination) in enumerate(zip(self.models, potential_positions)):
            model_start = model.get_location()
            logging.debug(f"Model {model._id} {model.name} attempting to move from {model_start} to {model_destination}")
            
            # Calculate straight-line distance for this model
            model_distance = measure_direct_distance(
                (model_start[0], model_start[1], model_start[2] if len(model_start) > 2 else 0.0),
                (model_destination[0], model_destination[1], model_destination[2] if len(model_destination) > 2 else 0.0),
                self,
                movement_type,
                game_map,
            )
            
            # Check if this model can reach its destination
            if model_distance > movement_range:
                logger.info(f"Model {model._id} cannot reach destination {model_distance:.1f}\" away (max: {movement_range}\")")
                continue  # Skip this model, don't move it
            
            # Use new optimized pathfinding for individual model movement
            path = get_individual_model_movement_path(self, model_index, model_destination, game_map, movement_range)
            
            if not path:
                logger.debug(f"Model {model._id} optimized pathfinding failed - destination may violate movement rules")
                continue
            
            # Calculate path distance
            path_distance = measure_path_distance(path, self, movement_type, game_map)
            
            if path_distance > movement_range:
                logger.info(f"Model {model._id} path distance {path_distance:.1f}\" exceeds movement {movement_range}\"")
                # Try to move as far as possible along the path
                last_node = model_start
                model.last_move_path = [last_node]
                distance_along_path = 0.0
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                
                for node in path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, movement_type)
                    
                    if distance_along_path + segment_distance > movement_range:
                        # Stop here, can't go further
                        break
                    
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                # Move to the furthest reachable position
                if distance_along_path > 0:
                    final_position = model.last_move_path[-1]
                    model.set_location(final_position[0], final_position[1], final_position[2], final_position[3])
                    model_movements.append((model_index, model.last_move_path))
                    successful_moves += 1
                    logger.debug(f"Model {model._id} moved along path to {final_position[:3]}, distance: {distance_along_path:.1f}\"")
            else:
                # Path is within range, move to destination
                model.set_location(*model_destination)
                last_node = model_start
                model.last_move_path = [last_node]
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                distance_along_path = 0.0
                
                for node in path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, movement_type)
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                model_movements.append((model_index, model.last_move_path))
                successful_moves += 1
                logger.debug(f"Model {model._id} moved to {model_destination}, path distance: {distance_along_path:.1f}\"")

        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            logger.info(f"{self.name} could not move - no models could reach any valid positions")
            return False

        # NEW: Validate unit coherency after all models have moved
        is_coherent, non_coherent_models = process_unit_movement_with_coherency_check(self, model_movements)
        
        if not is_coherent:
            logger.info(f"{self.name} move rejected: unit coherency would be broken (non-coherent models: {non_coherent_models})")
            # ROLLBACK: Restore original positions (movement ending out of coherency is not allowed)
            for i, original_pos in enumerate(original_model_positions):
                if i < len(self.models):
                    self.models[i].set_location(*original_pos)
            return False
        
        # CRITICAL VALIDATION: Check for illegal overlaps after movement
        # This catches cases where models might be overlapping with enemies after movement
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
            end_z = final_position[2] if len(final_position) > 2 else start_z
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
            end_z = start_z
        
        # Check for base overlaps with enemy models
        enemy_units = game_map.get_enemy_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for enemy_unit in enemy_units:
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the enemy model's base
                    if model.model_base.collides_with(enemy_model.model_base):
                        logger.info(f"{self.name} cannot move - {model.name} would overlap with {enemy_model.name} from {enemy_unit.name}")
                        # ROLLBACK: Restore original positions
                        for i, original_pos in enumerate(original_model_positions):
                            if i < len(self.models):
                                self.models[i].set_location(*original_pos)
                        return False
        
        # Calculate actual distance the unit moved (rules-aware)
        unit_distance_moved = measure_direct_distance(
            (start_x, start_y, start_z),
            (end_x, end_y, end_z),
            self,
            movement_type,
            game_map,
        )
        
        # Provide detailed feedback
        action_name = 'advanced' if advance else 'moved'
        logger.info(f"{self.name} {action_name} from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if successful_moves < len(self.models):
            logger.info(f" Note: Only {successful_moves}/{len(self.models)} models could move to valid positions")

        logger.info(f"Unit {self.name} {action_name} from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        self.round_state.advanced_this_round = advance
        try:
            self._apply_super_heavy_walker_terrain_shock(
                game_map,
                action="advance" if advance else "move",
            )
        except Exception:
            pass
        return True

    def charge_move(
        self,
        destination: Tuple[float, float, float],
        game_map: 'Map',
        target_unit: 'Unit' = None,
        target_units: Optional[list['Unit']] = None,
    ) -> bool:
        """Special movement for charge actions that allows moving into engagement range.
        
        Unlike normal movement, charge movement:
        1. Allows models to move into engagement range of enemy units
        2. Uses relaxed collision detection for final positioning
        3. Prioritizes achieving engagement range over perfect formations
        """
        if bool(getattr(self, "is_aircraft", False)):
            logger.info(f"{self.name} cannot declare charges (AIRCRAFT)")
            return False
        # Mission Actions: a unit performing an Action is not eligible to declare a charge
        if getattr(self.round_state, 'action_locked_until_turn_end', False):
            logger.info(f"{self.name} is performing an Action and cannot declare a charge this turn")
            return False
        if not self.models:
            logger.error(f"Cannot charge move unit {self.name}: no models in unit")
            return False

        # Publish movement start for stratagem reaction windows (e.g. FIRE OVERWATCH).
        try:
            _player = getattr(self.get_parent_army(), 'player', None)
            _game = getattr(_player, 'game', None) if _player else None
            if _game and hasattr(_game, 'event_system'):
                _game.event_system.publish("unit_move_started", unit=self, action="charge")
        except Exception:
            pass
        
        # Get starting position from first model
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot charge move unit {self.name}: no valid models")
            return False

        first_model = self.models[0]
        if callable(getattr(first_model, "get_location", None)):
            first_model_pos = first_model.get_location()
        else:
            base = getattr(first_model, "model_base", None)
            if base is None:
                logger.error(f"Cannot fall back unit {self.name}: first model has no position")
                return False
            first_model_pos = (float(getattr(base, "x", 0.0)), float(getattr(base, "y", 0.0)), float(getattr(base, "z", 0.0)))
        if not first_model_pos:
            logger.error(f"Cannot charge move unit {self.name}: first model has no position")
            return False
        
        # Store starting position for feedback and rollback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0
        
        # Store original model positions for potential rollback
        original_model_positions = []
        for model in self.models:
            model_pos = model.get_location()
            original_model_positions.append(model_pos)
        
        # Store original model positions for potential rollback
        
        from ...utility.calcs import MovementType
        # Calculate maximum charge distance available (rules-aware)
        max_charge_distance = measure_direct_distance(
            (start_x, start_y, start_z),
            (destination[0], destination[1], destination[2]),
            self,
            MovementType.CHARGE,
            game_map,
        )
        
        targets = list(target_units or [])
        if not targets and target_unit is not None:
            targets = [target_unit]
        if not targets:
            logger.error(f"ERROR: {self.name} cannot charge without target units.")
            return False
        if any(t is None or not t.is_alive() for t in targets):
            logger.error(f"ERROR: {self.name} cannot charge - one or more targets are invalid.")
            return False
        # Charge toward specific target unit (primary)
        all_enemy_models = [model for model in targets[0].models if model.is_alive]
        logger.info(f"{self.name} charging specifically toward {targets[0].name} ({len(all_enemy_models)} models)")
        if not all_enemy_models:
            logger.info(f"{self.name} cannot charge - no alive models in target unit {targets[0].name}")
            return False
        
        successful_moves = 0
        
        # FAST PATH FOR SINGLE MODEL UNITS - use pathfinding but skip formation complexity
        if len(self.models) == 1:
            logger.info(f"{self.name} using single-model charge path")
            model = self.models[0]
            model_start = model.get_location()
            
            # Calculate straight-line distance to destination (rules-aware)
            model_distance = measure_direct_distance(
                (model_start[0], model_start[1], model_start[2] if len(model_start) > 2 else 0.0),
                (destination[0], destination[1], destination[2]),
                self,
                MovementType.CHARGE,
                game_map,
            )
            
            # Check if within charge distance
            if model_distance > max_charge_distance:
                logger.info(f"{self.name} cannot reach charge destination {model_distance:.1f}\" away (max: {max_charge_distance}\")")
                return False
            
            # Use charge-aware pathfinding for single model (can navigate around obstacles and into engagement range)
            from ...utility.calcs import get_charge_movement_path

            pathfinding_result = get_charge_movement_path(
                model, destination, max_charge_distance, game_map, targets[0], target_units=targets
            )
            
            if not pathfinding_result or not pathfinding_result.get('valid'):
                logger.error(f"{self.name} cannot charge to destination - pathfinding failed (obstacles in way)")
                return False

            shortest_path = pathfinding_result['path']
            
            # Calculate path distance
            path_distance = measure_path_distance(shortest_path, self, MovementType.CHARGE, game_map)
            
            # Check if path is within charge distance
            if path_distance > max_charge_distance:
                logger.info(f"{self.name} path distance {path_distance:.1f}\" exceeds charge distance {max_charge_distance}\"")
                return False
            
            # Move the model to destination
            new_z = game_map.get_height_at_point(destination[0], destination[1])
            new_facing = self.calculate_strategic_facing(destination[0], destination[1], game_map)
            model.set_location(destination[0], destination[1], new_z, new_facing)
            successful_moves = 1
            
            logger.info(f"{self.name} (single model) charged via pathfinding - distance: {path_distance:.1f}\"")
        
        else:
            # COMPLEX PATH FOR MULTI-MODEL UNITS - use formation positioning
            logger.info(f"{self.name} using multi-model charge path")
            
            # Generate potential positions for models with enhanced pathfinding for charges
            boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
            potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
            
            # Use formation positioning if available, otherwise fall back to individual positioning
            if potential_positions is not None:
                # Use formation positioning with enhanced pathfinding validation
                for model, model_destination in zip(self.models, potential_positions):
                    model_start = model.get_location()
                    
                    # Calculate distance for this model
                    model_distance = measure_direct_distance(
                        (model_start[0], model_start[1], model_start[2] if len(model_start) > 2 else 0.0),
                        (model_destination[0], model_destination[1], model_destination[2] if len(model_destination) > 2 else 0.0),
                        self,
                        MovementType.CHARGE,
                        game_map,
                    )
                    
                    # Check if within charge distance
                    if model_distance > max_charge_distance:
                        logger.debug(f"Model {model._id} cannot reach charge destination {model_distance:.1f}\" away (max: {max_charge_distance}\")")
                        continue
                    
                    # Use charge-aware pathfinding for charge movement
                    from ...utility.calcs import get_charge_movement_path

                    pathfinding_result = get_charge_movement_path(
                        model, model_destination, max_charge_distance, game_map, targets[0], target_units=targets
                    )

                    if pathfinding_result and pathfinding_result.get('valid'):
                        shortest_path = pathfinding_result['path']
                        
                        # Calculate path distance
                        path_distance = measure_path_distance(shortest_path, self, MovementType.CHARGE, game_map)
                        
                        if path_distance <= max_charge_distance:
                            # Move to destination
                            model.set_location(*model_destination)
                            successful_moves += 1
                            logger.debug(f"Model {model._id} charge moved {path_distance:.1f}\" to formation position")
                        else:
                            logger.debug(f"Model {model._id} path distance {path_distance:.1f}\" exceeds charge distance {max_charge_distance}\"")
                    else:
                        logger.debug(f"Model {model._id} cannot charge to formation position - pathfinding failed")
            else:
                logger.error(f"{self.name} charge failed - no valid formation found, trying individual positioning")
            
            # If formation failed or had limited success, try individual model positioning
            if successful_moves < len(self.models) // 2:  # If less than half succeeded
                # Move each model individually using enhanced pathfinding
                for model in self.models:
                    model_start = model.get_location()
                
                    # Find the closest enemy model to this model
                    closest_enemy = None
                    closest_distance = float('inf')
                    
                    for enemy_model in all_enemy_models:
                        enemy_pos = enemy_model.get_location()
                        distance = get_dist(
                            enemy_pos[0] - model_start[0],
                            enemy_pos[1] - model_start[1],
                            enemy_pos[2] - model_start[2] if len(model_start) > 2 else 0
                        )
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_enemy = enemy_model
                    
                    if not closest_enemy:
                        continue
                    
                    # Calculate direction towards closest enemy
                    enemy_pos = closest_enemy.get_location()
                    dx = enemy_pos[0] - model_start[0]
                    dy = enemy_pos[1] - model_start[1]
                    dz = enemy_pos[2] - model_start[2] if len(model_start) > 2 else 0
                    
                    distance_to_enemy = get_dist(dx, dy, dz)
                    
                    if distance_to_enemy == 0:
                        # Already at enemy position, no movement needed
                        successful_moves += 1
                        continue
                    
                    # Normalize direction vector
                    dx /= distance_to_enemy
                    dy /= distance_to_enemy
                    dz /= distance_to_enemy if distance_to_enemy > 0 else 1
                    
                    # Calculate how far to move: use the distance provided by attempt_charge
                    # Get as close as possible to the enemy for better pile-in positioning
                    target_distance = max_charge_distance  # Use the distance calculated by attempt_charge
                    
                    if target_distance <= 0:
                        # Already close enough or can't move closer
                        successful_moves += 1
                        continue
                    
                    # Calculate new position
                    new_x = model_start[0] + dx * target_distance
                    new_y = model_start[1] + dy * target_distance
                    new_z = game_map.get_height_at_point(new_x, new_y)
                    new_facing = self.calculate_strategic_facing(new_x, new_y, game_map)
                    
                    # CRITICAL: Validate position before moving to prevent friendly unit overlaps
                    # Import here to avoid circular imports
                    from ...utility.calcs import check_friendly_ending_collision
                    
                    # Check if the new position would collide with friendly units
                    if check_friendly_ending_collision(model, (new_x, new_y, new_z), game_map):
                        # Position would cause collision - try to find alternative position
                        # Try positions at different distances along the same direction
                        alternative_found = False
                        for distance_factor in [0.9, 0.8, 0.7, 0.6, 0.5]:
                            alt_distance = target_distance * distance_factor
                            alt_x = model_start[0] + dx * alt_distance
                            alt_y = model_start[1] + dy * alt_distance
                            alt_z = game_map.get_height_at_point(alt_x, alt_y)
                            
                            if not check_friendly_ending_collision(model, (alt_x, alt_y, alt_z), game_map):
                                # Found a valid alternative position
                                new_x, new_y, new_z = alt_x, alt_y, alt_z
                                target_distance = alt_distance
                                alternative_found = True
                                logger.debug(f"Model {model._id} found alternative charge position at {distance_factor:.1f} of original distance")
                                break
                        
                        if not alternative_found:
                            # No valid position found - skip this model
                            logger.debug(f"Model {model._id} cannot charge - no valid position found without friendly collisions")
                            continue
                    
                    # Move the model to the validated position
                    model.set_location(new_x, new_y, new_z, new_facing)
                    successful_moves += 1
                    
                    actual_distance_moved = get_dist(
                        new_x - model_start[0],
                        new_y - model_start[1],
                        new_z - model_start[2] if len(model_start) > 2 else 0
                    )
                    target_name = target_unit.name if target_unit else "closest enemy"
                    logger.debug(f"Model {model._id} charge moved {actual_distance_moved:.1f}\" towards {closest_enemy.name} (from {target_name})")
        
        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            logger.info(f"{self.name} could not charge - no models could reach any valid positions")
            return False
        
        # CRITICAL VALIDATION: Final check for any overlaps after all models positioned
        # This catches edge cases where models might still overlap despite individual validation
        friendly_units = game_map.get_friendly_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for friendly_unit in friendly_units:
                if friendly_unit == self or not friendly_unit.is_alive() or not friendly_unit.deployed:
                    continue
                for friendly_model in friendly_unit.models:
                    if not friendly_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the friendly model's base
                    if model.model_base.collides_with(friendly_model.model_base):
                        logger.error(f"{self.name} charge failed - {model.name} would overlap with {friendly_model.name} from {friendly_unit.name}")
                        # ROLLBACK: Restore original positions
                        for i, original_pos in enumerate(original_model_positions):
                            if i < len(self.models):
                                self.models[i].set_location(*original_pos)
                        return False

        # Coherency validation: charge moves must end in coherency (movement ending out of coherency is not allowed)
        try:
            from ...utility.calcs import validate_unit_coherency_after_movement
            final_positions = [m.get_location() for m in self.models]
            is_coherent, non_coherent_models = validate_unit_coherency_after_movement(self, final_positions)
            if not is_coherent:
                logger.info(f"{self.name} charge move rejected: unit coherency would be broken (non-coherent models: {non_coherent_models})")
                for i, original_pos in enumerate(original_model_positions):
                    if i < len(self.models):
                        self.models[i].set_location(*original_pos)
                return False
        except Exception as e:
            # If coherency validation itself fails, fail-fast rather than silently allowing illegal states.
            raise

        # Charge targets validation (must engage all targets, avoid non-targets)
        ok, reason = self.validate_charge_end_state(targets, game_map)
        if not ok:
            logger.info(f"{self.name} charge move rejected: {reason}")
            for i, original_pos in enumerate(original_model_positions):
                if i < len(self.models):
                    self.models[i].set_location(*original_pos)
            return False
        
        # Get final position for feedback from first model
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
            end_z = final_position[2] if len(final_position) > 2 else start_z
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
            end_z = start_z
        
        # Calculate actual distance the unit moved (rules-aware)
        unit_distance_moved = measure_direct_distance(
            (start_x, start_y, start_z),
            (end_x, end_y, end_z),
            self,
            MovementType.CHARGE,
            game_map,
        )
        
        # Provide detailed feedback
        logger.info(f"{self.name} moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if successful_moves < len(self.models):
            logger.info(f" Note: Only {successful_moves}/{len(self.models)} models could move to valid positions")
        
        # Mark unit as having moved this round
        self.round_state.moved_this_round = True
        
        logger.info(f"Unit {self.name} charge moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        # Publish movement end for stratagem reaction windows (e.g. TANK SHOCK / FIRE OVERWATCH on Charge moves).
        try:
            _player = getattr(self.get_parent_army(), 'player', None)
            _game = getattr(_player, 'game', None) if _player else None
            if _game and hasattr(_game, 'event_system'):
                _game.event_system.publish("unit_move_ended", unit=self, action="charge")
        except Exception:
            pass
        return True

    def _grant_charge_move_devastating_wounds(self, model: 'Model', source: str = "") -> None:
        """Apply temporary Devastating Wounds (melee) to a model until end of turn."""
        if model is None:
            return
        if not isinstance(getattr(model, "_temporary_effects", None), dict):
            model._temporary_effects = {}
        model._temporary_effects["charge_move_devastating_wounds"] = {
            "devastating_wounds_melee": True,
            "expires_phase": "FIGHT_PHASE",
            "source": str(source or "Charge move ability"),
        }

    def _grant_charge_end_model_melee_strength_ap_bonus(
        self,
        model: 'Model',
        *,
        strength_bonus: int = 0,
        ap_bonus: int = 0,
        source: str = "",
    ) -> bool:
        if model is None:
            return False
        try:
            strength_bonus = int(strength_bonus or 0)
        except Exception:
            strength_bonus = 0
        try:
            ap_bonus = int(ap_bonus or 0)
        except Exception:
            ap_bonus = 0
        if strength_bonus <= 0 and ap_bonus <= 0:
            return False
        if not isinstance(getattr(model, "_temporary_effects", None), dict):
            model._temporary_effects = {}
        source_label = str(source or "Charge move ability").strip() or "Charge move ability"
        model_id = str(get_entity_id(model) or "")
        source_key = self._normalize_keyword_phrase(source_label) or source_label.lower()
        key = (
            f"charge_end_model_melee_strength_ap:{model_id}:{source_key}:"
            f"{int(strength_bonus)}:{int(ap_bonus)}"
        ).lower()
        entry = {
            "expires_phase": "FIGHT_PHASE",
            "source": source_label,
        }
        if strength_bonus:
            entry["melee_strength_bonus"] = int(strength_bonus)
            entry["melee_strength_bonus_source"] = source_label
        if ap_bonus:
            entry["melee_ap_bonus"] = int(ap_bonus)
        model._temporary_effects[key] = entry
        return True

    def _apply_charge_move_devastating_wounds(self) -> bool:
        """
        Apply temporary Devastating Wounds (melee) to models when the unit completes a charge move.

        Supports rules like:
          "Each time this model makes a Charge move, until the end of the turn, its melee weapons have the
          [DEVASTATING WOUNDS] ability."
        """
        applied = False

        def _iter_sentences(text: str) -> list[str]:
            if not text:
                return []
            cleaned = re.sub(r";\s*", ". ", text)
            return [part.strip() for part in re.split(r"\.\s*", cleaned) if part.strip()]

        try:
            members = list(self.get_attached_unit_members() or [])
        except Exception:
            members = [self]

        # Unit-level abilities (apply to all models in that unit member).
        for unit in members:
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text = unit._normalize_rules_text(desc or name or "")
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                for sentence in _iter_sentences(text):
                    if self._CHARGE_MOVE_DEVASTATING_WOUNDS_RE.search(sentence):
                        for model in list(getattr(unit, "models", []) or []):
                            if not getattr(model, "is_alive", True):
                                continue
                            self._grant_charge_move_devastating_wounds(model, source=name or "Charge move ability")
                        applied = True
                        break

        # Model-level abilities (apply only to that model).
        for unit in members:
            for model in list(getattr(unit, "models", []) or []):
                if model is None or not getattr(model, "is_alive", True):
                    continue
                for name, desc in unit._iter_model_specific_ability_entries(model):
                    text = unit._normalize_rules_text(desc or name or "")
                    if not text:
                        continue
                    text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                    for sentence in _iter_sentences(text):
                        if self._CHARGE_MOVE_DEVASTATING_WOUNDS_RE.search(sentence):
                            self._grant_charge_move_devastating_wounds(model, source=name or "Charge move ability")
                            applied = True
                            break

        return applied

    def _apply_charge_end_model_melee_strength_ap_bonuses(self) -> bool:
        """
        Apply temporary model-only melee Strength/AP bonuses when the unit completes a charge move.

        Supports rules like:
          "Each time this model's unit ends a Charge move, until the end of the turn, add 1 to the
           Strength characteristic of melee weapons equipped by this model and improve the Armour
           Penetration characteristics of those weapons by 1."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        applied = False
        for unit in members:
            if unit is None:
                continue
            for model in list(getattr(unit, "models", []) or []):
                if model is None or not getattr(model, "is_alive", True):
                    continue
                for name, desc in unit._iter_model_specific_ability_entries(model):
                    text_src = desc or name or ""
                    if not text_src:
                        continue
                    text_src = unit._strip_eligibility_prefix(text_src)
                    normalized = unit._normalize_rules_text(text_src)
                    normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                    normalized = normalized.lower()
                    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                    normalized = re.sub(r"\s+", " ", normalized).strip()
                    m = self._CHARGE_END_MODEL_MELEE_STRENGTH_AP_BONUS_RE.fullmatch(normalized)
                    if not m:
                        continue
                    try:
                        strength_bonus = int(m.group("strength") or 0)
                    except Exception:
                        strength_bonus = 0
                    try:
                        ap_bonus = int(m.group("ap") or 0)
                    except Exception:
                        ap_bonus = 0
                    source = str(name or "Charge move ability").strip() or "Charge move ability"
                    if self._grant_charge_end_model_melee_strength_ap_bonus(
                        model,
                        strength_bonus=int(strength_bonus),
                        ap_bonus=int(ap_bonus),
                        source=source,
                    ):
                        applied = True
        return applied

    def _apply_charge_move_model_weapon_profile_attacks_bonuses(self) -> bool:
        """
        Apply temporary model-only weapon-profile Attacks bonuses when the unit completes a charge move.

        Supports rules like:
          "Each time this model makes a Charge move, until the end of the turn, add 1 to the Attacks
           characteristic of this model's <weapon> - strike profile, and add 2 ... - sweep profile."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        applied = False
        for unit in members:
            if unit is None:
                continue
            for model in list(getattr(unit, "models", []) or []):
                if model is None or not getattr(model, "is_alive", True):
                    continue
                for name, desc in unit._iter_model_specific_ability_entries(model):
                    text_src = desc or name or ""
                    if not text_src:
                        continue
                    text_src = unit._strip_eligibility_prefix(text_src)
                    normalized = unit._normalize_rules_text(text_src)
                    normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                    normalized = normalized.lower()
                    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                    normalized = re.sub(r"\s+", " ", normalized).strip()
                    m = self._CHARGE_MOVE_MODEL_WEAPON_PROFILE_ATTACKS_BONUS_RE.fullmatch(normalized)
                    if not m:
                        continue
                    try:
                        strike_bonus = int(m.group("strike") or 0)
                    except Exception:
                        strike_bonus = 0
                    try:
                        sweep_bonus = int(m.group("sweep") or 0)
                    except Exception:
                        sweep_bonus = 0
                    weapon1_raw = str(m.group("weapon1") or "").strip()
                    weapon2_raw = str(m.group("weapon2") or "").strip()
                    weapon_base = weapon1_raw or weapon2_raw
                    if weapon1_raw and weapon2_raw:
                        w1_key = unit._normalize_keyword_phrase(weapon1_raw)
                        w2_key = unit._normalize_keyword_phrase(weapon2_raw)
                        if w1_key and w2_key and w1_key == w2_key:
                            weapon_base = weapon1_raw
                    weapon_base = str(weapon_base or "").strip()
                    if not weapon_base:
                        continue
                    source = str(name or "Charge move ability").strip() or "Charge move ability"
                    source_key = unit._normalize_keyword_phrase(source) or source.lower()
                    model_id = str(get_entity_id(model) or "")
                    if strike_bonus > 0:
                        model.set_temporary_weapon_bonus(
                            key=f"charge_move_profile_attacks:{model_id}:{source_key}:{weapon_base}:strike",
                            weapon_name=f"{weapon_base} strike profile",
                            attacks_bonus=int(strike_bonus),
                            source=source,
                            expires_phase="FIGHT_PHASE",
                        )
                        applied = True
                    if sweep_bonus > 0:
                        model.set_temporary_weapon_bonus(
                            key=f"charge_move_profile_attacks:{model_id}:{source_key}:{weapon_base}:sweep",
                            weapon_name=f"{weapon_base} sweep profile",
                            attacks_bonus=int(sweep_bonus),
                            source=source,
                            expires_phase="FIGHT_PHASE",
                        )
                        applied = True
        return applied

    def unit_charge_end_weapon_keyword_bonus_specs(self) -> list[dict]:
        """
        Return specs for charge-end weapon keyword bonuses (e.g., granting DEVASTATING WOUNDS).

        Each spec dict includes:
            - weapon: str (weapon name)
            - keyword: str (keyword, uppercased)
            - source: str (ability name)
            - attack_type: str ("melee" by default)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "charge_end_weapon_keyword_bonus_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, str]] = set()

        try:
            leaders = list(getattr(root, "attached_leaders", []) or [])
        except Exception:
            leaders = []

        for leader in leaders:
            if leader is None:
                continue
            try:
                if not bool(getattr(leader, "is_attached_leader", False)):
                    continue
            except Exception:
                continue
            try:
                alive = getattr(leader, "is_alive", None)
                if callable(alive) and not alive():
                    continue
            except Exception:
                pass
            for name, desc in leader._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = self._strip_eligibility_prefix(text_src)
                normalized = self._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = self._CHARGE_END_WEAPON_KEYWORD_BONUS_RE.fullmatch(normalized)
                if not m:
                    continue
                weapon = str(m.group("weapon") or "").strip()
                keyword = str(m.group("keyword") or "").strip()
                if not weapon or not keyword:
                    continue
                source = str(name or "Charge move ability").strip() or "Charge move ability"
                key = (weapon.lower(), keyword.lower(), source.lower())
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "weapon": weapon,
                        "keyword": keyword.upper(),
                        "source": source,
                        "attack_type": "melee",
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def _apply_charge_move_weapon_keyword_bonuses(self) -> bool:
        """
        Apply temporary weapon keyword bonuses when the unit completes a charge move.

        Supports rules like:
          "Each time that unit ends a Charge move, until the end of the turn,
           <weapon> equipped by models in that unit have the [KEYWORD] ability."
        """
        specs = self.unit_charge_end_weapon_keyword_bonus_specs()
        if not specs:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        if not models:
            return False

        applied = False
        for spec in specs:
            weapon = str(spec.get("weapon", "") or "").strip()
            keyword = str(spec.get("keyword", "") or "").strip()
            if not weapon or not keyword:
                continue
            source = str(spec.get("source", "") or "Charge move ability").strip() or "Charge move ability"
            attack_type = str(spec.get("attack_type", "") or "melee").strip().lower()
            for model in models:
                if model is None or not getattr(model, "is_alive", True):
                    continue
                model_id = get_entity_id(model) or ""
                key = f"charge_end_weapon_keyword:{model_id}:{weapon}:{keyword}".lower()
                if hasattr(model, "set_temporary_weapon_keyword_bonuses"):
                    model.set_temporary_weapon_keyword_bonuses(
                        key=key,
                        weapon_name=weapon,
                        keywords=[keyword],
                        source=source,
                        expires_phase="FIGHT_PHASE",
                        attack_type=attack_type,
                    )
                    applied = True
        return applied

    def fall_back(self, destination: Tuple[float, float, float], path: List[Tuple[float, float, float]], game_map: 'Map') -> bool:
        """Falls back from close combat.
        
        Battle-Shocked units that fall back must take Desperate Escape Tests.
        Units that fall back can move within engagement range and over enemy models,
        but cannot end within engagement range of any enemy models.
        """
        if bool(getattr(self, "is_aircraft", False)):
            logger.info(f"{self.name} cannot Fall Back (AIRCRAFT)")
            return False
        logger.info(f"{self.name} falls back from combat")

        sources = []
        source_labels = []
        try:
            from ...rules.wrathful_presence import overwhelming_wrath_sources_for_unit, OVERWHELMING_WRATH_NAME
            ow_sources = overwhelming_wrath_sources_for_unit(self, game_map=game_map)
            if ow_sources:
                sources.extend(ow_sources)
                source_labels.append(OVERWHELMING_WRATH_NAME)
        except Exception:
            pass
        try:
            from ...rules.daemon_primarch_slaanesh import (
                enthralling_hypnosis_sources_for_unit,
                ENTHRALLING_HYPNOSIS_NAME,
            )
            eh_sources = enthralling_hypnosis_sources_for_unit(self, game_map=game_map)
            if eh_sources:
                sources.extend(eh_sources)
                source_labels.append(ENTHRALLING_HYPNOSIS_NAME)
        except Exception:
            pass
        if sources:
            try:
                passed = bool(self.pass_leadership_check())
            except Exception:
                passed = True
            if not passed:
                try:
                    self.round_state.remained_stationary_this_round = True
                except Exception:
                    pass
                try:
                    from ...utility.event_bus import append_action
                    pn = self.get_parent_army().player
                    src_names = [getattr(s, "name", "") for s in sources if getattr(s, "name", "")]
                    if src_names:
                        src_text = ", ".join(src_names)
                    else:
                        src_text = ", ".join(source_labels) if source_labels else "Leadership suppression"
                    append_action(pn, f"{self.name} failed a Leadership test and remains stationary ({src_text}).")
                except Exception:
                    pass
                return False
        
        fallback_desperate = False
        fallback_bs_penalty = 0
        fallback_any_penalty = 0
        if game_map is not None:
            try:
                enemy_units = list(game_map.get_enemy_units(self) or [])
            except Exception:
                try:
                    unit_army = self.get_parent_army()
                except Exception:
                    unit_army = None
                enemy_units = [
                    u for u in list(getattr(game_map, "units", []) or [])
                    if getattr(u, "get_parent_army", lambda: None)() is not unit_army
                ]
            seen_enemy_roots: set[str] = set()
            for enemy in enemy_units:
                if enemy is None:
                    continue
                try:
                    enemy_root = enemy.get_attached_unit_root()
                except Exception:
                    enemy_root = enemy
                if enemy_root is None:
                    continue
                try:
                    enemy_root_id = str(get_entity_id(enemy_root) or "")
                except Exception:
                    enemy_root_id = ""
                if enemy_root_id and enemy_root_id in seen_enemy_roots:
                    continue
                if enemy_root_id:
                    seen_enemy_roots.add(enemy_root_id)
                try:
                    if hasattr(game_map, "is_within_engagement_range") and not game_map.is_within_engagement_range(self, enemy_root):
                        continue
                except Exception:
                    continue

                source_desperate = False
                source_exclude_mv = False
                source_bs_penalty = 0
                source_any_penalty = 0
                source_target_enemy_id = ""
                try:
                    members = list(enemy_root.get_attached_unit_members() or [])
                except Exception:
                    members = [enemy_root]
                if not members:
                    members = [enemy_root]
                for source_unit in members:
                    source_sr = getattr(source_unit, "special_rules", None)
                    if not isinstance(source_sr, dict):
                        source_sr = {}
                    if source_sr.get("enemy_fallback_desperate_escape"):
                        source_desperate = True
                        if source_sr.get("enemy_fallback_desperate_escape_exclude_monster_vehicle"):
                            source_exclude_mv = True
                        target_enemy_id = str(source_sr.get("enemy_fallback_desperate_escape_target_enemy_id", "") or "")
                        if target_enemy_id:
                            source_target_enemy_id = target_enemy_id
                        try:
                            source_bs_penalty = max(
                                source_bs_penalty,
                                int(source_sr.get("enemy_fallback_desperate_escape_bs_penalty", 0) or 0),
                            )
                        except Exception:
                            pass
                        try:
                            source_any_penalty = max(
                                source_any_penalty,
                                int(source_sr.get("enemy_fallback_desperate_escape_penalty", 0) or 0),
                            )
                        except Exception:
                            pass
                    try:
                        source_army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
                    except Exception:
                        source_army = None
                    sm_mgr = getattr(source_army, "space_marines_detachments", None) if source_army is not None else None
                    apply_fn = getattr(sm_mgr, "in_the_lions_claws_ravenwing_source_applies", None) if sm_mgr is not None else None
                    if callable(apply_fn):
                        game_obj = getattr(getattr(source_army, "player", None), "game", None) if source_army is not None else None
                        if bool(apply_fn(source_unit, self, game=game_obj)):
                            source_desperate = True
                            source_exclude_mv = True
                            source_bs_penalty = max(source_bs_penalty, 1)

                if source_target_enemy_id and str(source_target_enemy_id) != str(enemy_root_id):
                    continue

                repulsed_active = False
                try:
                    checker = getattr(enemy_root, "_attached_unit_has_active_enhancement", None)
                    if callable(checker):
                        repulsed_active = bool(
                            checker(
                                "enhancement_repulsed_by_weakness",
                                enhancement_id="000010018003",
                                enhancement_name="repulsed by weakness",
                            )
                        )
                except Exception:
                    repulsed_active = False
                if repulsed_active:
                    source_desperate = True
                    source_exclude_mv = True
                    try:
                        enemy_army = enemy_root.get_parent_army()
                    except Exception:
                        enemy_army = None
                    mgr = getattr(enemy_army, "emperors_children", None) if enemy_army is not None else None
                    if mgr is None and enemy_army is not None:
                        mgr = getattr(enemy_army, "emperors_children_detachments", None)
                    if mgr is not None and bool(getattr(mgr, "is_favoured_champions", lambda _u: False)(enemy_root)):
                        favoured_penalty = 1
                        for source_unit in members:
                            source_sr = getattr(source_unit, "special_rules", None)
                            if not isinstance(source_sr, dict):
                                continue
                            if not source_sr.get("enhancement_repulsed_by_weakness"):
                                continue
                            try:
                                favoured_penalty = max(
                                    favoured_penalty,
                                    int(
                                        source_sr.get(
                                            "enhancement_repulsed_by_weakness_favoured_penalty",
                                            1,
                                        )
                                        or 1
                                    ),
                                )
                            except Exception:
                                continue
                        source_any_penalty = max(source_any_penalty, int(favoured_penalty))

                mask_of_secrets_active = False
                try:
                    checker = getattr(enemy_root, "_attached_unit_has_active_enhancement", None)
                    if callable(checker):
                        mask_of_secrets_active = bool(
                            checker(
                                "enhancement_mask_of_secrets",
                                enhancement_id="000009915003",
                                enhancement_name="mask of secrets",
                            )
                        )
                except Exception:
                    mask_of_secrets_active = False
                if mask_of_secrets_active:
                    source_desperate = True
                    for source_unit in members:
                        source_sr = getattr(source_unit, "special_rules", None)
                        if not isinstance(source_sr, dict):
                            continue
                        if not source_sr.get("enhancement_mask_of_secrets"):
                            continue
                        if bool(source_sr.get("enhancement_mask_of_secrets_exclude_monster_vehicle", True)):
                            source_exclude_mv = True
                        try:
                            source_bs_penalty = max(
                                source_bs_penalty,
                                int(source_sr.get("enhancement_mask_of_secrets_battleshock_penalty", 1) or 1),
                            )
                        except Exception:
                            continue

                if not source_desperate:
                    continue
                if source_exclude_mv:
                    try:
                        if self.has_any_keyword("MONSTER") or self.has_any_keyword("VEHICLE"):
                            continue
                    except Exception:
                        pass
                fallback_desperate = True
                if source_any_penalty:
                    fallback_any_penalty = max(fallback_any_penalty, int(source_any_penalty))
                try:
                    fallback_bs_penalty = max(fallback_bs_penalty, int(source_bs_penalty or 0))
                except Exception:
                    pass

        is_battleshocked = self.is_battle_shocked()
        fortification_escape_exempt = False
        if is_battleshocked and game_map is not None:
            try:
                fortification_escape_exempt = self.is_only_within_enemy_fortifications(game_map)
            except Exception:
                fortification_escape_exempt = False
        if (is_battleshocked and not fortification_escape_exempt) or fallback_desperate:
            roll_modifier = 0
            if fallback_desperate and fallback_any_penalty:
                roll_modifier -= abs(int(fallback_any_penalty))
            if is_battleshocked and fallback_desperate and fallback_bs_penalty:
                roll_modifier -= abs(int(fallback_bs_penalty))
            models_lost = self.take_desperate_escape_test(
                game_map,
                reason="fall back",
                roll_modifier=roll_modifier,
            )
            # Check if unit was wiped out during Desperate Escape Test
            if not self.is_alive():
                logger.info(f"INFO: {self.name} was completely destroyed during Desperate Escape Test!")
                return False

        # Execute Fall Back movement for each model
        if not self.models:
            logger.error(f"Cannot fall back unit {self.name}: no models in unit")
            return False
        
        # Get starting position from first model
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot fall back unit {self.name}: no valid models")
            return False

        first_model = self.models[0]
        if callable(getattr(first_model, "get_location", None)):
            first_model_pos = first_model.get_location()
        else:
            base = getattr(first_model, "model_base", None)
            if base is None:
                logger.error(f"Cannot fall back unit {self.name}: first model has no position")
                return False
            first_model_pos = (float(getattr(base, "x", 0.0)), float(getattr(base, "y", 0.0)), float(getattr(base, "z", 0.0)))
        if not first_model_pos:
            logger.error(f"Cannot fall back unit {self.name}: first model has no position")
            return False

        # Store starting position for feedback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0
        
        # Fall Back movement distance is the unit's Move characteristic
        movement_range = self.movement
        
        from ...utility.calcs import MovementType
        # Calculate straight-line distance to destination (rules-aware)
        distance_to_destination = measure_direct_distance(
            (start_x, start_y, start_z),
            (destination[0], destination[1], destination[2]),
            self,
            MovementType.FALL_BACK,
            game_map,
        )
        
        # Check if destination is within movement range
        if distance_to_destination > movement_range:
            logger.info(f"{self.name} cannot reach fall back destination {distance_to_destination:.1f}\" away (max move: {movement_range}\")")
            return False

        # Generate potential positions for models with reduced boundary repulsors for better formation finding
        boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
        potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
        
        # Check if formation finding failed
        if potential_positions is None:
            logger.info(f"{self.name} cannot fall back - no valid formation found at destination")
            return False
            
        successful_moves = 0
        total_models_moved_over_enemies = 0
        
        for model, model_destination in zip(self.models, potential_positions):
            model_start = model.get_location()
            logging.debug(f"Model {model._id} {model.name} attempting to fall back from {model_start} to {model_destination}")
            
            # Calculate straight-line distance for this model
            model_distance = measure_direct_distance(
                (model_start[0], model_start[1], model_start[2] if len(model_start) > 2 else 0.0),
                (model_destination[0], model_destination[1], model_destination[2] if len(model_destination) > 2 else 0.0),
                self,
                MovementType.FALL_BACK,
                game_map,
            )
            
            # Check if this model can reach its destination
            if model_distance > movement_range:
                logger.info(f"Model {model._id} cannot reach fall back destination {model_distance:.1f}\" away (max: {movement_range}\")")
                continue  # Skip this model, don't move it
            
            # Try pathfinding for Fall Back movement using standard pathfinding
            from ...utility.calcs import get_movement_path_preview, MovementType

            pathfinding_result = get_movement_path_preview(
                model,
                model_destination,
                self.movement,
                game_map,
                movement_type=MovementType.FALL_BACK,
            )

            if not pathfinding_result or not pathfinding_result.get('valid'):
                logger.debug(f"Model {model._id} pathfinding failed for fall back - destination may be invalid")
                continue

            # Convert 2D path to 3D
            shortest_path = pathfinding_result['path']
            
            # Calculate path distance
            path_distance = measure_path_distance(shortest_path, self, MovementType.FALL_BACK, game_map)
            
            # Check for Desperate Escape Tests (models that move over enemy models).
            # New pathfinding does not track enemy models moved over, so this stays empty.
            enemy_models_moved_over = []
            if enemy_models_moved_over and not self.is_titanic and not self.is_flying:
                logger.info(f" Model {model._id} must take Desperate Escape Test for moving over {len(enemy_models_moved_over)} enemy model(s)")
                
                # Take Desperate Escape Test for this model
                roll = get_roll("D6")
                if roll <= 2:
                    logger.info(f"Model {model._id}: Rolled {roll} on Desperate Escape Test - DESTROYED! ")
                    self.remove_model(model, fleed=True, game_map=game_map)
                    continue  # Model is destroyed, don't move it
                else:
                    logger.info(f"Model {model._id}: Rolled {roll} on Desperate Escape Test - Survives ")
                    total_models_moved_over_enemies += 1
            
            if path_distance > movement_range:
                logger.info(f"Model {model._id} path distance {path_distance:.1f}\" exceeds movement {movement_range}\"")
                # Try to move as far as possible along the path
                last_node = model_start
                model.last_move_path = [last_node]
                distance_along_path = 0.0
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                
                for node in shortest_path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, MovementType.FALL_BACK)
                    
                    if distance_along_path + segment_distance > movement_range:
                        # Stop here, can't go further
                        break
                    
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                # Move to the furthest reachable position
                if distance_along_path > 0:
                    final_position = model.last_move_path[-1]
                    model.set_location(final_position[0], final_position[1], final_position[2], final_position[3])
                    successful_moves += 1
                    logger.debug(f"Model {model._id} fell back along path to {final_position[:3]}, distance: {distance_along_path:.1f}\"")
            else:
                # Path is within range, move to destination
                model.set_location(*model_destination)
                last_node = model_start
                model.last_move_path = [last_node]
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                distance_along_path = 0.0
                
                for node in shortest_path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, MovementType.FALL_BACK)
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                successful_moves += 1
                logger.debug(f"Model {model._id} fell back to {model_destination}, path distance: {distance_along_path:.1f}\"")
        
        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            logger.info(f"{self.name} could not fall back - no models could reach valid positions")
            return False
        
        # Check if unit was wiped out during Desperate Escape Tests
        if not self.is_alive():
            logger.info(f"{self.name} was completely destroyed during Fall Back Desperate Escape Tests!")
            return False
        
        # CRITICAL VALIDATION: Check for illegal overlaps after fall back
        # Fall back has special rules - units can move over enemies but cannot end overlapping
        enemy_units = game_map.get_enemy_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for enemy_unit in enemy_units:
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the enemy model's base
                    if model.model_base.collides_with(enemy_model.model_base):
                        logger.info(f"{self.name} cannot fall back - {model.name} cannot end overlapping with {enemy_model.name} from {enemy_unit.name}")
                        # For fall back, we don't have original positions stored, so this is a critical error
                        # The fall back move should have been validated during pathfinding
                        return False
        
        # Get final position for feedback from first model
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
            end_z = final_position[2] if len(final_position) > 2 else start_z
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
            end_z = start_z
        
        # Calculate actual distance the unit moved (rules-aware)
        unit_distance_moved = measure_direct_distance(
            (start_x, start_y, start_z),
            (end_x, end_y, end_z),
            self,
            MovementType.FALL_BACK,
            game_map,
        )
        
        # Provide detailed feedback
        logger.info(f"{self.name} fell back from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if total_models_moved_over_enemies > 0:
            logger.info(f" {total_models_moved_over_enemies} model(s) moved over enemy models and survived Desperate Escape Tests")
        
        if successful_moves < len(self.models):
            remaining_models = len(self.models)
            logger.info(f" Note: Only {successful_moves} models could fall back to valid positions, {remaining_models} models remain")
        
        logger.info(f"Unit {self.name} fell back from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        self.round_state.fell_back_this_round = True
        try:
            self._apply_super_heavy_walker_terrain_shock(game_map, action="fall_back")
        except Exception:
            pass
        return True

    def _eligibility_text_has_extra_clauses(self, text: str) -> bool:
        if not text:
            return False
        markers = [
            " but ",
            " instead ",
            " unless ",
            " except ",
            " however ",
            " only ",
            " while ",
            " after ",
            " before ",
            " until ",
            " once per ",
            " at the start",
            " start of",
            " each time",
            " choose ",
            " select ",
            " one of",
            " following",
            ":",
        ]
        t = f" {text} "
        return any(m in t for m in markers)

    def _has_simple_eligibility_rule(self, patterns: List[str]) -> bool:
        for name, desc in self._iter_ability_entries_for_rules():
            text = self._normalize_rules_text(f"{name} {desc}").lower()
            if not text:
                continue
            if any(p in text for p in patterns):
                if self._eligibility_text_has_extra_clauses(text):
                    continue
                return True
        return False

    def _get_fall_back_shoot_extended_rule_data(self) -> dict:
        """
        Parse extended Fall Back-and-Shoot clauses that include additional restrictions.

        Returns a dict with:
          - grants_fall_back_shoot: bool
          - lose_smoke_keyword: bool
          - restricted_wargear_names: tuple[str, ...] (normalized names)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and "fall_back_shoot_extended_rule_data" in cache:
            return dict(cache.get("fall_back_shoot_extended_rule_data") or {})

        patterns = (
            "eligible to shoot in a turn in which it fell back",
            "eligible to shoot in a turn in which it fell back or advanced",
            "eligible to shoot in a turn in which it advanced or fell back",
            "eligible to shoot and declare a charge in a turn in which it fell back",
            "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
            "that unit is eligible to shoot and declare a charge in a turn in which it fell back",
            "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced",
        )

        grants_fall_back_shoot = False
        lose_smoke_keyword = False
        restricted_wargear_names: set[str] = set()

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit_obj in members:
            for raw_name, desc in unit_obj._iter_ability_entries_for_rules():
                normalized = unit_obj._normalize_rules_text(desc or "")
                if not normalized:
                    continue
                low = normalized.lower()
                if not any(p in low for p in patterns):
                    continue

                grants_fall_back_shoot = True

                if "loses the smoke keyword" in low:
                    lose_smoke_keyword = True

                if "only models equipped with this wargear can make ranged attacks" in low:
                    norm_name = Unit._norm_wargear_name(str(raw_name or ""))
                    if norm_name:
                        restricted_wargear_names.add(norm_name)

        data = {
            "grants_fall_back_shoot": bool(grants_fall_back_shoot),
            "lose_smoke_keyword": bool(lose_smoke_keyword),
            "restricted_wargear_names": tuple(sorted(restricted_wargear_names)),
        }

        if not isinstance(cache, dict):
            cache = {}
        cache["fall_back_shoot_extended_rule_data"] = dict(data)
        root._ability_cache = cache
        return dict(data)

    def _fall_back_shoot_restricted_wargear_names(self) -> tuple[str, ...]:
        data = self._get_fall_back_shoot_extended_rule_data()
        names = data.get("restricted_wargear_names", ())
        return tuple(names) if isinstance(names, (list, tuple)) else tuple()

    def _model_meets_fall_back_shoot_wargear_restriction(self, model: Optional['Model']) -> bool:
        required = self._fall_back_shoot_restricted_wargear_names()
        if not required:
            return True
        for name in required:
            if self._model_has_wargear_named(model, name):
                return True
        return False

    def loses_smoke_keyword_when_shooting_after_fall_back(self) -> bool:
        data = self._get_fall_back_shoot_extended_rule_data()
        return bool(data.get("lose_smoke_keyword"))

    def has_advance_and_shoot(self) -> bool:
        """Check if the unit has an ability that allows shooting after advancing.
        
        This checks for unit abilities that allow shooting after advancing,
        based on actual Warhammer 40k ability descriptions.
        
        Returns:
            bool: True if the unit has an ability that allows shooting after advancing
        """
        # Use cached result if available
        if 'advance_and_shoot' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['advance_and_shoot']
        
        found = False
        if self.has_thrill_seekers():
            found = True
        elif self._first_prince_of_chaos_active() and self._first_prince_has_god_keyword("KHORNE"):
            found = True
        else:
            found = self._has_simple_eligibility_rule([
                "eligible to shoot in a turn in which it advanced",
                "eligible to shoot in a turn in which it fell back or advanced",
                "eligible to shoot in a turn in which it advanced or fell back",
                "eligible to shoot and declare a charge in a turn in which it advanced",
                "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
                "that unit is eligible to shoot and declare a charge in a turn in which it advanced",
                "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced",
            ])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['advance_and_shoot'] = found
        
        return found

    def has_advance_and_charge(self) -> bool:
        """Check if the unit has an ability that allows charging after advancing.

        This checks for unit abilities that allow charging after advancing,
        based on actual Warhammer 40k ability descriptions.

        Returns:
            bool: True if the unit has an ability that allows charging after advancing
        """
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "waaagh", None) if army is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if mgr is not None and mgr.unit_is_affected(self, game=game):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("apoplectic_frenzy_active"):
                return True
        except Exception:
            pass
        # Use cached result if available
        if 'advance_and_charge' in getattr(self, '_ability_cache', {}):
            cached_result = self._ability_cache['advance_and_charge']
            #print(f"{self.name} has_advance_and_charge (cached): {cached_result}")
            return cached_result

        logger.info(f"{self.name} checking for advance and charge abilities...")

        found = False
        if self.has_thrill_seekers():
            found = True
        elif self._first_prince_of_chaos_active() and self._first_prince_has_god_keyword("KHORNE"):
            found = True
        else:
            found = self._has_simple_eligibility_rule([
                "eligible to declare a charge in a turn in which it advanced",
                "eligible to declare a charge in a turn in which it advanced or fell back",
                "eligible to declare a charge in a turn in which it fell back or advanced",
                "eligible to charge in a turn in which it advanced",
                "eligible to charge in a turn in which it advanced or fell back",
                "eligible to charge in a turn in which it fell back or advanced",
                "eligible to shoot and declare a charge in a turn in which it advanced",
                "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
                "that unit is eligible to shoot and declare a charge in a turn in which it advanced",
                "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced",
            ])

        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['advance_and_charge'] = found

        return found

    def has_fell_back_and_shoot(self) -> bool:
        """Check if the unit has an ability that allows shooting after falling back.
        
        This checks for unit abilities that allow shooting after falling back,
        based on actual Warhammer 40k ability descriptions.
        
        Returns:
            bool: True if the unit has an ability that allows shooting after falling back
        """
        try:
            if self._needgaard_ordered_retreat_active_this_turn():
                return True
        except Exception:
            pass
        try:
            if self._thousand_sons_rubricae_stratagem_active(
                active_key="thousand_sons_ardent_automata_active",
                owner_key="thousand_sons_ardent_automata_turn_owner",
                turn_key="thousand_sons_ardent_automata_turn",
            ):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("feigned_retreat_active"):
                owner = str(sr.get("feigned_retreat_turn_owner", "") or "")
                turn = int(sr.get("feigned_retreat_turn", 0) or 0)
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                if game is None:
                    return True
                if owner and str(getattr(game.get_current_player(), "id", "") or "") == owner:
                    if int(getattr(game, "turn", 0) or 0) == int(turn or 0):
                        return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("feigned_weakness_active"):
                owner = str(sr.get("feigned_weakness_turn_owner", "") or "")
                turn = int(sr.get("feigned_weakness_turn", 0) or 0)
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                if game is None:
                    return True
                if owner and str(getattr(game.get_current_player(), "id", "") or "") == owner:
                    if int(getattr(game, "turn", 0) or 0) == int(turn or 0):
                        return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("manoeuvre_and_fire_active"):
                owner = str(sr.get("manoeuvre_and_fire_turn_owner", "") or "")
                turn = int(sr.get("manoeuvre_and_fire_turn", 0) or 0)
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                if game is None:
                    return True
                if owner and str(getattr(game.get_current_player(), "id", "") or "") == owner:
                    if int(getattr(game, "turn", 0) or 0) == int(turn or 0):
                        return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("command_phase_fell_back_and_shoot_active"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_kunnin_but_brutal_active"):
                return True
        except Exception:
            pass
        # Use cached result if available
        if 'fell_back_and_shoot' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['fell_back_and_shoot']
        
        found = False
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "duty_before_all_applies", None):
                if mgr.duty_before_all_applies(self):
                    found = True
        except Exception:
            pass
        if not found:
            if self.has_thrill_seekers():
                found = True
            else:
                found = self._has_simple_eligibility_rule([
                    "eligible to shoot in a turn in which it fell back",
                    "eligible to shoot in a turn in which it fell back or advanced",
                    "eligible to shoot in a turn in which it advanced or fell back",
                    "eligible to shoot and declare a charge in a turn in which it fell back",
                    "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                    "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
                    "that unit is eligible to shoot and declare a charge in a turn in which it fell back",
                    "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                    "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced",
                ])
                if not found:
                    data = self._get_fall_back_shoot_extended_rule_data()
                    found = bool(data.get("grants_fall_back_shoot"))
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['fell_back_and_shoot'] = found
        
        return found

    def can_shoot_after_advance(self, profile) -> bool:
        """Check if this unit can shoot after advancing with the given weapon profile.
        
        A unit can shoot after advancing if either:
        1. The weapon profile is an Assault weapon, OR
        2. The unit has an ability that allows shooting after advancing
        
        Args:
            profile: The weapon profile to check
            
        Returns:
            bool: True if the unit can shoot this weapon after advancing
        """
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("battle_focus_star_engines_active"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                mode = str(sr.get("red_wrath_mode", "") or "").strip().lower()
                if mode in ("shoot", "both"):
                    return True
        except Exception:
            pass
        try:
            if self._thousand_sons_rubricae_stratagem_active(
                active_key="aeldari_time_to_strike_active",
                owner_key="aeldari_time_to_strike_turn_owner",
                turn_key="aeldari_time_to_strike_turn",
            ):
                if getattr(profile, "parent_wargear", None) is not None and profile.parent_wargear.is_ranged():
                    return True
        except Exception:
            pass
        try:
            if self._thousand_sons_rubricae_stratagem_active(
                active_key="thousand_sons_inexorable_advance_assault_active",
                owner_key="thousand_sons_inexorable_advance_turn_owner",
                turn_key="thousand_sons_inexorable_advance_turn",
                expires_phase_key="thousand_sons_inexorable_advance_assault_expires_phase",
            ):
                if getattr(profile, "parent_wargear", None) is not None and profile.parent_wargear.is_ranged():
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "doctrina_imperatives", None) if army is not None else None
            if mgr is not None:
                game = getattr(getattr(army, "player", None), "game", None)
                if mgr.conqueror_assault_applies(self, game=game):
                    if getattr(profile, "parent_wargear", None) is not None and profile.parent_wargear.is_ranged():
                        return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bondsman_assault_ranged"):
                if getattr(profile, "parent_wargear", None) is not None and profile.parent_wargear.is_ranged():
                    return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bearer_unit_assault_ranged"):
                if getattr(profile, "parent_wargear", None) is not None and profile.parent_wargear.is_ranged():
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "necrons_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "relentless_onslaught_assault_applies", None):
                if mgr.relentless_onslaught_assault_applies(self):
                    if getattr(profile, "parent_wargear", None) is not None and profile.parent_wargear.is_ranged():
                        return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "skilled_crews_assault_applies", None):
                if mgr.skilled_crews_assault_applies(self):
                    if getattr(profile, "parent_wargear", None) is not None and profile.parent_wargear.is_ranged():
                        return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
            if mgr is not None and callable(getattr(mgr, "raiders_and_reavers_assault_applies", None)):
                if mgr.raiders_and_reavers_assault_applies(self, profile):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "tau_empire_detachments", None) if army is not None else None
            if mgr is not None and callable(getattr(mgr, "killing_blow_assault_applies", None)):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr.killing_blow_assault_applies(self, profile, game=game):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "imperial_knights_detachments", None) if army is not None else None
            if mgr is not None and callable(getattr(mgr, "bold_gallantry_assault_applies", None)):
                if mgr.bold_gallantry_assault_applies(self, profile):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "combat_doctrines", None) if army is not None else None
            if mgr is not None and getattr(mgr, "can_shoot_after_advance", None):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr.can_shoot_after_advance(self, profile, game=game):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "interlocking_tactics_shoot_after_advance_applies", None):
                if mgr.interlocking_tactics_shoot_after_advance_applies(self, profile):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "masters_of_manoeuvre_shoot_after_advance_applies", None):
                if mgr.masters_of_manoeuvre_shoot_after_advance_applies(self, profile):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "close_range_eradication_assault_applies", None):
                if mgr.close_range_eradication_assault_applies(self, profile):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "vulkans_quest_assault_applies", None):
                if mgr.vulkans_quest_assault_applies(self, profile):
                    return True
        except Exception:
            pass
        # Check for Assault weapons
        if profile.is_assault():
            return True
            
        # Check for unit abilities that allow advance and shoot
        if self.has_advance_and_shoot():
            return True
            
        return False

    def can_shoot_after_fall_back(self, profile, model: Optional['Model'] = None) -> bool:
        """Check if this unit can shoot after falling back with the given weapon profile.
        
        In 10th edition, Falling Back normally makes a unit not eligible to shoot.
        A unit can only shoot after falling back if it has an ability that explicitly allows it.
        
        Args:
            profile: The weapon profile to check
            
        Returns:
            bool: True if the unit can shoot this weapon after falling back
        """
        # Check for unit abilities that allow shooting after falling back
        if self.has_fell_back_and_shoot():
            # Some abilities restrict this to models equipped with specific wargear.
            required = self._fall_back_shoot_restricted_wargear_names()
            if required:
                if model is not None:
                    return self._model_meets_fall_back_shoot_wargear_restriction(model)
                try:
                    root = self.get_attached_unit_root()
                except Exception:
                    root = self
                try:
                    members = list(root.get_attached_unit_members() or [])
                except Exception:
                    members = [root]
                if not members:
                    members = [root]
                candidates = []
                for member in members:
                    for candidate in list(getattr(member, "models", []) or []):
                        if bool(getattr(candidate, "is_alive", False)):
                            candidates.append(candidate)
                if profile is not None and callable(getattr(self, "_model_has_weapon_profile", None)):
                    candidates = [m for m in candidates if self._model_has_weapon_profile(m, profile)]
                for candidate in candidates:
                    if self._model_meets_fall_back_shoot_wargear_restriction(candidate):
                        return True
                return False
            return True

        try:
            army = self.get_parent_army()
            mgr = getattr(army, "combat_doctrines", None) if army is not None else None
            if mgr is not None and getattr(mgr, "can_shoot_after_fall_back", None):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr.can_shoot_after_fall_back(self, profile, game=game):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "interlocking_tactics_shoot_after_fall_back_applies", None):
                if mgr.interlocking_tactics_shoot_after_fall_back_applies(self, profile):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "masters_of_manoeuvre_shoot_after_fall_back_applies", None):
                if mgr.masters_of_manoeuvre_shoot_after_fall_back_applies(self, profile):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "legacy_of_the_angel_sanguinary_grace_applies", None):
                if mgr.legacy_of_the_angel_sanguinary_grace_applies(self):
                    return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("vectored_engines_active"):
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                owner = str(sr.get("vectored_engines_turn_owner", "") or "")
                turn = int(sr.get("vectored_engines_turn", 0) or 0)
                active = True
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    if owner and cur_owner and owner != cur_owner:
                        active = False
                    if turn and cur_turn and turn != cur_turn:
                        active = False
                if active:
                    return True
        except Exception:
            pass
            
        return False

    def is_shooting_phase_ineligible(self, game=None) -> bool:
        """Return True if this unit is currently not eligible to shoot in the Shooting phase."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("shooting_phase_ineligible_active"):
            return False
        if game is None:
            try:
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        owner_id = str(sr.get("shooting_phase_ineligible_owner", "") or "")
        try:
            turn = int(sr.get("shooting_phase_ineligible_turn", 0) or 0)
        except Exception:
            turn = 0
        if game is None:
            return True
        try:
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase_name = ""
        if phase_name and phase_name != "SHOOTING_PHASE":
            return False
        if owner_id:
            try:
                current = game.get_current_player()
            except Exception:
                current = None
            if current is not None and str(getattr(current, "id", "") or "") != owner_id:
                return False
        if turn:
            try:
                if int(getattr(game, "turn", 0) or 0) != turn:
                    return False
            except Exception:
                return False
        return True

    def _dark_ritual_active(self, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("dark_ritual_active"):
            return False
        owner = str(sr.get("dark_ritual_turn_owner", "") or "")
        try:
            turn = int(sr.get("dark_ritual_turn", 0) or 0)
        except Exception:
            turn = 0
        if owner or turn:
            if game is None:
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
            if game is None:
                return False
            cur_turn = int(getattr(game, "turn", 0) or 0)
            cur_player = getattr(game, "get_current_player", lambda: None)()
            cur_owner = str(getattr(cur_player, "id", "") or "")
            if owner and owner != cur_owner:
                return False
            if turn and turn != cur_turn:
                return False
        return True

    def get_dark_ritual_bonuses(self, game=None) -> tuple[int, int, str]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if not root._dark_ritual_active(game=game):
            return (0, 0, "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return (0, 0, "")
        try:
            hit_bonus = int(sr.get("dark_ritual_hit_bonus", 1) or 0)
        except Exception:
            hit_bonus = 0
        try:
            wound_bonus = int(sr.get("dark_ritual_wound_bonus", 1) or 0)
        except Exception:
            wound_bonus = 0
        source = str(sr.get("dark_ritual_source", "") or "Dark Ritual").strip() or "Dark Ritual"
        return (hit_bonus, wound_bonus, source)

    def _advance_and_charge_always_available(self) -> bool:
        """Return True if this unit can always charge after advancing (non-once-per-battle sources)."""
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                mode = str(sr.get("red_wrath_mode", "") or "").strip().lower()
                if mode in ("charge", "both"):
                    return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bondsman_charge_after_advance"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_charge_after_advance"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("warp_surge_charge_after_advance"):
                apply_bonus = True
                exp = str(sr.get("warp_surge_expires_phase", "") or "").strip().upper()
                if exp:
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    try:
                        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    except Exception:
                        game = None
                    if game is not None:
                        pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    else:
                        pname = ""
                    if pname and pname != exp:
                        apply_bonus = False
                if apply_bonus:
                    return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("carnival_sycophantic_surge_charge_after_advance")):
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if self._carnival_sycophantic_surge_active_for_charge(game=game):
                    return True
        except Exception:
            pass
        try:
            if self._dark_ritual_active():
                return True
        except Exception:
            pass
        try:
            if self._thousand_sons_rubricae_stratagem_active(
                active_key="aeldari_time_to_strike_active",
                owner_key="aeldari_time_to_strike_turn_owner",
                turn_key="aeldari_time_to_strike_turn",
            ):
                return True
        except Exception:
            pass
        try:
            if self._thousand_sons_rubricae_stratagem_active(
                active_key="serpents_brood_striking_stride_active",
                owner_key="serpents_brood_striking_stride_turn_owner",
                turn_key="serpents_brood_striking_stride_turn",
                expires_phase_key="serpents_brood_striking_stride_expires_phase",
            ):
                return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "combat_doctrines", None) if army is not None else None
            if mgr is not None and getattr(mgr, "can_charge_after_advance", None):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr.can_charge_after_advance(self, game=game):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "interlocking_tactics_charge_after_advance_applies", None):
                if mgr.interlocking_tactics_charge_after_advance_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "masters_of_manoeuvre_charge_after_advance_applies", None):
                if mgr.masters_of_manoeuvre_charge_after_advance_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "lightning_assault_charge_after_advance_applies", None):
                if mgr.lightning_assault_charge_after_advance_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "storm_swift_onslaught_charge_after_advance_applies", None):
                if mgr.storm_swift_onslaught_charge_after_advance_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "can_charge_after_advance", None):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr.can_charge_after_advance(self, game=game):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "can_charge_after_advance", None):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr.can_charge_after_advance(self, game=game):
                    return True
        except Exception:
            pass
        return bool(self.has_advance_and_charge())

    def _advance_and_charge_once_per_battle_spec(self) -> Optional[dict]:
        """Return an available once-per-battle advance+charge spec, if any."""
        try:
            specs = list(self.leading_once_per_battle_advance_and_charge_specs() or [])
        except Exception:
            specs = []
        if not specs:
            return None
        for spec in specs:
            key = str(spec.get("ability_key") or "").strip().lower()
            if not key:
                continue
            if self.has_used_unit_once_per_battle(key):
                continue
            return dict(spec)
        return None

    def can_charge_after_advance(self) -> bool:
        """Check if this unit can charge after advancing.

        A unit can charge after advancing if it has an ability that allows it.

        Returns:
            bool: True if the unit can charge after advancing
        """
        try:
            if Unit._advance_and_charge_always_available(self):
                return True
        except Exception:
            pass
        spec_fn = getattr(self, "_advance_and_charge_once_per_battle_spec", None)
        if callable(spec_fn):
            return spec_fn() is not None
        try:
            return bool(self.has_advance_and_charge())
        except Exception:
            return False

    def can_charge_after_fall_back(self) -> bool:
        """Check if this unit can charge after falling back."""
        if self.has_thrill_seekers():
            return True
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "interlocking_tactics_charge_after_fall_back_applies", None):
                if mgr.interlocking_tactics_charge_after_fall_back_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "masters_of_manoeuvre_charge_after_fall_back_applies", None):
                if mgr.masters_of_manoeuvre_charge_after_fall_back_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "legacy_of_the_angel_sanguinary_grace_applies", None):
                if mgr.legacy_of_the_angel_sanguinary_grace_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "lightning_assault_charge_after_fall_back_applies", None):
                if mgr.lightning_assault_charge_after_fall_back_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "storm_swift_onslaught_charge_after_fall_back_applies", None):
                if mgr.storm_swift_onslaught_charge_after_fall_back_applies(self):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is not None and getattr(mgr, "beguiling_aura_applies", None):
            try:
                if bool(mgr.beguiling_aura_applies(self)):
                    return True
            except Exception:
                pass
        try:
            if self._needgaard_ordered_retreat_active_this_turn():
                return True
        except Exception:
            pass
        try:
            if self._thousand_sons_rubricae_stratagem_active(
                active_key="thousand_sons_ardent_automata_active",
                owner_key="thousand_sons_ardent_automata_turn_owner",
                turn_key="thousand_sons_ardent_automata_turn",
            ):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_kunnin_but_brutal_active"):
                return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "duty_before_all_applies", None):
                if mgr.duty_before_all_applies(self):
                    return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("aeldari_lethal_ruse_charge_after_fall_back_active"):
                owner = str(sr.get("aeldari_lethal_ruse_turn_owner", "") or "")
                turn = int(sr.get("aeldari_lethal_ruse_turn", 0) or 0)
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                if game is None:
                    return True
                if owner and str(getattr(game.get_current_player(), "id", "") or "") == owner:
                    if int(getattr(game, "turn", 0) or 0) == int(turn or 0):
                        return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("feigned_retreat_active"):
                owner = str(sr.get("feigned_retreat_turn_owner", "") or "")
                turn = int(sr.get("feigned_retreat_turn", 0) or 0)
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                if game is None:
                    return True
                if owner and str(getattr(game.get_current_player(), "id", "") or "") == owner:
                    if int(getattr(game, "turn", 0) or 0) == int(turn or 0):
                        return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("feigned_weakness_active"):
                owner = str(sr.get("feigned_weakness_turn_owner", "") or "")
                turn = int(sr.get("feigned_weakness_turn", 0) or 0)
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                if game is None:
                    return True
                if owner and str(getattr(game.get_current_player(), "id", "") or "") == owner:
                    if int(getattr(game, "turn", 0) or 0) == int(turn or 0):
                        return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_charge_after_fall_back"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("carnival_sycophantic_surge_charge_after_fall_back")):
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if self._carnival_sycophantic_surge_active_for_charge(game=game):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "templar_vows", None) if army is not None else None
            if mgr is not None and mgr.can_charge_after_fall_back(self):
                return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "combat_doctrines", None) if army is not None else None
            if mgr is not None and getattr(mgr, "can_charge_after_fall_back", None):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr.can_charge_after_fall_back(self, game=game):
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "can_charge_after_fall_back", None):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr.can_charge_after_fall_back(self, game=game):
                    return True
        except Exception:
            pass
        return self._has_simple_eligibility_rule([
            "eligible to declare a charge in a turn in which it fell back",
            "eligible to declare a charge in a turn in which it advanced or fell back",
            "eligible to declare a charge in a turn in which it fell back or advanced",
            "eligible to charge in a turn in which it advanced or fell back",
            "eligible to charge in a turn in which it fell back or advanced",
            "eligible to shoot and declare a charge in a turn in which it fell back",
            "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
            "that unit is eligible to shoot and declare a charge in a turn in which it fell back",
            "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced",
        ])

    def _thrill_seekers_restrictions_active(self) -> bool:
        if not self.has_thrill_seekers():
            return False
        return bool(getattr(self.round_state, "advanced_this_round", False) or getattr(self.round_state, "fell_back_this_round", False))

    def _carnival_sycophantic_surge_active_for_charge(self, *, game=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("carnival_sycophantic_surge_active")):
            return False
        if not (
            bool(sr.get("carnival_sycophantic_surge_charge_after_advance"))
            or bool(sr.get("carnival_sycophantic_surge_charge_after_fall_back"))
        ):
            return False
        gm = game
        if gm is None:
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            gm = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        if gm is None:
            return True
        owner_id = str(sr.get("carnival_sycophantic_surge_turn_owner", "") or "")
        effect_turn = int(sr.get("carnival_sycophantic_surge_turn", 0) or 0)
        exp_phase = str(sr.get("carnival_sycophantic_surge_expires_phase", "") or "").strip().upper()
        try:
            cur_player = getattr(gm, "get_current_player", lambda: None)()
            cur_owner = str(getattr(cur_player, "id", "") or "")
        except Exception:
            cur_owner = ""
        try:
            cur_turn = int(getattr(gm, "turn", 0) or 0)
        except Exception:
            cur_turn = 0
        try:
            cur_phase = str(getattr(getattr(gm, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            cur_phase = ""
        if owner_id and cur_owner and owner_id != cur_owner:
            return False
        if effect_turn and cur_turn and effect_turn != cur_turn:
            return False
        if exp_phase and cur_phase and exp_phase != cur_phase:
            return False
        return True

    def _carnival_sycophantic_target_condition_met(self, target_unit: 'Unit', game) -> bool:
        if target_unit is None or game is None:
            return False
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        if target_root is None:
            return False
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        player = getattr(army, "player", None)
        if player is None:
            return False
        mgr = getattr(army, "emperors_children", None)
        checker = getattr(mgr, "is_emperors_children_unit", None) if mgr is not None else None

        def _is_emperors_children_unit(unit_obj) -> bool:
            if unit_obj is None:
                return False
            if callable(checker):
                try:
                    return bool(checker(unit_obj))
                except Exception:
                    return False
            try:
                if unit_obj.has_keyword("EMPEROR'S CHILDREN"):
                    return True
            except Exception:
                pass
            try:
                if unit_obj.has_any_keyword("EMPEROR'S CHILDREN"):
                    return True
            except Exception:
                pass
            return False

        seen: set[str] = set()
        for unit_obj in list(getattr(army, "units", []) or []):
            try:
                friendly_root = unit_obj.get_attached_unit_root()
            except Exception:
                friendly_root = unit_obj
            if friendly_root is None:
                continue
            uid = str(get_entity_id(friendly_root) or "")
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            try:
                if friendly_root.get_parent_army().player is not player:
                    continue
            except Exception:
                continue
            if not _is_emperors_children_unit(friendly_root):
                continue
            try:
                if not friendly_root.is_alive():
                    continue
            except Exception:
                continue
            if not bool(getattr(friendly_root, "deployed", False)):
                continue
            if str(getattr(friendly_root, "reserve_status", "deployed")) != "deployed":
                continue
            if getattr(friendly_root, "embarked_in", None) is not None:
                continue
            if bool(getattr(friendly_root, "is_embarked", False)):
                continue
            try:
                if bool(game_map.is_within_engagement_range(friendly_root, target_root)):
                    return True
            except Exception:
                continue
        return False

    def _thrill_seekers_restriction_reason(self, target_unit: 'Unit', game) -> Optional[str]:
        if not self._thrill_seekers_restrictions_active():
            return None
        if target_unit is None:
            return None
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        target_id = get_entity_id(target_root)
        engaged_ids = getattr(self.round_state, "engaged_enemies_at_turn_start", None) or set()
        if target_id is not None and target_id in engaged_ids:
            return "Thrill Seekers: cannot target a unit engaged at start of turn"
        try:
            phase_targets = getattr(game, "phase_targeted_units", None)
        except Exception:
            phase_targets = None
        try:
            phase_charge_targets = getattr(game, "phase_charge_targets", None)
        except Exception:
            phase_charge_targets = None
        if isinstance(phase_targets, dict) and target_id is not None:
            attackers = phase_targets.get(target_id, set()) or set()
            other_attackers = [a for a in attackers if a != get_entity_id(self)]
            if other_attackers:
                return "Thrill Seekers: target already selected by another unit this phase"
        if isinstance(phase_charge_targets, dict) and target_id is not None:
            chargers = phase_charge_targets.get(target_id, set()) or set()
            other_chargers = [a for a in chargers if a != get_entity_id(self)]
            if other_chargers:
                return "Thrill Seekers: target already selected by another unit this phase"
        return None

    def _sensational_performance_restriction_reason(self, target_unit: 'Unit', game) -> Optional[str]:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        if not sr.get("sensational_performance_active"):
            return None
        exp = str(sr.get("sensational_performance_expires_phase", "") or "").strip().upper()
        if exp:
            try:
                pname = str(getattr(getattr(game, "phase", None), "name", "") or getattr(game, "phase", "") or "").strip().upper()
            except Exception:
                pname = ""
            if pname and pname != exp:
                return None
        if target_unit is None:
            return None
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        target_id = get_entity_id(target_root)
        engaged_ids = getattr(self.round_state, "engaged_enemies_at_turn_start", None) or set()
        if target_id is not None and target_id in engaged_ids:
            return "Sensational Performance: cannot target a unit engaged at start of turn"
        try:
            phase_targets = getattr(game, "phase_targeted_units", None)
        except Exception:
            phase_targets = None
        if isinstance(phase_targets, dict) and target_id is not None:
            attackers = phase_targets.get(target_id, set()) or set()
            other_attackers = [a for a in attackers if a != getattr(self, "_id", None)]
            if other_attackers:
                return "Sensational Performance: target already selected by another unit this phase"
        return None

    def scout_move(self, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        """Execute a scout move for the unit during pre-battle rules phase.
        
        Scout moves have special restrictions:
        - Cannot move within engagement range of enemy units
        - Cannot end within 9" of enemy units
        - Cannot charge or advance during scout move
        - Considered a normal move action (terrain rules apply)
        
        Args:
            destination: Target position (x, y, z)
            game_map: The game map for validation and movement
            
        Returns:
            bool: True if scout move was successful
        """
        if not self.models:
            logger.error(f"Cannot scout move unit {self.name}: no models in unit")
            return False
        
        # Check if unit has scout ability
        has_scout, scout_distance = self.has_scout()
        if not has_scout:
            logger.error(f"Unit {self.name} does not have Scout ability")
            return False
        
        # Check if unit has already made a scout move
        if hasattr(self, 'scout_move_made') and self.scout_move_made:
            logger.error(f"Unit {self.name} has already made a scout move")
            return False
        
        # Check if unit is deployed (not in reserves)
        if not self.deployed or self.reserve_status != 'deployed':
            logger.error(f"Unit {self.name} is not deployed and cannot make scout move")
            return False
        
        # Get starting position from first model
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot scout move unit {self.name}: no valid models")
            return False

        first_model_pos = self.models[0].get_location()
        if not first_model_pos:
            logger.error(f"Cannot scout move unit {self.name}: first model has no position")
            return False

        # Store starting position for feedback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0
        
        from ...utility.calcs import MovementType
        # Calculate straight-line distance to destination (rules-aware)
        distance_to_destination = measure_direct_distance(
            (start_x, start_y, start_z),
            (destination[0], destination[1], destination[2]),
            self,
            MovementType.SCOUT,
            game_map,
        )
        
        # Check if destination is within scout distance
        if distance_to_destination > scout_distance:
            logger.info(f"{self.name} cannot reach scout destination {distance_to_destination:.1f}\" away (max scout: {scout_distance}\")")
            return False
        
        # Generate potential positions for models with reduced boundary repulsors for better formation finding
        boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
        potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
        
        # Check if formation finding failed
        if potential_positions is None:
            logger.info(f"{self.name} cannot scout move - no valid formation found at destination")
            return False

        # Check scout restriction: cannot end within 9" of enemy models (base-to-base closest-point distance).
        from ...utility.aura_utils import distance_between_bases_3d
        enemy_models = [em for eu in game_map.get_enemy_units(self) if eu.is_alive() and eu.deployed for em in eu.models if em.is_alive]
        for idx, (x, y, z, facing) in enumerate(potential_positions):
            if idx >= len(self.models):
                break
            mb = self._create_potential_base(x, y, z, facing, model=self.models[idx])
            for em in enemy_models:
                if float(distance_between_bases_3d(mb, em.model_base)) < 9.0:
                    logger.info(f"{self.name} cannot scout move to destination - would end within 9\" of {em.parent_unit.name}")
                    return False
            
        # BACKUP ORIGINAL POSITIONS - Critical for proper rollback on failure
        original_model_positions = []
        for model in self.models:
            original_model_positions.append(model.get_location())

        successful_moves = 0
        
        for model, model_destination in zip(self.models, potential_positions):
            model_start = model.get_location()
            logging.debug(f"Model {model._id} {model.name} attempting scout move from {model_start} to {model_destination}")
            
            # Calculate straight-line distance for this model
            model_distance = measure_direct_distance(
                (model_start[0], model_start[1], model_start[2] if len(model_start) > 2 else 0.0),
                (model_destination[0], model_destination[1], model_destination[2] if len(model_destination) > 2 else 0.0),
                self,
                MovementType.SCOUT,
                game_map,
            )
            
            # Check if this model can reach its destination
            if model_distance > scout_distance:
                logger.info(f"Model {model._id} cannot reach scout destination {model_distance:.1f}\" away (max: {scout_distance}\")")
                continue  # Skip this model, don't move it
            
            # Use new optimized pathfinding for scout move (individual model movement)
            from ...utility.calcs import get_individual_model_movement_path
            
            # Find model index for pathfinding
            model_index = None
            for i, m in enumerate(self.models):
                if m == model:
                    model_index = i
                    break
            
            if model_index is None:
                logger.error(f"Could not find model index for {model.name}")
                continue
            
            path = get_individual_model_movement_path(self, model_index, model_destination, game_map, scout_distance)
            
            if not path:
                logger.debug(f"Model {model._id} optimized pathfinding failed for scout move - destination may be invalid")
                continue
            
            # Calculate path distance
            path_distance = measure_path_distance(path, self, MovementType.SCOUT, game_map)
            
            if path_distance > scout_distance:
                logger.info(f"Model {model._id} path distance {path_distance:.1f}\" exceeds scout distance {scout_distance}\"")
                # Try to move as far as possible along the path
                last_node = model_start
                model.last_move_path = [last_node]
                distance_along_path = 0.0
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                
                for node in path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, MovementType.SCOUT)
                    
                    if distance_along_path + segment_distance > scout_distance:
                        # Stop here, can't go further
                        break
                    
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                # Move to the furthest reachable position
                if distance_along_path > 0:
                    final_position = model.last_move_path[-1]
                    model.set_location(final_position[0], final_position[1], final_position[2], final_position[3])
                    successful_moves += 1
                    logger.debug(f"Model {model._id} scout moved along path to {final_position[:3]}, distance: {distance_along_path:.1f}\"")
            else:
                # Path is within range, move to destination
                model.set_location(*model_destination)
                last_node = model_start
                model.last_move_path = [last_node]
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                distance_along_path = 0.0
                
                for node in path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, MovementType.SCOUT)
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                successful_moves += 1
                logger.debug(f"Model {model._id} scout moved to {model_destination}, path distance: {distance_along_path:.1f}\"")
        
        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            logger.info(f"{self.name} could not scout move - no models could reach valid positions")
            return False
        
        # NEW: Validate unit coherency after all models have moved (scout moves must maintain coherency)
        from ...utility.calcs import validate_unit_coherency_after_movement
        
        # Get final positions of all models
        final_positions = []
        for model in self.models:
            final_positions.append(model.get_location())
        
        is_coherent, non_coherent_models = validate_unit_coherency_after_movement(self, final_positions)
        
        if not is_coherent:
            logger.info(f"{self.name} scout move rejected: unit coherency would be broken (non-coherent models: {non_coherent_models})")
            # ROLLBACK: Restore original positions (movement ending out of coherency is not allowed)
            for i, original_pos in enumerate(original_model_positions):
                if i < len(self.models):
                    self.models[i].set_location(*original_pos)
            return False
        
        # CRITICAL VALIDATION: Check for illegal overlaps after scout move
        # Scout moves cannot end overlapping with enemy models
        enemy_units = game_map.get_enemy_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for enemy_unit in enemy_units:
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the enemy model's base
                    if model.model_base.collides_with(enemy_model.model_base):
                        logger.info(f"{self.name} cannot scout move - {model.name} cannot end overlapping with {enemy_model.name} from {enemy_unit.name}")
                        # ROLLBACK: Restore original positions
                        for i, original_pos in enumerate(original_model_positions):
                            if i < len(self.models):
                                self.models[i].set_location(*original_pos)
                        return False
        
        # Get final position for feedback from first model
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
            end_z = final_position[2] if len(final_position) > 2 else start_z
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
            end_z = start_z
        
        # Calculate actual distance the unit moved (rules-aware)
        unit_distance_moved = measure_direct_distance(
            (start_x, start_y, start_z),
            (end_x, end_y, end_z),
            self,
            MovementType.SCOUT,
            game_map,
        )
        
        # Mark unit as having made a scout move
        self.scout_move_made = True
        
        # Provide detailed feedback
        logger.info(f"{self.name} scout moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if successful_moves < len(self.models):
            logger.info(f" Note: Only {successful_moves}/{len(self.models)} models could scout move to valid positions")
        
        logger.info(f"Unit {self.name} scout moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        return True

    def can_shoot_in_engagement_range(self, game_map: 'Map', profile=None) -> bool:
        """Check if this unit can shoot while in engagement range with the given weapon profile."""
        # Check if unit is in engagement range ("Locked in Combat")
        is_engaged = any(
            game_map.is_within_engagement_range(self, enemy)
            for enemy in game_map.get_enemy_units(self)
            if enemy.is_alive()
        )
        
        if not is_engaged:
            return True

        if self._is_ficklefire_active():
            return True
            
        # If engaged and no profile provided, assume cannot shoot
        if profile is None:
            return False
            
        # PISTOLS: can be used while within Engagement Range (target restriction enforced elsewhere)
        if profile.is_pistol():
            return True

        # BIG GUNS NEVER TIRE (BGNT):
        # In the controlling player's Shooting phase, VEHICLE/MONSTER units remain eligible to shoot while Locked in Combat.
        if (self.is_vehicle or self.is_monster) and self._is_controlling_players_shooting_phase():
            return True

        return False

    def can_shoot_at_target_while_engaged(self, target, profile, game_map) -> bool:
        """Check if this unit can shoot at a specific target while engaged with other units."""
        if self._is_ficklefire_active():
            return True
        # If unit is not in engagement range, they can always shoot
        if not any(game_map.is_within_engagement_range(self, enemy)
                  for enemy in game_map.get_enemy_units(self) if enemy.is_alive()):
            return True

        # If target is the unit we're engaged with, Pistols can shoot; Vehicles/Monsters can shoot in-phase via BGNT.
        if target.is_alive() and game_map.is_within_engagement_range(self, target):
            if profile.is_pistol():
                return True
            return (self.is_vehicle or self.is_monster) and self._is_controlling_players_shooting_phase()

        # If target is not the unit we're engaged with, only Vehicles/Monsters can shoot in-phase via BGNT.
        return (self.is_vehicle or self.is_monster) and self._is_controlling_players_shooting_phase()

    def _is_controlling_players_shooting_phase(self) -> bool:
        """
        Return True only during this unit's controlling player's Shooting phase.

        Used for rules that explicitly apply only "in your Shooting phase" (e.g., Big Guns Never Tire).
        """
        army = self.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        if game is None or player is None:
            return False
        return bool(getattr(game, "is_shooting_phase", lambda: False)() and getattr(game, "get_current_player", lambda: None)() is player)

    def _is_ficklefire_active(self, *, game=None, phase_name: Optional[str] = None) -> bool:
        """Return True if this unit is under Ficklefire for the current phase."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("ficklefire_active"):
            return False
        if game is None:
            try:
                game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        owner = str(sr.get("ficklefire_turn_owner", "") or "")
        if owner:
            try:
                unit_owner = str(getattr(root.get_parent_army().player, "id", "") or "")
            except Exception:
                unit_owner = ""
            if unit_owner and owner != unit_owner:
                return False
        exp = str(sr.get("ficklefire_expires_phase", "") or "").strip().upper()
        if exp:
            phase_key = ""
            if phase_name:
                phase_key = str(phase_name or "").strip().upper().replace(" ", "_")
            if not phase_key and game is not None:
                phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            if phase_key and phase_key != exp:
                return False
        turn = int(sr.get("ficklefire_turn", 0) or 0)
        if turn:
            if game is None:
                return False
            if int(getattr(game, "turn", 0) or 0) != turn:
                return False
        return True

    def _is_locked_in_combat(self, game_map: 'Map') -> bool:
        """Return True if this unit is within Engagement Range of any enemy unit."""
        return any(
            game_map.is_within_engagement_range(self, enemy)
            for enemy in game_map.get_enemy_units(self)
            if enemy.is_alive()
        )

    @staticmethod
    def _is_unit_locked_in_combat(unit: 'Unit', game_map: 'Map') -> bool:
        """Return True if `unit` is within Engagement Range of any of its enemy units."""
        return any(
            game_map.is_within_engagement_range(unit, enemy)
            for enemy in game_map.get_enemy_units(unit)
            if enemy.is_alive()
        )

    def is_only_within_enemy_fortifications(self, game_map: 'Map', *, enemy_unit: Optional['Unit'] = None) -> bool:
        """
        Return True if this unit is within Engagement Range of one or more enemy Fortifications
        and no other enemy units.

        If enemy_unit is provided, treat that unit's army as the "enemy" perspective.
        """
        if game_map is None:
            return False
        try:
            if not self.is_alive() or not getattr(self, "deployed", True):
                return False
        except Exception:
            return False

        if enemy_unit is not None:
            candidates = list(game_map.get_friendly_units(enemy_unit))
        else:
            candidates = list(game_map.get_enemy_units(self))

        engaged = []
        seen = set()
        for unit in list(candidates or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            try:
                if not root.is_alive() or not getattr(root, "deployed", True):
                    continue
            except Exception:
                continue
            try:
                if bool(getattr(root, "is_embarked", False)) or root.is_in_reserves():
                    continue
            except Exception:
                pass
            try:
                if not game_map.is_within_engagement_range(root, self):
                    continue
            except Exception:
                continue
            engaged.append(root)

        if not engaged:
            return False
        for unit in engaged:
            try:
                if not bool(getattr(unit, "is_fortification", False)):
                    return False
            except Exception:
                return False
        return True

    ###########################################################################
    ### Shooting Phase Actions
    ###########################################################################
