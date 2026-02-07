from __future__ import annotations

from typing import Any, List

from ..utility.entity_ids import get_entity_id


class ChaosKnightsStratagemMixin:
    @staticmethod
    def _chaos_knights_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                return get_root()
            except Exception:
                return unit
        return unit

    @staticmethod
    def _chaos_knights_sort_key(unit: Any) -> str:
        try:
            return str(get_entity_id(unit) or "")
        except Exception:
            return ""

    def _chaos_knights_detachment_manager(self):
        army = getattr(self.player, "army", None)
        if army is None:
            return None
        mgr = getattr(army, "chaos_knights_detachments", None)
        if mgr is None or not hasattr(mgr, "is_infernal_lance"):
            return None
        if not mgr.is_infernal_lance():
            return None
        return mgr

    def _is_chaos_knights_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        army = getattr(self.player, "army", None)
        if army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        if parent_army is not None and parent_army is not army:
            return False
        has_any_kw = getattr(root, "has_any_keyword", None)
        if callable(has_any_kw) and has_any_kw("CHAOS KNIGHTS"):
            return True
        root_faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if root_faction_id == "QT":
            return True
        return False

    def _is_chaos_knights_character_unit(self, unit: Any) -> bool:
        if not self._is_chaos_knights_unit(unit):
            return False
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        has_any_kw = getattr(root, "has_any_keyword", None)
        if callable(has_any_kw) and has_any_kw("CHARACTER"):
            return True
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model in models:
            if bool(getattr(model, "is_character", False)):
                return True
        return False

    def _profane_symbiosis_used_this_round(self, unit: Any) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        try:
            last_turn = int(sr.get("profane_symbiosis_last_turn", -1) or -1)
        except Exception:
            last_turn = -1
        owner = str(sr.get("profane_symbiosis_last_owner", "") or "")
        current_owner = str(getattr(self.player, "id", "") or "")
        if owner and current_owner and owner != current_owner:
            return False
        try:
            current_turn = int(getattr(self.game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        return last_turn >= 0 and current_turn >= 0 and last_turn == current_turn

    def _infernal_lance_unit_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_empowered: bool = False,
        require_character: bool = False,
    ) -> List[Any]:
        mgr = self._chaos_knights_detachment_manager()
        if mgr is None:
            return []
        army = getattr(self.player, "army", None)
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in units:
            if unit is None:
                continue
            root = self._chaos_knights_root(unit)
            if root is None:
                continue
            uid = self._chaos_knights_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue
            try:
                if not getattr(root, "deployed", False):
                    continue
            except Exception:
                continue
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    continue
            except Exception:
                continue
            try:
                if self._unit_cannot_be_target_of_stratagem(root):
                    continue
            except Exception:
                continue
            if not self._is_chaos_knights_unit(root):
                continue
            if require_character and not self._is_chaos_knights_character_unit(root):
                continue
            if require_not_shot:
                try:
                    if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                        continue
                except Exception:
                    continue
            if require_not_empowered:
                try:
                    if mgr.is_unit_empowered(root, game=self.game):
                        continue
                except Exception:
                    continue
                if self._profane_symbiosis_used_this_round(root):
                    continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
        return candidates

    def _infernal_lance_shooting_candidates(self) -> List[Any]:
        return self._infernal_lance_unit_candidates(require_not_shot=True)

    def _profane_symbiosis_candidates(self) -> List[Any]:
        return self._infernal_lance_unit_candidates(require_not_empowered=True)

    def _corrupting_taint_objective_candidates(self, unit: Any) -> List[Any]:
        if unit is None or self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        root = self._chaos_knights_root(unit)
        if root is None:
            return []
        candidates: List[Any] = []
        for obj in list(getattr(game_map, "objectives", []) or []):
            try:
                loc = getattr(obj, "location", None)
                if loc is None or getattr(loc, "removed", False):
                    continue
                if getattr(loc, "controlling_player", None) is not self.player:
                    continue
                if hasattr(root, "is_within_objective_range") and root.is_within_objective_range(loc):
                    candidates.append(obj)
            except Exception:
                continue
        return candidates
