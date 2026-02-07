from __future__ import annotations

from typing import Any, List

from ..utility.entity_ids import get_entity_id


class ChaosDaemonsStratagemMixin:
    @staticmethod
    def _chaos_daemons_root(unit: Any) -> Any:
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
    def _chaos_daemons_sort_key(unit: Any) -> str:
        try:
            return str(get_entity_id(unit) or "")
        except Exception:
            return ""

    def _is_legiones_daemonica_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        army = getattr(self.player, "army", None)
        if army is None:
            return False
        try:
            if hasattr(root, "get_parent_army") and root.get_parent_army() is not army:
                return False
        except Exception:
            return False
        has_kw = False
        try:
            has_kw = bool(root.has_any_keyword("LEGIONES DAEMONICA"))
        except Exception:
            has_kw = False
        try:
            faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if not has_kw and faction_id != "CD":
            return False
        return True

    def _is_scintillating_legion_detachment(self) -> bool:
        army = self.player.get_army()
        if army is None:
            return False
        mgr = getattr(army, "chaos_daemons_detachments", None)
        if mgr is not None and hasattr(mgr, "is_scintillating_legion_detachment"):
            return bool(mgr.is_scintillating_legion_detachment())
        det = " ".join(str(getattr(army, "detachment_type", "") or "").lower().split())
        return det == "scintillating legion"

    def _is_tzeentch_legiones_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        if not self._is_legiones_daemonica_unit(root):
            return False
        try:
            return bool(root.has_any_keyword("TZEENTCH"))
        except Exception:
            return False

    def _scintillating_legion_tzeentch_unit_candidates(
        self,
        *,
        require_engaged: bool = False,
        require_not_engaged: bool = False,
        require_monster: bool = False,
    ) -> List[Any]:
        if self.player is None or self.game is None:
            return []
        if not self._is_scintillating_legion_detachment():
            return []
        army = self.player.get_army()
        if army is None:
            return []
        game_map = getattr(self.game, "map", None)
        if (require_engaged or require_not_engaged) and game_map is None:
            return []
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = unit.get_attached_unit_root()
            if root is None:
                continue
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            if not root.is_alive():
                continue
            if not getattr(root, "deployed", False):
                continue
            if getattr(root, "is_in_reserves", lambda: False)():
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_tzeentch_legiones_unit(root):
                continue
            if require_monster:
                if not (bool(getattr(root, "is_monster", False)) or root.has_any_keyword("MONSTER")):
                    continue
            if require_engaged or require_not_engaged:
                engaged = False
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
                if require_engaged and not engaged:
                    continue
                if require_not_engaged and engaged:
                    continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
        return candidates

    def _flux_tokens_available(self) -> int:
        if self.game is None or self.player is None:
            return 0
        mgr = getattr(self.game, "fates_in_flux", None)
        if mgr is None:
            return 0
        try:
            return int(mgr.tokens_for_player(self.player) or 0)
        except Exception:
            return 0

    def _daemon_incursion_battlefield_unit_candidates(self) -> List[Any]:
        if self.player is None:
            return []
        try:
            army = self.player.get_army()
        except Exception:
            return []
        if army is None:
            return []
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_daemons_root(unit)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
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
                if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                    continue
            except Exception:
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_legiones_daemonica_unit(root):
                continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
        return candidates

    def _daemon_incursion_reserve_deep_strike_candidates(self) -> List[Any]:
        if self.player is None or self.game is None:
            return []
        try:
            army = self.player.get_army()
        except Exception:
            return []
        if army is None:
            return []
        turn = int(getattr(self.game, "turn", 0) or 0)
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_daemons_root(unit)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
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
                if not getattr(root, "is_in_reserves", lambda: False)():
                    continue
            except Exception:
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_legiones_daemonica_unit(root):
                continue
            try:
                if not getattr(root, "has_deep_strike", lambda: False)():
                    continue
            except Exception:
                continue
            try:
                if not getattr(root, "can_arrive_from_reserves", lambda _t: False)(turn):
                    continue
            except Exception:
                continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
        return candidates

    def _unit_within_shadow_of_chaos(self, unit: Any) -> bool:
        if unit is None or self.game is None:
            return False
        try:
            army = self.player.get_army()
        except Exception:
            return False
        if army is None:
            return False
        mgr = getattr(army, "shadow_of_chaos", None)
        if mgr is None or not getattr(mgr, "army_has_shadow", lambda: False)():
            return False
        try:
            return bool(mgr.is_unit_within_shadow(unit, game=self.game))
        except Exception:
            return False
