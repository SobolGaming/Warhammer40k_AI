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

    def _is_hammer_of_the_emperor(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_hammer_of_the_emperor", None) if mgr is not None else None
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
            if int(get_roll("D6") or 0) < 2:
                continue
            mortal_wounds = int(get_roll("D6") or 0)
            if mortal_wounds <= 0:
                continue
            root._apply_mortal_wounds_to_unit(enemy_root, mortal_wounds, game_map=game_map)
        self_mortals = int(get_roll("D3") or 0) + int(get_roll("D3") or 0) + int(get_roll("D3") or 0)
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
        if name_u == "COORDINATED ACTION":
            return self._use_combined_arms_coordinated_action(stratagem, **kwargs)
        if name_u == "CRASH THROUGH":
            return self._use_hammer_crash_through(stratagem, **kwargs)
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
        if name_u == "INSPIRED COMMAND":
            return self._use_combined_arms_inspired_command(stratagem, **kwargs)
        if name_u == "ON MY POSITION":
            return self._use_bridgehead_on_my_position(stratagem, **kwargs)
        if name_u == "REINFORCEMENTS!":
            return self._use_combined_arms_reinforcements(stratagem, **kwargs)
        if name_u in {"SERVO-DESIGNATORS", "SERVOÃ¢â‚¬â€˜DESIGNATORS", "SERVOÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ËœDESIGNATORS"}:
            return self._use_bridgehead_servo_designators(stratagem, **kwargs)
        if name_u == "STALWART PROTECTOR":
            return self._use_combined_arms_stalwart_protector(stratagem, **kwargs)
        if name_u == "TACTICAL WITHDRAWAL":
            return self._use_hammer_tactical_withdrawal(stratagem, **kwargs)
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
