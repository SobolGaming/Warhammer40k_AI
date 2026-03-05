from __future__ import annotations

from typing import Any, List

from ..utility.entity_ids import get_entity_id


class NecronsStratagemMixin:
    def _get_necrons_mgr(self):
        army = self.player.get_army()
        return getattr(army, "necrons_detachments", None) if army is not None else None

    def _is_hypercrypt_legion(self) -> bool:
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return False
        return bool(mgr.is_hypercrypt_legion())

    def _is_starshatter_arsenal(self) -> bool:
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return False
        return bool(mgr.is_starshatter_arsenal())

    def _starshatter_candidates(
        self,
        *,
        require_vehicle_or_mounted: bool = False,
        require_not_moved: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> List[Any]:
        if not self._is_starshatter_arsenal():
            return []
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return []
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen = set()
        for unit in units:
            if unit is None:
                continue
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
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not mgr.unit_is_necrons(root):
                continue
            if mgr.unit_is_titanic(root):
                continue
            if require_vehicle_or_mounted and not mgr.unit_is_vehicle_or_mounted(root):
                continue
            if require_not_moved and bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            candidates.append(root)
        return candidates

    def _starshatter_merciless_reclamation_candidates(self, phase_name: str | None = None) -> List[Any]:
        phase_key = str(phase_name or "").strip().lower()
        require_not_shot = "shooting" in phase_key
        require_not_fought = "fight" in phase_key
        return self._starshatter_candidates(
            require_vehicle_or_mounted=False,
            require_not_shot=require_not_shot,
            require_not_fought=require_not_fought,
        )

    def _starshatter_dimensional_tunnel_candidates(self) -> List[Any]:
        return self._starshatter_candidates(require_vehicle_or_mounted=True)

    def _starshatter_chronoshift_candidates(self) -> List[Any]:
        return self._starshatter_candidates(require_vehicle_or_mounted=True, require_not_moved=True)

    def _unit_arrives_via_hyperphasing_this_phase(self, unit: Any) -> bool:
        if unit is None or self.game is None:
            return False
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("hyperphasing_arrival_pending", False)):
            return False
        owner_id = str(sr.get("hyperphasing_arrival_turn_owner", "") or "")
        if owner_id and owner_id != str(getattr(self.player, "id", "") or ""):
            return False
        try:
            current_player = getattr(self.game, "get_current_player", lambda: None)()
            current_player_id = str(getattr(current_player, "id", "") or "")
        except Exception:
            current_player_id = ""
        if current_player_id and current_player_id != str(getattr(self.player, "id", "") or ""):
            return False
        try:
            in_reserves = bool(getattr(root, "is_in_reserves", lambda: False)())
        except Exception:
            in_reserves = False
        return bool(in_reserves)

    def _hypercrypt_cosmic_precision_candidates(self) -> List[Any]:
        if not self._is_hypercrypt_legion():
            return []
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return []
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen = set()
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        for unit in units:
            if unit is None:
                continue
            root = unit.get_attached_unit_root()
            if root is None:
                continue
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            if not root.is_alive():
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not mgr.unit_is_necrons(root):
                continue
            has_any_keyword = getattr(root, "has_any_keyword", None)
            if callable(has_any_keyword) and bool(has_any_keyword("MONSTER")):
                continue
            if not bool(getattr(root, "is_in_reserves", lambda: False)()):
                continue
            if not bool(getattr(root, "can_arrive_from_reserves", lambda _t: False)(current_turn)):
                continue
            arrives_via_hyperphasing = self._unit_arrives_via_hyperphasing_this_phase(root)
            has_deep_strike = bool(getattr(root, "has_deep_strike", lambda: False)())
            if not arrives_via_hyperphasing and not has_deep_strike:
                continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
        return candidates
