"""Ability-state and source-selection helpers for Unit positioning/runtime state."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class PositioningAbilityStateMixin:
    def has_command_phase_sticky_objective(self) -> bool:
        """
        True if this unit has the datasheet ability that makes objectives sticky at end of your Command phase.
        """
        cache_key = "command_phase_sticky_objective"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])

        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("sticky_objectives"):
                found = True
            else:
                found = self._scan_command_phase_sticky_objective()
                if isinstance(sr, dict):
                    if found:
                        sr["sticky_objectives"] = True
                    elif "sticky_objectives" in sr:
                        del sr["sticky_objectives"]
        except Exception:
            found = self._scan_command_phase_sticky_objective()

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def get_command_phase_bodyguard_return_ability(self):
        """
        Return ability info dict for command-phase bodyguard model returns, or None if not available.
        """
        cache_key = "command_phase_bodyguard_return_ability"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        ability = None
        try:
            if not bool(getattr(self, "is_attached_leader", False)):
                ability = None
            else:
                ability = self._scan_command_phase_bodyguard_return_ability()
                sr = getattr(self, "special_rules", None)
                if ability and isinstance(sr, dict) and bool(sr.get("enhancement_needle_of_nurgle", False)):
                    bearer_id = str(
                        sr.get("enhancement_needle_of_nurgle_bearer_model_id", "")
                        or sr.get("enhancement_bearer_model_id", "")
                        or ""
                    ).strip()
                    bearer_alive = False
                    if bearer_id:
                        for model in list(getattr(self, "models", []) or []):
                            model_entity_id = str(get_entity_id(model) or "").strip()
                            model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                            if bearer_id != model_entity_id and bearer_id != model_local_id:
                                continue
                            alive_attr = getattr(model, "is_alive", True)
                            bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                            break
                    else:
                        get_bearer = getattr(self, "_get_enhancement_bearer_model", None)
                        bearer = get_bearer() if callable(get_bearer) else None
                        if bearer is not None:
                            alive_attr = getattr(bearer, "is_alive", True)
                            bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    requires_leading = bool(sr.get("enhancement_needle_of_nurgle_requires_bearer_leading", True))
                    if bearer_alive and (not requires_leading or bool(getattr(self, "is_attached_leader", False))):
                        amount_roll = str(
                            sr.get("enhancement_needle_of_nurgle_command_phase_return_amount_roll", "D3") or "D3"
                        ).strip().upper()
                        try:
                            max_return = int(sr.get("enhancement_needle_of_nurgle_command_phase_return_max", 3) or 3)
                        except Exception:
                            max_return = 3
                        ability_key = str(
                            sr.get("enhancement_needle_of_nurgle_ability_key", "needle_of_nurgle")
                            or "needle_of_nurgle"
                        ).strip().lower()
                        merged = dict(ability or {})
                        merged["name"] = str(
                            sr.get("enhancement_needle_of_nurgle_source", "Needle of Nurgle") or "Needle of Nurgle"
                        ).strip() or "Needle of Nurgle"
                        merged["ability_key"] = ability_key if ability_key else "needle_of_nurgle"
                        merged["amount_roll"] = amount_roll if amount_roll else "D3"
                        merged["amount"] = int(max(1, max_return))
                        merged["allow_skip"] = bool(merged.get("allow_skip", True))
                        ability = merged
                if not ability:
                    if isinstance(sr, dict) and bool(sr.get("enhancement_steel_font", False)):
                        bearer_id = str(
                            sr.get("enhancement_bearer_model_id", "")
                            or sr.get("enhancement_steel_font_bearer_model_id", "")
                            or ""
                        ).strip()
                        bearer_alive = False
                        if bearer_id:
                            for model in list(getattr(self, "models", []) or []):
                                model_entity_id = str(get_entity_id(model) or "").strip()
                                model_local_id = str(
                                    getattr(model, "id", getattr(model, "_id", "")) or ""
                                ).strip()
                                if bearer_id != model_entity_id and bearer_id != model_local_id:
                                    continue
                                alive_attr = getattr(model, "is_alive", True)
                                bearer_alive = bool(
                                    alive_attr() if callable(alive_attr) else alive_attr
                                )
                                break
                        else:
                            get_bearer = getattr(self, "_get_enhancement_bearer_model", None)
                            bearer = get_bearer() if callable(get_bearer) else None
                            if bearer is not None:
                                alive_attr = getattr(bearer, "is_alive", True)
                                bearer_alive = bool(
                                    alive_attr() if callable(alive_attr) else alive_attr
                                )
                        if bearer_alive:
                            try:
                                amount = int(
                                    sr.get("enhancement_steel_font_command_phase_return_amount", 1)
                                    or 1
                                )
                            except Exception:
                                amount = 1
                            ability_key = str(
                                sr.get("enhancement_steel_font_ability_key", "steel_font")
                                or "steel_font"
                            ).strip().lower()
                            ability = {
                                "name": str(
                                    sr.get("enhancement_steel_font_source", "Steel Font")
                                    or "Steel Font"
                                ).strip()
                                or "Steel Font",
                                "description": "",
                                "ability_key": ability_key if ability_key else "steel_font",
                                "amount": int(max(1, amount)),
                                "allow_skip": True,
                            }
                    if not ability and isinstance(sr, dict) and bool(sr.get("enhancement_amulet_of_tainted_vigour", False)):
                        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
                        bearer_alive = False
                        if bearer_id:
                            for model in list(getattr(self, "models", []) or []):
                                model_entity_id = str(get_entity_id(model) or "").strip()
                                model_local_id = str(
                                    getattr(model, "id", getattr(model, "_id", "")) or ""
                                ).strip()
                                if bearer_id != model_entity_id and bearer_id != model_local_id:
                                    continue
                                alive_attr = getattr(model, "is_alive", True)
                                bearer_alive = bool(
                                    alive_attr() if callable(alive_attr) else alive_attr
                                )
                                break
                        else:
                            get_bearer = getattr(self, "_get_enhancement_bearer_model", None)
                            bearer = get_bearer() if callable(get_bearer) else None
                            if bearer is not None:
                                alive_attr = getattr(bearer, "is_alive", True)
                                bearer_alive = bool(
                                    alive_attr() if callable(alive_attr) else alive_attr
                                )
                        if bearer_alive:
                            ability_key = str(
                                sr.get("enhancement_amulet_of_tainted_vigour_ability_key", "amulet_of_tainted_vigour")
                                or "amulet_of_tainted_vigour"
                            ).strip().lower()
                            amount_roll = str(
                                sr.get("enhancement_amulet_of_tainted_vigour_return_roll", "D3")
                                or "D3"
                            ).strip().upper()
                            required_keyword = str(
                                sr.get("enhancement_amulet_of_tainted_vigour_required_model_keyword", "DAMNED")
                                or "DAMNED"
                            ).strip().upper()
                            ability = {
                                "name": str(
                                    sr.get("enhancement_amulet_of_tainted_vigour_source", "Amulet of Tainted Vigour")
                                    or "Amulet of Tainted Vigour"
                                ).strip()
                                or "Amulet of Tainted Vigour",
                                "description": "",
                                "ability_key": ability_key if ability_key else "amulet_of_tainted_vigour",
                                "amount": 3,
                                "amount_roll": amount_roll if amount_roll else "D3",
                                "exclude_character": bool(
                                    sr.get("enhancement_amulet_of_tainted_vigour_exclude_character", True)
                                ),
                                "required_keyword": required_keyword if required_keyword else "DAMNED",
                                "allow_skip": bool(
                                    sr.get("enhancement_amulet_of_tainted_vigour_allow_skip", True)
                                ),
                            }
        except Exception:
            ability = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability


    def get_command_phase_unit_return_ability(self):
        """
        Return ability info dict for command-phase destroyed-model returns to this unit, or None.
        """
        cache_key = "command_phase_unit_return_ability"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        ability = None
        try:
            ability = self._scan_command_phase_unit_return_ability()
        except Exception:
            ability = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability


    def get_charge_phase_bodyguard_loss_ability(self):
        """
        Return ability info dict for end-of-Charge-phase Leadership test bodyguard losses, or None.
        """
        cache_key = "charge_phase_bodyguard_loss_ability"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        ability = None
        try:
            if not bool(getattr(self, "is_attached_leader", False)):
                ability = None
            else:
                ability = self._scan_charge_phase_bodyguard_loss_ability()
        except Exception:
            ability = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability


    def get_end_of_opponent_turn_strategic_reserves_ability(self):
        """
        Return ability info dict for end-of-opponent-turn Strategic Reserves removal, or None if not available.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "opponent_turn_strategic_reserves_ability"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        ability = None
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("enhancement_warp_fuelled_thrusters")):
            bearer_alive = False
            bearer_id = str(
                sr.get("enhancement_warp_fuelled_thrusters_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            if bearer_id:
                for model in list(getattr(root, "models", []) or []):
                    if str(get_entity_id(model) or "") != bearer_id:
                        continue
                    alive_attr = getattr(model, "is_alive", True)
                    bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    break
            else:
                get_bearer = getattr(root, "_get_enhancement_bearer_model", None)
                bearer_model = get_bearer() if callable(get_bearer) else None
                if bearer_model is not None:
                    alive_attr = getattr(bearer_model, "is_alive", True)
                    bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if bearer_alive or not bool(sr.get("enhancement_warp_fuelled_thrusters_requires_bearer_alive", True)):
                ability_name = (
                    str(sr.get("enhancement_warp_fuelled_thrusters_source", "") or "Warp-fuelled Thrusters").strip()
                    or "Warp-fuelled Thrusters"
                )
                ability_key = (
                    str(sr.get("enhancement_warp_fuelled_thrusters_ability_key", "") or "warp_fuelled_thrusters")
                    .strip()
                    .lower()
                )
                if not ability_key:
                    ability_key = "warp_fuelled_thrusters"
                ability = {
                    "name": ability_name,
                    "description": "",
                    "once_per_battle": bool(sr.get("enhancement_warp_fuelled_thrusters_once_per_battle", False)),
                    "ability_key": ability_key,
                    "trigger_phase": (
                        str(sr.get("enhancement_warp_fuelled_thrusters_trigger_phase", "") or "OPPONENT_TURN_END")
                        .strip()
                        .upper()
                    ),
                    "min_enemy_distance_horiz": 0,
                    "min_battlefield_edge_distance_horiz": 0,
                }

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not ability:
            for member in members:
                try:
                    ability = member._scan_end_of_opponent_turn_strategic_reserves_ability()
                except Exception:
                    ability = None
                if ability:
                    break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = ability
        return ability


    def get_end_of_fight_phase_destroyed_strategic_reserves_ability(self):
        """
        Return ability info dict for end-of-fight-phase Strategic Reserves removal after destroying enemy units.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "fight_phase_destroyed_strategic_reserves_ability"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        ability = None
        try:
            has_fade_to_darkness = bool(
                root._attached_unit_has_active_enhancement(
                    "enhancement_fade_to_darkness",
                    enhancement_id="000009980004",
                    enhancement_name="fade to darkness",
                )
            )
        except Exception:
            has_fade_to_darkness = False
        if has_fade_to_darkness:
            source_name = "Fade to Darkness"
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not bool(sr.get("enhancement_fade_to_darkness")):
                    continue
                raw = str(sr.get("enhancement_fade_to_darkness_source", "") or "").strip()
                if raw:
                    source_name = raw
                break
            ability = {
                "name": source_name,
                "description": "",
                "ability_key": "fight_phase_destroyed_strategic_reserves",
            }

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not ability:
            for member in members:
                try:
                    ability = member._scan_end_of_fight_phase_destroyed_strategic_reserves_ability()
                except Exception:
                    ability = None
                if ability:
                    break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = ability
        return ability


    def _transport_has_embarked_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip()
        if not kw:
            return False
        try:
            if not bool(getattr(self, "is_transport", False)):
                return False
        except Exception:
            return False
        passengers = list(getattr(self, "transport_passengers", []) or [])
        if not passengers:
            return False
        for passenger in passengers:
            if passenger is None:
                continue
            try:
                root = passenger.get_attached_unit_root()
            except Exception:
                root = passenger
            if root is None:
                continue
            try:
                if bool(root.has_any_keyword(kw)):
                    return True
            except Exception:
                continue
        return False


    def _transport_embarked_models_with_keyword_count(self, keyword: str) -> int:
        kw = str(keyword or "").strip()
        if not kw:
            return 0
        try:
            if not bool(getattr(self, "is_transport", False)):
                return 0
        except Exception:
            return 0
        passengers = list(getattr(self, "transport_passengers", []) or [])
        if not passengers:
            return 0
        total = 0
        for passenger in passengers:
            if passenger is None:
                continue
            try:
                root = passenger.get_attached_unit_root()
            except Exception:
                root = passenger
            if root is None:
                continue
            try:
                if not bool(root.has_any_keyword(kw)):
                    continue
            except Exception:
                continue
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            total += sum(1 for m in list(models or []) if getattr(m, "is_alive", False))
        return int(total)

    def rapid_strike_vehicle_objective_control_bonus(self) -> tuple[int, str]:
        """Centaur RSV: +1 OC for every three embarked models while not Battle-shocked."""
        get_root = getattr(self, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else self
        if root is None:
            return (0, "")
        cache_key = "rapid_strike_vehicle_rule_source"
        cache = getattr(root, "_ability_cache", None)
        source = ""
        if isinstance(cache, dict) and cache_key in cache:
            source = str(cache.get(cache_key, "") or "")
        else:
            found = ""
            get_members = getattr(root, "get_attached_unit_members", None)
            members = list(get_members() or []) if callable(get_members) else [root]
            if not members:
                members = [root]
            for member in list(members or []):
                if member is None:
                    continue
                for name, desc in member._iter_ability_entries_for_rules(model=None):
                    text = member._normalize_rules_text(member._strip_eligibility_prefix(desc or name or ""))
                    normalized = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                    normalized = re.sub(r"\s+", " ", normalized).strip()
                    if (
                        "while one or more units are embarked within this transport" in normalized
                        and "unless this unit is battle shocked" in normalized
                        and "add 1 to its objective control characteristic for every 3 models embarked within it" in normalized
                    ):
                        found = str(name or "Rapid Strike Vehicle").strip() or "Rapid Strike Vehicle"
                        break
                if found:
                    break
            if not isinstance(cache, dict):
                cache = {}
            cache[cache_key] = found
            root._ability_cache = cache
            source = found
        if not source:
            return (0, "")
        is_battle_shocked = getattr(root, "is_battle_shocked", None)
        if callable(is_battle_shocked) and bool(is_battle_shocked()):
            return (0, "")
        if not bool(getattr(root, "is_transport", False)):
            return (0, "")
        total_models = 0
        for passenger in list(getattr(root, "transport_passengers", []) or []):
            if passenger is None:
                continue
            get_passenger_root = getattr(passenger, "get_attached_unit_root", None)
            passenger_root = get_passenger_root() if callable(get_passenger_root) else passenger
            if passenger_root is None:
                continue
            get_models = getattr(passenger_root, "get_attached_unit_models", None)
            models = list(get_models() or []) if callable(get_models) else list(getattr(passenger_root, "models", []) or [])
            total_models += sum(1 for model in list(models or []) if getattr(model, "is_alive", False))
        bonus = int(total_models // 3)
        if bonus <= 0:
            return (0, "")
        return (int(bonus), source)

    def has_vanguard_of_dark_city(self) -> bool:
        cache_key = "vanguard_of_dark_city"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        try:
            found, _ = self._find_ability_with_patterns(["vanguard of the dark city"])
        except Exception:
            found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def get_vanguard_of_dark_city_selected_mode(self) -> str:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        return str(sr.get("vanguard_of_dark_city_selected_mode", "") or "").strip().lower()


    def vanguard_of_dark_city_mode_active(self, mode_key: str) -> bool:
        mode = str(mode_key or "").strip().lower()
        if not mode:
            return False
        if not self.has_vanguard_of_dark_city():
            return False
        return self.get_vanguard_of_dark_city_selected_mode() == mode


    def has_canticles_of_the_omnissiah(self) -> bool:
        cache_key = "canticles_of_the_omnissiah"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        try:
            found, _ = self._find_ability_with_patterns(["canticles of the omnissiah"])
        except Exception:
            found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def get_canticles_of_the_omnissiah_selected_mode(self) -> str:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        return str(sr.get("canticles_of_the_omnissiah_selected_mode", "") or "").strip().lower()


    def canticles_of_the_omnissiah_mode_active(self, mode_key: str) -> bool:
        mode = str(mode_key or "").strip().lower()
        if not mode:
            return False
        if not self.has_canticles_of_the_omnissiah():
            return False
        return self.get_canticles_of_the_omnissiah_selected_mode() == mode


    def get_temple_relics_source_unit(self):
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        try:
            from ...rules.space_marines_temple_relics import unit_has_temple_relics_ability
        except Exception:
            return None

        for member in sorted(list(members or []), key=lambda u: str(get_entity_id(u) or "")):
            if member is None or not bool(unit_has_temple_relics_ability(member)):
                continue
            contains_named = getattr(member, "_unit_contains_model_named", None)
            if callable(contains_named) and bool(contains_named("Grimaldus")):
                return member
        return None


    def has_temple_relics(self) -> bool:
        return self.get_temple_relics_source_unit() is not None


    def temple_relics_can_select(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None or self.get_temple_relics_source_unit() is None:
            return False
        contains_named = getattr(root, "_attached_unit_contains_model_named", None)
        return bool(callable(contains_named) and contains_named("Cenobyte Servitor"))


    def get_temple_relics_selected_mode(self) -> str:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        return str(sr.get("space_marines_temple_relics_selected_mode", "") or "").strip().lower()


    def temple_relics_mode_active(self, mode_key: str) -> bool:
        mode = str(mode_key or "").strip().lower()
        if not mode:
            return False
        return self.get_temple_relics_selected_mode() == mode


    def _unit_has_battle_protocols_ability_local(self) -> bool:
        for ability in list(getattr(self, "possible_abilities", []) or []):
            name = str(getattr(ability, "name", "") or "").replace("\u2019", "'").strip().lower()
            if name == "battle protocols":
                return True
        return False


    def _battle_protocols_unit_is_kastelan_robots(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        try:
            if bool(root.has_any_keyword("KASTELAN ROBOT")) or bool(root.has_any_keyword("KASTELAN ROBOTS")):
                return True
        except Exception:
            pass
        name = str(getattr(root, "name", "") or "").replace("\u2019", "'").strip().lower()
        return "kastelan robots" in name or "kastelan robot" in name


    def has_battle_protocols(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        cache_key = "battle_protocols"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))

        found = False
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            if bool(member._unit_has_battle_protocols_ability_local()):
                found = True
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)


    def battle_protocols_source_is_eligible(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if not bool(root.has_battle_protocols()):
            return False
        if not bool(root._battle_protocols_unit_is_kastelan_robots()):
            return False

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for member in list(members or []):
            if member is None:
                continue
            if not bool(member._unit_has_battle_protocols_ability_local()):
                continue
            if not bool(getattr(member, "is_attached_leader", False)):
                continue
            try:
                if member.get_attached_unit_root() is not root:
                    continue
            except Exception:
                continue
            alive_fn = getattr(member, "is_alive", None)
            if callable(alive_fn) and not bool(alive_fn()):
                continue
            return True
        return False


    def get_battle_protocols_selected_mode(self) -> str:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        return str(sr.get("battle_protocols_selected_mode", "") or "").strip().lower()


    def battle_protocols_mode_active(self, mode_key: str) -> bool:
        mode = str(mode_key or "").strip().lower()
        if not mode:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if not bool(root.has_battle_protocols()):
            return False
        return str(root.get_battle_protocols_selected_mode() or "") == mode


    def command_phase_sticky_objective_prerequisites_met(self) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return True
        required_mode = str(sr.get("sticky_objectives_requires_vanguard_mode", "") or "").strip().lower()
        if required_mode and not self.vanguard_of_dark_city_mode_active(required_mode):
            return False
        required_keyword = str(sr.get("sticky_objectives_requires_embarked_keyword", "") or "").strip()
        if required_keyword and not self._transport_has_embarked_keyword(required_keyword):
            return False
        return True


    def _command_phase_sticky_objective_rule_is_active(self, root, member, rule: dict[str, object]) -> bool:
        if not bool(rule.get("requires_bearer_leading", False)):
            return True
        return bool(getattr(member, "is_leader", False)) and getattr(member, "attached_to", None) is root


    def _iter_command_phase_sticky_objective_rules(self) -> list[tuple["Unit", dict[str, object]]]:
        root = self.get_attached_unit_root()
        members = sorted(
            list(root.get_attached_unit_members() or []),
            key=lambda unit: str(get_entity_id(unit) or ""),
        )
        entries: list[tuple["Unit", dict[str, object]]] = []
        seen: set[tuple[str, str, str, str, bool, bool]] = set()

        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}

            for raw_entry in list(sr.get("enhancement_sticky_objective_rules", []) or []):
                if not isinstance(raw_entry, dict):
                    continue
                entry = {
                    "source_scope": str(raw_entry.get("source_scope", "unit") or "unit").strip().lower(),
                    "source": str(raw_entry.get("source", "unit_sticky_objective") or "unit_sticky_objective").strip()
                    or "unit_sticky_objective",
                    "allow_embarked_transport": bool(raw_entry.get("allow_embarked_transport", False)),
                    "requires_bearer_leading": bool(raw_entry.get("requires_bearer_leading", False)),
                    "source_model_id": str(raw_entry.get("source_model_id", "") or "").strip(),
                }
                if entry["source_scope"] not in ("unit", "bearer"):
                    entry["source_scope"] = "unit"
                if not self._command_phase_sticky_objective_rule_is_active(root, member, entry):
                    continue
                dedupe_key = (
                    str(get_entity_id(member) or ""),
                    str(entry["source_scope"]),
                    str(entry["source_model_id"]),
                    str(entry["source"]).lower(),
                    bool(entry["allow_embarked_transport"]),
                    bool(entry["requires_bearer_leading"]),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                entries.append((member, entry))

            scan = member._command_phase_sticky_objective_scan_result()
            if not bool(scan.get("found", False)):
                continue
            entry = {
                "source_scope": "unit",
                "source": "unit_sticky_objective",
                "allow_embarked_transport": bool(scan.get("allow_embarked_transport", False)),
                "requires_bearer_leading": bool(scan.get("requires_leading_unit", False)),
                "source_model_id": "",
            }
            if not self._command_phase_sticky_objective_rule_is_active(root, member, entry):
                continue
            dedupe_key = (
                str(get_entity_id(member) or ""),
                "unit",
                "",
                "unit_sticky_objective",
                bool(entry["allow_embarked_transport"]),
                bool(entry["requires_bearer_leading"]),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            entries.append((member, entry))

        return entries


    def _command_phase_sticky_objective_rule_in_range(self, objective_point, *, member, rule: dict[str, object]) -> bool:
        root = self.get_attached_unit_root()
        if str(rule.get("source_scope", "unit") or "unit").strip().lower() == "bearer":
            source_model_id = str(rule.get("source_model_id", "") or "").strip()
            if not source_model_id:
                return False
            source_model = root.get_attached_unit_model_by_id(source_model_id)
            if source_model is None:
                return False
            return bool(root.is_model_within_objective_range(source_model, objective_point))

        if root.is_within_objective_range(objective_point):
            return True
        if not bool(rule.get("allow_embarked_transport", False)):
            return False
        transport = getattr(root, "embarked_in", None)
        return bool(transport is not None and transport.is_within_objective_range(objective_point))


    def command_phase_sticky_objective_claim_rule(self, objective_point) -> dict[str, object] | None:
        root = self.get_attached_unit_root()
        if root is not self:
            return root.command_phase_sticky_objective_claim_rule(objective_point)
        if objective_point is None:
            return None
        for member, rule in root._iter_command_phase_sticky_objective_rules():
            if not member.command_phase_sticky_objective_prerequisites_met():
                continue
            if root._command_phase_sticky_objective_rule_in_range(objective_point, member=member, rule=rule):
                return dict(rule)
        return None


    def visions_of_butchery_attacks_bonus_for_weapon(self, weapon_name: str) -> int:
        if not self.vanguard_of_dark_city_mode_active("visions_of_butchery"):
            return 0
        weapon_norm = re.sub(r"[^a-z0-9]+", " ", str(weapon_name or "").lower()).strip()
        if not weapon_norm:
            return 0
        if "bladevane" not in weapon_norm and "chainsnare" not in weapon_norm:
            return 0
        return max(0, int(self._transport_embarked_models_with_keyword_count("WRACKS")))


    def archons_will_effects_active(self, *, game=None, game_map=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        objective_id = str(sr.get("archons_will_objective_id", "") or "").strip()
        if not objective_id:
            return False
        if self.is_battle_shocked():
            return False

        objective = None
        if game_map is None and game is None:
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)

        for obj in list(getattr(game_map, "objectives", []) or []):
            if str(get_entity_id(obj) or "") == objective_id:
                objective = obj
                break
        if objective is None:
            for obj in list(getattr(game, "objectives", []) or []):
                if str(get_entity_id(obj) or "") == objective_id:
                    objective = obj
                    break
        if objective is None:
            return False

        loc = getattr(objective, "location", None)
        if loc is None or bool(getattr(loc, "removed", False)):
            return False
        return bool(self.is_within_objective_range(loc))


    def _selected_model_objective_effects_active(
        self,
        *,
        objective_id_key: str,
        source_model_id_key: str,
        model=None,
        game=None,
        game_map=None,
    ) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        objective_id = str(sr.get(objective_id_key, "") or "").strip()
        if not objective_id:
            return False

        source_model_id = str(sr.get(source_model_id_key, "") or "").strip()
        if model is not None and source_model_id:
            model_id = str(get_entity_id(model) or "").strip()
            if model_id and model_id != source_model_id:
                return False

        try:
            if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                return False
            if not bool(getattr(root, "deployed", True)):
                return False
        except Exception:
            return False
        try:
            if bool(getattr(root, "is_embarked", False)) or root.is_in_reserves():
                return False
        except Exception:
            pass

        objective = None
        if game_map is None and game is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        for obj in list(getattr(game_map, "objectives", []) or []):
            if str(get_entity_id(obj) or "") == objective_id:
                objective = obj
                break
        if objective is None:
            for obj in list(getattr(game, "objectives", []) or []):
                if str(get_entity_id(obj) or "") == objective_id:
                    objective = obj
                    break
        if objective is None:
            return False

        loc = getattr(objective, "location", None)
        if loc is None or bool(getattr(loc, "removed", False)):
            return False

        source_model = None
        try:
            models = list(root.get_models_for_collision() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for candidate in list(models or []):
            if candidate is None:
                continue
            try:
                if not bool(getattr(candidate, "is_alive", True)):
                    continue
            except Exception:
                pass
            candidate_id = str(get_entity_id(candidate) or "").strip()
            if source_model_id and candidate_id and candidate_id != source_model_id:
                continue
            source_model = candidate
            break
        if source_model is None and model is not None:
            source_model = model
        if source_model is None:
            return False

        try:
            from shapely.geometry import Point as _ShPoint

            area = _ShPoint(float(getattr(loc, "x", 0.0)), float(getattr(loc, "y", 0.0))).buffer(
                float(getattr(loc, "control_radius", 0.0) or 0.0)
            )
            base = source_model.model_base.get_base_shape()
            if base.intersects(area):
                return True
        except Exception:
            pass

        try:
            sx, sy, _sz, _facing = source_model.get_location()
        except Exception:
            return False
        try:
            dx = float(sx) - float(getattr(loc, "x", 0.0))
            dy = float(sy) - float(getattr(loc, "y", 0.0))
            radius = float(getattr(loc, "control_radius", 0.0) or 0.0)
            base_r = float(getattr(source_model.model_base, "get_radius", lambda: 1.0)())
            return (dx * dx + dy * dy) ** 0.5 <= (radius + base_r)
        except Exception:
            return False


    def singular_purpose_objective_effects_active(self, *, model=None, game=None, game_map=None) -> bool:
        """
        TYRANIDS: Singular Purpose (objective branch).
        Active while the selected source model is within range of the selected objective marker.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        mode = str(sr.get("singular_purpose_mode", "") or "").strip().lower()
        if mode != "objective_marker":
            return False
        return self._selected_model_objective_effects_active(
            objective_id_key="singular_purpose_objective_id",
            source_model_id_key="singular_purpose_source_model_id",
            model=model,
            game=game,
            game_map=game_map,
        )


    def seeker_of_lost_relics_effects_active(self, *, model=None, game=None, game_map=None) -> bool:
        """
        Space Marines: Seeker of the Unfound.
        Active while the selected source model is within range of its chosen objective marker.
        """
        return self._selected_model_objective_effects_active(
            objective_id_key="seeker_of_lost_relics_objective_id",
            source_model_id_key="seeker_of_lost_relics_source_model_id",
            model=model,
            game=game,
            game_map=game_map,
        )


    def _has_aethersails(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "aethersails_ability"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        for name, desc in root._iter_ability_entries_for_rules(model=None):
            text = f"{name or ''} {desc or ''}".lower()
            if "aethersails" in text:
                found = True
                break
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)


    def _aethersails_reroll_active(self) -> bool:
        if not self._has_aethersails():
            return False
        return bool(self._transport_has_embarked_keyword("DRUKHARI"))


    def has_dance_of_death(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "dance_of_death"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        try:
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
                except Exception:
                    name = ""
                    desc = ""
                text = f"{name or ''} {desc or ''}".lower()
                if "dance of death" in text:
                    found = True
                    break
        except Exception:
            found = False
        if not found:
            for name, desc in root._iter_ability_entries_for_rules(model=None):
                text = f"{name or ''} {desc or ''}".lower()
                if "dance of death" in text:
                    found = True
                    break
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)


    def has_bladeguard_stance(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "bladeguard_stance"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        for name, desc in root._iter_ability_entries_for_rules(model=None):
            text = f"{name or ''} {desc or ''}".lower()
            if "swords of the chapter" in text and "shields of the chapter" in text:
                found = True
                break
            if "bladeguard" in text and "re-roll a saving throw of 1" in text:
                found = True
                break
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)


    def has_adaptive_instincts(self) -> bool:
        root_fn = getattr(self, "get_attached_unit_root", None)
        root = root_fn() if callable(root_fn) else self
        cache_key = "adaptive_instincts"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        for name, desc in root._iter_ability_entries_for_rules(model=None):
            text = f"{name or ''} {desc or ''}".lower()
            if "adaptive instincts" in text:
                found = True
                break
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)


    def _iter_attached_model_specific_ability_entries(self, root, model):
        """Resolve model-specific ability text via each model's owning unit."""
        if model is None:
            return
        model_unit = getattr(model, "parent_unit", None) or root
        iter_fn = getattr(model_unit, "_iter_model_specific_ability_entries", None)
        if callable(iter_fn):
            for name, desc in iter_fn(model):
                yield name, desc
            return
        fallback_fn = getattr(root, "_iter_model_specific_ability_entries", None)
        if callable(fallback_fn):
            for name, desc in fallback_fn(model):
                yield name, desc


    def iter_cruel_amusement_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                if "cruel amusement" not in str(name or text_src).lower():
                    normalized = root._normalize_rules_text(text_src)
                    if not normalized:
                        continue
                    normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                    normalized = normalized.lower()
                    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                    normalized = re.sub(r"\s+", " ", normalized).strip()
                    if not root._CRUEL_AMUSEMENT_RE.fullmatch(normalized):
                        continue
                weapon_name = "shrieker cannon"
                try:
                    normalized = root._normalize_rules_text(text_src)
                    normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                    normalized = re.sub(r"\s+", " ", normalized).strip()
                    m = root._CRUEL_AMUSEMENT_RE.fullmatch(normalized)
                    if m:
                        weapon_name = str(m.group("weapon") or weapon_name).strip() or weapon_name
                except Exception:
                    weapon_name = "shrieker cannon"
                results.append(
                    {
                        "model": model,
                        "weapon_name": weapon_name,
                        "source": str(name or "Cruel Amusement").strip() or "Cruel Amusement",
                    }
                )
                break
        return results


    def iter_master_of_magicks_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "master of magicks" not in str(name or text_src).lower():
                    if not root._MASTER_OF_MAGICKS_RE.fullmatch(normalized):
                        continue
                weapon_name = "bolt of change"
                try:
                    m = root._MASTER_OF_MAGICKS_RE.fullmatch(normalized)
                    if m:
                        weapon_name = str(m.group("weapon") or weapon_name).strip() or weapon_name
                except Exception:
                    weapon_name = "bolt of change"
                results.append(
                    {
                        "model": model,
                        "weapon_name": weapon_name,
                        "source": str(name or "Master of Magicks").strip() or "Master of Magicks",
                    }
                )
                break
        return results


    def iter_harbinger_of_death_models(self) -> list[dict]:
        """
        Return models with Harbinger of Death (hellforged weapon keyword choice in Fight phase).
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "harbinger of death" not in str(name or text_src).lower():
                    if not root._HARBINGER_OF_DEATH_RE.fullmatch(normalized):
                        continue
                results.append(
                    {
                        "model": model,
                        "weapon_name": "hellforged",
                        "source": str(name or "Harbinger of Death").strip() or "Harbinger of Death",
                    }
                )
                break
        return results


    def get_embodied_prophecy_source(self) -> str:
        """
        Return the source name for Embodied Prophecy on this attached unit root, if present.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "embodied_prophecy_source"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return str(cache.get(cache_key) or "")

        source = ""
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = member._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                name_norm = str(name or "").strip().lower()
                if "embodied prophecy" not in name_norm:
                    if not root._EMBODIED_PROPHECY_RE.fullmatch(normalized):
                        continue
                source = str(name or "Embodied Prophecy").strip() or "Embodied Prophecy"
                break
            if source:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = source
        return str(source or "")


    def get_extremis_trigger_word_source(self) -> str:
        """
        Return the source name for Extremis Trigger Word on this attached unit root, if present.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "extremis_trigger_word_source"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return str(cache.get(cache_key) or "")

        source = ""
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                name_norm = str(name or "").strip().lower()
                text_src = member._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "extremis trigger word" not in name_norm:
                    if "extremis trigger word" not in normalized:
                        continue
                    if "selected to fight" not in normalized:
                        continue
                    if "arco flails equipped by models in this unit" not in normalized:
                        continue
                    if "attacks characteristic of 6" not in normalized:
                        continue
                    if "hazardous" not in normalized:
                        continue
                source = str(name or "Extremis Trigger Word").strip() or "Extremis Trigger Word"
                break
            if source:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = source
        return str(source or "")


    def apply_extremis_trigger_word_effect(
        self,
        *,
        weapon_name: str = "arco-flails",
        attacks_value: int = 6,
        source: str = "",
        game=None,
        expires_phase: str = "FIGHT_PHASE",
    ) -> bool:
        """
        Apply Extremis Trigger Word to this attached unit:
        - set arco-flails Attacks to a fixed value
        - grant [HAZARDOUS] to those weapons
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        source_name = str(source or "").strip()
        if not source_name:
            source_name = str(root.get_extremis_trigger_word_source() or "").strip()
        if not source_name:
            return False
        try:
            fixed_attacks = int(attacks_value or 0)
        except Exception:
            fixed_attacks = 0
        if fixed_attacks <= 0:
            return False
        target_weapon = str(weapon_name or "").strip() or "arco-flails"
        phase_name = str(expires_phase or "FIGHT_PHASE").strip().upper() or "FIGHT_PHASE"

        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        if not models:
            models = list(getattr(root, "models", []) or [])

        applied = False
        for model in list(models or []):
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if not model_id:
                continue
            if hasattr(model, "set_temporary_weapon_attacks_override"):
                model.set_temporary_weapon_attacks_override(
                    key=f"extremis_trigger_word:{model_id}:attacks",
                    weapon_name=target_weapon,
                    attacks_value=int(fixed_attacks),
                    source=source_name,
                    expires_phase=phase_name,
                )
            if hasattr(model, "set_temporary_weapon_keyword_bonuses"):
                model.set_temporary_weapon_keyword_bonuses(
                    key=f"extremis_trigger_word:{model_id}:keywords",
                    weapon_name=target_weapon,
                    keywords=["HAZARDOUS"],
                    source=source_name,
                    expires_phase=phase_name,
                    attack_type="melee",
                )
            applied = True

        if not applied:
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["extremis_trigger_word_active"] = True
        sr["extremis_trigger_word_source"] = source_name
        sr["extremis_trigger_word_weapon_name"] = target_weapon
        sr["extremis_trigger_word_attacks_value"] = int(fixed_attacks)
        sr["extremis_trigger_word_expires_phase"] = phase_name

        game_obj = game
        if game_obj is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            player = getattr(army, "player", None) if army is not None else None
            game_obj = getattr(player, "game", None) if player is not None else None
        if game_obj is not None:
            try:
                sr["extremis_trigger_word_turn"] = int(getattr(game_obj, "turn", 0) or 0)
            except Exception:
                sr["extremis_trigger_word_turn"] = 0
            try:
                current_player = getattr(game_obj, "get_current_player", lambda: None)()
                owner_id = str(getattr(current_player, "id", "") or "")
            except Exception:
                owner_id = ""
            if owner_id:
                sr["extremis_trigger_word_owner"] = owner_id
        root.special_rules = sr
        return True


    def clear_embodied_prophecy_effect(self) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "embodied_prophecy_lethal_hits_active",
            "embodied_prophecy_sustained_hits_value",
            "embodied_prophecy_expires_phase",
            "embodied_prophecy_turn",
            "embodied_prophecy_turn_owner",
            "embodied_prophecy_source",
        ):
            sr.pop(key, None)
        root.special_rules = sr


    def apply_embodied_prophecy_effect(
        self,
        *,
        lethal_hits: bool = False,
        sustained_hits_value: int = 0,
        source: str = "",
        game=None,
        expires_phase: str = "FIGHT_PHASE",
    ) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        source_name = str(source or "").strip()
        if not source_name:
            source_name = str(root.get_embodied_prophecy_source() or "").strip()
        if not source_name:
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        for key in (
            "embodied_prophecy_lethal_hits_active",
            "embodied_prophecy_sustained_hits_value",
            "embodied_prophecy_expires_phase",
            "embodied_prophecy_turn",
            "embodied_prophecy_turn_owner",
            "embodied_prophecy_source",
        ):
            sr.pop(key, None)

        try:
            sustained_value = int(sustained_hits_value or 0)
        except Exception:
            sustained_value = 0
        sustained_value = max(0, int(sustained_value))
        if not bool(lethal_hits) and sustained_value <= 0:
            root.special_rules = sr
            return True

        game_obj = game
        if game_obj is None:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            player = getattr(army, "player", None) if army is not None else None
            game_obj = getattr(player, "game", None) if player is not None else None
        try:
            turn_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        except Exception:
            turn_now = 0

        owner_id = ""
        if game_obj is not None:
            current_player = getattr(game_obj, "get_current_player", lambda: None)()
            owner_id = str(getattr(current_player, "id", "") or "")
        if not owner_id:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            owner_id = str(getattr(getattr(army, "player", None), "id", "") or "")

        sr["embodied_prophecy_lethal_hits_active"] = bool(lethal_hits)
        sr["embodied_prophecy_sustained_hits_value"] = int(sustained_value)
        sr["embodied_prophecy_expires_phase"] = str(expires_phase or "FIGHT_PHASE").strip().upper() or "FIGHT_PHASE"
        sr["embodied_prophecy_turn"] = int(turn_now or 0)
        sr["embodied_prophecy_turn_owner"] = owner_id
        sr["embodied_prophecy_source"] = source_name
        root.special_rules = sr
        return True


    def iter_cry_of_the_wind_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not root._CRY_OF_THE_WIND_RE.fullmatch(normalized) and "cry of the wind" not in normalized:
                    continue
                results.append(
                    {
                        "model": model,
                        "source": str(name or "Cry of the Wind").strip() or "Cry of the Wind",
                    }
                )
                break
        return results


    def iter_hysterical_frenzy_models(self) -> list[dict]:
        """
        Return Psyker models with the reactive Hysterical Frenzy (Psychic) ability
        (once per Fight phase, within range of a targeted SLAANESH unit).
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                name_low = str(name or text_src).lower()
                if "hysterical frenzy" not in name_low:
                    if not root._HYSTERICAL_FRENZY_RE.fullmatch(normalized):
                        continue
                if "once per fight phase" not in normalized:
                    continue
                range_value = 6
                try:
                    m = root._HYSTERICAL_FRENZY_RE.fullmatch(normalized)
                    if m:
                        range_value = int(m.group("range") or 6)
                    else:
                        m = re.search(r"within (\d+)", normalized)
                        if m:
                            range_value = int(m.group(1) or 6)
                except Exception:
                    range_value = 6
                results.append(
                    {
                        "model": model,
                        "range": int(range_value),
                        "source": str(name or "Hysterical Frenzy").strip() or "Hysterical Frenzy",
                    }
                )
                break
        return results


    def iter_sacrificial_dagger_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                name_low = str(name or text_src).lower()
                normalized = root._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "sacrificial dagger" not in name_low:
                    if not root._SACRIFICIAL_DAGGER_RE.fullmatch(normalized):
                        continue
                results.append(
                    {
                        "model": model,
                        "source": str(name or "Sacrificial Dagger").strip() or "Sacrificial Dagger",
                    }
                )
                break
        return results


    def iter_sacrificial_blessing_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                name_low = str(name or text_src).lower()
                normalized = root._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "sacrificial blessing" not in name_low:
                    if not root._SACRIFICIAL_BLESSING_RE.fullmatch(normalized):
                        continue
                results.append(
                    {
                        "model": model,
                        "source": str(name or "Sacrificial Blessing").strip() or "Sacrificial Blessing",
                    }
                )
                break
        return results


    def iter_twisted_sorceries_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                name_low = str(name or text_src).lower()
                normalized = root._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "twisted sorceries" not in name_low:
                    if not root._TWISTED_SORCERIES_RE.fullmatch(normalized):
                        continue
                results.append(
                    {
                        "model": model,
                        "source": str(name or "Twisted Sorceries").strip() or "Twisted Sorceries",
                    }
                )
                break
        return results


    def iter_gift_of_chaos_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                name_low = str(name or text_src).lower()
                normalized = root._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "gift of chaos" not in name_low:
                    if not root._GIFT_OF_CHAOS_RE.fullmatch(normalized):
                        continue
                results.append(
                    {
                        "model": model,
                        "source": str(name or "Gift of Chaos").strip() or "Gift of Chaos",
                    }
                )
                break
        return results


    def _extract_cloudstrider_deep_strike_rule(self, *, name: str = "", description: str = "") -> Optional[dict]:
        text = self._normalize_rules_text(description or name or "")
        if not text:
            return None
        normalized = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if "deep strike" not in normalized:
            return None
        if "not eligible to declare a charge" not in normalized and "not eligible to charge" not in normalized:
            return None
        match = re.search(r"\bmore than\s+(?P<distance>\d+(?:\.\d+)?)\b", normalized)
        if match is None:
            return None
        try:
            min_distance = float(match.group("distance"))
        except (TypeError, ValueError):
            return None
        if min_distance <= 0.0:
            return None
        source = str(name or "Cloudstrider").strip() or "Cloudstrider"
        return {
            "source": source,
            "deep_strike_min_distance": float(min_distance),
        }


    def get_cloudstrider_deep_strike_rule(self) -> Optional[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "cloudstrider_deep_strike_rule"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            cached = cache.get(cache_key)
            return cached if isinstance(cached, dict) else None
        rule = None
        for ab, _leader in root._iter_attached_leader_leading_abilities():
            try:
                name = str(getattr(ab, "name", "") or "")
                desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            rule = root._extract_cloudstrider_deep_strike_rule(name=name, description=desc)
            if rule is not None:
                break
        if rule is None:
            for name, desc in root._iter_ability_entries_for_rules(model=None):
                rule = root._extract_cloudstrider_deep_strike_rule(
                    name=str(name or ""),
                    description=str(desc or name or ""),
                )
                if rule is not None:
                    break
        if rule is None:
            fallback = ""
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    name = str(getattr(ab, "name", "") or "")
                except Exception:
                    name = ""
                if name.strip().lower() == "cloudstrider":
                    fallback = name or "Cloudstrider"
                    break
            if not fallback:
                for name, _desc in root._iter_ability_entries_for_rules(model=None):
                    if str(name or "").strip().lower() == "cloudstrider":
                        fallback = str(name or "Cloudstrider").strip() or "Cloudstrider"
                        break
            if fallback:
                rule = {
                    "source": fallback,
                    "deep_strike_min_distance": 6.0,
                }
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule if isinstance(rule, dict) else None


    def get_cloudstrider_deep_strike_source(self) -> str:
        rule = self.get_cloudstrider_deep_strike_rule()
        if not isinstance(rule, dict):
            return ""
        source = str(rule.get("source", "") or "").strip()
        return str(source or "")


    def get_opponent_turn_friendly_unit_destroyed_reposition_ability(self):
        """
        Return ability info dict for opponent-turn reposition after a friendly unit is destroyed.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "opponent_turn_friendly_unit_destroyed_reposition_ability"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        ability = None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            try:
                ability = member._scan_opponent_turn_friendly_unit_destroyed_reposition_ability()
            except Exception:
                ability = None
            if ability:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = ability
        return ability


    def get_friendly_destroyed_model_weapon_attacks_override_ability(self):
        """
        Return ability info dict for model-destruction triggered weapon attacks overrides.
        """
        try:
            root = self.get_attached_unit_root()
        except (AttributeError, TypeError, ValueError):
            root = self
        cache_key = "friendly_destroyed_model_weapon_attacks_override_ability"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        ability = None
        try:
            members = list(root.get_attached_unit_members() or [])
        except (AttributeError, TypeError, ValueError):
            members = [root]
        for member in members:
            try:
                ability = member._scan_friendly_destroyed_model_weapon_attacks_override_ability()
            except (AttributeError, TypeError, ValueError):
                ability = None
            if ability:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = ability
        return ability


    def get_transport_reactive_disembark_ability(self):
        """
        Return ability info dict for reactive transport disembark triggers, or None if not available.
        """
        cache_key = "transport_reactive_disembark_ability"
        cache = getattr(self, "_ability_cache", {})
        if cache_key in cache:
            cached = cache.get(cache_key)
            if cached is not None or not bool(getattr(self, "is_transport", False)):
                return cached

        ability = None
        if bool(getattr(self, "is_transport", False)):
            for ab in self._iter_active_abilities():
                parsed = self._parse_transport_reactive_disembark_ability(ab)
                if parsed is not None:
                    ability = parsed
                    break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability


    def attached_unit_has_icon_of_khorne(self) -> bool:
        """Attached unit eligibility: true if any attached member has Icon of Khorne."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_icon_of_khorne():
                    return True
            except Exception:
                continue
        return False


    def attached_unit_has_command_phase_sticky_objective(self) -> bool:
        """Attached unit eligibility: true if any attached member has sticky objective ability."""
        return bool(self._iter_command_phase_sticky_objective_rules())


    def attached_unit_has_kill_team(self) -> bool:
        """Attached unit eligibility: true if any attached member has the Kill Team ability."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_kill_team():
                    return True
            except Exception:
                continue
        return False


    def attached_unit_has_martial_katah(self) -> bool:
        """Attached unit eligibility: true if any attached member has Martial Ka'tah."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_martial_katah():
                    return True
            except Exception:
                continue
        return False


    def leading_unit_weapons_have_lethal_hits(self, attack_type: Optional[str] = None) -> bool:
        """
        Leading-only ability: while a leader is attached, weapons in that unit gain [LETHAL HITS].

        attack_type: "melee", "ranged", or None to check any weapon type.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        def _resolve(flags: dict, attack_kind: Optional[str]) -> bool:
            kind = str(attack_kind or "").strip().lower()
            if kind == "melee":
                return bool(flags.get("any")) or bool(flags.get("melee"))
            if kind == "ranged":
                return bool(flags.get("any")) or bool(flags.get("ranged"))
            return bool(flags.get("any")) or bool(flags.get("melee")) or bool(flags.get("ranged"))

        cache_key = "leading_unit_lethal_hits"
        cache = getattr(root, "_ability_cache", {})
        if cache_key in cache:
            cached = cache.get(cache_key)
            if isinstance(cached, dict):
                return _resolve(cached, attack_type)
            return bool(cached)

        flags = {"any": False, "melee": False, "ranged": False}
        lethal_any_re = re.compile(
            r"weapons equipped by models in that unit have the \[?lethal hits\]? ability",
            re.IGNORECASE,
        )
        lethal_melee_re = re.compile(
            r"melee weapons equipped by models in that unit have the \[?lethal hits\]? ability",
            re.IGNORECASE,
        )
        lethal_ranged_re = re.compile(
            r"ranged weapons equipped by models in that unit have the \[?lethal hits\]? ability",
            re.IGNORECASE,
        )
        for ab, _leader in root._iter_attached_leader_leading_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            text = text.replace("\u2019", "'").replace("\u0192?T", "'")
            try:
                rest = self._LEADING_ABILITY_PREFIX_RE.sub("", text, count=1).strip(" ,:;-")
            except Exception:
                rest = text
            if lethal_melee_re.search(rest):
                flags["melee"] = True
            elif lethal_ranged_re.search(rest):
                flags["ranged"] = True
            elif lethal_any_re.search(rest):
                flags["any"] = True
            if flags["any"]:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = flags
        return _resolve(flags, attack_type)


    def leading_unit_melta_range_bonus(self) -> int:
        """
        Leading-only ability: while a leader is attached, Melta weapon range in that unit is increased.
        Returns the summed range bonus (in inches).
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        cache_key = "leading_unit_melta_range_bonus"
        cache = getattr(root, "_ability_cache", {})
        if cache_key in cache:
            try:
                return int(cache.get(cache_key) or 0)
            except Exception:
                return 0

        total_bonus = 0
        melta_range_re = re.compile(
            r"add\s+(?P<val>\d+)\s*\"?\s+to\s+the\s+range\s+characteristic\s+of\s+melta\s+weapons?\s+"
            r"equipped\s+by\s+models\s+in\s+(?:the\s+bearer'?s|that|this)\s+unit",
            re.IGNORECASE,
        )
        for ab, _leader in root._iter_attached_leader_leading_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            text = text.replace("\u2019", "'").replace("\u0192?T", "'")
            try:
                rest = self._LEADING_ABILITY_PREFIX_RE.sub("", text, count=1).strip(" ,:;-")
            except Exception:
                rest = text
            m = melta_range_re.search(rest)
            if not m:
                continue
            try:
                total_bonus += int(m.group("val"))
            except Exception:
                continue

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = int(total_bonus)
        return int(total_bonus)


    def _enhancement_local_passive_entity_id(self, entity) -> str:
        try:
            resolved = get_entity_id(entity)
        except ValueError:
            resolved = getattr(entity, "id", getattr(entity, "_id", ""))
        return str(resolved or "")
