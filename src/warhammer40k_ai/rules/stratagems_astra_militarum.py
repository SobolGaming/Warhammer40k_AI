from __future__ import annotations

from typing import Any, Optional

import logging

from ..utility.dice import get_roll
from ..utility.entity_ids import maybe_entity_id

logger = logging.getLogger(__name__)


class AstraMilitarumStratagemMixin:
    @staticmethod
    def _am_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _am_sort_key(unit: Any) -> str:
        return str(maybe_entity_id(unit) or "")

    def _get_astra_militarum_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "astra_militarum_detachments", None) if army is not None else None

    def _is_grizzled_company(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_grizzled_company", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_bridgehead_strike(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_bridgehead_strike", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_combined_arms(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_combined_arms", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_armoured_infantry(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_armoured_infantry", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_hammer_of_the_emperor(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_hammer_of_the_emperor", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_mechanised_assault(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_mechanised_assault", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_recon_element(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_recon_element", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_siege_regiment(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_siege_regiment", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_astra_militarum_unit(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "unit_is_astra_militarum", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        return bool(has_any_keyword("ASTRA MILITARUM")) if callable(has_any_keyword) else False

    def _is_officer_unit(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "unit_is_officer", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        return bool(has_any_keyword("OFFICER")) if callable(has_any_keyword) else False

    @staticmethod
    def _am_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _am_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _am_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "is_in_reserves", False))

    @staticmethod
    def _am_has_keyword(unit: Any, keyword: str) -> bool:
        if unit is None:
            return False
        key = str(keyword or "").strip()
        if not key:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            return bool(has_keyword(key))
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword(key))
        return False

    @staticmethod
    def _am_has_deep_strike(unit: Any) -> bool:
        if unit is None:
            return False
        has_deep_strike = getattr(unit, "has_deep_strike", None)
        return bool(has_deep_strike()) if callable(has_deep_strike) else False

    @staticmethod
    def _am_name_matches(unit: Any, phrase: str) -> bool:
        name = str(getattr(unit, "name", "") or "").strip().lower()
        token = str(phrase or "").strip().lower()
        return bool(name and token and token in name)

    def _am_on_battlefield(self, unit: Any) -> bool:
        if not self._am_is_alive(unit):
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if self._am_is_in_reserves(unit):
            return False
        if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
            return False
        return True

    def _am_army_roots(self) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._am_root(unit)
            if root is None:
                continue
            uid = self._am_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _am_is_in_engagement_range(self, unit: Any) -> bool:
        root = self._am_root(unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if root is None or game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement_range):
            return False
        for enemy in list(get_enemy_units(root) or []):
            if enemy is None or not self._am_is_alive(enemy):
                continue
            if not bool(getattr(enemy, "deployed", True)):
                continue
            if self._am_is_in_reserves(enemy):
                continue
            if bool(is_within_engagement_range(root, enemy)):
                return True
        return False

    def _am_is_visible_to_unit(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._am_root(source_unit)
        target_root = self._am_root(target_unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if source_root is None or target_root is None or game_map is None:
            return False
        has_los = getattr(source_root, "_has_line_of_sight_to_target", None)
        if not callable(has_los):
            return True
        for model in list(getattr(source_root, "models", []) or []):
            if not bool(getattr(model, "is_alive", False)):
                continue
            if bool(has_los(model, target_root, game_map)):
                return True
        return False

    def _am_attached_has_order_key(self, unit: Any, order_key: str) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        key = str(order_key or "").strip().upper()
        if not key:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        checker = getattr(voice, "_attached_unit_has_order_key", None)
        if callable(checker):
            return bool(checker(root, key))
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            active = str(sr.get("voice_of_command_order_key", "") or "").strip().upper()
            if active == key:
                return True
        return False

    def _am_attached_has_any_order(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        checker = getattr(voice, "attached_unit_has_any_order", None) if voice is not None else None
        if callable(checker):
            return bool(checker(root))
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if str(sr.get("voice_of_command_order_key", "") or "").strip():
                return True
        return False

    def _am_within_any_objective_range(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        checker = getattr(root, "is_within_any_objective_range", None)
        if callable(checker):
            return bool(checker(game_map=game_map))
        return False

    def _am_within_controlled_objective_range(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        checker = getattr(root, "_within_controlled_objective_range", None)
        if callable(checker):
            return bool(checker(game_map=game_map))
        return False

    def _am_battlefield_units(
        self,
        *,
        require_infantry: bool = False,
        require_officer: bool = False,
        require_not_shot: bool = False,
        require_order_key: str = "",
        require_any_order: bool = False,
        require_within_objective: bool = False,
        require_within_controlled_objective: bool = False,
        require_regiment: bool = False,
        require_squadron: bool = False,
        require_vehicle: bool = False,
    ) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._am_root(unit)
            if root is None:
                continue
            uid = self._am_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if require_officer and not self._is_officer_unit(root):
                continue
            if require_infantry:
                has_keyword = getattr(root, "has_keyword", None)
                if not callable(has_keyword) or not bool(has_keyword("INFANTRY")):
                    continue
            if require_regiment and not self._am_has_keyword(root, "REGIMENT"):
                continue
            if require_squadron and not self._am_has_keyword(root, "SQUADRON"):
                continue
            if require_vehicle and not self._am_has_keyword(root, "VEHICLE"):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_order_key and not self._am_attached_has_order_key(root, require_order_key):
                continue
            if require_any_order and not self._am_attached_has_any_order(root):
                continue
            if require_within_objective and not self._am_within_any_objective_range(root):
                continue
            if require_within_controlled_objective and not self._am_within_controlled_objective_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _grizzled_mordian_minute_candidates(self) -> list[Any]:
        return self._am_battlefield_units(
            require_infantry=True,
            require_not_shot=True,
            require_order_key="FIRST_RANK_FIRE",
        )

    def _grizzled_purging_fire_candidates(self) -> list[Any]:
        return self._am_battlefield_units(
            require_not_shot=True,
            require_any_order=True,
            require_within_objective=True,
        )

    def _grizzled_veteran_sharpshooters_candidates(self) -> list[Any]:
        return self._am_battlefield_units(require_not_shot=True)

    def _grizzled_no_retreat_candidates(self) -> list[Any]:
        return self._am_battlefield_units(
            require_order_key="DUTY_HONOUR",
            require_within_controlled_objective=True,
        )

    def _grizzled_snap_to_it_officer_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_grizzled_company():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        if voice is None:
            return []
        getter = getattr(voice, "get_eligible_officers", None)
        if not callable(getter):
            return []
        officers = list(
            getter(
                game=self.game,
                player=self.player,
                phase_name=str(phase_name or "").strip().upper(),
                trigger="snap_to_it",
            )
            or []
        )
        out: list[Any] = []
        seen: set[str] = set()
        for unit in officers:
            root = self._am_root(unit)
            if root is None:
                continue
            uid = self._am_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root) or not self._is_officer_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _am_can_use_grizzled_snap_to_it_tool_action(self, kwargs: dict[str, Any]) -> bool:
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        if not phase_name:
            return False
        officer_candidates = self._grizzled_snap_to_it_officer_candidates(phase_name=phase_name)
        if not officer_candidates:
            return False

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        if voice is None:
            return False

        officer = (
            kwargs.get("officer_unit")
            or kwargs.get("officer")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        target_unit = (
            kwargs.get("order_target_unit")
            or kwargs.get("order_target")
            or kwargs.get("target_unit")
        )
        order_key = str(kwargs.get("order_key") or kwargs.get("order") or "").strip().upper()
        if officer is not None and target_unit is not None and order_key:
            officer_root = self._am_root(officer)
            target_root = self._am_root(target_unit)
            if officer_root is None or target_root is None:
                return False
            if officer_root not in officer_candidates:
                return False
            available_getter = getattr(voice, "get_available_orders", None)
            if callable(available_getter):
                order_keys = {
                    str(getattr(order, "key", order) or "").strip().upper()
                    for order in list(available_getter(officer_root) or [])
                }
                if order_keys and order_key not in order_keys:
                    return False
            target_getter = getattr(voice, "get_eligible_targets", None)
            if callable(target_getter):
                eligible_targets = list(target_getter(officer_root, game=self.game, order_key=order_key) or [])
                if target_root not in eligible_targets:
                    return False
            return True

        has_control = getattr(self.player, "has_control", None)
        if not (callable(has_control) and bool(has_control())):
            return False
        return self._am_has_voice_prompt_subscriber()

    def _grizzled_no_retreat_objective_candidates(self, unit: Any) -> list[Any]:
        if unit is None:
            return []
        helper = getattr(self, "_corrupting_taint_objective_candidates", None)
        if callable(helper):
            candidates = list(helper(unit) or [])
            if candidates:
                return sorted(candidates, key=self._am_sort_key)
        if self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        root = self._am_root(unit)
        if game_map is None or root is None:
            return []
        out = []
        for obj in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(obj, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            if getattr(loc, "controlling_player", None) is not self.player:
                continue
            if not bool(root.is_within_objective_range(loc)):
                continue
            out.append(obj)
        return sorted(out, key=self._am_sort_key)

    def _am_pending_choose_quarry_request(self, *, ability: str, **match_context: Any) -> bool:
        game = getattr(self, "game", None)
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != str(DECISION_CHOOSE_QUARRY):
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != str(ability or ""):
                continue
            matches = True
            for key, value in dict(match_context or {}).items():
                if isinstance(value, (list, tuple, set)):
                    expected = [str(item or "").strip() for item in list(value or []) if str(item or "").strip()]
                    current = [
                        str(item or "").strip()
                        for item in list(ctx.get(key, []) or [])
                        if str(item or "").strip()
                    ]
                    if current != expected:
                        matches = False
                        break
                    continue
                if str(ctx.get(key, "") or "").strip() != str(value or "").strip():
                    matches = False
                    break
            if matches:
                return True
        return False

    def _am_enemy_battlefield_roots(self) -> list[Any]:
        if self.game is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for player in list(getattr(self.game, "players", []) or []):
            if player is None or player is self.player:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                root = self._am_root(unit)
                if root is None:
                    continue
                uid = self._am_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                if not self._am_on_battlefield(root):
                    continue
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _combined_arms_coordinated_action_squadron_candidates(self, regiment_unit: Any) -> list[Any]:
        if not self._is_combined_arms():
            return []
        regiment_root = self._am_root(regiment_unit)
        if regiment_root is None:
            return []
        if regiment_root not in self._am_battlefield_units(require_regiment=True):
            return []
        out: list[Any] = []
        for squadron_root in self._am_battlefield_units(require_squadron=True):
            if squadron_root is regiment_root:
                continue
            game_map = getattr(self.game, "map", None) if self.game is not None else None
            distance_fn = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
            if not callable(distance_fn):
                continue
            try:
                distance = float(distance_fn(regiment_root, squadron_root))
            except (TypeError, ValueError):
                continue
            if distance > 6.0 + 1e-6:
                continue
            if not self._am_is_visible_to_unit(regiment_root, squadron_root):
                continue
            out.append(squadron_root)
        return sorted(out, key=self._am_sort_key)

    def _combined_arms_coordinated_action_regiment_candidates(self) -> list[Any]:
        if not self._is_combined_arms():
            return []
        out = []
        for regiment_root in self._am_battlefield_units(require_regiment=True):
            if self._combined_arms_coordinated_action_squadron_candidates(regiment_root):
                out.append(regiment_root)
        return sorted(out, key=self._am_sort_key)

    def _combined_arms_fields_of_fire_squadron_candidates(self, regiment_unit: Any) -> list[Any]:
        if not self._is_combined_arms():
            return []
        regiment_root = self._am_root(regiment_unit)
        if regiment_root is None:
            return []
        if regiment_root not in self._am_battlefield_units(require_regiment=True, require_not_shot=True):
            return []
        return self._am_battlefield_units(require_squadron=True, require_not_shot=True)

    def _combined_arms_fields_of_fire_regiment_candidates(self) -> list[Any]:
        if not self._is_combined_arms():
            return []
        enemies = self._am_enemy_battlefield_roots()
        if not enemies:
            return []
        out = []
        for regiment_root in self._am_battlefield_units(require_regiment=True, require_not_shot=True):
            if self._combined_arms_fields_of_fire_squadron_candidates(regiment_root):
                out.append(regiment_root)
        return sorted(out, key=self._am_sort_key)

    def _combined_arms_fields_of_fire_enemy_candidates(self, regiment_unit: Any, squadron_unit: Any) -> list[Any]:
        if not self._is_combined_arms():
            return []
        regiment_root = self._am_root(regiment_unit)
        squadron_root = self._am_root(squadron_unit)
        if regiment_root is None or squadron_root is None:
            return []
        if regiment_root not in self._combined_arms_fields_of_fire_regiment_candidates():
            return []
        if squadron_root not in self._combined_arms_fields_of_fire_squadron_candidates(regiment_root):
            return []
        return self._am_enemy_battlefield_roots()

    def _combined_arms_flexible_command_officer_candidates(self) -> list[Any]:
        if not self._is_combined_arms():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        getter = getattr(voice, "get_eligible_officers", None) if voice is not None else None
        if callable(getter):
            officers = list(getter(game=self.game, player=self.player, phase_name="COMMAND_PHASE") or [])
        else:
            officers = list(self._am_battlefield_units(require_officer=True) or [])
        out: list[Any] = []
        seen: set[str] = set()
        for officer in list(officers or []):
            root = self._am_root(officer)
            if root is None:
                continue
            uid = self._am_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root) or not self._is_officer_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _combined_arms_inspired_command_officer_candidates(self) -> list[Any]:
        if not self._is_combined_arms():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        has_voice = getattr(voice, "_unit_has_voice", None) if voice is not None else None
        out: list[Any] = []
        seen: set[str] = set()
        for officer in list(self._am_battlefield_units(require_officer=True) or []):
            root = self._am_root(officer)
            if root is None:
                continue
            uid = self._am_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root) or not self._is_officer_unit(root):
                continue
            if callable(has_voice) and not bool(has_voice(root)):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _combined_arms_reinforcements_candidates(self, *, destroyed_unit: Any = None) -> list[Any]:
        if not self._is_combined_arms():
            return []
        root = self._am_root(destroyed_unit)
        if root is None:
            return []
        if not self._am_owned_by_player(root, self.player):
            return []
        if not self._is_astra_militarum_unit(root):
            return []
        if self._am_is_alive(root):
            return []
        if not self._am_has_keyword(root, "INFANTRY"):
            return []
        if not self._am_has_keyword(root, "REGIMENT"):
            return []
        is_battle_shocked = getattr(root, "is_battle_shocked", None)
        if callable(is_battle_shocked) and bool(is_battle_shocked()):
            return []
        return [root]

    def _combined_arms_stalwart_protector_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_combined_arms():
            return []
        if attacking_unit is not None:
            attacker_root = self._am_root(attacking_unit)
            if attacker_root is None or self._am_owned_by_player(attacker_root, self.player):
                return []
        _ = target_units
        return self._am_battlefield_units(require_vehicle=True)

    def _hammer_selected_to_act_this_phase(self, unit: Any, *, phase_name: str) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        phase_key = str(phase_name or "").strip().lower()
        round_state = getattr(root, "round_state", None)
        if phase_key == "movement phase":
            return bool(getattr(round_state, "moved_this_round", False))
        if phase_key == "charge phase":
            return bool(getattr(round_state, "attempted_charge_this_round", False))
        return False

    def _hammer_ablative_plating_candidates(self, *, target_units: Any = None) -> list[Any]:
        if not self._is_hammer_of_the_emperor():
            return []
        eligible_ids = {
            self._am_sort_key(unit)
            for unit in list(self._am_battlefield_units(require_vehicle=True) or [])
            if self._am_sort_key(unit)
        }
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._am_root(unit)
            if root is None:
                continue
            unit_id = self._am_sort_key(root)
            if unit_id and unit_id not in eligible_ids:
                continue
            if (not unit_id) and root not in self._am_battlefield_units(require_vehicle=True):
                continue
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _hammer_crash_through_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_hammer_of_the_emperor():
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units(require_vehicle=True) or []):
            if self._hammer_selected_to_act_this_phase(root, phase_name=phase_name):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _hammer_final_hour_candidates(self) -> list[Any]:
        if not self._is_hammer_of_the_emperor():
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units(require_squadron=True) or []):
            if self._is_officer_unit(root):
                continue
            is_below_half = getattr(root, "is_below_half_strength", None)
            if not callable(is_below_half) or not bool(is_below_half()):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _hammer_furious_cannonade_candidates(self) -> list[Any]:
        if not self._is_hammer_of_the_emperor():
            return []
        return self._am_battlefield_units(require_squadron=True, require_not_shot=True)

    def _bridgehead_bellicosa_drop_candidates(self) -> list[Any]:
        if not self._is_bridgehead_strike():
            return []
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_is_alive(root):
                continue
            if not self._am_is_in_reserves(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if not self._am_has_keyword(root, "INFANTRY"):
                continue
            if not self._am_has_deep_strike(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_fire_and_relocate_candidates(self) -> list[Any]:
        if not self._is_bridgehead_strike():
            return []
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if self._am_has_keyword(root, "TITANIC"):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_firing_hot_candidates(self) -> list[Any]:
        if not self._is_bridgehead_strike():
            return []
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if self._am_has_keyword(root, "MILITARUM TEMPESTUS") or self._am_name_matches(root, "kasrkin"):
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_aerial_extraction_candidates(self) -> list[Any]:
        if not self._is_bridgehead_strike():
            return []
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if self._am_is_in_engagement_range(root):
                continue
            if self._am_has_deep_strike(root) or self._am_name_matches(root, "valkyrie"):
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_on_my_position_candidates(self) -> list[Any]:
        if not self._is_bridgehead_strike():
            return []
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if not self._am_has_keyword(root, "REGIMENT"):
                continue
            if not self._am_has_keyword(root, "INFANTRY"):
                continue
            if not self._am_is_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_reaction_exists(self, event_name: str, stratagem_name: str) -> bool:
        wanted_event = str(event_name or "").strip().lower()
        wanted_name = str(stratagem_name or "").strip().upper()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            event = str(reaction.get("event", "") or "").strip().lower()
            name = str(reaction.get("stratagem", "") or "").strip().upper()
            if event == wanted_event and name == wanted_name:
                return True
        return False

    def _queue_bridgehead_servo_designators_target_decision(
        self,
        *,
        stratagem: Any,
        source_unit: Any,
        candidates: list[Any],
    ) -> bool:
        if self.game is None:
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        source_root = self._am_root(source_unit)
        if source_root is None:
            return False
        candidate_units = [
            candidate
            for candidate in list(candidates or [])
            if candidate is not None and self._am_root(candidate) is not None
        ]
        if not candidate_units:
            return False
        options = [
            DecisionOption.create(
                str(getattr(candidate, "name", "Unit") or "Unit"),
                payload={"target_unit_id": maybe_entity_id(candidate)},
            )
            for candidate in candidate_units
        ]
        if not options:
            return False
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "SERVO-DESIGNATORS: select a visible enemy unit hit by that unit.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "post_shoot_no_cover",
                "ability_name": str(getattr(stratagem, "name", "") or "SERVO-DESIGNATORS"),
                "attacker_unit_id": maybe_entity_id(source_root),
                "expires_phase": "SHOOTING_PHASE",
                "expires_timing": "PHASE_END",
            },
        )
        request_decision = getattr(self.game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
            return True
        return False

    def _queue_armoured_infantry_combined_fire_target_decision(
        self,
        *,
        stratagem: Any,
        source_unit: Any,
        candidates: list[Any],
    ) -> bool:
        if self.game is None:
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        source_root = self._am_root(source_unit)
        if source_root is None:
            return False
        candidate_units = [
            candidate
            for candidate in list(candidates or [])
            if candidate is not None and self._am_root(candidate) is not None
        ]
        if not candidate_units:
            return False
        options = [
            DecisionOption.create(
                str(getattr(candidate, "name", "Unit") or "Unit"),
                payload={"target_unit_id": maybe_entity_id(candidate)},
            )
            for candidate in candidate_units
        ]
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "COMBINED FIRE: select an enemy unit hit by that unit.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "armoured_infantry_combined_fire",
                "ability_name": str(getattr(stratagem, "name", "") or "COMBINED FIRE"),
                "attacker_unit_id": maybe_entity_id(source_root),
                "candidate_unit_ids": [maybe_entity_id(candidate) for candidate in candidate_units],
                "expires_phase": "SHOOTING_PHASE",
                "expires_timing": "PHASE_END",
            },
        )
        request_decision = getattr(self.game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
            return True
        return False

    def _queue_combined_arms_choose_quarry_request(
        self,
        *,
        ability: str,
        prompt: str,
        options_data: list[tuple[str, dict[str, Any]]],
        context: dict[str, Any],
    ) -> bool:
        if self.game is None:
            return False
        request_decision = getattr(self.game, "request_decision", None)
        if not callable(request_decision):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [DecisionOption.create("Cancel", payload={"action": "skip"})]
        for label, payload in list(options_data or []):
            options.append(DecisionOption.create(str(label or "Unit"), payload=dict(payload or {})))
        if len(options) <= 1:
            return False
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(self.player, "id", None),
            options=options,
            context=dict(context or {}),
        )
        request_decision(request)
        return True

    def _queue_combined_arms_coordinated_action_regiment_request(self, stratagem: Any, *, phase_name: str) -> bool:
        candidates = self._combined_arms_coordinated_action_regiment_candidates()
        if not candidates:
            return False
        ability_name = str(getattr(stratagem, "name", "") or "COORDINATED ACTION").strip() or "COORDINATED ACTION"
        candidate_ids = [self._am_sort_key(candidate) for candidate in list(candidates or []) if self._am_sort_key(candidate)]
        if not candidate_ids:
            return False
        if self._am_pending_choose_quarry_request(
            ability="combined_arms_coordinated_action_regiment",
            phase_name=str(phase_name or ""),
            candidate_unit_ids=candidate_ids,
        ):
            return False
        return self._queue_combined_arms_choose_quarry_request(
            ability="combined_arms_coordinated_action_regiment",
            prompt=f"{ability_name}: select one friendly REGIMENT unit.",
            options_data=[
                (
                    str(getattr(candidate, "name", "Unit") or "Unit"),
                    {"regiment_unit_id": self._am_sort_key(candidate)},
                )
                for candidate in list(candidates or [])
                if self._am_sort_key(candidate)
            ],
            context={
                "ability": "combined_arms_coordinated_action_regiment",
                "ability_name": ability_name,
                "phase_name": str(phase_name or ""),
                "candidate_unit_ids": list(candidate_ids),
                "optional": True,
            },
        )

    def _queue_combined_arms_coordinated_action_squadron_request(
        self,
        stratagem: Any,
        *,
        phase_name: str,
        regiment_unit: Any,
    ) -> bool:
        regiment_root = self._am_root(regiment_unit)
        if regiment_root is None:
            return False
        candidates = self._combined_arms_coordinated_action_squadron_candidates(regiment_root)
        if not candidates:
            return False
        ability_name = str(getattr(stratagem, "name", "") or "COORDINATED ACTION").strip() or "COORDINATED ACTION"
        regiment_id = self._am_sort_key(regiment_root)
        candidate_ids = [self._am_sort_key(candidate) for candidate in list(candidates or []) if self._am_sort_key(candidate)]
        if not regiment_id or not candidate_ids:
            return False
        if self._am_pending_choose_quarry_request(
            ability="combined_arms_coordinated_action_squadron",
            phase_name=str(phase_name or ""),
            regiment_unit_id=regiment_id,
            candidate_unit_ids=candidate_ids,
        ):
            return False
        return self._queue_combined_arms_choose_quarry_request(
            ability="combined_arms_coordinated_action_squadron",
            prompt=(
                f"{ability_name}: select one friendly SQUADRON unit within 6\" of and visible to "
                f"{getattr(regiment_root, 'name', 'Unit')}."
            ),
            options_data=[
                (
                    str(getattr(candidate, "name", "Unit") or "Unit"),
                    {
                        "regiment_unit_id": regiment_id,
                        "squadron_unit_id": self._am_sort_key(candidate),
                    },
                )
                for candidate in list(candidates or [])
                if self._am_sort_key(candidate)
            ],
            context={
                "ability": "combined_arms_coordinated_action_squadron",
                "ability_name": ability_name,
                "phase_name": str(phase_name or ""),
                "regiment_unit_id": regiment_id,
                "candidate_unit_ids": list(candidate_ids),
                "optional": True,
            },
        )

    def _queue_combined_arms_fields_of_fire_regiment_request(self, stratagem: Any, *, phase_name: str) -> bool:
        candidates = self._combined_arms_fields_of_fire_regiment_candidates()
        if not candidates:
            return False
        ability_name = str(getattr(stratagem, "name", "") or "FIELDS OF FIRE").strip() or "FIELDS OF FIRE"
        candidate_ids = [self._am_sort_key(candidate) for candidate in list(candidates or []) if self._am_sort_key(candidate)]
        if not candidate_ids:
            return False
        if self._am_pending_choose_quarry_request(
            ability="combined_arms_fields_of_fire_regiment",
            phase_name=str(phase_name or ""),
            candidate_unit_ids=candidate_ids,
        ):
            return False
        return self._queue_combined_arms_choose_quarry_request(
            ability="combined_arms_fields_of_fire_regiment",
            prompt=f"{ability_name}: select one friendly REGIMENT unit that has not been selected to shoot.",
            options_data=[
                (
                    str(getattr(candidate, "name", "Unit") or "Unit"),
                    {"regiment_unit_id": self._am_sort_key(candidate)},
                )
                for candidate in list(candidates or [])
                if self._am_sort_key(candidate)
            ],
            context={
                "ability": "combined_arms_fields_of_fire_regiment",
                "ability_name": ability_name,
                "phase_name": str(phase_name or ""),
                "candidate_unit_ids": list(candidate_ids),
                "optional": True,
            },
        )

    def _queue_combined_arms_fields_of_fire_squadron_request(
        self,
        stratagem: Any,
        *,
        phase_name: str,
        regiment_unit: Any,
    ) -> bool:
        regiment_root = self._am_root(regiment_unit)
        if regiment_root is None:
            return False
        candidates = self._combined_arms_fields_of_fire_squadron_candidates(regiment_root)
        if not candidates:
            return False
        ability_name = str(getattr(stratagem, "name", "") or "FIELDS OF FIRE").strip() or "FIELDS OF FIRE"
        regiment_id = self._am_sort_key(regiment_root)
        candidate_ids = [self._am_sort_key(candidate) for candidate in list(candidates or []) if self._am_sort_key(candidate)]
        if not regiment_id or not candidate_ids:
            return False
        if self._am_pending_choose_quarry_request(
            ability="combined_arms_fields_of_fire_squadron",
            phase_name=str(phase_name or ""),
            regiment_unit_id=regiment_id,
            candidate_unit_ids=candidate_ids,
        ):
            return False
        return self._queue_combined_arms_choose_quarry_request(
            ability="combined_arms_fields_of_fire_squadron",
            prompt=f"{ability_name}: select one friendly SQUADRON unit that has not been selected to shoot.",
            options_data=[
                (
                    str(getattr(candidate, "name", "Unit") or "Unit"),
                    {
                        "regiment_unit_id": regiment_id,
                        "squadron_unit_id": self._am_sort_key(candidate),
                    },
                )
                for candidate in list(candidates or [])
                if self._am_sort_key(candidate)
            ],
            context={
                "ability": "combined_arms_fields_of_fire_squadron",
                "ability_name": ability_name,
                "phase_name": str(phase_name or ""),
                "regiment_unit_id": regiment_id,
                "candidate_unit_ids": list(candidate_ids),
                "optional": True,
            },
        )

    def _queue_combined_arms_fields_of_fire_enemy_request(
        self,
        stratagem: Any,
        *,
        phase_name: str,
        regiment_unit: Any,
        squadron_unit: Any,
    ) -> bool:
        regiment_root = self._am_root(regiment_unit)
        squadron_root = self._am_root(squadron_unit)
        if regiment_root is None or squadron_root is None:
            return False
        candidates = self._combined_arms_fields_of_fire_enemy_candidates(regiment_root, squadron_root)
        if not candidates:
            return False
        ability_name = str(getattr(stratagem, "name", "") or "FIELDS OF FIRE").strip() or "FIELDS OF FIRE"
        regiment_id = self._am_sort_key(regiment_root)
        squadron_id = self._am_sort_key(squadron_root)
        candidate_ids = [self._am_sort_key(candidate) for candidate in list(candidates or []) if self._am_sort_key(candidate)]
        if not regiment_id or not squadron_id or not candidate_ids:
            return False
        if self._am_pending_choose_quarry_request(
            ability="combined_arms_fields_of_fire_enemy",
            phase_name=str(phase_name or ""),
            regiment_unit_id=regiment_id,
            squadron_unit_id=squadron_id,
            candidate_unit_ids=candidate_ids,
        ):
            return False
        return self._queue_combined_arms_choose_quarry_request(
            ability="combined_arms_fields_of_fire_enemy",
            prompt=f"{ability_name}: select one enemy unit.",
            options_data=[
                (
                    str(getattr(candidate, "name", "Unit") or "Unit"),
                    {
                        "regiment_unit_id": regiment_id,
                        "squadron_unit_id": squadron_id,
                        "enemy_unit_id": self._am_sort_key(candidate),
                    },
                )
                for candidate in list(candidates or [])
                if self._am_sort_key(candidate)
            ],
            context={
                "ability": "combined_arms_fields_of_fire_enemy",
                "ability_name": ability_name,
                "phase_name": str(phase_name or ""),
                "regiment_unit_id": regiment_id,
                "squadron_unit_id": squadron_id,
                "candidate_unit_ids": list(candidate_ids),
                "optional": True,
            },
        )

    def _am_clone_reinforcements_unit(self, unit: Any) -> Any:
        root = self._am_root(unit)
        if root is None:
            return None
        clone_hook = getattr(root, "clone_for_cult_ambush", None)
        if callable(clone_hook):
            return clone_hook()
        try:
            from ..units.unit import Unit as UnitClass
        except ImportError:
            return None
        datasheet = getattr(root, "_datasheet", None)
        if datasheet is None:
            return None
        count = int(getattr(root, "starting_model_count", 0) or 0)
        if count <= 0:
            count = len(list(getattr(root, "models", []) or []))
        if count <= 0:
            count = len(list(getattr(root, "models_lost", []) or []))
        if count <= 0:
            return None
        try:
            new_unit = UnitClass(datasheet, quantity=count, enhancement=getattr(root, "enhancement", None))
        except TypeError:
            new_unit = UnitClass(datasheet, quantity=count)
        self._am_copy_model_wargear(root, new_unit)
        new_unit.is_warlord = bool(getattr(root, "is_warlord", False))
        return new_unit

    def _am_copy_model_wargear(self, source_unit: Any, target_unit: Any) -> None:
        if source_unit is None or target_unit is None:
            return

        def _norm(text: str) -> str:
            raw = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in str(text or "").lower())
            return " ".join(raw.split())

        source_models = list(getattr(source_unit, "models", []) or [])
        source_models.extend(list(getattr(source_unit, "models_lost", []) or []))
        buckets: dict[str, list[Any]] = {}
        for source_model in source_models:
            key = _norm(getattr(source_model, "name", "") or "")
            buckets.setdefault(key, []).append(source_model)
        possible = list(getattr(target_unit, "possible_wargear", []) or [])
        possible_by_name = {_norm(getattr(wg, "name", "") or ""): wg for wg in possible}
        leftovers = [model for model in source_models if model is not None]
        for target_model in list(getattr(target_unit, "models", []) or []):
            key = _norm(getattr(target_model, "name", "") or "")
            source_model = None
            if key in buckets and buckets[key]:
                source_model = buckets[key].pop(0)
            elif leftovers:
                source_model = leftovers.pop(0)
            if source_model is None:
                continue
            target_model.wargear = []
            for wargear in list(getattr(source_model, "wargear", []) or []):
                name_key = _norm(getattr(wargear, "name", "") or "")
                target_model.wargear.append(possible_by_name.get(name_key, wargear))
            target_model.optional_wargear = list(getattr(source_model, "optional_wargear", []) or [])

    def _am_prepare_unit_in_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        if unit is None:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        set_parent = getattr(unit, "set_parent_army", None)
        if callable(set_parent):
            set_parent(army)
        else:
            unit.parent_army = army
        if hasattr(army, "add_unit"):
            army.add_unit(unit)
        else:
            army.units.append(unit)
        enter_midgame = getattr(unit, "enter_strategic_reserves_midgame", None)
        if callable(enter_midgame):
            ok = bool(
                enter_midgame(
                    game=self.game,
                    game_map=getattr(self.game, "map", None) if self.game is not None else None,
                    reason=str(reason or "REINFORCEMENTS!"),
                )
            )
        else:
            unit.reserve_status = "strategic_reserves"
            unit.deployed = True
            unit.arrived_from_reserves_this_turn = False
            game_map = getattr(self.game, "map", None) if self.game is not None else None
            if game_map is not None and isinstance(getattr(game_map, "units", None), list) and unit in game_map.units:
                game_map.units.remove(unit)
            ok = True
        rebuild = getattr(self.game, "rebuild_entity_registry", None) if self.game is not None else None
        if callable(rebuild):
            rebuild()
        return ok

    def _am_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        preview = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(preview):
            data = preview(stratagem, target_unit=target_unit) or {}
            cp_cost = int(data.get("cost", cp_cost))
        return cp_cost

    def _am_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._am_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _am_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _am_has_voice_prompt_subscriber(self) -> bool:
        event_system = getattr(self.game, "event_system", None) if self.game is not None else None
        subscribers = getattr(event_system, "subscribers", None) if event_system is not None else None
        if event_system is None or not isinstance(subscribers, dict):
            return False
        return bool(subscribers.get("voice_of_command_prompt"))

    def _am_pending_reaction_by_names(self, *names: str):
        wanted = {
            str(name or "").strip().upper()
            for name in list(names or [])
            if str(name or "").strip()
        }
        if not wanted:
            return None
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            reaction_name = str(reaction.get("stratagem", "") or "").strip().upper()
            if reaction_name in wanted:
                return reaction
        return None

    def _am_resolve_unit_list(self, units: Any) -> list[Any]:
        if units is None:
            return []
        if isinstance(units, (list, tuple, set)):
            values = list(units)
        else:
            values = [units]
        out: list[Any] = []
        seen: set[str] = set()
        for value in values:
            root = self._am_root(value)
            if root is None:
                continue
            unit_id = self._am_sort_key(root)
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _am_distance_between_units(self, unit_a: Any, unit_b: Any) -> Optional[float]:
        root_a = self._am_root(unit_a)
        root_b = self._am_root(unit_b)
        if root_a is None or root_b is None:
            return None
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        distance_fn = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
        if not callable(distance_fn) and self.game is not None:
            distance_fn = getattr(self.game, "get_distance_between_units", None)
        if not callable(distance_fn):
            return None
        try:
            return float(distance_fn(root_a, root_b))
        except (TypeError, ValueError):
            return None

    def _am_embarked_target_blocked_by_rules(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        allow_while_battle_shocked = False
        allow_fn = getattr(root, "can_be_targeted_with_stratagems_while_battle_shocked", None)
        if callable(allow_fn):
            allow_while_battle_shocked = bool(allow_fn())
        is_battle_shocked = getattr(root, "is_battle_shocked", None)
        if callable(is_battle_shocked) and bool(is_battle_shocked()) and not allow_while_battle_shocked:
            return True
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("cannot_use_stratagems", False)) and not allow_while_battle_shocked:
            return True
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        get_enemy_units = getattr(game_map, "get_enemy_units", None) if game_map is not None else None
        is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
        if not callable(get_enemy_units) or not callable(is_within_engagement_range):
            return False
        seen: set[str] = set()
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._am_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._am_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            is_alive = getattr(enemy_root, "is_alive", None)
            if callable(is_alive) and not bool(is_alive()):
                continue
            has_voice_eater = getattr(enemy_root, "has_voice_eater", None)
            if not callable(has_voice_eater) or not bool(has_voice_eater()):
                continue
            if bool(is_within_engagement_range(root, enemy_root)):
                return True
        return False

    def _am_disembarked_from_transport_this_turn(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        if round_state is None:
            return False
        if not bool(getattr(round_state, "disembarked_this_round", False)):
            return False
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip()
        if not transport_id:
            return False
        game = getattr(self, "game", None)
        if game is None:
            return True
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return True
        try:
            disembark_turn = int(sr.get("voice_of_command_disembark_round", 0) or 0)
        except (TypeError, ValueError):
            disembark_turn = 0
        if disembark_turn > 0:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            if current_turn > 0 and current_turn != disembark_turn:
                return False
        current_owner = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "").strip()
        disembark_owner = str(sr.get("voice_of_command_disembark_owner", "") or "").strip()
        if current_owner and disembark_owner and current_owner != disembark_owner:
            return False
        return True

    def _am_disembarked_from_transport_this_phase(self, unit: Any) -> bool:
        if not self._am_disembarked_from_transport_this_turn(unit):
            return False
        root = self._am_root(unit)
        sr = getattr(root, "special_rules", None) if root is not None else None
        if not isinstance(sr, dict):
            return True
        game = getattr(self, "game", None)
        if game is None:
            return True
        current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        disembark_phase = str(sr.get("voice_of_command_disembark_phase", "") or "").strip().upper()
        if current_phase and disembark_phase and current_phase != disembark_phase:
            return False
        return True

    def _am_pending_charge_roll_request(self, charging_unit: Any):
        game = getattr(self, "game", None)
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if queue is None or not hasattr(queue, "list"):
            return None, None
        charging_unit_id = self._am_sort_key(charging_unit)
        if not charging_unit_id:
            return None, None
        from ..engine.decision_kinds import DECISION_REQUEST_DICE_ROLL

        for request in list(queue.list() or []):
            if str(getattr(request, "decision_type", "") or "") != str(DECISION_REQUEST_DICE_ROLL):
                continue
            ctx = dict(getattr(request, "context", {}) or {})
            if str(ctx.get("roll_type", "") or "").strip().lower() != "charge":
                continue
            roll_spec = dict(ctx.get("roll_spec", {}) or {})
            if str(roll_spec.get("unit_id", "") or "") != charging_unit_id:
                continue
            roll_id = ctx.get("roll_id")
            state = None
            roll_manager = getattr(game, "roll_manager", None)
            if roll_id is not None and roll_manager is not None:
                state = roll_manager.get_roll(int(roll_id))
            return request, state
        return None, None

    def _am_remove_pending_charge_roll_request(self, charging_unit: Any) -> bool:
        request, state = self._am_pending_charge_roll_request(charging_unit)
        if request is None:
            return False
        game = getattr(self, "game", None)
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if queue is not None and hasattr(queue, "pop"):
            queue.pop(getattr(request, "decision_id", None))
        if state is not None and game is not None:
            roll_manager = getattr(game, "roll_manager", None)
            if roll_manager is not None:
                roll_manager.rolls.pop(int(state.roll_id), None)
        round_state = getattr(charging_unit, "round_state", None)
        if round_state is not None:
            setattr(round_state, "charge_roll_id", None)
        return True

    def _am_apply_pending_charge_roll_modifier(self, charging_unit: Any, *, value: int, source: str) -> None:
        request, state = self._am_pending_charge_roll_request(charging_unit)
        if request is None or state is None:
            return
        try:
            modifier_value = int(value or 0)
        except (TypeError, ValueError):
            modifier_value = 0
        if modifier_value == 0:
            return
        source_name = str(source or "").strip()
        state.sum_modifier = int(getattr(state, "sum_modifier", 0) or 0) + modifier_value
        reasons = list(getattr(state, "sum_modifier_reasons", []) or [])
        label = f"{modifier_value:+d}"
        reasons.append(f"{source_name}: {label}" if source_name else label)
        state.sum_modifier_reasons = reasons
        context = dict(getattr(request, "context", {}) or {})
        roll_spec = dict(context.get("roll_spec", {}) or {})
        roll_spec["sum_modifier"] = int(getattr(state, "sum_modifier", 0) or 0)
        roll_spec["sum_modifier_reasons"] = list(getattr(state, "sum_modifier_reasons", []) or [])
        context["roll_spec"] = roll_spec
        request.context = context

    def _queue_mechanised_pair_embark_decision(
        self,
        *,
        ability: str,
        ability_name: str,
        prompt: str,
        candidates: list[dict[str, Any]],
        context: dict[str, Any],
        duplicate_match: Optional[dict[str, Any]] = None,
        allow_skip: bool = False,
    ):
        game = getattr(self, "game", None)
        request_decision = getattr(game, "request_decision", None) if game is not None else None
        if game is None or not callable(request_decision):
            return None
        if self._am_pending_choose_quarry_request(ability=ability, **dict(duplicate_match or {})):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = []
        if allow_skip:
            options.append(DecisionOption.create("None", payload={"action": "skip"}))
        sorted_candidates = [
            dict(candidate or {})
            for candidate in list(candidates or [])
            if isinstance(candidate, dict)
        ]
        sorted_candidates.sort(
            key=lambda candidate: (
                str(candidate.get("transport_id", "") or ""),
                str(candidate.get("target_unit_id", "") or ""),
            )
        )
        for candidate in sorted_candidates:
            transport_id = str(candidate.get("transport_id", "") or "")
            target_unit_id = str(candidate.get("target_unit_id", "") or "")
            if not transport_id or not target_unit_id:
                continue
            label = str(candidate.get("label", "") or "").strip()
            if not label:
                label = "Embark"
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "transport_id": transport_id,
                        "target_unit_id": target_unit_id,
                        "spec": dict(candidate.get("spec", {}) or {}),
                    },
                )
            )
        if not options:
            return None

        ctx = {
            "ability": str(ability or "").strip(),
            "ability_name": str(ability_name or "").strip(),
            "optional": bool(allow_skip),
        }
        ctx.update(dict(context or {}))
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(self.player, "id", None),
            options=options,
            context=ctx,
        )
        request_decision(request)
        return request

    def _mechanised_vox_relay_candidates(self) -> list[Any]:
        if not self._is_mechanised_assault():
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "COMMAND_PHASE":
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for root in self._am_army_roots():
            unit_id = self._am_sort_key(root)
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_is_alive(root):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if not self._is_officer_unit(root) or not self._am_has_keyword(root, "INFANTRY"):
                continue
            if self._am_embarked_target_blocked_by_rules(root):
                continue
            transport = getattr(root, "embarked_in", None)
            if transport is None:
                continue
            transport_root = self._am_root(transport)
            if transport_root is None or not self._am_on_battlefield(transport_root):
                continue
            if not self._is_astra_militarum_unit(transport_root) or not self._am_has_keyword(transport_root, "TRANSPORT"):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _mechanised_rapid_dispersal_candidates(self) -> list[Any]:
        if not self._is_mechanised_assault():
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "MOVEMENT_PHASE":
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return []
        out: list[Any] = []
        for root in self._am_battlefield_units(require_infantry=True):
            if not self._am_disembarked_from_transport_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _armoured_infantry_burst_of_speed_candidates(self) -> list[Any]:
        if not self._is_armoured_infantry():
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "MOVEMENT_PHASE":
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return []
        out: list[Any] = []
        for root in self._am_battlefield_units():
            round_state = getattr(root, "round_state", None)
            if bool(getattr(round_state, "remained_stationary_this_round", False)):
                continue
            if bool(getattr(root, "arrived_from_reserves_this_phase", False)):
                continue
            if bool(getattr(root, "arrived_from_reserves_this_turn", False)):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _mechanised_clear_and_secure_candidates(self) -> list[Any]:
        if not self._is_mechanised_assault():
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "SHOOTING_PHASE":
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return []
        out: list[Any] = []
        for root in self._am_battlefield_units(require_not_shot=True):
            if not self._am_disembarked_from_transport_this_turn(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _mechanised_transport_units_on_battlefield(
        self,
        *,
        require_targetable: bool,
        exclude_aircraft: bool = False,
        exclude_titanic: bool = False,
    ) -> list[Any]:
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._am_has_keyword(root, "TRANSPORT"):
                continue
            if exclude_aircraft and self._am_has_keyword(root, "AIRCRAFT"):
                continue
            if exclude_titanic and self._am_has_keyword(root, "TITANIC"):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _mechanised_swift_interception_candidates(self, *, enemy_unit: Any, action: str) -> list[Any]:
        if not self._is_mechanised_assault():
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "MOVEMENT_PHASE":
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return []
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"move", "normal", "normal move", "advance", "fall back", "fallback"}:
            return []
        enemy_root = self._am_root(enemy_unit)
        if enemy_root is None or self._am_owned_by_player(enemy_root, self.player):
            return []
        out: list[Any] = []
        for transport in self._mechanised_transport_units_on_battlefield(
            require_targetable=True,
            exclude_aircraft=True,
            exclude_titanic=True,
        ):
            distance = self._am_distance_between_units(transport, enemy_root)
            if distance is None or distance > 9.0 + 1e-6:
                continue
            if self._am_is_in_engagement_range(transport):
                continue
            out.append(transport)
        return sorted(out, key=self._am_sort_key)

    def _mechanised_embark_pairs_for_units(
        self,
        units: Any,
        *,
        source: str,
    ) -> list[dict[str, Any]]:
        if not self._is_mechanised_assault():
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game is None or game_map is None:
            return []
        try:
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
        except ImportError:
            return []
        transports = self._mechanised_transport_units_on_battlefield(require_targetable=False)
        if not transports:
            return []
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for target in self._am_resolve_unit_list(units):
            if not self._am_owned_by_player(target, self.player):
                continue
            if not self._am_on_battlefield(target):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(target)):
                continue
            if self._am_is_in_engagement_range(target):
                continue
            for transport in list(transports):
                if transport is target:
                    continue
                can_transport = getattr(transport, "can_transport", None)
                if not callable(can_transport) or not bool(can_transport(target)):
                    continue
                if not bool(unit_wholly_within_range_of_unit(transport, target, 3.0)):
                    continue
                transport_id = self._am_sort_key(transport)
                target_id = self._am_sort_key(target)
                pair_key = (transport_id, target_id)
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                out.append(
                    {
                        "transport_id": transport_id,
                        "transport_unit": transport,
                        "target_unit_id": target_id,
                        "target_unit": target,
                        "label": f"{getattr(target, 'name', 'Unit')} -> {getattr(transport, 'name', 'Transport')}",
                        "spec": {
                            "source": str(source or "").strip() or "Embark",
                            "range": 3.0,
                            "allow_existing_passengers": True,
                        },
                    }
                )
        out.sort(key=lambda item: (str(item.get("transport_id", "") or ""), str(item.get("target_unit_id", "") or "")))
        return out

    def _mechanised_hasty_extraction_candidates(
        self,
        *,
        charging_unit: Any = None,
        target_units: Any = None,
    ) -> list[dict[str, Any]]:
        if not self._is_mechanised_assault():
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "CHARGE_PHASE":
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return []
        charging_root = self._am_root(charging_unit)
        if charging_root is None or self._am_owned_by_player(charging_root, self.player):
            return []
        declared_targets = []
        for target in self._am_resolve_unit_list(target_units):
            if not self._am_owned_by_player(target, self.player):
                continue
            if not self._is_astra_militarum_unit(target):
                continue
            if not self._am_has_keyword(target, "INFANTRY"):
                continue
            declared_targets.append(target)
        return self._mechanised_embark_pairs_for_units(
            declared_targets,
            source="HASTY EXTRACTION",
        )

    def _mechanised_move_out_candidates(self) -> list[dict[str, Any]]:
        if not self._is_mechanised_assault():
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return []
        return self._mechanised_embark_pairs_for_units(
            self._am_battlefield_units(),
            source="MOVE OUT",
        )

    def _recon_crack_shots_candidates(self) -> list[Any]:
        if not self._is_recon_element():
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units(require_not_shot=True) or []):
            if self._am_has_keyword(root, "PLATOON"):
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _recon_courageous_diversion_candidates(self) -> list[Any]:
        if not self._is_recon_element():
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units() or []):
            if self._am_has_keyword(root, "INFANTRY") or self._am_has_keyword(root, "MOUNTED"):
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _recon_draw_them_out_candidates(self, *, enemy_unit: Any, action: str) -> list[Any]:
        if not self._is_recon_element():
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "MOVEMENT_PHASE":
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return []
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"move", "normal", "normal move", "advance", "fall back", "fallback"}:
            return []
        enemy_root = self._am_root(enemy_unit)
        if enemy_root is None or self._am_owned_by_player(enemy_root, self.player):
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units() or []):
            if not self._am_has_keyword(root, "PLATOON"):
                continue
            if self._am_is_in_engagement_range(root):
                continue
            distance = self._am_distance_between_units(root, enemy_root)
            if distance is None or distance > 9.0 + 1e-6:
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _recon_scramble_field_candidates(self) -> list[Any]:
        if not self._is_recon_element():
            return []
        return self._am_battlefield_units(require_infantry=True)

    def _recon_tanglefoot_grenades_candidates(self) -> list[Any]:
        if not self._is_recon_element():
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units() or []):
            if self._am_has_keyword(root, "GRENADES"):
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _recon_scouting_outriders_candidates(self) -> list[Any]:
        if not self._is_recon_element():
            return []
        edge_checker = getattr(self, "_unit_wholly_within_battlefield_edge_distance", None)
        if not callable(edge_checker):
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units() or []):
            if not (self._am_has_keyword(root, "MOUNTED") or self._am_has_keyword(root, "WALKER")):
                continue
            if self._am_is_in_engagement_range(root):
                continue
            if not bool(edge_checker(root, 10.0)):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _siege_callous_sacrifice_candidates(self) -> list[Any]:
        if not self._is_siege_regiment():
            return []
        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return []
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units() or []):
            if not self._am_has_keyword(root, "PLATOON"):
                continue
            if not self._am_is_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _siege_flare_burst_candidates(self) -> list[Any]:
        if not self._is_siege_regiment():
            return []
        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return []
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units(require_not_shot=True) or []):
            if self._am_has_keyword(root, "CHARACTER"):
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _siege_furious_fusillade_candidates(self) -> list[Any]:
        if not self._is_siege_regiment():
            return []
        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return []
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units(require_not_shot=True) or []):
            if self._am_has_keyword(root, "PLATOON"):
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _siege_minefield_candidates(self) -> list[Any]:
        if not self._is_siege_regiment():
            return []
        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "CHARGE_PHASE":
            return []
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return []
        out: list[Any] = []
        for root in list(self._am_battlefield_units() or []):
            if self._am_has_keyword(root, "PLATOON"):
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _siege_over_the_top_candidates(self) -> list[Any]:
        if not self._is_siege_regiment():
            return []
        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "COMMAND_PHASE":
            return []
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        getter = getattr(voice, "get_eligible_officers", None) if voice is not None else None
        if callable(getter):
            officers = list(
                getter(
                    game=self.game,
                    player=self.player,
                    phase_name="COMMAND_PHASE",
                    trigger="command_phase_start",
                )
                or []
            )
        else:
            officers = list(self._am_battlefield_units(require_infantry=True, require_officer=True) or [])
        out: list[Any] = []
        seen: set[str] = set()
        for officer in officers:
            root = officer
            uid = self._am_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._am_has_keyword(root, "INFANTRY"):
                continue
            if not self._is_officer_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _siege_trench_fighters_candidates(self, *, attacking_unit: Any, target_units: list[Any]) -> list[Any]:
        if not self._is_siege_regiment():
            return []
        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return []
        attacker_root = self._am_root(attacking_unit)
        if attacker_root is None or self._am_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._am_root(unit)
            if root is None:
                continue
            uid = self._am_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if not self._is_astra_militarum_unit(root) or not self._am_has_keyword(root, "INFANTRY"):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _queue_siege_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_siege_regiment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if player is self.player and phase_key == "COMMAND_PHASE":
            stratagem_name = "OVER THE TOP"
            candidates = self._siege_over_the_top_candidates()
            phase_label = "Command phase"
        elif player is not self.player and phase_key == "CHARGE_PHASE":
            stratagem_name = "MINEFIELD"
            candidates = self._siege_minefield_candidates()
            phase_label = "Charge phase"
        else:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)(stratagem_name)
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_start":
                continue
            if self._normalize_stratagem_name(reaction.get("stratagem", "") or "") != name_u:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() == phase_label.lower():
                return
        payload = {
            "event": "phase_start",
            "phase_name": phase_label,
            "phase": phase_label,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_siege_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_siege_regiment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacking_root = self._am_root(attacking_unit)
        if attacking_root is None or self._am_owned_by_player(attacking_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("TRENCH FIGHTERS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._siege_trench_fighters_candidates(
            attacking_unit=attacking_root,
            target_units=list(target_units or []),
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if self._normalize_stratagem_name(reaction.get("stratagem", "") or "") != name_u:
                continue
            if reaction.get("attacking_unit") is attacking_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_root,
            "enemy_unit": attacking_root,
            "target_units": list(target_units or []),
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _siege_callous_sacrifice_has_pending_decision(self, *, unit_id: str) -> bool:
        if self.game is None:
            return False
        queue = getattr(self.game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_SELECT_TARGET_MODEL

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_TARGET_MODEL:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("selection_kind", "") or "") != "worthless_chattel_destroy":
                continue
            if str(ctx.get("ability_name", "") or "").strip().upper() != "CALLOUS SACRIFICE":
                continue
            if str(ctx.get("target_unit_id", "") or "") != str(unit_id or ""):
                continue
            return True
        return False

    def _resolve_siege_callous_sacrifice_after_shooting(
        self,
        *,
        attacker_unit: Any,
        damage_by_target_while_engaged: dict[Any, int] | None,
    ) -> None:
        if not self._is_siege_regiment() or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._am_root(attacker_unit)
        if attacker_root is None or not self._am_owned_by_player(attacker_root, self.player):
            return
        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("siege_regiment_callous_sacrifice_active", False)):
            return
        exp = str(sr.get("siege_regiment_callous_sacrifice_expires_phase", "") or "").strip().upper()
        if exp and exp != "SHOOTING_PHASE":
            return
        owner = str(sr.get("siege_regiment_callous_sacrifice_turn_owner", "") or "").strip()
        if owner and owner != str(getattr(self.player, "id", "") or ""):
            return
        damage_map = damage_by_target_while_engaged if isinstance(damage_by_target_while_engaged, dict) else {}
        if not damage_map:
            return
        total_rolls = 0
        for target in sorted(list(damage_map), key=self._am_sort_key):
            target_root = self._am_root(target)
            if target_root is None or self._am_owned_by_player(target_root, self.player):
                continue
            try:
                total_rolls += max(0, int(damage_map.get(target, 0) or 0))
            except (TypeError, ValueError):
                continue
        if total_rolls <= 0:
            return
        destroy_count = 0
        for _ in range(int(total_rolls)):
            if get_roll("D6") >= 4:
                destroy_count += 1
        get_models = getattr(attacker_root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(attacker_root, "models", []) or [])
        alive_models = []
        for model in models:
            alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if is_alive:
                alive_models.append(model)
        destroy_count = min(int(destroy_count), len(alive_models))
        if destroy_count <= 0:
            return
        try:
            from ..utility.event_bus import append_action
        except Exception:
            append_action = None
        if len(alive_models) == 1:
            try:
                alive_models[0].die(game_map=getattr(self.game, "map", None))
            except Exception:
                return
            if callable(append_action):
                append_action(
                    self.player,
                    f"{getattr(attacker_root, 'name', 'Unit')}: Callous Sacrifice destroys 1 model after shooting.",
                )
            return
        unit_id = self._am_sort_key(attacker_root)
        if self._siege_callous_sacrifice_has_pending_decision(unit_id=unit_id):
            return
        from ..engine.decision_kinds import DECISION_SELECT_TARGET_MODEL
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [
            DecisionOption.create(
                str(getattr(model, "name", "Model") or "Model"),
                payload={"model_id": maybe_entity_id(model)},
            )
            for model in list(alive_models or [])
        ]
        if not options:
            return
        request = DecisionRequest.create(
            DECISION_SELECT_TARGET_MODEL,
            f"Callous Sacrifice: select a model to destroy ({int(destroy_count)} remaining).",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "selection_kind": "worthless_chattel_destroy",
                "target_unit_id": unit_id,
                "destroy_remaining": int(destroy_count),
                "ability_name": "Callous Sacrifice",
            },
        )
        try:
            self.game.request_decision(request)
        except Exception:
            queue = getattr(self.game, "decision_queue", None)
            if queue is not None and hasattr(queue, "add"):
                queue.add(request)

    def _queue_recon_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_recon_element() or player is self.player:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key == "SHOOTING_PHASE":
            stratagem_name = "COURAGEOUS DIVERSION"
            candidates = self._recon_courageous_diversion_candidates()
            phase_label = "Shooting phase"
        elif phase_key == "CHARGE_PHASE":
            stratagem_name = "TANGLEFOOT GRENADES"
            candidates = self._recon_tanglefoot_grenades_candidates()
            phase_label = "Charge phase"
        else:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)(stratagem_name)
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_start":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() == phase_label.lower():
                return
        payload = {
            "event": "phase_start",
            "phase_name": phase_label,
            "phase": phase_label,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_recon_draw_them_out_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_recon_element():
            return
        enemy_root = self._am_root(unit)
        if enemy_root is None or self._am_owned_by_player(enemy_root, self.player):
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("DRAW THEM OUT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._recon_draw_them_out_candidates(enemy_unit=enemy_root, action=action)
        if not candidates:
            return
        enemy_id = self._am_sort_key(enemy_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("enemy_unit_id", "") or "") == enemy_id:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "enemy_unit_id": enemy_id,
            "candidates": list(candidates),
            "action": action,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_recon_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_recon_element() or player is self.player:
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("SCOUTING OUTRIDERS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._recon_scouting_outriders_candidates()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_end":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() == name_u:
                return
        payload = {
            "event": "phase_end",
            "phase_name": "Fight phase",
            "phase": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_recon_element_reinforcements_step_reactions(self, *, current_player: Any) -> None:
        if not self._is_recon_element():
            return
        if current_player is None or current_player is self.player:
            return
        if str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("SCRAMBLE FIELD")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._recon_scramble_field_candidates()
        if not candidates:
            return
        current_player_id = str(getattr(current_player, "id", "") or "")
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "reinforcements_step_start":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("current_player_id", "") or "") == current_player_id:
                return
        payload = {
            "event": "reinforcements_step_start",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "current_player_id": current_player_id,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _process_recon_tanglefoot_charge_declared(self, *, charging_unit: Any, target_units: Any) -> None:
        if not self._is_recon_element():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        charging_root = self._am_root(charging_unit)
        if charging_root is None or self._am_owned_by_player(charging_root, self.player):
            return
        for target in self._am_resolve_unit_list(target_units):
            if not self._am_owned_by_player(target, self.player):
                continue
            sr = getattr(target, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("recon_tanglefoot_grenades_active", False)):
                continue
            source_name = str(sr.get("recon_tanglefoot_grenades_source", "") or "TANGLEFOOT GRENADES").strip() or "TANGLEFOOT GRENADES"
            charging_sr = getattr(charging_root, "special_rules", None)
            if not isinstance(charging_sr, dict):
                charging_sr = {}
            modifiers = [
                entry
                for entry in list(charging_sr.get("charge_roll_modifiers", []) or [])
                if not (isinstance(entry, dict) and str(entry.get("source_key", "") or "") == "astra_militarum_tanglefoot_grenades")
            ]
            modifiers.append(
                {
                    "value": -2,
                    "source": source_name,
                    "source_key": "astra_militarum_tanglefoot_grenades",
                    "tag": "stratagem:astra_militarum_tanglefoot_grenades",
                }
            )
            charging_sr["charge_roll_modifiers"] = modifiers
            charging_sr["astra_militarum_tanglefoot_grenades_source"] = source_name
            charging_sr["astra_militarum_tanglefoot_grenades_turn"] = int(getattr(game, "turn", 0) or 0)
            charging_sr["astra_militarum_tanglefoot_grenades_turn_owner"] = str(getattr(self.player, "id", "") or "")
            charging_root.special_rules = charging_sr
            self._am_apply_pending_charge_roll_modifier(charging_root, value=-2, source=source_name)
            return

    def _queue_mechanised_swift_interception_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_mechanised_assault():
            return
        enemy_root = self._am_root(unit)
        if enemy_root is None or self._am_owned_by_player(enemy_root, self.player):
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("SWIFT INTERCEPTION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._mechanised_swift_interception_candidates(enemy_unit=enemy_root, action=action)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("event") != "unit_move_ended":
                continue
            if reaction.get("enemy_unit") is enemy_root:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "candidates": list(candidates),
            "action": action,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_mechanised_hasty_extraction_charge_reactions(
        self,
        *,
        charging_unit: Any,
        target_units: Any,
    ) -> None:
        if not self._is_mechanised_assault():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        charging_root = self._am_root(charging_unit)
        if charging_root is None or self._am_owned_by_player(charging_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("HASTY EXTRACTION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._mechanised_hasty_extraction_candidates(
            charging_unit=charging_root,
            target_units=target_units,
        )
        if not candidates:
            return
        charging_id = self._am_sort_key(charging_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("event") != "charge_declared":
                continue
            if str(reaction.get("charging_unit_id", "") or "") == charging_id:
                return
        payload = {
            "event": "charge_declared",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "charging_unit": charging_root,
            "charging_unit_id": charging_id,
            "target_units": list(target_units or []),
            "candidates": list(candidates),
        }
        unique_target_ids = {
            str(candidate.get("target_unit_id", "") or "")
            for candidate in list(candidates)
            if isinstance(candidate, dict)
        }
        if len(unique_target_ids) == 1:
            only_target_id = next(iter(unique_target_ids))
            for candidate in list(candidates):
                if str(candidate.get("target_unit_id", "") or "") != only_target_id:
                    continue
                payload["unit"] = candidate.get("target_unit")
                payload["target_unit"] = candidate.get("target_unit")
                break
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_mechanised_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_mechanised_assault():
            return
        if player is self.player:
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("MOVE OUT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._mechanised_move_out_candidates()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("event") == "phase_end":
                return
        payload = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
        }
        unique_target_ids = {
            str(candidate.get("target_unit_id", "") or "")
            for candidate in list(candidates)
            if isinstance(candidate, dict)
        }
        if len(unique_target_ids) == 1:
            only_target_id = next(iter(unique_target_ids))
            for candidate in list(candidates):
                if str(candidate.get("target_unit_id", "") or "") != only_target_id:
                    continue
                payload["unit"] = candidate.get("target_unit")
                payload["target_unit"] = candidate.get("target_unit")
                break
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_armoured_infantry_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_armoured_infantry():
            return
        if player is not self.player:
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "MOVEMENT_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("BURST OF SPEED")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._armoured_infantry_burst_of_speed_candidates()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("event") == "phase_end":
                return
        payload = {
            "event": "phase_end",
            "phase": "Movement phase",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_armoured_infantry_mobile_firebase_reactions(self, *, unit: Any, action: str) -> None:
        action_key = str(action or "").strip().lower()
        if action_key not in {"advance", "fall_back", "fallback"}:
            return
        if not self._is_armoured_infantry():
            return
        root = self._am_root(unit)
        if root is None or not self._am_owned_by_player(root, self.player):
            return
        if not self._am_on_battlefield(root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        if not self._is_astra_militarum_unit(root):
            return
        if not (self._am_has_keyword(root, "ARMOURED") and self._am_has_keyword(root, "SKIRMISHER")):
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("MOBILE FIREBASE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        canonical_action = "fall_back" if action_key in {"fall_back", "fallback"} else "advance"
        if canonical_action == "advance":
            if not bool(getattr(getattr(root, "round_state", None), "advanced_this_round", False)):
                return
        elif not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("event") != "unit_move_ended":
                continue
            if reaction.get("unit") is root:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "candidates": [root],
            "action": canonical_action,
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_combined_arms_stalwart_protector_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None or not self._is_combined_arms():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._am_root(attacking_unit)
        if attacker_root is None or self._am_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("STALWART PROTECTOR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._combined_arms_stalwart_protector_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("event") != "shooting_targets_selected":
                continue
            if reaction.get("attacking_unit") is attacking_unit:
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_hammer_ablative_plating_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None or not self._is_hammer_of_the_emperor():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._am_root(attacking_unit)
        if attacker_root is None or self._am_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("ABLATIVE PLATING")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._hammer_ablative_plating_candidates(target_units=target_units)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("event") != "shooting_targets_selected":
                continue
            if reaction.get("attacking_unit") is attacker_root:
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_hammer_blazing_advance_reactions(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower() != "advance" or not self._is_hammer_of_the_emperor():
            return
        root = self._am_root(unit)
        if root is None or not self._am_owned_by_player(root, self.player):
            return
        if not self._am_on_battlefield(root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        if not self._is_astra_militarum_unit(root) or not self._am_has_keyword(root, "SQUADRON"):
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("BLAZING ADVANCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("event") != "unit_move_ended":
                continue
            if reaction.get("unit") is root:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "candidates": [root],
            "action": "advance",
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_hammer_tactical_withdrawal_reactions(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower() != "fall_back" or not self._is_hammer_of_the_emperor():
            return
        root = self._am_root(unit)
        if root is None or not self._am_owned_by_player(root, self.player):
            return
        if not self._am_on_battlefield(root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        if not self._is_astra_militarum_unit(root) or not self._am_has_keyword(root, "SQUADRON"):
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("TACTICAL WITHDRAWAL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("event") != "unit_move_ended":
                continue
            if reaction.get("unit") is root:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "candidates": [root],
            "action": "fall_back",
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_combined_arms_unit_destroyed_reactions(
        self,
        *,
        destroyed_unit: Any,
        destroyed_by_unit: Any = None,
    ) -> None:
        if destroyed_unit is None or not self._is_combined_arms():
            return
        used_once = getattr(self, "_used_once_per_battle", None)
        if isinstance(used_once, dict) and bool(used_once.get("REINFORCEMENTS!", False)):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("REINFORCEMENTS!")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._combined_arms_reinforcements_candidates(destroyed_unit=destroyed_unit)
        if not candidates:
            return
        destroyed_root = candidates[0]
        destroyed_id = self._am_sort_key(destroyed_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("destroyed_unit_id", "") or "") == destroyed_id:
                return
        payload = {
            "event": "unit_destroyed",
            "phase_name": str(getattr(self, "_current_phase_name", "") or "").strip() or "Any phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "destroyed_unit": destroyed_root,
            "destroyed_unit_id": destroyed_id,
            "destroyed_by_unit": self._am_root(destroyed_by_unit),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _on_unit_shooting_resolved_bridgehead_servo_designators(
        self,
        attacker_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self._is_bridgehead_strike():
            return
        current_phase = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if current_phase != "SHOOTING_PHASE":
            return
        source_root = self._am_root(attacker_unit)
        if source_root is None:
            return
        attacker_army = getattr(source_root, "get_parent_army", lambda: None)()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is not self.player:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        if not self._am_on_battlefield(source_root):
            return
        if not self._is_astra_militarum_unit(source_root) or not self._am_has_keyword(source_root, "INFANTRY"):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("SERVO-DESIGNATORS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if (str(getattr(stratagem, "name", "") or "").strip().upper()) in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for target_unit, hits in list((hits_by_target or {}).items()):
            target_root = self._am_root(target_unit)
            if target_root is None:
                continue
            if int(hits or 0) <= 0:
                continue
            if not self._am_is_alive(target_root):
                continue
            if self._am_owned_by_player(target_root, self.player):
                continue
            if not self._am_is_visible_to_unit(source_root, target_root):
                continue
            uid = self._am_sort_key(target_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            candidates.append(target_root)
        candidates = sorted(candidates, key=self._am_sort_key)
        if not candidates:
            return
        if self._bridgehead_reaction_exists("unit_shooting_resolved", stratagem.name):
            return
        if not bool(stratagem.can_use(self.player, self.game, unit=source_root, candidates=candidates, phase_name="Shooting phase")):
            return
        self._queue_reaction(
            {
                "event": "unit_shooting_resolved",
                "phase": "Shooting phase",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": source_root,
                "target_unit": source_root,
                "candidates": candidates,
            },
            use_timer=False,
        )

    def _armoured_infantry_combined_fire_hit_candidates(
        self,
        source_unit: Any,
        hits_by_target: Any,
    ) -> list[Any]:
        source_root = self._am_root(source_unit)
        if source_root is None:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for target_unit, hits in list((hits_by_target or {}).items()):
            target_root = self._am_root(target_unit)
            if target_root is None:
                continue
            if int(hits or 0) <= 0:
                continue
            if not self._am_is_alive(target_root):
                continue
            if self._am_owned_by_player(target_root, self.player):
                continue
            uid = self._am_sort_key(target_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            candidates.append(target_root)
        return sorted(candidates, key=self._am_sort_key)

    def _armoured_infantry_opening_salvo_candidates(self) -> list[Any]:
        if not self._is_armoured_infantry():
            return []
        mgr = self._get_astra_militarum_mgr()
        disembarked_fn = (
            getattr(mgr, "_attached_unit_disembarked_from_transport_this_round", None)
            if mgr is not None
            else None
        )
        candidates: list[Any] = []
        for unit in self._am_battlefield_units(require_not_shot=True):
            root = self._am_root(unit)
            if root is None:
                continue
            if callable(disembarked_fn):
                if not bool(disembarked_fn(root)):
                    continue
            else:
                round_state = getattr(root, "round_state", None)
                if not bool(getattr(round_state, "disembarked_this_round", False)):
                    continue
                if not str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip():
                    continue
            candidates.append(root)
        return sorted(candidates, key=self._am_sort_key)

    def _on_unit_shooting_resolved_armoured_infantry_combined_fire(
        self,
        attacker_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self._is_armoured_infantry():
            return
        current_phase = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if current_phase != "SHOOTING_PHASE":
            return
        source_root = self._am_root(attacker_unit)
        if source_root is None:
            return
        attacker_army = getattr(source_root, "get_parent_army", lambda: None)()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is not self.player:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        if not self._am_on_battlefield(source_root):
            return
        if not self._is_astra_militarum_unit(source_root):
            return
        if not (self._am_has_keyword(source_root, "ARMOURED") and self._am_has_keyword(source_root, "SKIRMISHER")):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("COMBINED FIRE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates = self._armoured_infantry_combined_fire_hit_candidates(source_root, hits_by_target)
        if not candidates:
            return
        if self._bridgehead_reaction_exists("unit_shooting_resolved", stratagem.name):
            return
        if not bool(stratagem.can_use(self.player, self.game, unit=source_root, candidates=candidates, phase_name="Shooting phase")):
            return
        self._queue_reaction(
            {
                "event": "unit_shooting_resolved",
                "phase": "Shooting phase",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": source_root,
                "target_unit": source_root,
                "candidates": candidates,
            },
            use_timer=False,
        )

    def _queue_bridgehead_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_bridgehead_strike():
            return
        if player is self.player:
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return

        def _queue(name: str, candidates: list[Any]) -> None:
            stratagem = getattr(self, "get_by_name", lambda _name: None)(name)
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            if not candidates or self._bridgehead_reaction_exists("phase_end", stratagem.name):
                return
            if not bool(stratagem.can_use(self.player, self.game, unit=candidates[0], candidates=candidates, phase_name="Fight phase")):
                return
            self._queue_reaction(
                {
                    "event": "phase_end",
                    "phase": "Fight phase",
                    "phase_name": "Fight phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "candidates": list(candidates),
                },
                use_timer=False,
            )

        _queue("AERIAL EXTRACTION", self._bridgehead_aerial_extraction_candidates())
        _queue("ON MY POSITION", self._bridgehead_on_my_position_candidates())

    def _use_bridgehead_bellicosa_drop(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BELLICOSA DROP: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: BELLICOSA DROP: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BELLICOSA DROP: not your Movement phase")
            return False
        if root not in self._bridgehead_bellicosa_drop_candidates():
            logger.error("ERROR: BELLICOSA DROP: target must be ASTRA MILITARUM INFANTRY in Reserves with Deep Strike")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bridgehead_bellicosa_deep_strike_min_distance"] = 6.0
        sr["bridgehead_bellicosa_expires_phase"] = "MOVEMENT_PHASE"
        sr["bridgehead_bellicosa_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["bridgehead_bellicosa_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["bridgehead_bellicosa_no_charge_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["bridgehead_bellicosa_no_charge_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["bridgehead_bellicosa_source"] = str(getattr(stratagem, "name", "") or "BELLICOSA DROP")
        root.special_rules = sr
        ability_cache = getattr(root, "_ability_cache", None)
        if isinstance(ability_cache, dict):
            ability_cache.pop("deep_strike", None)
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: BELLICOSA DROP: unit can Deep Strike more than 6\" away and cannot charge this turn.")
        return True

    def _use_bridgehead_fire_and_relocate(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FIRE AND RELOCATE: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FIRE AND RELOCATE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FIRE AND RELOCATE: not your Shooting phase")
            return False
        if root not in self._bridgehead_fire_and_relocate_candidates():
            logger.error("ERROR: FIRE AND RELOCATE: target must be non-TITANIC ASTRA MILITARUM unit on the battlefield")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bridgehead_fire_and_relocate_active"] = True
        sr["bridgehead_fire_and_relocate_expires_phase"] = "SHOOTING_PHASE"
        sr["bridgehead_fire_and_relocate_owner"] = str(getattr(self.player, "id", "") or "")
        sr["bridgehead_fire_and_relocate_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["bridgehead_fire_and_relocate_source"] = str(getattr(stratagem, "name", "") or "FIRE AND RELOCATE")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: FIRE AND RELOCATE: unit can shoot after advancing this phase.")
        return True

    def _use_bridgehead_firing_hot(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FIRING HOT: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FIRING HOT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FIRING HOT: not your Shooting phase")
            return False
        if root not in self._bridgehead_firing_hot_candidates():
            logger.error("ERROR: FIRING HOT: target must be MILITARUM TEMPESTUS or Kasrkin and not yet shot")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bridgehead_firing_hot_active"] = True
        sr["bridgehead_firing_hot_expires_phase"] = "SHOOTING_PHASE"
        sr["bridgehead_firing_hot_owner"] = str(getattr(self.player, "id", "") or "")
        sr["bridgehead_firing_hot_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["bridgehead_firing_hot_source"] = str(getattr(stratagem, "name", "") or "FIRING HOT")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: FIRING HOT: hot-shot weapons gain +1 Strength and AP within 12\" this phase.")
        return True

    def _use_bridgehead_servo_designators(self, stratagem: Any, **kwargs) -> bool:
        source_unit = kwargs.get("unit") or kwargs.get("source_unit") or kwargs.get("target_unit")
        pending = None
        if source_unit is None or not list(kwargs.get("candidates") or []):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                name_u = self._normalize_stratagem_name(reaction.get("stratagem", "") or "")
                if name_u in {"SERVO-DESIGNATORS", "SERVOÃ¢â‚¬â€˜DESIGNATORS", "SERVOÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ËœDESIGNATORS"}:
                    pending = reaction
                    break
        if source_unit is None and pending is not None:
            source_unit = pending.get("unit") or pending.get("target_unit")
        if source_unit is None:
            logger.error("ERROR: SERVO-DESIGNATORS: no source unit provided")
            return False
        root = self._am_root(source_unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SERVO-DESIGNATORS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SERVO-DESIGNATORS: not your Shooting phase")
            return False
        if not self._am_on_battlefield(root):
            logger.error("ERROR: SERVO-DESIGNATORS: source unit must be on the battlefield")
            return False
        if not self._is_astra_militarum_unit(root) or not self._am_has_keyword(root, "INFANTRY"):
            logger.error("ERROR: SERVO-DESIGNATORS: source unit must be ASTRA MILITARUM INFANTRY")
            return False
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        candidates = [self._am_root(candidate) for candidate in candidates if self._am_root(candidate) is not None]
        candidates = [
            candidate
            for candidate in candidates
            if self._am_is_alive(candidate) and not self._am_owned_by_player(candidate, self.player)
        ]
        candidates = sorted(candidates, key=self._am_sort_key)
        if not candidates:
            logger.error("ERROR: SERVO-DESIGNATORS: no eligible enemy units were hit and visible")
            return False
        direct_target = kwargs.get("enemy_unit") or kwargs.get("quarry") or kwargs.get("selected_unit")
        if direct_target is not None:
            target_root = self._am_root(direct_target)
            if target_root not in candidates:
                logger.error("ERROR: SERVO-DESIGNATORS: selected enemy unit is not eligible")
                return False
            if not self._am_spend_cp(stratagem, target_unit=root):
                return False
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_no_cover_active"] = True
            sr["post_shoot_no_cover_expires_phase"] = "SHOOTING_PHASE"
            sr["post_shoot_no_cover_source"] = str(getattr(stratagem, "name", "") or "SERVO-DESIGNATORS")
            sr["post_shoot_no_cover_owner"] = str(getattr(self.player, "id", "") or "")
            sr["post_shoot_no_cover_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
            target_root.special_rules = sr
            self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(f"INFO: SERVO-DESIGNATORS: {getattr(target_root, 'name', 'Unit')} loses Benefit of Cover this phase.")
            return True
        request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
        if self.game is None or not callable(request_decision):
            logger.error("ERROR: SERVO-DESIGNATORS: no decision queue available")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not self._queue_bridgehead_servo_designators_target_decision(
            stratagem=stratagem,
            source_unit=root,
            candidates=candidates,
        ):
            logger.error("ERROR: SERVO-DESIGNATORS: failed to queue target selection")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: SERVO-DESIGNATORS: choose a hit visible enemy unit to lose Benefit of Cover this phase.")
        return True

    def _use_bridgehead_aerial_extraction(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        pending = None
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() == "AERIAL EXTRACTION":
                    pending = reaction
                    break
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: AERIAL EXTRACTION: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: AERIAL EXTRACTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: AERIAL EXTRACTION: not opponent's Fight phase")
            return False
        if root not in self._bridgehead_aerial_extraction_candidates():
            logger.error("ERROR: AERIAL EXTRACTION: target must be eligible Deep Strike unit or Valkyrie not in Engagement Range")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        root.enter_strategic_reserves_midgame(
            game=self.game,
            game_map=getattr(self.game, "map", None),
            reason=str(getattr(stratagem, "name", "") or "AERIAL EXTRACTION"),
        )
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: AERIAL EXTRACTION: {getattr(root, 'name', 'Unit')} placed into Strategic Reserves.")
        return True

    def _use_bridgehead_on_my_position(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        pending = None
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() == "ON MY POSITION":
                    pending = reaction
                    break
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ON MY POSITION: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: ON MY POSITION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: ON MY POSITION: not opponent's Fight phase")
            return False
        if root not in self._bridgehead_on_my_position_candidates():
            logger.error("ERROR: ON MY POSITION: target must be engaged REGIMENT INFANTRY")
            return False

        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            logger.error("ERROR: ON MY POSITION: no game map available")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        enemy_targets: list[Any] = []
        seen: set[str] = set()
        for enemy in list(game_map.get_enemy_units(root) or []):
            enemy_root = self._am_root(enemy)
            if enemy_root is None or not self._am_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", True)):
                continue
            if self._am_is_in_reserves(enemy_root):
                continue
            if not bool(game_map.is_within_engagement_range(root, enemy_root)):
                continue
            uid = self._am_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            enemy_targets.append(enemy_root)
        for enemy_root in enemy_targets:
            if get_roll("D6") < 2:
                continue
            mortal_wounds = get_roll("D6")
            if mortal_wounds <= 0:
                continue
            root._apply_mortal_wounds_to_unit(enemy_root, mortal_wounds, game_map=game_map)
        self_mortals = get_roll("D3") + get_roll("D3") + get_roll("D3")
        if self_mortals > 0:
            root._apply_mortal_wounds_to_unit(root, self_mortals, game_map=game_map)
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: ON MY POSITION: resolved mortal wounds against engaged enemies and the target unit.")
        return True

    def _use_combined_arms_coordinated_action(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_combined_arms():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        if not phase_name:
            logger.error("ERROR: COORDINATED ACTION: phase context missing")
            return False
        regiment_unit = kwargs.get("regiment_unit") or kwargs.get("regiment")
        squadron_unit = kwargs.get("squadron_unit") or kwargs.get("squadron")
        if regiment_unit is not None and squadron_unit is not None:
            regiment_root = self._am_root(regiment_unit)
            squadron_root = self._am_root(squadron_unit)
            if regiment_root is None or squadron_root is None or regiment_root is squadron_root:
                logger.error("ERROR: COORDINATED ACTION: invalid regiment or squadron unit")
                return False
            eligible_regiments = self._combined_arms_coordinated_action_regiment_candidates()
            if regiment_root not in eligible_regiments:
                logger.error("ERROR: COORDINATED ACTION: selected REGIMENT unit is not eligible")
                return False
            eligible_squadrons = self._combined_arms_coordinated_action_squadron_candidates(regiment_root)
            if squadron_root not in eligible_squadrons:
                logger.error("ERROR: COORDINATED ACTION: selected SQUADRON unit is not eligible")
                return False
            get_army = getattr(self.player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(self.player, "army", None)
            voice = getattr(army, "voice_of_command", None) if army is not None else None
            if voice is None:
                logger.error("ERROR: COORDINATED ACTION: Voice of Command manager unavailable")
                return False
            if not self._am_spend_cp(stratagem, target_unit=regiment_root):
                return False
            if not bool(
                voice.set_coordinated_action_pair(
                    regiment_root,
                    squadron_root,
                    game=self.game,
                    phase_name=phase_name,
                    source=str(getattr(stratagem, "name", "") or "COORDINATED ACTION"),
                )
            ):
                logger.error("ERROR: COORDINATED ACTION: failed to activate paired order mirroring")
                return False
            self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: COORDINATED ACTION: %s and %s share orders until the end of the phase.",
                getattr(regiment_root, "name", "Regiment"),
                getattr(squadron_root, "name", "Squadron"),
            )
            return True
        if not bool(getattr(self.player, "has_control", lambda: False)()):
            logger.error("ERROR: COORDINATED ACTION: remote controllers must provide regiment_unit and squadron_unit")
            return False
        if not self._queue_combined_arms_coordinated_action_regiment_request(stratagem, phase_name=phase_name):
            logger.error("ERROR: COORDINATED ACTION: no eligible regiment/squadron pair available")
            return False
        logger.info("INFO: COORDINATED ACTION: queued regiment and squadron selection.")
        return True

    def _use_combined_arms_reinforcements(self, stratagem: Any, **kwargs) -> bool:
        destroyed_unit = kwargs.get("destroyed_unit") or kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if destroyed_unit is None or not candidates:
            pending = self._am_pending_reaction_by_names("REINFORCEMENTS!")
            if pending is not None:
                destroyed_unit = destroyed_unit or pending.get("destroyed_unit") or pending.get("unit") or pending.get("target_unit")
                if not candidates:
                    candidates = list(pending.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = pending.get("phase_name")
        if destroyed_unit is None and len(candidates) == 1:
            destroyed_unit = candidates[0]
        root = self._am_root(destroyed_unit)
        if root is None:
            logger.error("ERROR: REINFORCEMENTS!: no destroyed unit provided")
            return False
        used_once = getattr(self, "_used_once_per_battle", None)
        if isinstance(used_once, dict) and bool(used_once.get("REINFORCEMENTS!", False)):
            logger.error("ERROR: REINFORCEMENTS!: already used this battle")
            return False
        if not self._am_owned_by_player(root, self.player):
            logger.error("ERROR: REINFORCEMENTS!: target must be a friendly unit")
            return False
        if not self._is_astra_militarum_unit(root):
            logger.error("ERROR: REINFORCEMENTS!: target must be an ASTRA MILITARUM unit")
            return False
        if not self._am_has_keyword(root, "INFANTRY") or not self._am_has_keyword(root, "REGIMENT"):
            logger.error("ERROR: REINFORCEMENTS!: target must be an INFANTRY REGIMENT unit")
            return False
        if self._am_is_alive(root):
            logger.error("ERROR: REINFORCEMENTS!: target unit must have been just destroyed")
            return False
        is_battle_shocked = getattr(root, "is_battle_shocked", None)
        if callable(is_battle_shocked) and bool(is_battle_shocked()):
            logger.error("ERROR: REINFORCEMENTS!: target unit cannot be Battle-shocked")
            return False
        eligible = candidates or self._combined_arms_reinforcements_candidates(destroyed_unit=root)
        if not eligible or root not in list(eligible or []):
            logger.error("ERROR: REINFORCEMENTS!: target unit is not currently eligible")
            return False
        replacement = self._am_clone_reinforcements_unit(root)
        if replacement is None:
            logger.error("ERROR: REINFORCEMENTS!: failed to create replacement unit")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not self._am_prepare_unit_in_strategic_reserves(
            replacement,
            reason=str(getattr(stratagem, "name", "") or "REINFORCEMENTS!"),
        ):
            logger.error("ERROR: REINFORCEMENTS!: failed to place replacement unit into Strategic Reserves")
            return False
        if isinstance(used_once, dict):
            used_once["REINFORCEMENTS!"] = True
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REINFORCEMENTS!: added a new %s unit to Strategic Reserves at Starting Strength.",
            getattr(replacement, "name", "Unit"),
        )
        return True

    def _use_combined_arms_flexible_command(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_combined_arms():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: FLEXIBLE COMMAND: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FLEXIBLE COMMAND: not your Command phase")
            return False
        officers = self._combined_arms_flexible_command_officer_candidates()
        if not officers:
            logger.error("ERROR: FLEXIBLE COMMAND: no eligible OFFICER units available")
            return False
        mgr = self._get_astra_militarum_mgr()
        activate = getattr(mgr, "activate_combined_arms_flexible_command", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: FLEXIBLE COMMAND: detachment manager unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=officers[0]):
            return False
        applied = int(
            activate(
                officers,
                game=self.game,
                phase_name=phase_name,
                source=str(getattr(stratagem, "name", "") or "FLEXIBLE COMMAND"),
            )
            or 0
        )
        if applied <= 0:
            logger.error("ERROR: FLEXIBLE COMMAND: failed to activate cross-keyword order targeting")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: FLEXIBLE COMMAND: eligible officers can order both REGIMENT and SQUADRON units this phase.")
        return True

    def _use_combined_arms_fields_of_fire(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_combined_arms():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FIELDS OF FIRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FIELDS OF FIRE: not your Shooting phase")
            return False
        regiment_unit = kwargs.get("regiment_unit") or kwargs.get("regiment")
        squadron_unit = kwargs.get("squadron_unit") or kwargs.get("squadron")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("enemy")
        if regiment_unit is not None and squadron_unit is not None and enemy_unit is not None:
            regiment_root = self._am_root(regiment_unit)
            squadron_root = self._am_root(squadron_unit)
            enemy_root = self._am_root(enemy_unit)
            if regiment_root is None or squadron_root is None or enemy_root is None or regiment_root is squadron_root:
                logger.error("ERROR: FIELDS OF FIRE: invalid regiment, squadron or enemy target")
                return False
            eligible_regiments = self._combined_arms_fields_of_fire_regiment_candidates()
            if regiment_root not in eligible_regiments:
                logger.error("ERROR: FIELDS OF FIRE: selected REGIMENT unit is not eligible")
                return False
            eligible_squadrons = self._combined_arms_fields_of_fire_squadron_candidates(regiment_root)
            if squadron_root not in eligible_squadrons:
                logger.error("ERROR: FIELDS OF FIRE: selected SQUADRON unit is not eligible")
                return False
            eligible_enemies = self._combined_arms_fields_of_fire_enemy_candidates(regiment_root, squadron_root)
            if enemy_root not in eligible_enemies:
                logger.error("ERROR: FIELDS OF FIRE: selected enemy unit is not eligible")
                return False
            mgr = self._get_astra_militarum_mgr()
            activate = getattr(mgr, "activate_combined_arms_fields_of_fire", None) if mgr is not None else None
            if not callable(activate):
                logger.error("ERROR: FIELDS OF FIRE: detachment manager unavailable")
                return False
            if not self._am_spend_cp(stratagem, target_unit=regiment_root):
                return False
            if not bool(
                activate(
                    regiment_root,
                    squadron_root,
                    enemy_root,
                    game=self.game,
                    phase_name=phase_name,
                    source=str(getattr(stratagem, "name", "") or "FIELDS OF FIRE"),
                )
            ):
                logger.error("ERROR: FIELDS OF FIRE: failed to activate the AP bonus")
                return False
            self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: FIELDS OF FIRE: %s and %s gain AP vs %s until end of phase.",
                getattr(regiment_root, "name", "Regiment"),
                getattr(squadron_root, "name", "Squadron"),
                getattr(enemy_root, "name", "Enemy"),
            )
            return True
        if not bool(getattr(self.player, "has_control", lambda: False)()):
            logger.error(
                "ERROR: FIELDS OF FIRE: remote controllers must provide regiment_unit, squadron_unit and enemy_unit"
            )
            return False
        if not self._queue_combined_arms_fields_of_fire_regiment_request(stratagem, phase_name=phase_name):
            logger.error("ERROR: FIELDS OF FIRE: no eligible regiment, squadron and enemy combination available")
            return False
        logger.info("INFO: FIELDS OF FIRE: queued regiment, squadron and enemy selection.")
        return True

    def _use_combined_arms_inspired_command(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_combined_arms():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: INSPIRED COMMAND: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: INSPIRED COMMAND: not opponent's Command phase")
            return False
        officer_candidates = self._combined_arms_inspired_command_officer_candidates()
        if not officer_candidates:
            logger.error("ERROR: INSPIRED COMMAND: no eligible OFFICER units available")
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        if voice is None:
            logger.error("ERROR: INSPIRED COMMAND: Voice of Command manager unavailable")
            return False
        battle_round = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        officer = kwargs.get("officer_unit") or kwargs.get("officer") or kwargs.get("unit")
        target_unit = kwargs.get("order_target_unit") or kwargs.get("order_target") or kwargs.get("target_unit")
        order_key = str(kwargs.get("order_key") or kwargs.get("order") or "").strip().upper()
        if officer is not None and target_unit is not None and order_key:
            officer_root = self._am_root(officer)
            target_root = self._am_root(target_unit)
            if officer_root is None or target_root is None:
                logger.error("ERROR: INSPIRED COMMAND: invalid officer or target unit")
                return False
            if officer_root not in officer_candidates:
                logger.error("ERROR: INSPIRED COMMAND: selected officer is not eligible")
                return False
            available_orders = {
                str(getattr(order, "key", "") or "").strip().upper()
                for order in list(getattr(voice, "get_available_orders", lambda *_a, **_k: [])(officer_root) or [])
            }
            if order_key not in available_orders:
                logger.error("ERROR: INSPIRED COMMAND: selected officer cannot issue the chosen order")
                return False
            eligible_targets = list(getattr(voice, "get_eligible_targets", lambda *_a, **_k: [])(officer_root, game=self.game, order_key=order_key) or [])
            if target_root not in eligible_targets:
                logger.error("ERROR: INSPIRED COMMAND: selected target is not eligible for the chosen order")
                return False
            pending_officers = list(voice.start_inspired_command_pending([officer_root], battle_round) or [])
            if officer_root not in pending_officers:
                logger.error("ERROR: INSPIRED COMMAND: failed to register the pending inspired order")
                return False
            if not self._am_spend_cp(stratagem, target_unit=officer_root):
                voice.consume_inspired_command_skip(officer_root, game=self.game, battle_round=battle_round)
                return False
            ok = bool(
                voice.issue_order(
                    self.game,
                    officer_root,
                    target_root,
                    order_key,
                    phase_name=phase_name,
                    trigger="inspired_command",
                )
            )
            if not ok:
                voice.consume_inspired_command_skip(officer_root, game=self.game, battle_round=battle_round)
                logger.error("ERROR: INSPIRED COMMAND: failed to issue the selected order")
                return False
            self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: INSPIRED COMMAND: %s issued %s to %s.",
                getattr(officer_root, "name", "Officer"),
                order_key,
                getattr(target_root, "name", "Unit"),
            )
            return True
        if not bool(getattr(self.player, "has_control", lambda: False)()):
            logger.error(
                "ERROR: INSPIRED COMMAND: remote controllers must provide officer_unit, order_key and order_target_unit"
            )
            return False
        if not self._am_has_voice_prompt_subscriber():
            logger.error("ERROR: INSPIRED COMMAND: no Voice of Command prompt subscriber available")
            return False
        pending_officers = list(voice.start_inspired_command_pending(officer_candidates, battle_round) or [])
        if not pending_officers:
            logger.error("ERROR: INSPIRED COMMAND: failed to register pending officers")
            return False
        if not self._am_spend_cp(stratagem, target_unit=pending_officers[0]):
            voice.consume_inspired_command_skip(pending_officers[0], game=self.game, battle_round=battle_round)
            return False
        event_system = getattr(self.game, "event_system", None) if self.game is not None else None
        publish = getattr(event_system, "publish", None) if event_system is not None else None
        if not callable(publish):
            voice.consume_inspired_command_skip(pending_officers[0], game=self.game, battle_round=battle_round)
            logger.error("ERROR: INSPIRED COMMAND: event system unavailable for Voice of Command prompt")
            return False
        publish(
            "voice_of_command_prompt",
            player=self.player,
            game=self.game,
            phase_name=str(phase_name or "").strip().upper(),
            trigger="inspired_command",
        )
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: INSPIRED COMMAND: resolve one Voice of Command order now.")
        return True

    def _use_combined_arms_stalwart_protector(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_combined_arms():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: STALWART PROTECTOR: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: STALWART PROTECTOR: not opponent's Shooting phase")
            return False
        vehicle_unit = kwargs.get("vehicle_unit") or kwargs.get("vehicle") or kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if vehicle_unit is None or (not target_units and not candidates):
            pending = self._am_pending_reaction_by_names("STALWART PROTECTOR")
            if pending is not None:
                vehicle_unit = vehicle_unit or pending.get("unit") or pending.get("target_unit")
                attacking_unit = attacking_unit or pending.get("attacking_unit") or pending.get("enemy_unit")
                if not target_units:
                    target_units = list(pending.get("target_units") or [])
                if not candidates:
                    candidates = list(pending.get("candidates") or [])
        if vehicle_unit is None and len(candidates) == 1:
            vehicle_unit = candidates[0]
        vehicle_root = self._am_root(vehicle_unit)
        attacker_root = self._am_root(attacking_unit)
        if vehicle_root is None:
            logger.error("ERROR: STALWART PROTECTOR: no vehicle unit provided")
            return False
        eligible = candidates or self._combined_arms_stalwart_protector_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or vehicle_root not in list(eligible or []):
            logger.error("ERROR: STALWART PROTECTOR: selected vehicle is not eligible")
            return False
        mgr = self._get_astra_militarum_mgr()
        activate = getattr(mgr, "activate_combined_arms_stalwart_protector", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: STALWART PROTECTOR: detachment manager unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=vehicle_root):
            return False
        if not bool(
            activate(
                vehicle_root,
                game=self.game,
                phase_name=phase_name,
                source=str(getattr(stratagem, "name", "") or "STALWART PROTECTOR"),
            )
        ):
            logger.error("ERROR: STALWART PROTECTOR: failed to activate cover protection")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: STALWART PROTECTOR: %s now grants cover to obscured INFANTRY until end of phase.",
            getattr(vehicle_root, "name", "Vehicle"),
        )
        return True

    def _use_hammer_ablative_plating(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hammer_of_the_emperor():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: ABLATIVE PLATING: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: ABLATIVE PLATING: not opponent's Shooting phase")
            return False
        vehicle_unit = kwargs.get("vehicle_unit") or kwargs.get("vehicle") or kwargs.get("unit") or kwargs.get("target_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if vehicle_unit is None or not candidates:
            pending = self._am_pending_reaction_by_names("ABLATIVE PLATING")
            if pending is not None:
                vehicle_unit = vehicle_unit or pending.get("unit") or pending.get("target_unit")
                if not target_units:
                    target_units = list(pending.get("target_units") or [])
                if not candidates:
                    candidates = list(pending.get("candidates") or [])
        if vehicle_unit is None and len(candidates) == 1:
            vehicle_unit = candidates[0]
        vehicle_root = self._am_root(vehicle_unit)
        if vehicle_root is None:
            logger.error("ERROR: ABLATIVE PLATING: no vehicle unit provided")
            return False
        eligible = candidates or self._hammer_ablative_plating_candidates(target_units=target_units)
        if not eligible or vehicle_root not in list(eligible or []):
            logger.error("ERROR: ABLATIVE PLATING: selected vehicle is not eligible")
            return False
        if not self._am_spend_cp(stratagem, target_unit=vehicle_root):
            return False
        entry = {
            "value": 1,
            "attack_type": "ranged",
            "expires_phase": "SHOOTING_PHASE",
            "source": str(getattr(stratagem, "name", "") or "ABLATIVE PLATING"),
        }
        self._append_defensive_effect(vehicle_root, "defensive_damage_reductions", entry)
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ABLATIVE PLATING: %s reduces incoming ranged attack Damage by 1 until end of phase.",
            getattr(vehicle_root, "name", "Vehicle"),
        )
        return True

    def _use_hammer_blazing_advance(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hammer_of_the_emperor():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        if phase_name.lower() != "movement phase":
            logger.error("ERROR: BLAZING ADVANCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BLAZING ADVANCE: not your Movement phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or not candidates:
            pending = self._am_pending_reaction_by_names("BLAZING ADVANCE")
            if pending is not None:
                unit = unit or pending.get("unit") or pending.get("target_unit")
                if not candidates:
                    candidates = list(pending.get("candidates") or [])
                kwargs.setdefault("action", pending.get("action"))
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: BLAZING ADVANCE: no SQUADRON unit provided")
            return False
        if str(kwargs.get("action", "") or "").strip().lower() not in ("", "advance"):
            logger.error("ERROR: BLAZING ADVANCE: invalid trigger")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "advanced_this_round", False)):
            logger.error("ERROR: BLAZING ADVANCE: target did not Advance this turn")
            return False
        if candidates and root not in list(candidates or []):
            logger.error("ERROR: BLAZING ADVANCE: selected unit is not eligible")
            return False
        mgr = self._get_astra_militarum_mgr()
        activate = getattr(mgr, "activate_hammer_of_the_emperor_blazing_advance", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: BLAZING ADVANCE: detachment manager unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not bool(activate(root, game=self.game, source=str(getattr(stratagem, "name", "") or "BLAZING ADVANCE"))):
            logger.error("ERROR: BLAZING ADVANCE: failed to activate shoot-after-Advance")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: BLAZING ADVANCE: %s can shoot after Advancing this turn.", getattr(root, "name", "Unit"))
        return True

    def _use_hammer_crash_through(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hammer_of_the_emperor():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        phase_key = phase_name.lower()
        if phase_key not in {"movement phase", "charge phase"}:
            logger.error("ERROR: CRASH THROUGH: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CRASH THROUGH: not your turn")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: CRASH THROUGH: no vehicle unit provided")
            return False
        eligible = candidates or self._hammer_crash_through_candidates(phase_name=phase_name)
        if not eligible or root not in list(eligible or []):
            logger.error("ERROR: CRASH THROUGH: selected vehicle is not eligible")
            return False
        mgr = self._get_astra_militarum_mgr()
        activate = getattr(mgr, "activate_hammer_of_the_emperor_crash_through", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: CRASH THROUGH: detachment manager unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not bool(
            activate(
                root,
                game=self.game,
                phase_name=phase_name,
                source=str(getattr(stratagem, "name", "") or "CRASH THROUGH"),
            )
        ):
            logger.error("ERROR: CRASH THROUGH: failed to activate movement override")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CRASH THROUGH: %s can move horizontally through terrain until end of phase.",
            getattr(root, "name", "Vehicle"),
        )
        return True

    def _use_hammer_final_hour(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hammer_of_the_emperor():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        if phase_name.lower() != "command phase":
            logger.error("ERROR: FINAL HOUR: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FINAL HOUR: not your Command phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: FINAL HOUR: no SQUADRON unit provided")
            return False
        eligible = candidates or self._hammer_final_hour_candidates()
        if not eligible or root not in list(eligible or []):
            logger.error("ERROR: FINAL HOUR: selected unit is not eligible")
            return False
        mgr = self._get_astra_militarum_mgr()
        activate = getattr(mgr, "activate_hammer_of_the_emperor_final_hour", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: FINAL HOUR: detachment manager unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not bool(activate(root, game=self.game, source=str(getattr(stratagem, "name", "") or "FINAL HOUR"))):
            logger.error("ERROR: FINAL HOUR: failed to activate the battle-round buff")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FINAL HOUR: %s gains hazardous ranged weapons and ignores ranged hit modifiers until end of battle round.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hammer_furious_cannonade(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hammer_of_the_emperor():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        if phase_name.lower() != "shooting phase":
            logger.error("ERROR: FURIOUS CANNONADE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FURIOUS CANNONADE: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: FURIOUS CANNONADE: no SQUADRON unit provided")
            return False
        eligible = candidates or self._hammer_furious_cannonade_candidates()
        if not eligible or root not in list(eligible or []):
            logger.error("ERROR: FURIOUS CANNONADE: selected unit is not eligible")
            return False
        mgr = self._get_astra_militarum_mgr()
        activate = getattr(mgr, "activate_hammer_of_the_emperor_furious_cannonade", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: FURIOUS CANNONADE: detachment manager unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not bool(
            activate(
                root,
                game=self.game,
                phase_name=phase_name,
                source=str(getattr(stratagem, "name", "") or "FURIOUS CANNONADE"),
            )
        ):
            logger.error("ERROR: FURIOUS CANNONADE: failed to activate AP bonus")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: FURIOUS CANNONADE: %s gains AP within 12\" this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_hammer_tactical_withdrawal(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hammer_of_the_emperor():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        if phase_name.lower() != "movement phase":
            logger.error("ERROR: TACTICAL WITHDRAWAL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: TACTICAL WITHDRAWAL: not your Movement phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or not candidates:
            pending = self._am_pending_reaction_by_names("TACTICAL WITHDRAWAL")
            if pending is not None:
                unit = unit or pending.get("unit") or pending.get("target_unit")
                if not candidates:
                    candidates = list(pending.get("candidates") or [])
                kwargs.setdefault("action", pending.get("action"))
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: TACTICAL WITHDRAWAL: no SQUADRON unit provided")
            return False
        if str(kwargs.get("action", "") or "").strip().lower() not in ("", "fall_back"):
            logger.error("ERROR: TACTICAL WITHDRAWAL: invalid trigger")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: TACTICAL WITHDRAWAL: target did not Fall Back this turn")
            return False
        if candidates and root not in list(candidates or []):
            logger.error("ERROR: TACTICAL WITHDRAWAL: selected unit is not eligible")
            return False
        mgr = self._get_astra_militarum_mgr()
        activate = getattr(mgr, "activate_hammer_of_the_emperor_tactical_withdrawal", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: TACTICAL WITHDRAWAL: detachment manager unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not bool(
            activate(
                root,
                game=self.game,
                source=str(getattr(stratagem, "name", "") or "TACTICAL WITHDRAWAL"),
            )
        ):
            logger.error("ERROR: TACTICAL WITHDRAWAL: failed to activate shoot-after-Fall Back")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TACTICAL WITHDRAWAL: %s can shoot after Falling Back this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_mechanised_vox_relay(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_mechanised_assault():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: VOX-RELAY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: VOX-RELAY: not your Command phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: VOX-RELAY: no embarked Infantry Officer provided")
            return False
        eligible = [self._am_root(candidate) for candidate in (candidates or self._mechanised_vox_relay_candidates()) if self._am_root(candidate) is not None]
        if not eligible or root not in eligible:
            logger.error("ERROR: VOX-RELAY: target must be an embarked ASTRA MILITARUM INFANTRY OFFICER")
            return False
        transport = self._am_root(getattr(root, "embarked_in", None))
        if transport is None:
            logger.error("ERROR: VOX-RELAY: target officer is not embarked in a Transport")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["mechanised_vox_relay_active"] = True
        sr["mechanised_vox_relay_expires_phase"] = "COMMAND_PHASE"
        sr["mechanised_vox_relay_owner"] = str(getattr(self.player, "id", "") or "")
        sr["mechanised_vox_relay_transport_id"] = self._am_sort_key(transport)
        sr["mechanised_vox_relay_source"] = str(getattr(stratagem, "name", "") or "VOX-RELAY")
        if self.game is not None:
            sr["mechanised_vox_relay_turn"] = int(getattr(self.game, "turn", 0) or 0)
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: VOX-RELAY: %s can issue Orders while embarked and can order friendly non-TITANIC Transports regardless of distance this phase.",
            getattr(root, "name", "Officer"),
        )
        return True

    def _use_mechanised_rapid_dispersal(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_mechanised_assault():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: RAPID DISPERSAL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: RAPID DISPERSAL: not your Movement phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: RAPID DISPERSAL: no target unit provided")
            return False
        eligible = [self._am_root(candidate) for candidate in (candidates or self._mechanised_rapid_dispersal_candidates()) if self._am_root(candidate) is not None]
        if not eligible or root not in eligible:
            logger.error("ERROR: RAPID DISPERSAL: target must be ASTRA MILITARUM INFANTRY that disembarked from a Transport this phase")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: RAPID DISPERSAL: reactive move queue unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        try:
            roll = get_roll("D6")
        except (TypeError, ValueError):
            roll = 0
        if roll <= 0:
            roll = 1
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(roll),
            kind="astra_militarum_rapid_dispersal",
            movement_type="move",
            reactive_movement_type="rapid_dispersal",
            source=str(getattr(stratagem, "name", "RAPID DISPERSAL") or "RAPID DISPERSAL"),
        )
        if request is None:
            logger.error("ERROR: RAPID DISPERSAL: failed to queue movement decision")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RAPID DISPERSAL: %s can make a Normal move of up to %s\".",
            getattr(root, "name", "Unit"),
            int(roll),
        )
        return True

    def _use_armoured_infantry_burst_of_speed(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_armoured_infantry():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: BURST OF SPEED: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BURST OF SPEED: not your Movement phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or not candidates:
            pending = self._am_pending_reaction_by_names("BURST OF SPEED")
            if pending is not None:
                unit = unit or pending.get("unit") or pending.get("target_unit")
                if not candidates:
                    candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: BURST OF SPEED: no target unit provided")
            return False
        eligible = [
            self._am_root(candidate)
            for candidate in (candidates or self._armoured_infantry_burst_of_speed_candidates())
            if self._am_root(candidate) is not None
        ]
        if not eligible or root not in eligible:
            logger.error(
                "ERROR: BURST OF SPEED: target must be an ASTRA MILITARUM unit that did not Remain Stationary or arrive from Reserves this phase"
            )
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: BURST OF SPEED: reactive move queue unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        try:
            roll = get_roll("D6")
        except (TypeError, ValueError):
            roll = 0
        if roll <= 0:
            roll = 1
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(roll),
            kind="astra_militarum_armoured_infantry_burst_of_speed",
            movement_type="move",
            reactive_movement_type="armoured_infantry_burst_of_speed",
            source=str(getattr(stratagem, "name", "BURST OF SPEED") or "BURST OF SPEED"),
        )
        if request is None:
            logger.error("ERROR: BURST OF SPEED: failed to queue movement decision")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BURST OF SPEED: %s can make a Normal move of up to %s\".",
            getattr(root, "name", "Unit"),
            int(roll),
        )
        return True

    def _use_armoured_infantry_combined_fire(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_armoured_infantry():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: COMBINED FIRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: COMBINED FIRE: not your Shooting phase")
            return False
        source_unit = kwargs.get("unit") or kwargs.get("source_unit") or kwargs.get("target_unit")
        pending = None
        if source_unit is None or not list(kwargs.get("candidates") or []):
            pending = self._am_pending_reaction_by_names("COMBINED FIRE")
        if source_unit is None and pending is not None:
            source_unit = pending.get("unit") or pending.get("target_unit")
        source_root = self._am_root(source_unit)
        if source_root is None:
            logger.error("ERROR: COMBINED FIRE: no source unit provided")
            return False
        if not self._am_on_battlefield(source_root):
            logger.error("ERROR: COMBINED FIRE: source unit must be on the battlefield")
            return False
        if not self._is_astra_militarum_unit(source_root):
            logger.error("ERROR: COMBINED FIRE: source unit must be ASTRA MILITARUM")
            return False
        if not (self._am_has_keyword(source_root, "ARMOURED") and self._am_has_keyword(source_root, "SKIRMISHER")):
            logger.error("ERROR: COMBINED FIRE: source unit must be ARMOURED SKIRMISHER")
            return False
        if pending is None and not bool(getattr(getattr(source_root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: COMBINED FIRE: source unit has not shot")
            return False
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        if not candidates:
            candidates = self._armoured_infantry_combined_fire_hit_candidates(
                source_root,
                kwargs.get("hits_by_target") or {},
            )
        candidates = [self._am_root(candidate) for candidate in candidates if self._am_root(candidate) is not None]
        candidates = sorted(candidates, key=self._am_sort_key)
        if not candidates:
            logger.error("ERROR: COMBINED FIRE: no eligible enemy units were hit")
            return False
        direct_target = kwargs.get("enemy_unit") or kwargs.get("quarry") or kwargs.get("selected_unit")
        if direct_target is not None:
            target_root = self._am_root(direct_target)
            if target_root not in candidates:
                logger.error("ERROR: COMBINED FIRE: selected enemy unit is not eligible")
                return False
            mgr = self._get_astra_militarum_mgr()
            marker = getattr(mgr, "mark_armoured_infantry_combined_fire_target", None) if mgr is not None else None
            if not callable(marker):
                logger.error("ERROR: COMBINED FIRE: detachment manager unavailable")
                return False
            if not self._am_spend_cp(stratagem, target_unit=source_root):
                return False
            if not bool(
                marker(
                    target_root,
                    game=self.game,
                    player=self.player,
                    phase_name=phase_name,
                    source=str(getattr(stratagem, "name", "") or "COMBINED FIRE"),
                )
            ):
                logger.error("ERROR: COMBINED FIRE: failed to mark target")
                return False
            self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: COMBINED FIRE: %s loses cover and is vulnerable to ARMOURED SKIRMISHER fire.",
                getattr(target_root, "name", "Unit"),
            )
            return True
        request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
        if self.game is None or not callable(request_decision):
            logger.error("ERROR: COMBINED FIRE: no decision queue available")
            return False
        if not self._am_spend_cp(stratagem, target_unit=source_root):
            return False
        if not self._queue_armoured_infantry_combined_fire_target_decision(
            stratagem=stratagem,
            source_unit=source_root,
            candidates=candidates,
        ):
            logger.error("ERROR: COMBINED FIRE: failed to queue target selection")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: COMBINED FIRE: choose a hit enemy unit to mark.")
        return True

    def _use_armoured_infantry_mobile_firebase(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_armoured_infantry():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: MOBILE FIREBASE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MOBILE FIREBASE: not your Movement phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or not candidates:
            pending = self._am_pending_reaction_by_names("MOBILE FIREBASE")
            if pending is not None:
                unit = unit or pending.get("unit") or pending.get("target_unit")
                if not candidates:
                    candidates = list(pending.get("candidates") or [])
                kwargs.setdefault("action", pending.get("action"))
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: MOBILE FIREBASE: no ARMOURED SKIRMISHER unit provided")
            return False
        action_key = str(kwargs.get("action", "") or "").strip().lower()
        if action_key not in {"", "advance", "fall_back", "fallback"}:
            logger.error("ERROR: MOBILE FIREBASE: invalid trigger")
            return False
        if action_key == "":
            advanced = bool(getattr(getattr(root, "round_state", None), "advanced_this_round", False))
            fell_back = bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False))
            if advanced:
                action_key = "advance"
            elif fell_back:
                action_key = "fall_back"
        canonical_action = "fall_back" if action_key in {"fall_back", "fallback"} else "advance"
        if canonical_action == "advance":
            if not bool(getattr(getattr(root, "round_state", None), "advanced_this_round", False)):
                logger.error("ERROR: MOBILE FIREBASE: target did not Advance this turn")
                return False
        else:
            if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                logger.error("ERROR: MOBILE FIREBASE: target did not Fall Back this turn")
                return False
        if candidates and root not in list(candidates or []):
            logger.error("ERROR: MOBILE FIREBASE: selected unit is not eligible")
            return False
        if not self._am_on_battlefield(root):
            logger.error("ERROR: MOBILE FIREBASE: target must be on the battlefield")
            return False
        if not self._is_astra_militarum_unit(root):
            logger.error("ERROR: MOBILE FIREBASE: target must be ASTRA MILITARUM")
            return False
        if not (self._am_has_keyword(root, "ARMOURED") and self._am_has_keyword(root, "SKIRMISHER")):
            logger.error("ERROR: MOBILE FIREBASE: target must be ARMOURED SKIRMISHER")
            return False
        mgr = self._get_astra_militarum_mgr()
        activate = getattr(mgr, "activate_armoured_infantry_mobile_firebase", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: MOBILE FIREBASE: detachment manager unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not bool(
            activate(
                root,
                game=self.game,
                action=canonical_action,
                source=str(getattr(stratagem, "name", "") or "MOBILE FIREBASE"),
            )
        ):
            logger.error("ERROR: MOBILE FIREBASE: failed to activate shoot-after-move")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MOBILE FIREBASE: %s can shoot after Advancing or Falling Back this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_armoured_infantry_opening_salvo(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_armoured_infantry():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: OPENING SALVO: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: OPENING SALVO: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._armoured_infantry_opening_salvo_candidates()
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: OPENING SALVO: no target unit provided")
            return False
        if candidates and root not in list(candidates or []):
            logger.error("ERROR: OPENING SALVO: selected unit is not eligible")
            return False
        if not self._am_on_battlefield(root):
            logger.error("ERROR: OPENING SALVO: target must be on the battlefield")
            return False
        if not self._is_astra_militarum_unit(root):
            logger.error("ERROR: OPENING SALVO: target must be ASTRA MILITARUM")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: OPENING SALVO: target has already been selected to shoot")
            return False
        mgr = self._get_astra_militarum_mgr()
        disembarked_fn = (
            getattr(mgr, "_attached_unit_disembarked_from_transport_this_round", None)
            if mgr is not None
            else None
        )
        if callable(disembarked_fn):
            disembarked = bool(disembarked_fn(root))
        else:
            round_state = getattr(root, "round_state", None)
            disembarked = bool(getattr(round_state, "disembarked_this_round", False)) and bool(
                str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip()
            )
        if not disembarked:
            logger.error("ERROR: OPENING SALVO: target must have disembarked from a Transport this turn")
            return False
        activate = getattr(mgr, "activate_armoured_infantry_opening_salvo", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: OPENING SALVO: detachment manager unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not bool(
            activate(
                root,
                game=self.game,
                phase_name=phase_name,
                source=str(getattr(stratagem, "name", "") or "OPENING SALVO"),
            )
        ):
            logger.error("ERROR: OPENING SALVO: failed to activate wound bonus")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: OPENING SALVO: %s adds 1 to ranged Wound rolls until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_mechanised_clear_and_secure(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_mechanised_assault():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CLEAR AND SECURE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CLEAR AND SECURE: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: CLEAR AND SECURE: no target unit provided")
            return False
        eligible = [self._am_root(candidate) for candidate in (candidates or self._mechanised_clear_and_secure_candidates()) if self._am_root(candidate) is not None]
        if not eligible or root not in eligible:
            logger.error("ERROR: CLEAR AND SECURE: target must be ASTRA MILITARUM unit that disembarked this turn and has not shot")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["mechanised_clear_and_secure_active"] = True
        sr["mechanised_clear_and_secure_expires_phase"] = "SHOOTING_PHASE"
        sr["mechanised_clear_and_secure_owner"] = str(getattr(self.player, "id", "") or "")
        sr["mechanised_clear_and_secure_source"] = str(getattr(stratagem, "name", "") or "CLEAR AND SECURE")
        if self.game is not None:
            sr["mechanised_clear_and_secure_turn"] = int(getattr(self.game, "turn", 0) or 0)
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CLEAR AND SECURE: %s re-rolls Hit and Wound rolls for ranged attacks against targets within objective range this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_mechanised_swift_interception(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_mechanised_assault() or self.game is None:
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        action = kwargs.get("action")
        pending = None
        if unit is None or enemy_unit is None or not candidates:
            pending = self._am_pending_reaction_by_names("SWIFT INTERCEPTION")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if enemy_unit is None and pending is not None:
            enemy_unit = pending.get("enemy_unit")
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if action is None and pending is not None:
            action = pending.get("action")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        enemy_root = self._am_root(enemy_unit)
        if root is None or enemy_root is None:
            logger.error("ERROR: SWIFT INTERCEPTION: target Transport or enemy trigger unit missing")
            return False
        phase_name = str(kwargs.get("phase_name") or (pending.get("phase_name") if pending is not None else None) or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: SWIFT INTERCEPTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: SWIFT INTERCEPTION: only usable in your opponent's Movement phase")
            return False
        eligible = [
            self._am_root(candidate)
            for candidate in (candidates or self._mechanised_swift_interception_candidates(enemy_unit=enemy_root, action=action))
            if self._am_root(candidate) is not None
        ]
        if not eligible or root not in eligible:
            logger.error("ERROR: SWIFT INTERCEPTION: target must be an eligible friendly Transport within 9\" of the enemy mover")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: SWIFT INTERCEPTION: reactive move queue unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind="astra_militarum_swift_interception",
            movement_type="move",
            reactive_movement_type="swift_interception",
            source=str(getattr(stratagem, "name", "SWIFT INTERCEPTION") or "SWIFT INTERCEPTION"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            range_value=9,
        )
        if request is None:
            logger.error("ERROR: SWIFT INTERCEPTION: failed to queue reactive move")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SWIFT INTERCEPTION: %s can make a Normal move of up to 6\".",
            getattr(root, "name", "Transport"),
        )
        return True

    def _use_mechanised_hasty_extraction(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_mechanised_assault() or self.game is None:
            return False
        pending = self._am_pending_reaction_by_names("HASTY EXTRACTION")
        phase_name = str(kwargs.get("phase_name") or (pending.get("phase_name") if pending is not None else None) or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: HASTY EXTRACTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: HASTY EXTRACTION: only usable in your opponent's Charge phase")
            return False
        charging_unit = kwargs.get("charging_unit") or kwargs.get("enemy_unit") or (pending.get("charging_unit") if pending is not None else None)
        charging_root = self._am_root(charging_unit)
        if charging_root is None or self._am_owned_by_player(charging_root, self.player):
            logger.error("ERROR: HASTY EXTRACTION: charging unit missing or not enemy")
            return False
        target_units = list(kwargs.get("target_units") or (pending.get("target_units") if pending is not None else []) or [])
        pair_candidates = [
            dict(candidate or {})
            for candidate in list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
            if isinstance(candidate, dict)
        ]
        if not pair_candidates:
            pair_candidates = list(
                self._mechanised_hasty_extraction_candidates(
                    charging_unit=charging_root,
                    target_units=target_units,
                )
                or []
            )
        selected_target = self._am_root(kwargs.get("unit") or kwargs.get("target_unit"))
        if selected_target is not None:
            target_id = self._am_sort_key(selected_target)
            pair_candidates = [
                candidate
                for candidate in list(pair_candidates)
                if str(candidate.get("target_unit_id", "") or "") == target_id
            ]
        selected_transport = self._am_root(kwargs.get("transport_unit") or kwargs.get("transport"))
        if selected_transport is not None:
            transport_id = self._am_sort_key(selected_transport)
            pair_candidates = [
                candidate
                for candidate in list(pair_candidates)
                if str(candidate.get("transport_id", "") or "") == transport_id
            ]
        if not pair_candidates:
            logger.error("ERROR: HASTY EXTRACTION: no eligible embark pair available")
            return False
        target_for_cp = selected_target if selected_target is not None else self._am_root(pair_candidates[0].get("target_unit"))
        if target_for_cp is None:
            logger.error("ERROR: HASTY EXTRACTION: unable to resolve target Infantry unit")
            return False
        if not self._am_spend_cp(stratagem, target_unit=target_for_cp):
            return False
        self._am_remove_pending_charge_roll_request(charging_root)
        charging_unit_id = self._am_sort_key(charging_root)
        target_unit_ids = [
            self._am_sort_key(target)
            for target in self._am_resolve_unit_list(target_units)
            if self._am_sort_key(target)
        ]
        request = self._queue_mechanised_pair_embark_decision(
            ability="mechanised_hasty_extraction",
            ability_name=str(getattr(stratagem, "name", "") or "HASTY EXTRACTION"),
            prompt="Hasty Extraction: select the unit and Transport pair to embark.",
            candidates=pair_candidates,
            context={
                "phase": "Opponent Charge phase",
                "charging_unit_id": charging_unit_id,
                "target_unit_ids": list(target_unit_ids),
                "out_of_turn": False,
                "count_as_charged": True,
            },
            duplicate_match={"charging_unit_id": charging_unit_id},
            allow_skip=False,
        )
        if request is None:
            logger.error("ERROR: HASTY EXTRACTION: failed to queue embark choice")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: HASTY EXTRACTION: queued embark choice against %s.",
            getattr(charging_root, "name", "Enemy unit"),
        )
        return True

    def _use_mechanised_move_out(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_mechanised_assault() or self.game is None:
            return False
        pending = self._am_pending_reaction_by_names("MOVE OUT")
        phase_name = str(kwargs.get("phase_name") or (pending.get("phase_name") if pending is not None else None) or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: MOVE OUT: wrong phase trigger")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: MOVE OUT: only usable at the end of your opponent's turn")
            return False
        pair_candidates = [
            dict(candidate or {})
            for candidate in list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
            if isinstance(candidate, dict)
        ]
        if not pair_candidates:
            pair_candidates = list(self._mechanised_move_out_candidates() or [])
        selected_target = self._am_root(kwargs.get("unit") or kwargs.get("target_unit"))
        if selected_target is not None:
            target_id = self._am_sort_key(selected_target)
            pair_candidates = [
                candidate
                for candidate in list(pair_candidates)
                if str(candidate.get("target_unit_id", "") or "") == target_id
            ]
        selected_transport = self._am_root(kwargs.get("transport_unit") or kwargs.get("transport"))
        if selected_transport is not None:
            transport_id = self._am_sort_key(selected_transport)
            pair_candidates = [
                candidate
                for candidate in list(pair_candidates)
                if str(candidate.get("transport_id", "") or "") == transport_id
            ]
        if not pair_candidates:
            logger.error("ERROR: MOVE OUT: no eligible embark pair available")
            return False
        target_for_cp = selected_target if selected_target is not None else self._am_root(pair_candidates[0].get("target_unit"))
        if target_for_cp is None:
            logger.error("ERROR: MOVE OUT: unable to resolve target unit")
            return False
        if not self._am_spend_cp(stratagem, target_unit=target_for_cp):
            return False
        request = self._queue_mechanised_pair_embark_decision(
            ability="mechanised_turn_end_embark",
            ability_name=str(getattr(stratagem, "name", "") or "MOVE OUT"),
            prompt="Move Out: select the unit and Transport pair to embark.",
            candidates=pair_candidates,
            context={
                "phase": "End of opponent's turn",
            },
            allow_skip=False,
        )
        if request is None:
            logger.error("ERROR: MOVE OUT: failed to queue embark choice")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: MOVE OUT: queued end-of-turn embark choice.")
        return True

    def _use_recon_crack_shots(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_recon_element():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CRACK SHOTS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CRACK SHOTS: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: CRACK SHOTS: no target unit provided")
            return False
        eligible = [
            self._am_root(candidate)
            for candidate in (candidates or self._recon_crack_shots_candidates())
            if self._am_root(candidate) is not None
        ]
        if not eligible or root not in eligible:
            logger.error("ERROR: CRACK SHOTS: target must be a PLATOON unit that has not yet shot this phase")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        source = str(getattr(stratagem, "name", "") or "CRACK SHOTS").strip() or "CRACK SHOTS"
        for model_index, model in enumerate(list(getattr(root, "models", []) or [])):
            alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not is_alive:
                continue
            set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
            if not callable(set_keywords):
                continue
            weapon_names: list[str] = []
            for wargear in list(getattr(model, "wargear", []) or []):
                is_ranged = getattr(wargear, "is_ranged", None)
                if callable(is_ranged) and bool(is_ranged()):
                    weapon_name = str(getattr(wargear, "name", "") or "").strip()
                    if weapon_name:
                        weapon_names.append(weapon_name)
            for weapon_index, weapon_name in enumerate(weapon_names):
                set_keywords(
                    key=f"astra_militarum_recon_crack_shots:{maybe_entity_id(model)}:{model_index}:{weapon_index}",
                    weapon_name=weapon_name,
                    keywords=["PRECISION"],
                    source=source,
                    expires_phase="SHOOTING_PHASE",
                    attack_type="ranged",
                )
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CRACK SHOTS: %s gains [PRECISION] on ranged weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_recon_courageous_diversion(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_recon_element():
            return False
        pending = self._am_pending_reaction_by_names("COURAGEOUS DIVERSION")
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if pending is not None else None)
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: COURAGEOUS DIVERSION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: COURAGEOUS DIVERSION: only usable in your opponent's Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or (pending.get("unit") if pending is not None else None)
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: COURAGEOUS DIVERSION: no target unit provided")
            return False
        eligible = [
            self._am_root(candidate)
            for candidate in (candidates or self._recon_courageous_diversion_candidates())
            if self._am_root(candidate) is not None
        ]
        if not eligible or root not in eligible:
            logger.error("ERROR: COURAGEOUS DIVERSION: target must be an ASTRA MILITARUM INFANTRY or MOUNTED unit")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        source = str(getattr(stratagem, "name", "") or "COURAGEOUS DIVERSION").strip() or "COURAGEOUS DIVERSION"
        for model_index, model in enumerate(list(getattr(root, "models", []) or [])):
            alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not is_alive:
                continue
            set_fnp = getattr(model, "set_temporary_fnp", None)
            if not callable(set_fnp):
                continue
            set_fnp(
                key=f"astra_militarum_recon_courageous_diversion:{maybe_entity_id(model)}:{model_index}",
                value=6,
                source=source,
                expires_phase="SHOOTING_PHASE",
            )
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["recon_courageous_diversion_active"] = True
        sr["recon_courageous_diversion_source"] = source
        sr["recon_courageous_diversion_expires_phase"] = "SHOOTING_PHASE"
        sr["recon_courageous_diversion_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["recon_courageous_diversion_turn_owner"] = str(getattr(self.player, "id", "") or "")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: COURAGEOUS DIVERSION: %s gains Feel No Pain 6+ and its closest-eligible-target hit penalty this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_recon_draw_them_out(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_recon_element() or self.game is None:
            return False
        pending = self._am_pending_reaction_by_names("DRAW THEM OUT")
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if pending is not None else None)
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: DRAW THEM OUT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: DRAW THEM OUT: only usable in your opponent's Movement phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or (pending.get("unit") if pending is not None else None)
        enemy_unit = kwargs.get("enemy_unit") or (pending.get("enemy_unit") if pending is not None else None)
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        action = kwargs.get("action") or (pending.get("action") if pending is not None else None)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        enemy_root = self._am_root(enemy_unit)
        if root is None or enemy_root is None:
            logger.error("ERROR: DRAW THEM OUT: target unit or enemy mover missing")
            return False
        eligible = [
            self._am_root(candidate)
            for candidate in (candidates or self._recon_draw_them_out_candidates(enemy_unit=enemy_root, action=action))
            if self._am_root(candidate) is not None
        ]
        if not eligible or root not in eligible:
            logger.error("ERROR: DRAW THEM OUT: target must be an eligible PLATOON unit within 9\" and not in Engagement Range")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: DRAW THEM OUT: reactive move queue unavailable")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind="astra_militarum_draw_them_out",
            movement_type="move",
            reactive_movement_type="draw_them_out",
            source=str(getattr(stratagem, "name", "DRAW THEM OUT") or "DRAW THEM OUT"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            range_value=9,
            allow_skip=True,
        )
        if request is None:
            logger.error("ERROR: DRAW THEM OUT: failed to queue reactive move")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DRAW THEM OUT: %s can make a Normal move of up to 6\".",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_recon_scramble_field(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_recon_element():
            return False
        pending = self._am_pending_reaction_by_names("SCRAMBLE FIELD")
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if pending is not None else None)
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: SCRAMBLE FIELD: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SCRAMBLE FIELD: only usable in your opponent's Movement phase")
            return False
        if self.game is None or not bool(getattr(self.game, "reinforcements_step_active", False)):
            logger.error("ERROR: SCRAMBLE FIELD: Reinforcements step is not active")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or (pending.get("unit") if pending is not None else None)
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: SCRAMBLE FIELD: no target unit provided")
            return False
        eligible = [
            self._am_root(candidate)
            for candidate in (candidates or self._recon_scramble_field_candidates())
            if self._am_root(candidate) is not None
        ]
        if not eligible or root not in eligible:
            logger.error("ERROR: SCRAMBLE FIELD: target must be an ASTRA MILITARUM INFANTRY unit")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._get_astra_militarum_mgr()
        activate = getattr(mgr, "activate_recon_element_scramble_field", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: SCRAMBLE FIELD: detachment effect helper unavailable")
            return False
        activate(root, game=self.game, source=str(getattr(stratagem, "name", "") or "SCRAMBLE FIELD"))
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SCRAMBLE FIELD: enemy Reinforcements must remain outside 12\" of %s this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_recon_tanglefoot_grenades(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_recon_element():
            return False
        pending = self._am_pending_reaction_by_names("TANGLEFOOT GRENADES")
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if pending is not None else None)
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: TANGLEFOOT GRENADES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: TANGLEFOOT GRENADES: only usable in your opponent's Charge phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or (pending.get("unit") if pending is not None else None)
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: TANGLEFOOT GRENADES: no target unit provided")
            return False
        eligible = [
            self._am_root(candidate)
            for candidate in (candidates or self._recon_tanglefoot_grenades_candidates())
            if self._am_root(candidate) is not None
        ]
        if not eligible or root not in eligible:
            logger.error("ERROR: TANGLEFOOT GRENADES: target must be an ASTRA MILITARUM GRENADES unit")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["recon_tanglefoot_grenades_active"] = True
        sr["recon_tanglefoot_grenades_source"] = str(getattr(stratagem, "name", "") or "TANGLEFOOT GRENADES")
        sr["recon_tanglefoot_grenades_expires_phase"] = "CHARGE_PHASE"
        sr["recon_tanglefoot_grenades_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["recon_tanglefoot_grenades_turn_owner"] = str(getattr(self.player, "id", "") or "")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TANGLEFOOT GRENADES: enemies that charge %s suffer -2 to their Charge roll this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_recon_scouting_outriders(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_recon_element():
            return False
        pending = self._am_pending_reaction_by_names("SCOUTING OUTRIDERS")
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if pending is not None else None)
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SCOUTING OUTRIDERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SCOUTING OUTRIDERS: only usable at the end of your opponent's turn")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or (pending.get("unit") if pending is not None else None)
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: SCOUTING OUTRIDERS: no target unit provided")
            return False
        eligible = [
            self._am_root(candidate)
            for candidate in (candidates or self._recon_scouting_outriders_candidates())
            if self._am_root(candidate) is not None
        ]
        if not eligible or root not in eligible:
            logger.error(
                "ERROR: SCOUTING OUTRIDERS: target must be an ASTRA MILITARUM MOUNTED or WALKER unit wholly within 10\" of a battlefield edge and not in Engagement Range"
            )
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not self._am_prepare_unit_in_strategic_reserves(
            root,
            reason=str(getattr(stratagem, "name", "") or "SCOUTING OUTRIDERS"),
        ):
            logger.error("ERROR: SCOUTING OUTRIDERS: failed to move unit into Strategic Reserves")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SCOUTING OUTRIDERS: %s moves into Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_siege_callous_sacrifice(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_siege_regiment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CALLOUS SACRIFICE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CALLOUS SACRIFICE: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: CALLOUS SACRIFICE: no PLATOON unit provided")
            return False
        eligible = candidates or self._siege_callous_sacrifice_candidates()
        if not eligible or root not in list(eligible or []):
            logger.error("ERROR: CALLOUS SACRIFICE: selected unit is not eligible")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["siege_regiment_callous_sacrifice_active"] = True
        sr["siege_regiment_callous_sacrifice_expires_phase"] = "SHOOTING_PHASE"
        sr["siege_regiment_callous_sacrifice_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["siege_regiment_callous_sacrifice_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["siege_regiment_callous_sacrifice_source"] = str(getattr(stratagem, "name", "") or "CALLOUS SACRIFICE")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CALLOUS SACRIFICE: %s can target out of Engagement Range and may lose models after damaging engaged enemies this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_siege_flare_burst(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_siege_regiment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FLARE BURST: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FLARE BURST: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: FLARE BURST: no CHARACTER unit provided")
            return False
        eligible = candidates or self._siege_flare_burst_candidates()
        if not eligible or root not in list(eligible or []):
            logger.error("ERROR: FLARE BURST: selected unit is not eligible")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["siege_regiment_flare_burst_active"] = True
        sr["siege_regiment_flare_burst_expires_phase"] = "SHOOTING_PHASE"
        sr["siege_regiment_flare_burst_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["siege_regiment_flare_burst_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["siege_regiment_flare_burst_source"] = str(getattr(stratagem, "name", "") or "FLARE BURST")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: FLARE BURST: %s gains ranged hit re-rolls within 12\" this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_siege_furious_fusillade(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_siege_regiment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FURIOUS FUSILLADE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FURIOUS FUSILLADE: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: FURIOUS FUSILLADE: no PLATOON unit provided")
            return False
        eligible = candidates or self._siege_furious_fusillade_candidates()
        if not eligible or root not in list(eligible or []):
            logger.error("ERROR: FURIOUS FUSILLADE: selected unit is not eligible")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["siege_regiment_furious_fusillade_active"] = True
        sr["siege_regiment_furious_fusillade_expires_phase"] = "SHOOTING_PHASE"
        sr["siege_regiment_furious_fusillade_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["siege_regiment_furious_fusillade_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["siege_regiment_furious_fusillade_source"] = str(getattr(stratagem, "name", "") or "FURIOUS FUSILLADE")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: FURIOUS FUSILLADE: %s gains +1 ranged attack within half range this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_siege_minefield(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_siege_regiment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: MINEFIELD: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: MINEFIELD: not opponent's Charge phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or not candidates:
            pending = self._am_pending_reaction_by_names("MINEFIELD")
            if pending is not None:
                unit = unit or pending.get("unit") or pending.get("target_unit")
                if not candidates:
                    candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: MINEFIELD: no PLATOON unit provided")
            return False
        eligible = candidates or self._siege_minefield_candidates()
        if not eligible or root not in list(eligible or []):
            logger.error("ERROR: MINEFIELD: selected unit is not eligible")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["siege_regiment_minefield_active"] = True
        sr["siege_regiment_minefield_expires_phase"] = "CHARGE_PHASE"
        sr["siege_regiment_minefield_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["siege_regiment_minefield_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["siege_regiment_minefield_source"] = str(getattr(stratagem, "name", "") or "MINEFIELD")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: MINEFIELD: %s threatens charging enemies until end of phase.", getattr(root, "name", "Unit"))
        return True

    def _use_siege_over_the_top(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_siege_regiment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: OVER THE TOP: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: OVER THE TOP: not your Command phase")
            return False
        officer = kwargs.get("officer_unit") or kwargs.get("officer") or kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if officer is None or not candidates:
            pending = self._am_pending_reaction_by_names("OVER THE TOP")
            if pending is not None:
                officer = officer or pending.get("officer_unit") or pending.get("officer") or pending.get("unit") or pending.get("target_unit")
                if not candidates:
                    candidates = list(pending.get("candidates") or [])
        if officer is None and len(candidates) == 1:
            officer = candidates[0]
        if officer is None:
            logger.error("ERROR: OVER THE TOP: no Infantry Officer provided")
            return False
        officer_candidates = candidates or self._siege_over_the_top_candidates()
        selected_officer = None
        selected_id = self._am_sort_key(officer)
        for candidate in list(officer_candidates or []):
            if candidate is officer or self._am_sort_key(candidate) == selected_id:
                selected_officer = candidate
                break
        if selected_officer is None:
            logger.error("ERROR: OVER THE TOP: selected officer is not eligible")
            return False
        if not self._am_spend_cp(stratagem, target_unit=selected_officer):
            return False
        sr = getattr(selected_officer, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["siege_regiment_over_the_top_active"] = True
        sr["siege_regiment_over_the_top_expires_phase"] = "COMMAND_PHASE"
        sr["siege_regiment_over_the_top_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["siege_regiment_over_the_top_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["siege_regiment_over_the_top_source"] = str(getattr(stratagem, "name", "") or "OVER THE TOP")
        selected_officer.special_rules = sr
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        clear_pending = getattr(voice, "_clear_siege_over_the_top_pending", None) if voice is not None else None
        if callable(clear_pending):
            clear_pending(selected_officer)
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: OVER THE TOP: %s can issue Move! Move! Move! to any number of eligible Infantry Regiment units this phase.",
            getattr(selected_officer, "name", "Officer"),
        )
        return True

    def _use_siege_trench_fighters(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_siege_regiment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: TRENCH FIGHTERS: wrong phase")
            return False
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or not candidates:
            pending = self._am_pending_reaction_by_names("TRENCH FIGHTERS")
            if pending is not None:
                attacking_unit = attacking_unit or pending.get("attacking_unit") or pending.get("enemy_unit")
                if not target_units:
                    target_units = list(pending.get("target_units") or [])
                unit = unit or pending.get("unit") or pending.get("target_unit")
                if not candidates:
                    candidates = list(pending.get("candidates") or [])
        attacking_root = self._am_root(attacking_unit)
        if attacking_root is not None and self._am_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: TRENCH FIGHTERS: attacking unit must be an enemy unit")
            return False
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._am_root(unit)
        if root is None:
            logger.error("ERROR: TRENCH FIGHTERS: no target Infantry unit provided")
            return False
        eligible = candidates or self._siege_trench_fighters_candidates(
            attacking_unit=attacking_root,
            target_units=target_units,
        )
        if not eligible or root not in list(eligible or []):
            logger.error("ERROR: TRENCH FIGHTERS: selected unit is not eligible")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["siege_regiment_trench_fighters_active"] = True
        sr["siege_regiment_trench_fighters_expires_phase"] = "FIGHT_PHASE"
        sr["siege_regiment_trench_fighters_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["siege_regiment_trench_fighters_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["siege_regiment_trench_fighters_source"] = str(getattr(stratagem, "name", "") or "TRENCH FIGHTERS")
        root.special_rules = sr
        mgr = self._get_astra_militarum_mgr()
        clear_cache = getattr(mgr, "_clear_unit_ability_cache", None) if mgr is not None else None
        if callable(clear_cache):
            clear_cache(root)
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: TRENCH FIGHTERS: %s gains fight-on-death sequencing until end of phase.", getattr(root, "name", "Unit"))
        return True

    def _use_astra_militarum_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u == "ABLATIVE PLATING":
            return self._use_hammer_ablative_plating(stratagem, **kwargs)
        if name_u == "AERIAL EXTRACTION":
            return self._use_bridgehead_aerial_extraction(stratagem, **kwargs)
        if name_u == "BELLICOSA DROP":
            return self._use_bridgehead_bellicosa_drop(stratagem, **kwargs)
        if name_u == "BLAZING ADVANCE":
            return self._use_hammer_blazing_advance(stratagem, **kwargs)
        if name_u == "BURST OF SPEED":
            return self._use_armoured_infantry_burst_of_speed(stratagem, **kwargs)
        if name_u == "COMBINED FIRE":
            return self._use_armoured_infantry_combined_fire(stratagem, **kwargs)
        if name_u == "CLEAR AND SECURE":
            return self._use_mechanised_clear_and_secure(stratagem, **kwargs)
        if name_u == "COORDINATED ACTION":
            return self._use_combined_arms_coordinated_action(stratagem, **kwargs)
        if name_u == "COURAGEOUS DIVERSION":
            return self._use_recon_courageous_diversion(stratagem, **kwargs)
        if name_u == "CRACK SHOTS":
            return self._use_recon_crack_shots(stratagem, **kwargs)
        if name_u == "CRASH THROUGH":
            return self._use_hammer_crash_through(stratagem, **kwargs)
        if name_u == "CALLOUS SACRIFICE":
            return self._use_siege_callous_sacrifice(stratagem, **kwargs)
        if name_u == "DRAW THEM OUT":
            return self._use_recon_draw_them_out(stratagem, **kwargs)
        if name_u == "FLARE BURST":
            return self._use_siege_flare_burst(stratagem, **kwargs)
        if name_u == "FIRE AND RELOCATE":
            return self._use_bridgehead_fire_and_relocate(stratagem, **kwargs)
        if name_u == "FIELDS OF FIRE":
            return self._use_combined_arms_fields_of_fire(stratagem, **kwargs)
        if name_u == "FINAL HOUR":
            return self._use_hammer_final_hour(stratagem, **kwargs)
        if name_u == "FIRING HOT":
            return self._use_bridgehead_firing_hot(stratagem, **kwargs)
        if name_u == "FLEXIBLE COMMAND":
            return self._use_combined_arms_flexible_command(stratagem, **kwargs)
        if name_u == "FURIOUS CANNONADE":
            return self._use_hammer_furious_cannonade(stratagem, **kwargs)
        if name_u == "FURIOUS FUSILLADE":
            return self._use_siege_furious_fusillade(stratagem, **kwargs)
        if name_u == "HASTY EXTRACTION":
            return self._use_mechanised_hasty_extraction(stratagem, **kwargs)
        if name_u == "INSPIRED COMMAND":
            return self._use_combined_arms_inspired_command(stratagem, **kwargs)
        if name_u == "MINEFIELD":
            return self._use_siege_minefield(stratagem, **kwargs)
        if name_u == "MOBILE FIREBASE":
            return self._use_armoured_infantry_mobile_firebase(stratagem, **kwargs)
        if name_u == "MOVE OUT":
            return self._use_mechanised_move_out(stratagem, **kwargs)
        if name_u == "OPENING SALVO":
            return self._use_armoured_infantry_opening_salvo(stratagem, **kwargs)
        if name_u == "ON MY POSITION":
            return self._use_bridgehead_on_my_position(stratagem, **kwargs)
        if name_u == "OVER THE TOP":
            return self._use_siege_over_the_top(stratagem, **kwargs)
        if name_u == "RAPID DISPERSAL":
            return self._use_mechanised_rapid_dispersal(stratagem, **kwargs)
        if name_u == "REINFORCEMENTS!":
            return self._use_combined_arms_reinforcements(stratagem, **kwargs)
        if name_u == "SCOUTING OUTRIDERS":
            return self._use_recon_scouting_outriders(stratagem, **kwargs)
        if name_u == "SCRAMBLE FIELD":
            return self._use_recon_scramble_field(stratagem, **kwargs)
        if name_u in {"SERVO-DESIGNATORS", "SERVOÃ¢â‚¬â€˜DESIGNATORS", "SERVOÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ËœDESIGNATORS"}:
            return self._use_bridgehead_servo_designators(stratagem, **kwargs)
        if name_u == "STALWART PROTECTOR":
            return self._use_combined_arms_stalwart_protector(stratagem, **kwargs)
        if name_u == "SWIFT INTERCEPTION":
            return self._use_mechanised_swift_interception(stratagem, **kwargs)
        if name_u == "TANGLEFOOT GRENADES":
            return self._use_recon_tanglefoot_grenades(stratagem, **kwargs)
        if name_u == "TACTICAL WITHDRAWAL":
            return self._use_hammer_tactical_withdrawal(stratagem, **kwargs)
        if name_u == "TRENCH FIGHTERS":
            return self._use_siege_trench_fighters(stratagem, **kwargs)
        if name_u == "VOX-RELAY":
            return self._use_mechanised_vox_relay(stratagem, **kwargs)
        if name_u == "MORDIAN MINUTE":
            return self._use_grizzled_mordian_minute(stratagem, **kwargs)
        if name_u == "NO RETREAT!":
            return self._use_grizzled_no_retreat(stratagem, **kwargs)
        if name_u == "PURGING FIRE":
            return self._use_grizzled_purging_fire(stratagem, **kwargs)
        if name_u == "SNAP TO IT":
            return self._use_grizzled_snap_to_it(stratagem, **kwargs)
        if name_u == "VETERAN SHARPSHOOTERS":
            return self._use_grizzled_veteran_sharpshooters(stratagem, **kwargs)
        return None

    def _use_astra_militarum_grizzled_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        return self._use_astra_militarum_stratagem(stratagem, **kwargs)

    def _use_grizzled_mordian_minute(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MORDIAN MINUTE: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None:
            return False
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: MORDIAN MINUTE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MORDIAN MINUTE: not your Shooting phase")
            return False
        if root not in self._grizzled_mordian_minute_candidates():
            logger.error(
                "ERROR: MORDIAN MINUTE: target must be ASTRA MILITARUM INFANTRY with First Rank, Fire! Second Rank, Fire! and not yet shot"
            )
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["mordian_minute_active"] = True
        sr["mordian_minute_strength_bonus"] = 1
        sr["mordian_minute_expires_phase"] = "SHOOTING_PHASE"
        sr["mordian_minute_owner"] = str(getattr(self.player, "id", "") or "")
        sr["mordian_minute_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["mordian_minute_source"] = str(getattr(stratagem, "name", "") or "MORDIAN MINUTE")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: MORDIAN MINUTE: {getattr(root, 'name', 'Unit')} gains +1 Strength with ranged weapons this phase.")
        return True

    def _use_grizzled_purging_fire(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PURGING FIRE: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None:
            return False
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PURGING FIRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PURGING FIRE: not your Shooting phase")
            return False
        if root not in self._grizzled_purging_fire_candidates():
            logger.error(
                "ERROR: PURGING FIRE: target must be ASTRA MILITARUM unit with an active Order, within objective range, and not yet shot"
            )
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["purging_fire_active"] = True
        sr["purging_fire_expires_phase"] = "SHOOTING_PHASE"
        sr["purging_fire_owner"] = str(getattr(self.player, "id", "") or "")
        sr["purging_fire_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["purging_fire_source"] = str(getattr(stratagem, "name", "") or "PURGING FIRE")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: PURGING FIRE: {getattr(root, 'name', 'Unit')} gains Lethal Hits with ranged weapons this phase.")
        return True

    def _use_grizzled_veteran_sharpshooters(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VETERAN SHARPSHOOTERS: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None:
            return False
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VETERAN SHARPSHOOTERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: VETERAN SHARPSHOOTERS: not your Shooting phase")
            return False
        if root not in self._grizzled_veteran_sharpshooters_candidates():
            logger.error("ERROR: VETERAN SHARPSHOOTERS: target must be ASTRA MILITARUM unit that has not yet shot")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["veteran_sharpshooters_active"] = True
        sr["veteran_sharpshooters_expires_phase"] = "SHOOTING_PHASE"
        sr["veteran_sharpshooters_owner"] = str(getattr(self.player, "id", "") or "")
        sr["veteran_sharpshooters_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["veteran_sharpshooters_source"] = str(getattr(stratagem, "name", "") or "VETERAN SHARPSHOOTERS")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: VETERAN SHARPSHOOTERS: {getattr(root, 'name', 'Unit')} gains Ignores Cover with ranged weapons this phase.")
        return True

    def _use_grizzled_no_retreat(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: NO RETREAT!: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None:
            return False
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: NO RETREAT!: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: NO RETREAT!: not your Command phase")
            return False
        if root not in self._grizzled_no_retreat_candidates():
            logger.error(
                "ERROR: NO RETREAT!: target must be ASTRA MILITARUM unit with Duty and Honour! while within objective range you control"
            )
            return False
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        if not objective_candidates:
            objective_candidates = self._grizzled_no_retreat_objective_candidates(root)
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: NO RETREAT!: no objective marker selected")
            return False
        if objective_candidates and objective not in objective_candidates:
            logger.error("ERROR: NO RETREAT!: selected objective marker is not eligible")
            return False
        loc = getattr(objective, "location", None)
        if loc is None:
            logger.error("ERROR: NO RETREAT!: objective has no location")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        setter = getattr(loc, "set_sticky_control", None)
        if callable(setter):
            setter(self.player, source="no_retreat")
        else:
            loc.sticky_controller = self.player
            loc.sticky_source = "no_retreat"
            loc.controlling_player = self.player
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: NO RETREAT!: objective remains under your control until opponent control breaks sticky hold.")
        return True

    def _use_grizzled_snap_to_it(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        if not phase_name:
            logger.error("ERROR: SNAP TO IT: phase context missing")
            return False

        officer = (
            kwargs.get("officer_unit")
            or kwargs.get("officer")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        target_unit = (
            kwargs.get("order_target_unit")
            or kwargs.get("order_target")
            or kwargs.get("target_unit")
        )
        order_key = str(kwargs.get("order_key") or kwargs.get("order") or "").strip().upper()

        officer_candidates = self._grizzled_snap_to_it_officer_candidates(phase_name=phase_name)
        if not officer_candidates:
            logger.error("ERROR: SNAP TO IT: no eligible OFFICER can issue Orders")
            return False

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        if voice is None:
            logger.error("ERROR: SNAP TO IT: Voice of Command manager unavailable")
            return False

        if officer is not None and target_unit is not None and order_key:
            officer_root = self._am_root(officer)
            target_root = self._am_root(target_unit)
            if officer_root is None or target_root is None:
                logger.error("ERROR: SNAP TO IT: invalid officer or target")
                return False
            if officer_root not in officer_candidates:
                logger.error("ERROR: SNAP TO IT: selected officer is not eligible")
                return False
            target_getter = getattr(voice, "get_eligible_targets", None)
            if callable(target_getter):
                eligible_targets = list(target_getter(officer_root, game=self.game, order_key=order_key) or [])
                if target_root not in eligible_targets:
                    logger.error("ERROR: SNAP TO IT: selected target is not eligible for the chosen Order")
                    return False
            if not self._am_spend_cp(stratagem, target_unit=officer_root):
                return False
            ok = bool(voice.issue_order(self.game, officer_root, target_root, order_key, phase_name=phase_name))
            if not ok:
                logger.error("ERROR: SNAP TO IT: failed to issue selected Order")
                return False
            self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                f"INFO: SNAP TO IT: {getattr(officer_root, 'name', 'Officer')} issued {order_key} to {getattr(target_root, 'name', 'Unit')}."
            )
            return True

        if not bool(getattr(self.player, "has_control", lambda: False)()):
            logger.error("ERROR: SNAP TO IT: remote controllers must provide officer_unit, order_key and order_target_unit")
            return False
        if not self._am_has_voice_prompt_subscriber():
            logger.error("ERROR: SNAP TO IT: no Voice of Command prompt subscriber available")
            return False
        if not self._am_spend_cp(stratagem, target_unit=officer_candidates[0]):
            return False
        event_system = getattr(self.game, "event_system", None) if self.game is not None else None
        event_system.publish(
            "voice_of_command_prompt",
            player=self.player,
            game=self.game,
            phase_name=str(phase_name or "").strip().upper(),
            trigger="snap_to_it",
        )
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: SNAP TO IT: resolve one Voice of Command order now.")
        return True
