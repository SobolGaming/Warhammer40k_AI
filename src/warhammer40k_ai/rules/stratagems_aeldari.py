from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class AeldariStratagemMixin:
    @staticmethod
    def _aeldari_norm_name(name: str) -> str:
        text = str(name or "").strip().upper()
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("â€™", "'").replace("\u00e2\u20ac\u2122", "'")
        for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "−"):
            text = text.replace(dash, "-")
        return text

    @staticmethod
    def _aeldari_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                return get_root()
            except (AttributeError, TypeError, ValueError):
                return unit
        return unit

    @staticmethod
    def _aeldari_sort_key(unit: Any) -> str:
        try:
            return str(get_entity_id(unit) or "")
        except (AttributeError, TypeError, ValueError):
            return ""

    @staticmethod
    def _aeldari_is_alive(unit: Any) -> bool:
        alive_fn = getattr(unit, "is_alive", None)
        if callable(alive_fn):
            try:
                return bool(alive_fn())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(getattr(unit, "is_alive", False))

    @staticmethod
    def _aeldari_in_reserves(unit: Any) -> bool:
        in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves):
            try:
                return bool(in_reserves())
            except (AttributeError, TypeError, ValueError):
                return True
        return bool(in_reserves)

    def _aeldari_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "aeldari_detachments", None) if army is not None else None

    def _is_warhost_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_warhost_detachment", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_armoured_warhost_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_armoured_warhost", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_aspect_host_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_aspect_host", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_corsair_coterie_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_corsair_coterie", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_devoted_of_ynnead_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_devoted_of_ynnead", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_ghosts_of_the_webway_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_ghosts_of_the_webway", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_eldritch_raiders_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_eldritch_raiders", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_seer_council_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_seer_council", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_guardian_battlehost_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_guardian_battlehost", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_serpents_brood_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_serpents_brood", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_spirit_conclave_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_spirit_conclave", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _blitzing_firepower_candidates(self) -> List[Any]:
        if not self._is_warhost_detachment():
            return []
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen = set()
        for unit in units:
            if unit is None:
                continue
            root = unit.get_attached_unit_root()
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
            if not root.has_any_keyword("ASURYANI"):
                continue
            if getattr(getattr(root, "round_state", None), "shot_this_round", False):
                continue
            candidates.append(root)
        return candidates

    def _aeldari_is_targetable(self, unit: Any) -> bool:
        checker = getattr(self, "_unit_cannot_be_target_of_stratagem", None)
        if callable(checker):
            return not bool(checker(unit))
        return True

    def _aeldari_armoured_vehicle_candidates(
        self,
        *,
        require_fly: bool = False,
        require_transport: bool = False,
        require_on_battlefield: bool = True,
        require_in_reserves: bool = False,
        require_not_shot: bool = False,
    ) -> List[Any]:
        if not self._is_armoured_warhost_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._aeldari_detachment_mgr()
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_alive(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            in_reserves = self._aeldari_in_reserves(root)
            if require_on_battlefield:
                if not bool(getattr(root, "deployed", False)):
                    continue
                if in_reserves:
                    continue
                if not self._aeldari_is_targetable(root):
                    continue
            if require_in_reserves and not in_reserves:
                continue
            if not require_in_reserves and not require_on_battlefield and not bool(getattr(root, "deployed", False)):
                # Keep reserves-only units when explicitly requested; otherwise require deployment state.
                continue
            unit_is_vehicle = getattr(mgr, "_unit_is_aeldari_vehicle", None) if mgr is not None else None
            unit_is_vehicle_fly = getattr(mgr, "_unit_is_aeldari_vehicle_fly", None) if mgr is not None else None
            is_vehicle = bool(unit_is_vehicle(root)) if callable(unit_is_vehicle) else (
                bool(getattr(root, "has_any_keyword", lambda _k: False)("AELDARI"))
                and bool(getattr(root, "has_any_keyword", lambda _k: False)("VEHICLE"))
            )
            if not is_vehicle:
                continue
            if require_fly:
                is_fly_vehicle = bool(unit_is_vehicle_fly(root)) if callable(unit_is_vehicle_fly) else (
                    bool(getattr(root, "has_any_keyword", lambda _k: False)("FLY"))
                )
                if not is_fly_vehicle:
                    continue
            if require_transport and not bool(getattr(root, "is_transport", False)):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._aeldari_sort_key)

    def _aeldari_armoured_embarked_candidates(self, transport_unit: Any) -> List[Any]:
        if transport_unit is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for passenger in list(getattr(transport_unit, "transport_passengers", []) or []):
            root = self._aeldari_root(passenger)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_alive(root):
                continue
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            is_battle_shocked = getattr(root, "is_battle_shocked", None)
            if callable(is_battle_shocked):
                try:
                    if bool(is_battle_shocked()):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("cannot_use_stratagems")):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_armoured_cloudstrike_candidates(self) -> List[Any]:
        candidates = self._aeldari_armoured_vehicle_candidates(
            require_fly=True,
            require_transport=False,
            require_on_battlefield=False,
            require_in_reserves=True,
        )
        out: List[Any] = []
        for root in list(candidates or []):
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_armoured_soulsight_candidates(self) -> List[Any]:
        return self._aeldari_armoured_vehicle_candidates(
            require_fly=False,
            require_transport=False,
            require_on_battlefield=True,
            require_not_shot=True,
        )

    def _aeldari_spirit_is_wraithblades_or_wraithguard(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if self._aeldari_has_keyword(root, "WRAITHBLADES") or self._aeldari_has_keyword(root, "WRAITHGUARD"):
            return True
        try:
            name = str(getattr(root, "name", "") or "").strip().lower()
        except (AttributeError, TypeError, ValueError):
            name = ""
        return bool("wraithblades" in name or "wraithguard" in name)

    def _aeldari_spirit_is_wraith_target(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if (
            self._aeldari_has_keyword(root, "WRAITHBLADES")
            or self._aeldari_has_keyword(root, "WRAITHGUARD")
            or self._aeldari_has_keyword(root, "WRAITHLORD")
        ):
            return True
        try:
            name = str(getattr(root, "name", "") or "").strip().lower()
        except (AttributeError, TypeError, ValueError):
            name = ""
        return bool("wraithblades" in name or "wraithguard" in name or "wraithlord" in name)

    def _aeldari_spirit_is_wraith_construct(self, unit: Any, *, exclude_titanic: bool = False) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if exclude_titanic and self._aeldari_has_keyword(root, "TITANIC"):
            return False
        if self._aeldari_has_keyword(root, "WRAITH CONSTRUCT"):
            return True
        if (
            self._aeldari_has_keyword(root, "WRAITHBLADES")
            or self._aeldari_has_keyword(root, "WRAITHGUARD")
            or self._aeldari_has_keyword(root, "WRAITHLORD")
            or self._aeldari_has_keyword(root, "WRAITHKNIGHT")
        ):
            return True
        try:
            name = str(getattr(root, "name", "") or "").strip().lower()
        except (AttributeError, TypeError, ValueError):
            name = ""
        if not name or "wraith" not in name:
            return False
        if exclude_titanic and "wraithknight" in name:
            return False
        return True

    def _aeldari_spirit_wraith_construct_candidates(
        self,
        *,
        exclude_titanic: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> List[Any]:
        if not self._is_spirit_conclave_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_spirit_is_wraith_construct(root, exclude_titanic=exclude_titanic):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_spirit_psyker_candidates(self) -> List[Any]:
        if not self._is_spirit_conclave_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "AELDARI"):
                continue
            if not self._aeldari_has_keyword(root, "PSYKER"):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_spirit_visible_enemy_candidates(self, source_unit: Any) -> List[Any]:
        if not self._is_spirit_conclave_detachment():
            return []
        source_root = self._aeldari_root(source_unit)
        if source_root is None:
            return []
        try:
            if source_root.get_parent_army().player is not self.player:
                return []
        except (AttributeError, TypeError, ValueError):
            return []
        if not self._aeldari_on_battlefield(source_root, require_targetable=True):
            return []
        if not self._aeldari_has_keyword(source_root, "AELDARI") or not self._aeldari_has_keyword(source_root, "PSYKER"):
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        get_enemy = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy):
            return []
        can_see_fn = getattr(game, "_model_can_see_unit", None)
        source_models = list(getattr(source_root, "get_attached_unit_models", lambda: [])() or [])
        out: List[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy(source_root) or []):
            enemy_root = self._aeldari_root(enemy)
            if enemy_root is None:
                continue
            uid = self._aeldari_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
                continue
            if self._aeldari_in_reserves(enemy_root):
                continue
            if callable(can_see_fn):
                visible = False
                for model in source_models:
                    try:
                        alive = getattr(model, "is_alive", True)
                        if callable(alive):
                            alive = alive()
                        if not bool(alive):
                            continue
                        if bool(can_see_fn(model, enemy_root, game_map=game_map)):
                            visible = True
                            break
                    except Exception:
                        continue
                if not visible:
                    continue
            out.append(enemy_root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_spirit_seers_eye_wraith_candidates(self, source_unit: Any) -> List[Any]:
        if not self._is_spirit_conclave_detachment():
            return []
        source_root = self._aeldari_root(source_unit)
        if source_root is None:
            return []
        try:
            if source_root.get_parent_army().player is not self.player:
                return []
        except (AttributeError, TypeError, ValueError):
            return []
        if not self._aeldari_on_battlefield(source_root, require_targetable=True):
            return []
        if not self._aeldari_has_keyword(source_root, "AELDARI") or not self._aeldari_has_keyword(source_root, "PSYKER"):
            return []
        from ..utility.aura_utils import unit_within_range_of_unit

        out: List[Any] = []
        for unit in self._aeldari_spirit_wraith_construct_candidates(
            exclude_titanic=False,
            require_not_shot=True,
            require_not_fought=True,
        ):
            if not unit_within_range_of_unit(source_root, unit, 12.0, use_attached_aggregate=True):
                continue
            out.append(unit)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_spirit_wraithbone_armour_candidates(self, *, target_units: List[Any]) -> List[Any]:
        if not self._is_spirit_conclave_detachment():
            return []
        eligible_units = self._aeldari_spirit_wraith_construct_candidates(
            exclude_titanic=True,
            require_not_shot=False,
            require_not_fought=False,
        )
        eligible_ids = {self._aeldari_sort_key(unit) for unit in list(eligible_units or [])}
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid not in eligible_ids:
                continue
            if (not uid) and root not in eligible_units:
                continue
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_spirit_wraithblades_or_guard_candidates(self) -> List[Any]:
        if not self._is_spirit_conclave_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_spirit_is_wraithblades_or_wraithguard(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_spirit_wraith_target_candidates(self) -> List[Any]:
        if not self._is_spirit_conclave_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_spirit_is_wraith_target(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_spirit_soul_bridge_psyker_candidates(self, *, target_unit: Any = None) -> List[Any]:
        if not self._is_spirit_conclave_detachment():
            return []
        target_root = self._aeldari_root(target_unit)
        if target_unit is not None:
            if target_root is None or not self._aeldari_spirit_is_wraith_target(target_root):
                return []
            try:
                if target_root.get_parent_army().player is not self.player:
                    return []
            except (AttributeError, TypeError, ValueError):
                return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "ASURYANI"):
                continue
            if not self._aeldari_has_keyword(root, "PSYKER"):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_spirit_token_objective_candidates(self, unit: Any) -> List[Any]:
        if not self._is_spirit_conclave_detachment():
            return []
        root = self._aeldari_root(unit)
        if root is None:
            return []
        try:
            if root.get_parent_army().player is not self.player:
                return []
        except (AttributeError, TypeError, ValueError):
            return []
        if not self._aeldari_on_battlefield(root, require_targetable=True):
            return []
        if not self._aeldari_spirit_is_wraithblades_or_wraithguard(root):
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        within_one = getattr(root, "is_within_objective_range", None)
        if not callable(within_one):
            return []
        out: List[Any] = []
        for objective in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(objective, "location", None)
            if loc is None:
                loc = objective
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            update_control = getattr(loc, "update_control", None)
            if callable(update_control):
                try:
                    update_control(game)
                except (AttributeError, TypeError, ValueError):
                    continue
            if getattr(loc, "controlling_player", None) is not self.player:
                continue
            try:
                if not bool(within_one(loc)):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            out.append(objective)

        def _objective_sort_key(obj: Any) -> str:
            loc = getattr(obj, "location", None)
            if loc is None:
                loc = obj
            sid = str(get_entity_id(loc) or get_entity_id(obj) or "")
            if sid:
                return f"id:{sid}"
            try:
                x = float(getattr(loc, "x", 0.0) or 0.0)
                y = float(getattr(loc, "y", 0.0) or 0.0)
            except (AttributeError, TypeError, ValueError):
                x = 0.0
                y = 0.0
            return f"xy:{x:.3f}:{y:.3f}"

        return sorted(out, key=_objective_sort_key)

    def _aeldari_seer_psyker_candidates(self) -> List[Any]:
        if not self._is_seer_council_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "ASURYANI"):
                continue
            if not self._aeldari_has_keyword(root, "PSYKER"):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_seer_presentiment_enemy_candidates(self, source_unit: Any) -> List[Any]:
        if not self._is_seer_council_detachment():
            return []
        source_root = self._aeldari_root(source_unit)
        if source_root is None:
            return []
        try:
            if source_root.get_parent_army().player is not self.player:
                return []
        except (AttributeError, TypeError, ValueError):
            return []
        if not self._aeldari_on_battlefield(source_root, require_targetable=True):
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        get_enemy = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy):
            return []

        from ..utility.aura_utils import unit_within_range_of_unit

        can_see_fn = getattr(game, "_model_can_see_unit", None)
        source_models = list(getattr(source_root, "get_attached_unit_models", lambda: [])() or [])
        out: List[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy(source_root) or []):
            enemy_root = self._aeldari_root(enemy)
            if enemy_root is None:
                continue
            uid = self._aeldari_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
                continue
            if self._aeldari_in_reserves(enemy_root):
                continue
            if not unit_within_range_of_unit(source_root, enemy_root, 18.0, use_attached_aggregate=True):
                continue
            if callable(can_see_fn):
                visible = False
                for model in source_models:
                    try:
                        alive = getattr(model, "is_alive", True)
                        if callable(alive):
                            alive = alive()
                        if not bool(alive):
                            continue
                        if bool(can_see_fn(model, enemy_root, game_map=game_map)):
                            visible = True
                            break
                    except Exception:
                        continue
                if not visible:
                    continue
            out.append(enemy_root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_seer_presentiment_psyker_candidates(self) -> List[Any]:
        if not self._is_seer_council_detachment():
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for psyker in self._aeldari_seer_psyker_candidates():
            root = self._aeldari_root(psyker)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_targetable(root):
                continue
            if not self._aeldari_seer_presentiment_enemy_candidates(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_seer_unshrouded_truth_candidates(self) -> List[Any]:
        if not self._is_seer_council_detachment():
            return []
        psykers = self._aeldari_seer_psyker_candidates()
        if not psykers:
            return []
        from ..utility.aura_utils import unit_within_range_of_unit

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "ASURYANI"):
                continue
            if not self._aeldari_has_keyword(root, "INFANTRY"):
                continue
            if self._aeldari_has_keyword(root, "WRAITH CONSTRUCT"):
                continue
            if self._aeldari_selected_to_move_this_phase(root):
                continue
            was_set_up = getattr(root, "_was_set_up_this_turn", None)
            if callable(was_set_up):
                try:
                    if bool(was_set_up(game=getattr(self, "game", None))):
                        continue
                except (AttributeError, TypeError, ValueError):
                    pass
            within_psyker = False
            for psyker in psykers:
                if unit_within_range_of_unit(root, psyker, 9.0, use_attached_aggregate=True):
                    within_psyker = True
                    break
            if not within_psyker:
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_seer_ishas_fury_candidates(self, *, enemy_unit: Any) -> List[Any]:
        if not self._is_seer_council_detachment():
            return []
        enemy_root = self._aeldari_root(enemy_unit)
        if enemy_root is None:
            return []
        try:
            if enemy_root.get_parent_army().player is self.player:
                return []
        except (AttributeError, TypeError, ValueError):
            return []
        if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
            return []

        from ..utility.aura_utils import unit_within_range_of_unit

        out: List[Any] = []
        seen: set[str] = set()
        for psyker in self._aeldari_seer_psyker_candidates():
            root = self._aeldari_root(psyker)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_seer_fate_inescapable_candidates(self) -> List[Any]:
        if not self._is_seer_council_detachment():
            return []
        psykers = self._aeldari_seer_psyker_candidates()
        if not psykers:
            return []
        from ..utility.aura_utils import unit_within_range_of_unit

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "ASURYANI"):
                continue
            if not self._aeldari_has_keyword(root, "INFANTRY"):
                continue
            if self._aeldari_has_keyword(root, "WRAITH CONSTRUCT"):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            within_psyker = False
            for psyker in psykers:
                if unit_within_range_of_unit(root, psyker, 9.0, use_attached_aggregate=True):
                    within_psyker = True
                    break
            if not within_psyker:
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_seer_defensive_infantry_candidates(self, *, target_units: List[Any]) -> List[Any]:
        if not self._is_seer_council_detachment():
            return []
        psykers = self._aeldari_seer_psyker_candidates()
        if not psykers:
            return []
        from ..utility.aura_utils import unit_within_range_of_unit

        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "ASURYANI"):
                continue
            if not self._aeldari_has_keyword(root, "INFANTRY"):
                continue
            if self._aeldari_has_keyword(root, "WRAITH CONSTRUCT"):
                continue
            within_psyker = False
            for psyker in psykers:
                if unit_within_range_of_unit(root, psyker, 9.0, use_attached_aggregate=True):
                    within_psyker = True
                    break
            if not within_psyker:
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_seer_psychic_shield_candidates(self, *, target_units: List[Any]) -> List[Any]:
        return self._aeldari_seer_defensive_infantry_candidates(target_units=target_units)

    def _aeldari_seer_forewarned_candidates(self, *, target_units: List[Any]) -> List[Any]:
        return self._aeldari_seer_defensive_infantry_candidates(target_units=target_units)

    def _aeldari_devoted_ynnari_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        exclude_wraith_construct: bool = False,
    ) -> List[Any]:
        if not self._is_devoted_of_ynnead_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._aeldari_detachment_mgr()
        counts_as_ynnari = getattr(mgr, "devoted_of_ynnead_unit_counts_as_ynnari", None) if mgr is not None else None
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            is_ynnari = bool(counts_as_ynnari(root)) if callable(counts_as_ynnari) else self._aeldari_has_keyword(root, "YNNARI")
            if not is_ynnari:
                continue
            if exclude_wraith_construct and self._aeldari_has_keyword(root, "WRAITH CONSTRUCT"):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_devoted_soulsight_candidates(self) -> List[Any]:
        return self._aeldari_devoted_ynnari_candidates(require_not_shot=True, exclude_wraith_construct=False)

    def _aeldari_devoted_death_answers_death_candidates(self) -> List[Any]:
        if not self._is_devoted_of_ynnead_detachment():
            return []
        snapshot = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
        if not isinstance(snapshot, dict) or not snapshot:
            return []
        out: List[Any] = []
        for root in self._aeldari_devoted_ynnari_candidates(require_not_shot=False, exclude_wraith_construct=True):
            uid = self._aeldari_sort_key(root)
            entry = snapshot.get(uid)
            if not isinstance(entry, dict):
                continue
            try:
                before = int(entry.get("models_before", 0) or 0)
            except (TypeError, ValueError):
                before = 0
            after = self._aeldari_models_alive(root)
            if before <= 0 or after >= before:
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_devoted_unit_counts_as_ynnari(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        mgr = self._aeldari_detachment_mgr()
        counts_as_ynnari = getattr(mgr, "devoted_of_ynnead_unit_counts_as_ynnari", None) if mgr is not None else None
        if callable(counts_as_ynnari):
            return bool(counts_as_ynnari(root))
        return self._aeldari_has_keyword(root, "YNNARI")

    def _aeldari_devoted_emissaries_candidates(self, *, attacking_unit: Any = None) -> List[Any]:
        candidates = self._aeldari_devoted_ynnari_candidates(
            require_not_shot=False,
            require_not_fought=True,
            exclude_wraith_construct=False,
        )
        infantry_candidates = [unit for unit in candidates if self._aeldari_has_keyword(unit, "INFANTRY")]
        if attacking_unit is None:
            return sorted(infantry_candidates, key=self._aeldari_sort_key)
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return []
        if attacker_root not in infantry_candidates:
            return []
        return [attacker_root]

    def _aeldari_devoted_parting_the_veil_candidates(self, *, target_units: List[Any]) -> List[Any]:
        if not self._is_devoted_of_ynnead_detachment():
            return []
        eligible_units = self._aeldari_devoted_ynnari_candidates(require_not_shot=False, exclude_wraith_construct=False)
        eligible_ids = {self._aeldari_sort_key(unit) for unit in list(eligible_units or [])}
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            uid = self._aeldari_sort_key(root)
            if root is None:
                continue
            if uid and uid not in eligible_ids:
                continue
            if (not uid) and root not in eligible_units:
                continue
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_devoted_macabre_resilience_candidates(self, *, target_units: List[Any]) -> List[Any]:
        if not self._is_devoted_of_ynnead_detachment():
            return []
        eligible_units = self._aeldari_devoted_ynnari_candidates(
            require_not_shot=False,
            require_not_fought=False,
            exclude_wraith_construct=True,
        )
        eligible_ids = {self._aeldari_sort_key(unit) for unit in list(eligible_units or [])}
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid not in eligible_ids:
                continue
            if (not uid) and root not in eligible_units:
                continue
            if not (self._aeldari_has_keyword(root, "INFANTRY") or self._aeldari_has_keyword(root, "MOUNTED")):
                continue
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_soulsight_candidates_for_active_detachment(self) -> List[Any]:
        if self._is_armoured_warhost_detachment():
            return self._aeldari_armoured_soulsight_candidates()
        if self._is_devoted_of_ynnead_detachment():
            return self._aeldari_devoted_soulsight_candidates()
        return []

    def _aeldari_guardian_is_dire_avengers_or_guardians(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("DIRE AVENGERS")) or bool(has_any("DIRE AVENGER")):
                    return True
                if bool(has_any("GUARDIANS")) or bool(has_any("GUARDIAN")):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "dire avenger" in name or "guardian" in name

    def _aeldari_guardian_is_guardians_unit(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("GUARDIANS")) or bool(has_any("GUARDIAN")):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "guardian" in name

    def _aeldari_guardian_is_storm_guardians(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("STORM GUARDIANS")):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "storm guardian" in name

    @staticmethod
    def _aeldari_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    def _aeldari_guardian_is_war_walkers(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("WAR WALKERS")) or bool(has_any("WAR WALKER")):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "war walker" in name

    def _aeldari_guardian_unit_within_objective_range(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        game_map = getattr(getattr(self, "game", None), "map", None)
        within_any = getattr(root, "is_within_any_objective_range", None)
        if callable(within_any):
            try:
                return bool(within_any(game_map))
            except (AttributeError, TypeError, ValueError):
                pass
        if game_map is None:
            return False
        within_one = getattr(root, "is_within_objective_range", None)
        if not callable(within_one):
            return False
        for objective in list(getattr(game_map, "objectives", []) or []):
            location = getattr(objective, "location", None)
            if location is None:
                location = objective
            if location is None or bool(getattr(location, "removed", False)):
                continue
            try:
                if bool(within_one(location)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _aeldari_guardian_dire_avengers_or_guardians_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> List[Any]:
        if not self._is_guardian_battlehost_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_guardian_is_dire_avengers_or_guardians(root):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_guardian_shield_nodes_candidates(self, *, target_units: List[Any]) -> List[Any]:
        eligible_units = self._aeldari_guardian_dire_avengers_or_guardians_candidates(
            require_not_shot=False,
            require_not_fought=False,
        )
        eligible_ids = {self._aeldari_sort_key(unit) for unit in list(eligible_units or [])}
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid not in eligible_ids:
                continue
            if (not uid) and root not in eligible_units:
                continue
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_guardian_war_walkers_candidates(self) -> List[Any]:
        if not self._is_guardian_battlehost_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_guardian_is_war_walkers(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_guardian_cost_of_victory_candidates(self) -> List[Any]:
        if not self._is_guardian_battlehost_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_guardian_is_guardians_unit(root):
                continue
            if self._aeldari_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_guardian_time_to_strike_candidates(self) -> List[Any]:
        if not self._is_guardian_battlehost_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_guardian_is_storm_guardians(root):
                continue
            if self._aeldari_selected_to_move_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_guardian_vauls_vengeance_used_this_round(self) -> bool:
        game = getattr(self, "game", None)
        if game is None:
            return False
        current_round = int(getattr(game, "turn", 0) or 0)
        used_round = int(getattr(self, "_aeldari_guardian_vauls_vengeance_used_round", 0) or 0)
        return bool(current_round and used_round and current_round == used_round)

    def _aeldari_guardian_mark_vauls_vengeance_used_round(self) -> None:
        game = getattr(self, "game", None)
        if game is None:
            return
        setattr(self, "_aeldari_guardian_vauls_vengeance_used_round", int(getattr(game, "turn", 0) or 0))

    def _aeldari_armoured_anti_grav_targets(self, target_units: List[Any]) -> List[Any]:
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_alive(root):
                continue
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if not self._aeldari_is_targetable(root):
                continue
            mgr = self._aeldari_detachment_mgr()
            checker = getattr(mgr, "_unit_is_aeldari_vehicle_fly", None) if mgr is not None else None
            is_valid = bool(checker(root)) if callable(checker) else (
                bool(getattr(root, "has_any_keyword", lambda _k: False)("AELDARI"))
                and bool(getattr(root, "has_any_keyword", lambda _k: False)("VEHICLE"))
                and bool(getattr(root, "has_any_keyword", lambda _k: False)("FLY"))
            )
            if not is_valid:
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_armoured_spend_cp(self, stratagem, *, target_unit: Any = None, enemy_unit: Any = None) -> bool:
        eff_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            try:
                preview = apply_fn(stratagem, target_unit=target_unit, enemy_unit=enemy_unit) or {}
                eff_cost = int(preview.get("cost", eff_cost))
            except (AttributeError, TypeError, ValueError):
                eff_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        return bool(
            self.player.spend_command_points(
                int(eff_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _aeldari_armoured_finalize_use(self, stratagem, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            raw_name = str(getattr(stratagem, "name", "") or "").strip().upper()
            if raw_name:
                used.add(raw_name)
            used.add(self._aeldari_norm_name(getattr(stratagem, "name", "")))

    def _aeldari_pending_context(self, stratagem_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        wanted = self._aeldari_norm_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._aeldari_norm_name(reaction.get("stratagem", "")) != wanted:
                continue
            merged.update(dict(reaction))
            break
        for key, value in dict(kwargs or {}).items():
            if value is not None:
                merged[key] = value
        return merged

    def _aeldari_get_stratagem_by_norm_name(self, name: str):
        wanted = self._aeldari_norm_name(name)
        if not wanted:
            return None
        for stratagem in list(getattr(self, "available", []) or []):
            if self._aeldari_norm_name(getattr(stratagem, "name", "")) == wanted:
                return stratagem
        return None

    def _aeldari_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None

        place_fn = getattr(root, "enter_strategic_reserves_midgame", None)
        if callable(place_fn):
            return bool(place_fn(game=game, game_map=game_map, reason=reason))

        members = list(getattr(root, "get_attached_unit_members", lambda: [root])() or [])
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            set_status = getattr(member, "set_reserve_status", None)
            if callable(set_status):
                set_status("strategic_reserves")
            else:
                member.reserve_status = "strategic_reserves"
            mark_midgame = getattr(member, "mark_entered_reserves_midgame", None)
            if callable(mark_midgame):
                mark_midgame(game=game)
            if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                if game is not None:
                    member._aircraft_return_turn = int(getattr(game, "turn", 0) or 0) + 1
            member.deployed = True
            member.reserve_turn_deployed = None
            member.arrived_from_reserves_this_turn = False
            if game_map is not None and isinstance(getattr(game_map, "units", None), list) and member in game_map.units:
                game_map.units.remove(member)
        return True

    def _aeldari_reaction_exists(self, event_name: str, stratagem_name: str, *, unit: Any = None) -> bool:
        wanted = self._aeldari_norm_name(stratagem_name)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            try:
                if str(reaction.get("event", "") or "") != str(event_name or ""):
                    continue
                if self._aeldari_norm_name(reaction.get("stratagem", "")) != wanted:
                    continue
                if unit is not None:
                    if reaction.get("unit") is not unit and reaction.get("target_unit") is not unit:
                        continue
                return True
            except Exception:
                continue
        return False

    def _queue_aeldari_armoured_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_armoured_warhost_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return

        if phase_key == "SHOOTING_PHASE":
            stratagem = self.get_by_name("SOULSIGHT")
            if stratagem is not None:
                if self.player.command_points >= int(getattr(stratagem, "cp_cost", 0) or 0):
                    used = getattr(self, "_used_stratagems_this_phase", set())
                    if self._aeldari_norm_name(stratagem.name) not in used:
                        candidates = self._aeldari_armoured_soulsight_candidates()
                        if candidates and not self._aeldari_reaction_exists("phase_start", stratagem.name):
                            payload: Dict[str, Any] = {
                                "event": "phase_start",
                                "phase": "Shooting phase",
                                "phase_name": "Shooting phase",
                                "stratagem": stratagem.name,
                                "cp_cost": stratagem.cp_cost,
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["unit"] = candidates[0]
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload, use_timer=False)

        if phase_key == "MOVEMENT_PHASE":
            stratagem = self.get_by_name("CLOUDSTRIKE")
            if stratagem is not None:
                if self.player.command_points >= int(getattr(stratagem, "cp_cost", 0) or 0):
                    used = getattr(self, "_used_stratagems_this_phase", set())
                    if self._aeldari_norm_name(stratagem.name) not in used:
                        candidates = self._aeldari_armoured_cloudstrike_candidates()
                        if candidates and not self._aeldari_reaction_exists("phase_start", stratagem.name):
                            payload = {
                                "event": "phase_start",
                                "phase": "Movement phase",
                                "phase_name": "Movement phase",
                                "stratagem": stratagem.name,
                                "cp_cost": stratagem.cp_cost,
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["unit"] = candidates[0]
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_seer_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_seer_council_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key == "COMMAND_PHASE":
            stratagem = self._aeldari_get_stratagem_by_norm_name("PRESENTIMENT OF DREAD")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_seer_presentiment_psyker_candidates()
            if not candidates or self._aeldari_reaction_exists("phase_start", stratagem.name):
                return
            payload: Dict[str, Any] = {
                "event": "phase_start",
                "phase": "Command phase",
                "phase_name": "Command phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
                enemy_candidates = self._aeldari_seer_presentiment_enemy_candidates(candidates[0])
                if enemy_candidates:
                    payload["enemy_candidates"] = enemy_candidates
                    if len(enemy_candidates) == 1:
                        payload["enemy_unit"] = enemy_candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        stratagem = self._aeldari_get_stratagem_by_norm_name("UNSHROUDED TRUTH")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_seer_unshrouded_truth_candidates()
        if not candidates or self._aeldari_reaction_exists("phase_start", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "phase_start",
            "phase": "Movement phase",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_aeldari_spirit_phase_start_effects(self, *, player, phase) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "COMMAND_PHASE":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player and player is not self.player:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        owner_id = str(getattr(self.player, "id", "") or "")
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            link_owner = str(sr.get("aeldari_soul_bridge_owner", "") or "")
            if link_owner and owner_id and link_owner != owner_id:
                continue
            if not bool(sr.get("aeldari_soul_bridge_active")):
                continue
            for key in (
                "aeldari_soul_bridge_active",
                "aeldari_soul_bridge_owner",
                "aeldari_soul_bridge_turn",
                "aeldari_soul_bridge_source",
                "aeldari_soul_bridge_psyker_unit_id",
            ):
                sr.pop(key, None)
            root.special_rules = sr

    def _queue_aeldari_spirit_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_spirit_conclave_detachment():
            return
        self._cleanup_aeldari_spirit_phase_start_effects(player=player, phase=phase)

        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()

        if phase_key == "COMMAND_PHASE":
            if active_player is not self.player:
                return
            soul_bridge = self._aeldari_get_stratagem_by_norm_name("SOUL BRIDGE")
            if soul_bridge is not None:
                if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(soul_bridge, "cp_cost", 0) or 0):
                    if self._aeldari_norm_name(soul_bridge.name) not in getattr(self, "_used_stratagems_this_phase", set()):
                        candidates = self._aeldari_spirit_wraith_target_candidates()
                        psykers = self._aeldari_spirit_soul_bridge_psyker_candidates()
                        if candidates and psykers and not self._aeldari_reaction_exists("phase_start", soul_bridge.name):
                            payload: Dict[str, Any] = {
                                "event": "phase_start",
                                "phase": "Command phase",
                                "phase_name": "Command phase",
                                "stratagem": soul_bridge.name,
                                "cp_cost": soul_bridge.cp_cost,
                                "candidates": candidates,
                                "psyker_candidates": psykers,
                            }
                            if len(candidates) == 1:
                                payload["unit"] = candidates[0]
                                payload["target_unit"] = candidates[0]
                                unit_psykers = self._aeldari_spirit_soul_bridge_psyker_candidates(target_unit=candidates[0])
                                if unit_psykers:
                                    payload["psyker_candidates"] = unit_psykers
                                    if len(unit_psykers) == 1:
                                        payload["source_unit"] = unit_psykers[0]
                                        payload["source_psyker_unit"] = unit_psykers[0]
                            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key == "MOVEMENT_PHASE":
            if active_player is not self.player:
                return
            spirit_token = self._aeldari_get_stratagem_by_norm_name("SPIRIT TOKEN")
            if spirit_token is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(spirit_token, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(spirit_token.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            all_candidates = self._aeldari_spirit_wraithblades_or_guard_candidates()
            candidate_units: List[Any] = []
            objective_map: Dict[str, List[Any]] = {}
            for unit in list(all_candidates or []):
                objectives = self._aeldari_spirit_token_objective_candidates(unit)
                if not objectives:
                    continue
                candidate_units.append(unit)
                uid = self._aeldari_sort_key(unit)
                if uid:
                    objective_map[uid] = list(objectives)
            if not candidate_units or self._aeldari_reaction_exists("phase_start", spirit_token.name):
                return
            payload: Dict[str, Any] = {
                "event": "phase_start",
                "phase": "Movement phase",
                "phase_name": "Movement phase",
                "stratagem": spirit_token.name,
                "cp_cost": spirit_token.cp_cost,
                "candidates": candidate_units,
                "objective_candidates_by_unit": objective_map,
            }
            if len(candidate_units) == 1:
                payload["unit"] = candidate_units[0]
                payload["target_unit"] = candidate_units[0]
                objective_candidates = self._aeldari_spirit_token_objective_candidates(candidate_units[0])
                if objective_candidates:
                    payload["objective_candidates"] = objective_candidates
                    if len(objective_candidates) == 1:
                        payload["objective"] = objective_candidates[0]
                        payload["objective_marker"] = objective_candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        if phase_key == "SHOOTING_PHASE" and active_player is not self.player:
            return

        seers_eye = self._aeldari_get_stratagem_by_norm_name("SEER'S EYE")
        if seers_eye is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(seers_eye, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(seers_eye.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        if self._aeldari_reaction_exists("phase_start", seers_eye.name):
            return

        phase_label = "Shooting phase" if phase_key == "SHOOTING_PHASE" else "Fight phase"
        psykers = self._aeldari_spirit_psyker_candidates()
        valid_psykers: List[Any] = []
        psyker_enemy_map: Dict[str, List[Any]] = {}
        psyker_wraith_map: Dict[str, List[Any]] = {}
        for psyker in list(psykers or []):
            root = self._aeldari_root(psyker)
            if root is None:
                continue
            pid = self._aeldari_sort_key(root)
            if not pid:
                continue
            enemies = self._aeldari_spirit_visible_enemy_candidates(root)
            if not enemies:
                continue
            wraiths = self._aeldari_spirit_seers_eye_wraith_candidates(root)
            if not wraiths:
                continue
            valid_psykers.append(root)
            psyker_enemy_map[pid] = list(enemies)
            psyker_wraith_map[pid] = list(wraiths)

        if not valid_psykers:
            return
        payload = {
            "event": "phase_start",
            "phase": phase_label,
            "phase_name": phase_label,
            "stratagem": seers_eye.name,
            "cp_cost": seers_eye.cp_cost,
            "psyker_candidates": sorted(valid_psykers, key=self._aeldari_sort_key),
            "enemy_candidates_by_psyker": psyker_enemy_map,
            "wraith_candidates_by_psyker": psyker_wraith_map,
        }
        if len(valid_psykers) == 1:
            source_root = valid_psykers[0]
            payload["source_unit"] = source_root
            payload["source_psyker_unit"] = source_root
            pid = self._aeldari_sort_key(source_root)
            wraith_candidates = list(psyker_wraith_map.get(pid) or [])
            enemy_candidates = list(psyker_enemy_map.get(pid) or [])
            if wraith_candidates:
                payload["candidates"] = wraith_candidates
                if len(wraith_candidates) == 1:
                    payload["unit"] = wraith_candidates[0]
                    payload["target_unit"] = wraith_candidates[0]
            if enemy_candidates:
                payload["enemy_candidates"] = enemy_candidates
                if len(enemy_candidates) == 1:
                    payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_aeldari_spirit_phase_end_effects(self, *, phase) -> None:
        if not self._is_spirit_conclave_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            exp = str(sr.get("aeldari_spirit_seers_eye_expires_phase", "") or "").strip().upper()
            if exp and exp != phase_key:
                continue
            if not bool(sr.get("aeldari_spirit_seers_eye_active")) and not exp:
                continue
            for key in (
                "aeldari_spirit_seers_eye_active",
                "aeldari_spirit_seers_eye_expires_phase",
                "aeldari_spirit_seers_eye_source",
                "aeldari_spirit_seers_eye_turn_owner",
                "aeldari_spirit_seers_eye_turn",
                "aeldari_spirit_seers_eye_enemy_unit_id",
                "aeldari_spirit_seers_eye_psyker_unit_id",
            ):
                sr.pop(key, None)
            root.special_rules = sr

    def _queue_aeldari_spirit_shooting_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_spirit_conclave_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("WRAITHBONE ARMOUR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_spirit_wraithbone_armour_candidates(target_units=list(target_units or []))
        if not candidates or self._aeldari_reaction_exists("shooting_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_spirit_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_spirit_conclave_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("WRAITHBONE ARMOUR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_spirit_wraithbone_armour_candidates(target_units=list(target_units or []))
        if not candidates or self._aeldari_reaction_exists("fight_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_seer_move_end_reactions(self, *, unit: Any, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_seer_council_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"move", "normal move", "advance", "fall back", "fallback"}:
            return

        enemy_root = self._aeldari_root(unit)
        if enemy_root is None:
            return
        try:
            if enemy_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("ISHA'S FURY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_seer_ishas_fury_candidates(enemy_unit=enemy_root)
        if not candidates:
            return
        if self._aeldari_reaction_exists("unit_move_ended", stratagem.name, unit=enemy_root):
            return
        payload: Dict[str, Any] = {
            "event": "unit_move_ended",
            "phase": "Movement phase",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "attacking_unit": enemy_root,
            "action": str(action or ""),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_seer_shooting_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_seer_council_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("PSYCHIC SHIELD")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_seer_psychic_shield_candidates(target_units=list(target_units or []))
        if not candidates or self._aeldari_reaction_exists("shooting_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_seer_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_seer_council_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("FOREWARNED")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_seer_forewarned_candidates(target_units=list(target_units or []))
        if not candidates or self._aeldari_reaction_exists("fight_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_guardian_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_guardian_battlehost_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_key == "MOVEMENT_PHASE":
            if active_player is not self.player:
                return
            stratagem = self._aeldari_get_stratagem_by_norm_name("TIME TO STRIKE")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_guardian_time_to_strike_candidates()
            if not candidates or self._aeldari_reaction_exists("phase_start", stratagem.name):
                return
            payload: Dict[str, Any] = {
                "event": "phase_start",
                "phase": "Movement phase",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key == "SHOOTING_PHASE":
            if active_player is not self.player:
                return
            blades = self._aeldari_get_stratagem_by_norm_name("BLADES OF ASURYAN")
            if blades is not None:
                if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(blades, "cp_cost", 0) or 0):
                    if self._aeldari_norm_name(blades.name) not in getattr(self, "_used_stratagems_this_phase", set()):
                        blades_candidates = self._aeldari_guardian_dire_avengers_or_guardians_candidates(
                            require_not_shot=True,
                            require_not_fought=False,
                        )
                        if blades_candidates and not self._aeldari_reaction_exists("phase_start", blades.name):
                            payload: Dict[str, Any] = {
                                "event": "phase_start",
                                "phase": "Shooting phase",
                                "phase_name": "Shooting phase",
                                "stratagem": blades.name,
                                "cp_cost": blades.cp_cost,
                                "candidates": blades_candidates,
                            }
                            if len(blades_candidates) == 1:
                                payload["unit"] = blades_candidates[0]
                                payload["target_unit"] = blades_candidates[0]
                            self._queue_reaction(payload, use_timer=False)

        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("WARDING SALVOES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_guardian_dire_avengers_or_guardians_candidates(
            require_not_shot=phase_key == "SHOOTING_PHASE",
            require_not_fought=phase_key == "FIGHT_PHASE",
        )
        if not candidates or self._aeldari_reaction_exists("phase_start", stratagem.name):
            return
        phase_label = "Shooting phase" if phase_key == "SHOOTING_PHASE" else "Fight phase"
        payload = {
            "event": "phase_start",
            "phase": phase_label,
            "phase_name": phase_label,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_guardian_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_guardian_battlehost_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("COST OF VICTORY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_guardian_cost_of_victory_candidates()
        if not candidates or self._aeldari_reaction_exists("phase_end", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_guardian_shooting_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_guardian_battlehost_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        stratagem = self._aeldari_get_stratagem_by_norm_name("SHIELD NODES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_guardian_shield_nodes_candidates(target_units=list(target_units or []))
        if not candidates or self._aeldari_reaction_exists("shooting_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_guardian_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_guardian_battlehost_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        stratagem = self._aeldari_get_stratagem_by_norm_name("SHIELD NODES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        target_list = list(target_units or [])
        candidates = self._aeldari_guardian_shield_nodes_candidates(target_units=target_list)
        if not candidates or self._aeldari_reaction_exists("fight_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": target_list,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_guardian_unit_destroyed_reactions(
        self,
        *,
        unit,
        destroyed_by_unit=None,
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_guardian_battlehost_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        root = self._aeldari_root(unit)
        if root is None:
            return
        try:
            if root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if not self._aeldari_guardian_is_dire_avengers_or_guardians(root):
            return

        enemy_root = self._aeldari_root(destroyed_by_unit)
        if enemy_root is None:
            return
        try:
            if enemy_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("VAUL'S VENGEANCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        if self._aeldari_guardian_vauls_vengeance_used_this_round():
            return
        candidates = self._aeldari_guardian_war_walkers_candidates()
        if not candidates or self._aeldari_reaction_exists("unit_destroyed", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "unit_destroyed",
            "phase_name": str(getattr(self, "_current_phase_name", "") or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "destroyed_unit": root,
            "destroyed_by_unit": enemy_root,
            "enemy_unit": enemy_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_devoted_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_devoted_of_ynnead_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return

        active_player = getattr(game, "get_current_player", lambda: None)()
        tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
        if not isinstance(tracker, dict):
            tracker = {}
            self._aeldari_devoted_models_before_opponent_shooting = tracker
        else:
            tracker.clear()

        if active_player is self.player:
            stratagem = self.get_by_name("SOULSIGHT")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_devoted_soulsight_candidates()
            if not candidates or self._aeldari_reaction_exists("phase_start", stratagem.name):
                return
            payload: Dict[str, Any] = {
                "event": "phase_start",
                "phase": "Shooting phase",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        # Opponent Shooting phase: capture per-unit alive model counts for Death Answers Death.
        for root in self._aeldari_devoted_ynnari_candidates(require_not_shot=False, exclude_wraith_construct=True):
            uid = self._aeldari_sort_key(root)
            if not uid:
                continue
            tracker[uid] = {
                "unit": root,
                "models_before": self._aeldari_models_alive(root),
            }

    def _queue_aeldari_devoted_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_devoted_of_ynnead_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
            if isinstance(tracker, dict):
                tracker.clear()
            return
        stratagem = self.get_by_name("DEATH ANSWERS DEATH")
        if stratagem is None:
            tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
            if isinstance(tracker, dict):
                tracker.clear()
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
            if isinstance(tracker, dict):
                tracker.clear()
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
            if isinstance(tracker, dict):
                tracker.clear()
            return
        candidates = self._aeldari_devoted_death_answers_death_candidates()
        tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
        if isinstance(tracker, dict):
            tracker.clear()
        if not candidates or self._aeldari_reaction_exists("phase_end", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "phase_end",
            "phase": "Shooting phase",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_devoted_shooting_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_devoted_of_ynnead_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        stratagem = self.get_by_name("MACABRE RESILIENCE")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_devoted_macabre_resilience_candidates(target_units=list(target_units or []))
        if not candidates or self._aeldari_reaction_exists("shooting_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _aeldari_devoted_pall_of_dread_objective_candidates(self, *, unit, last_model=None) -> List[Any]:
        game = getattr(self, "game", None)
        if game is None or unit is None:
            return []
        snapshot = getattr(game, "_objective_control_snapshot", None)
        if not isinstance(snapshot, dict) or not snapshot:
            return []
        pos = None
        if last_model is not None:
            try:
                pos = last_model.get_location()
            except (AttributeError, TypeError, ValueError):
                pos = None
        if pos is None:
            try:
                pos = getattr(unit, "position", None)
            except (AttributeError, TypeError, ValueError):
                pos = None
        if pos is None:
            return []
        try:
            ux, uy = float(pos[0]), float(pos[1])
        except (AttributeError, TypeError, ValueError, IndexError):
            return []

        base_radius = 0.0
        if last_model is not None:
            try:
                base = getattr(last_model, "model_base", None)
                if base is not None:
                    base_radius = float(getattr(base, "base_size", 0.0) or 0.0)
            except (AttributeError, TypeError, ValueError):
                base_radius = 0.0

        out: List[Any] = []
        for objective in list(getattr(getattr(game, "map", None), "objectives", []) or []):
            try:
                loc = getattr(objective, "location", None)
                if loc is None or bool(getattr(loc, "removed", False)):
                    continue
                if snapshot.get(loc) is not self.player:
                    continue
                radius = float(getattr(loc, "control_radius", 0.0) or 0.0)
                dx = ux - float(getattr(loc, "x", 0.0) or 0.0)
                dy = uy - float(getattr(loc, "y", 0.0) or 0.0)
                if (dx * dx + dy * dy) ** 0.5 > (radius + base_radius):
                    continue
                out.append(objective)
            except (AttributeError, TypeError, ValueError):
                continue
        return sorted(
            out,
            key=lambda obj: (
                float(getattr(getattr(obj, "location", None), "x", 0.0) or 0.0),
                float(getattr(getattr(obj, "location", None), "y", 0.0) or 0.0),
                str(getattr(obj, "name", "") or ""),
            ),
        )

    def _queue_aeldari_devoted_unit_destroyed_reactions(self, *, unit, last_model=None) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_devoted_of_ynnead_detachment():
            return
        root = self._aeldari_root(unit)
        if root is None:
            return
        try:
            if root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if not self._aeldari_devoted_unit_counts_as_ynnari(root):
            return
        stratagem = self.get_by_name("PALL OF DREAD")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        objective_candidates = self._aeldari_devoted_pall_of_dread_objective_candidates(unit=root, last_model=last_model)
        if not objective_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if reaction.get("event") != "unit_destroyed":
                continue
            if self._aeldari_norm_name(reaction.get("stratagem", "")) != self._aeldari_norm_name(stratagem.name):
                continue
            if reaction.get("unit") is root:
                return
        payload: Dict[str, Any] = {
            "event": "unit_destroyed",
            "phase_name": str(getattr(self, "_current_phase_name", "") or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "last_model": last_model,
            "objective_candidates": objective_candidates,
        }
        if len(objective_candidates) == 1:
            payload["objective"] = objective_candidates[0]
            payload["objective_marker"] = objective_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_devoted_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_devoted_of_ynnead_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            owner_player = attacker_root.get_parent_army().player
        except (AttributeError, TypeError, ValueError):
            return
        target_list = list(target_units or [])

        if owner_player is self.player:
            stratagem = self.get_by_name("EMISSARIES OF YNNEAD")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_devoted_emissaries_candidates(attacking_unit=attacker_root)
            if not candidates:
                return
            if self._aeldari_reaction_exists("fight_targets_selected", stratagem.name, unit=attacker_root):
                return
            payload: Dict[str, Any] = {
                "event": "fight_targets_selected",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "attacking_unit": attacker_root,
                "target_units": target_list,
                "candidates": candidates,
                "unit": attacker_root,
                "target_unit": attacker_root,
            }
            self._queue_reaction(payload, use_timer=False)
            return

        if owner_player is None:
            return
        parting = self.get_by_name("PARTING THE VEIL")
        if parting is not None:
            if self.player.command_points >= int(getattr(parting, "cp_cost", 0) or 0):
                if self._aeldari_norm_name(parting.name) not in getattr(self, "_used_stratagems_this_phase", set()):
                    candidates = self._aeldari_devoted_parting_the_veil_candidates(target_units=target_list)
                    if candidates and not self._aeldari_reaction_exists("fight_targets_selected", parting.name):
                        payload: Dict[str, Any] = {
                            "event": "fight_targets_selected",
                            "phase_name": "Fight phase",
                            "stratagem": parting.name,
                            "cp_cost": parting.cp_cost,
                            "attacking_unit": attacker_root,
                            "target_units": target_list,
                            "candidates": candidates,
                        }
                        if len(candidates) == 1:
                            payload["unit"] = candidates[0]
                            payload["target_unit"] = candidates[0]
                        self._queue_reaction(payload, use_timer=False)

        macabre = self.get_by_name("MACABRE RESILIENCE")
        if macabre is not None:
            if self.player.command_points >= int(getattr(macabre, "cp_cost", 0) or 0):
                if self._aeldari_norm_name(macabre.name) not in getattr(self, "_used_stratagems_this_phase", set()):
                    candidates = self._aeldari_devoted_macabre_resilience_candidates(target_units=target_list)
                    if candidates and not self._aeldari_reaction_exists("fight_targets_selected", macabre.name):
                        payload = {
                            "event": "fight_targets_selected",
                            "phase_name": "Fight phase",
                            "stratagem": macabre.name,
                            "cp_cost": macabre.cp_cost,
                            "attacking_unit": attacker_root,
                            "target_units": target_list,
                            "candidates": candidates,
                        }
                        if len(candidates) == 1:
                            payload["unit"] = candidates[0]
                            payload["target_unit"] = candidates[0]
                        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_ghosts_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_ghosts_of_the_webway_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            owner_player = attacker_root.get_parent_army().player
        except (AttributeError, TypeError, ValueError):
            return
        if owner_player is self.player:
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("HEROES' FALL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        target_list = list(target_units or [])
        candidates = self._aeldari_ghosts_heroes_fall_candidates(target_units=target_list)
        if not candidates or self._aeldari_reaction_exists("fight_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": target_list,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_ghosts_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_ghosts_of_the_webway_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        if phase_key == "CHARGE_PHASE":
            stratagem = self._aeldari_get_stratagem_by_norm_name("BLOODY DANCE")
            if stratagem is not None:
                if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(stratagem, "cp_cost", 0) or 0):
                    if self._aeldari_norm_name(stratagem.name) not in getattr(self, "_used_stratagems_this_phase", set()):
                        candidates, enemy_by_unit = self._aeldari_ghosts_bloody_dance_candidates()
                        if candidates and not self._aeldari_reaction_exists("phase_end", stratagem.name):
                            payload: Dict[str, Any] = {
                                "event": "phase_end",
                                "phase": "Charge phase",
                                "phase_name": "Charge phase",
                                "stratagem": stratagem.name,
                                "cp_cost": stratagem.cp_cost,
                                "candidates": candidates,
                                "enemy_by_unit": enemy_by_unit,
                            }
                            if len(candidates) == 1:
                                payload["unit"] = candidates[0]
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key != "FIGHT_PHASE":
            return
        stratagem = self._aeldari_get_stratagem_by_norm_name("EXIT THE STAGE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_ghosts_exit_the_stage_candidates()
        if not candidates or self._aeldari_reaction_exists("phase_end", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_serpents_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_serpents_brood_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key == "FIGHT_PHASE":
            stratagem = self._aeldari_get_stratagem_by_norm_name("FANGS OF THE BROOD")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_serpents_fangs_candidates()
            if not candidates or self._aeldari_reaction_exists("phase_start", stratagem.name):
                return
            payload: Dict[str, Any] = {
                "event": "phase_start",
                "phase": "Fight phase",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key == "SHOOTING_PHASE":
            active_player = getattr(game, "get_current_player", lambda: None)()
            if active_player is not self.player:
                return
            stratagem = self._aeldari_get_stratagem_by_norm_name("VENOMOUS WRATH")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_serpents_venomous_wrath_candidates()
            if not candidates or self._aeldari_reaction_exists("phase_start", stratagem.name):
                return
            payload: Dict[str, Any] = {
                "event": "phase_start",
                "phase": "Shooting phase",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("STRIKING STRIDE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_serpents_striking_stride_candidates()
        if not candidates or self._aeldari_reaction_exists("phase_start", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "phase_start",
            "phase": "Charge phase",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_serpents_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_serpents_brood_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is None:
            return

        if active_player is self.player:
            stratagem = self._aeldari_get_stratagem_by_norm_name("WEAVERS' COILS")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_serpents_weavers_coils_candidates()
            if not candidates or self._aeldari_reaction_exists("phase_end", stratagem.name):
                return
            payload: Dict[str, Any] = {
                "event": "phase_end",
                "phase": "Fight phase",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("SKYWARD LUNGE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_serpents_skyward_lunge_candidates()
        if not candidates or self._aeldari_reaction_exists("phase_end", stratagem.name):
            return
        payload = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_serpents_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Optional[Dict[Any, int]] = None,
    ) -> None:
        if attacker_unit is None or not self._is_serpents_brood_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return

        root = self._aeldari_root(attacker_unit)
        if root is None:
            return
        try:
            if root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        if not bool(sr.get("serpents_brood_venomous_wrath_active")):
            return
        owner = str(sr.get("serpents_brood_venomous_wrath_turn_owner", "") or "")
        if owner and str(getattr(self.player, "id", "") or "") and owner != str(getattr(self.player, "id", "") or ""):
            return
        try:
            effect_turn = int(sr.get("serpents_brood_venomous_wrath_turn", 0) or 0)
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
            current_turn = 0
        if effect_turn and current_turn and effect_turn != current_turn:
            return
        source = str(sr.get("serpents_brood_venomous_wrath_source", "") or "VENOMOUS WRATH").strip() or "VENOMOUS WRATH"

        for key in (
            "serpents_brood_venomous_wrath_active",
            "serpents_brood_venomous_wrath_turn_owner",
            "serpents_brood_venomous_wrath_turn",
            "serpents_brood_venomous_wrath_source",
        ):
            sr.pop(key, None)
        root.special_rules = sr

        if self._aeldari_in_engagement_range(root):
            return
        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            return
        queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind="venomous_wrath",
            movement_type="move",
            source=source,
            allow_skip=True,
        )

    def _queue_aeldari_serpents_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or not self._is_serpents_brood_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"move", "normal", "normal move", "advance", "fall back", "fallback"}:
            return

        enemy_root = self._aeldari_root(unit)
        if enemy_root is None:
            return
        try:
            if enemy_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("WEAVING STRIDE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_serpents_weaving_stride_candidates(enemy_unit=enemy_root)
        if not candidates:
            return
        if self._aeldari_reaction_exists("unit_move_ended", stratagem.name, unit=enemy_root):
            return
        payload: Dict[str, Any] = {
            "event": "unit_move_ended",
            "phase": "Movement phase",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "attacking_unit": enemy_root,
            "action": str(action or ""),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_ghosts_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or not self._is_ghosts_of_the_webway_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        root = self._aeldari_root(unit)
        if root is None:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        active_player = getattr(game, "get_current_player", lambda: None)()

        if active_player is self.player:
            if action_key not in {"fall back", "fallback"}:
                return
            try:
                if root.get_parent_army().player is not self.player:
                    return
            except (AttributeError, TypeError, ValueError):
                return
            stratagem = self._aeldari_get_stratagem_by_norm_name("MOCKING FLIGHT")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_ghosts_mocking_flight_candidates(moved_unit=root)
            if root not in candidates:
                return
            if self._aeldari_reaction_exists("unit_move_ended", stratagem.name, unit=root):
                return
            payload: Dict[str, Any] = {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "action": action,
                "unit": root,
                "target_unit": root,
                "candidates": [root],
            }
            self._queue_reaction(payload, use_timer=False)
            return

        if action_key not in {"move", "normal", "advance", "fall back", "fallback"}:
            return
        try:
            if root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        stratagem = self._aeldari_get_stratagem_by_norm_name("TRICKSTERS' RETORT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_ghosts_tricksters_retort_candidates(enemy_unit=root)
        if not candidates or self._aeldari_reaction_exists("unit_move_ended", stratagem.name):
            return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "action": action,
            "enemy_unit": root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_ghosts_model_destroyed_reactions(self, *, unit: Any, model: Any) -> None:
        if unit is None or model is None or not self._is_ghosts_of_the_webway_detachment():
            return
        root = self._aeldari_root(unit)
        if root is None:
            return
        try:
            if root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if not self._aeldari_ghosts_staged_death_model_eligible(unit=root, model=model):
            return
        model_id = str(get_entity_id(model) or "")
        if model_id and model_id in self._aeldari_ghosts_staged_death_used_model_ids():
            return
        stratagem = self._aeldari_get_stratagem_by_norm_name("STAGED DEATH")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "model_destroyed_before_removal":
                continue
            if self._aeldari_norm_name(reaction.get("stratagem", "")) != self._aeldari_norm_name(stratagem.name):
                continue
            if str(reaction.get("destroyed_model_id", "") or "") == model_id:
                return
        destroyed_position = None
        get_location = getattr(model, "get_location", None)
        if callable(get_location):
            try:
                pos = get_location()
            except (AttributeError, TypeError, ValueError):
                pos = None
            if isinstance(pos, (list, tuple)) and len(pos) >= 4:
                try:
                    destroyed_position = (
                        float(pos[0]),
                        float(pos[1]),
                        float(pos[2]),
                        float(pos[3]),
                    )
                except (TypeError, ValueError):
                    destroyed_position = None
        phase_name = str(getattr(self, "_current_phase_name", "") or "")
        payload: Dict[str, Any] = {
            "event": "model_destroyed_before_removal",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "destroyed_unit": root,
            "destroyed_model": model,
            "destroyed_model_id": model_id,
            "destroyed_position": destroyed_position,
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_eldritch_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_eldritch_raiders_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            owner_player = attacker_root.get_parent_army().player
        except (AttributeError, TypeError, ValueError):
            return
        if owner_player is self.player:
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("YRIEL'S EXAMPLE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return

        target_list = list(target_units or [])
        candidates = self._aeldari_eldritch_yriels_example_candidates(target_units=target_list)
        if not candidates or self._aeldari_reaction_exists("fight_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": target_list,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_eldritch_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_eldritch_raiders_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        stratagem = self._aeldari_get_stratagem_by_norm_name("WITHDRAW AND REINFORCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_eldritch_withdraw_and_reinforce_candidates()
        if not candidates or self._aeldari_reaction_exists("phase_end", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_aeldari_eldritch_phase_start_effects(self, *, phase) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "COMMAND_PHASE":
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            try:
                members = list(root.get_attached_unit_members() or [])
            except (AttributeError, TypeError, ValueError):
                members = [root]
            if not members:
                members = [root]
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict) or not bool(sr.get("aeldari_raiders_spoils_active")):
                    continue
                remove_mods = getattr(member, "remove_characteristic_modifiers_by_source", None)
                if callable(remove_mods):
                    remove_mods("stratagem:aeldari_raiders_spoils")
                for key in (
                    "aeldari_raiders_spoils_active",
                    "aeldari_raiders_spoils_owner",
                    "aeldari_raiders_spoils_turn",
                    "aeldari_raiders_spoils_source",
                    "aeldari_raiders_spoils_expires_trigger",
                ):
                    sr.pop(key, None)
                member.special_rules = sr

    def _queue_aeldari_eldritch_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_eldritch_raiders_detachment():
            return
        self._cleanup_aeldari_eldritch_phase_start_effects(phase=phase)

        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()

        if phase_key == "COMMAND_PHASE":
            raiders = self._aeldari_get_stratagem_by_norm_name("RAIDERS' SPOILS")
            if raiders is not None:
                if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(raiders, "cp_cost", 0) or 0):
                    if self._aeldari_norm_name(raiders.name) not in getattr(self, "_used_stratagems_this_phase", set()):
                        candidates = self._aeldari_eldritch_raiders_spoils_candidates()
                        if candidates and not self._aeldari_reaction_exists("phase_start", raiders.name):
                            payload: Dict[str, Any] = {
                                "event": "phase_start",
                                "phase": "Command phase",
                                "phase_name": "Command phase",
                                "stratagem": raiders.name,
                                "cp_cost": raiders.cp_cost,
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["unit"] = candidates[0]
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload, use_timer=False)

        if phase_key == "CHARGE_PHASE" and active_player is not self.player:
            impeding = self._aeldari_get_stratagem_by_norm_name("IMPEDING FIRE")
            if impeding is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(impeding, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(impeding.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_eldritch_impeding_fire_source_candidates()
            if not candidates or self._aeldari_reaction_exists("phase_start", impeding.name):
                return
            payload: Dict[str, Any] = {
                "event": "phase_start",
                "phase": "Charge phase",
                "phase_name": "Charge phase",
                "stratagem": impeding.name,
                "cp_cost": impeding.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
                enemy_candidates = self._aeldari_eldritch_impeding_fire_enemy_candidates(candidates[0])
                if enemy_candidates:
                    payload["enemy_candidates"] = enemy_candidates
                    if len(enemy_candidates) == 1:
                        payload["enemy_unit"] = enemy_candidates[0]
            self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_armoured_move_end_reactions(self, *, unit, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_armoured_warhost_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        root = self._aeldari_root(unit)
        if root is None:
            return
        try:
            if root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        action_key = str(action or "").strip().lower().replace("_", " ")

        if action_key == "advance":
            stratagem = self.get_by_name("SWIFT DEPLOYMENT")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_armoured_vehicle_candidates(
                require_fly=False,
                require_transport=True,
                require_on_battlefield=True,
            )
            if root not in candidates:
                return
            if not bool(getattr(getattr(root, "round_state", None), "advanced_this_round", False)):
                return
            if self._aeldari_reaction_exists("unit_move_ended", stratagem.name, unit=root):
                return
            self._queue_reaction(
                {
                    "event": "unit_move_ended",
                    "phase_name": "Movement phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "action": action,
                    "unit": root,
                    "target_unit": root,
                    "transport_unit": root,
                }
            )
            return

        if action_key in ("fall back", "fallback"):
            stratagem = self.get_by_name("VECTORED ENGINES")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_armoured_vehicle_candidates(
                require_fly=True,
                require_transport=False,
                require_on_battlefield=True,
            )
            if root not in candidates:
                return
            if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                return
            if self._aeldari_reaction_exists("unit_move_ended", stratagem.name, unit=root):
                return
            self._queue_reaction(
                {
                    "event": "unit_move_ended",
                    "phase_name": "Movement phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "action": action,
                    "unit": root,
                    "target_unit": root,
                }
            )

    def _queue_aeldari_armoured_charge_declared_reactions(self, *, charging_unit, target_units: List[Any]) -> None:
        game = getattr(self, "game", None)
        if game is None or charging_unit is None or not self._is_armoured_warhost_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("ANTI\u2011GRAV REPULSION") or self.get_by_name("ANTI-GRAV REPULSION")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_armoured_anti_grav_targets(list(target_units or []))
        if not candidates:
            return
        if self._aeldari_reaction_exists("charge_declared", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "charge_declared",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "charging_unit": charging_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_aeldari_armoured_layered_wards_reaction(
        self,
        *,
        target_unit,
        attacker_unit=None,
        target_model=None,
        phase_name: str = "",
        trigger_event: str = "mortal_wound_allocated",
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or target_unit is None or not self._is_armoured_warhost_detachment():
            return
        root = self._aeldari_root(target_unit)
        if root is None:
            return
        try:
            if root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        candidates = self._aeldari_armoured_vehicle_candidates(
            require_fly=False,
            require_transport=False,
            require_on_battlefield=True,
        )
        if root not in candidates:
            return
        stratagem = self.get_by_name("LAYERED WARDS")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        if self._aeldari_reaction_exists(trigger_event, stratagem.name, unit=root):
            return
        phase_label = str(phase_name or getattr(self, "_current_phase_name", "") or "").strip() or "Any phase"
        self._queue_reaction(
            {
                "event": str(trigger_event or "mortal_wound_allocated"),
                "phase_name": phase_label,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "attacker_unit": attacker_unit,
                "target_model": target_model,
            }
        )

    def _resolve_aeldari_ghosts_phase_end_effects(self, *, player, phase) -> None:
        if not self._is_ghosts_of_the_webway_detachment():
            return
        pending = self._aeldari_ghosts_staged_death_pending_returns()
        if not pending:
            return
        phase_key = self._aeldari_phase_key_from_name(
            getattr(phase, "name", "") or getattr(self, "_current_phase_name", "")
        )
        if not phase_key:
            return
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        find_pos = getattr(game, "_find_closest_valid_reposition_position", None) if game is not None else None
        remaining: List[Dict[str, Any]] = []
        for entry in list(pending):
            if not isinstance(entry, dict):
                continue
            trigger_key = self._aeldari_phase_key_from_name(
                entry.get("trigger_phase_key") or entry.get("trigger_phase_name") or ""
            )
            if trigger_key and trigger_key != phase_key:
                remaining.append(entry)
                continue
            root = self._aeldari_root(entry.get("unit"))
            model = entry.get("model")
            if root is None or model is None:
                continue

            try:
                in_unit = model in list(getattr(root, "models", []) or [])
            except (AttributeError, TypeError, ValueError):
                in_unit = False
            if not in_unit:
                try:
                    if model in list(getattr(root, "models_lost", []) or []):
                        root.models_lost.remove(model)
                except (AttributeError, TypeError, ValueError):
                    pass
                add_model = getattr(root, "add_model", None)
                if callable(add_model):
                    try:
                        add_model(model)
                    except (AttributeError, TypeError, ValueError):
                        try:
                            root.models.append(model)
                        except (AttributeError, TypeError, ValueError):
                            pass
                else:
                    try:
                        root.models.append(model)
                    except (AttributeError, TypeError, ValueError):
                        pass

            try:
                starting_wounds = int(
                    getattr(
                        model,
                        "_base_wounds",
                        getattr(model, "base_wounds", getattr(model, "wounds", getattr(model, "_wounds", 1))),
                    )
                    or 1
                )
            except (AttributeError, TypeError, ValueError):
                starting_wounds = 1
            wounds_remaining = max(1, (int(starting_wounds) + 1) // 2)
            try:
                model.wounds = int(wounds_remaining)
            except (AttributeError, TypeError, ValueError):
                try:
                    model._wounds = int(wounds_remaining)
                except (AttributeError, TypeError, ValueError):
                    pass

            for key, value in (
                ("_on_death_reactions_resolved", False),
                ("_fight_on_death_used", False),
                ("_shoot_on_death_used", False),
            ):
                try:
                    setattr(model, key, value)
                except (AttributeError, TypeError, ValueError):
                    pass

            anchor = entry.get("destroyed_position")
            if anchor is None:
                get_location = getattr(model, "get_location", None)
                if callable(get_location):
                    try:
                        anchor = get_location()
                    except (AttributeError, TypeError, ValueError):
                        anchor = None
            placement = None
            if callable(find_pos) and isinstance(anchor, (list, tuple)) and len(anchor) >= 3:
                try:
                    placement = find_pos(root, anchor, game_map=game_map)
                except (AttributeError, TypeError, ValueError):
                    placement = None
            if placement is None and isinstance(anchor, (list, tuple)) and len(anchor) >= 4:
                try:
                    placement = (float(anchor[0]), float(anchor[1]), float(anchor[2]), float(anchor[3]))
                except (TypeError, ValueError):
                    placement = None
            if placement is not None:
                try:
                    model.set_location(
                        float(placement[0]),
                        float(placement[1]),
                        float(placement[2]),
                        float(placement[3]),
                    )
                except (AttributeError, TypeError, ValueError):
                    pass

            root.deployed = True
            try:
                root.reserve_status = "deployed"
            except (AttributeError, TypeError, ValueError):
                pass
            try:
                root.embarked_in = None
            except (AttributeError, TypeError, ValueError):
                pass
            try:
                root.is_embarked = False
            except (AttributeError, TypeError, ValueError):
                pass

            if game_map is not None:
                units = list(getattr(game_map, "units", []) or [])
                if root not in units:
                    place_unit = getattr(game_map, "place_unit", None)
                    if callable(place_unit):
                        try:
                            placed = bool(place_unit(root))
                        except (AttributeError, TypeError, ValueError):
                            placed = False
                        if not placed and isinstance(getattr(game_map, "units", None), list):
                            game_map.units.append(root)
                    elif isinstance(getattr(game_map, "units", None), list):
                        game_map.units.append(root)
            logger.info(
                "INFO: STAGED DEATH: returned %s with %d wound(s).",
                getattr(model, "name", "Model"),
                int(wounds_remaining),
            )
        self._aeldari_ghosts_staged_death_pending = remaining

    def _cleanup_aeldari_armoured_phase_end_effects(self, *, phase) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_key:
            return
        game = getattr(self, "game", None)
        cur_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        get_current = getattr(game, "get_current_player", None) if game is not None else None
        current_player = get_current() if callable(get_current) else None
        current_owner = str(getattr(current_player, "id", "") or "")
        self_owner = str(getattr(self.player, "id", "") or "")

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        own_units = list(getattr(army, "units", []) or []) if army is not None else []
        seen: set[str] = set()
        roots: list[Any] = []
        for unit in own_units:
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            roots.append(root)

        for root in roots:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("soulsight_active")):
                for key in (
                    "soulsight_active",
                    "soulsight_owner",
                    "soulsight_turn",
                    "soulsight_expires_phase",
                    "soulsight_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                try:
                    models = list(root.get_attached_unit_models() or [])
                except (AttributeError, TypeError, ValueError):
                    models = list(getattr(root, "models", []) or [])
                for model in models:
                    try:
                        source = str(getattr(model, "get_selected_to_shoot_reroll_source", lambda: "")() or "")
                    except Exception:
                        source = ""
                    if "SOULSIGHT" in source.upper() and hasattr(model, "clear_selected_to_shoot_rerolls"):
                        try:
                            model.clear_selected_to_shoot_rerolls()
                        except Exception:
                            continue

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("aeldari_devoted_soulsight_active")):
                for key in (
                    "aeldari_devoted_soulsight_active",
                    "aeldari_devoted_soulsight_expires_phase",
                    "aeldari_devoted_soulsight_owner",
                    "aeldari_devoted_soulsight_turn",
                    "aeldari_devoted_soulsight_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("aeldari_cloak_and_shadow_active")):
                for key in (
                    "aeldari_cloak_and_shadow_active",
                    "aeldari_cloak_and_shadow_targeting_range",
                    "aeldari_cloak_and_shadow_expires_phase",
                    "aeldari_cloak_and_shadow_turn_owner",
                    "aeldari_cloak_and_shadow_turn",
                    "aeldari_cloak_and_shadow_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("aeldari_fate_inescapable_active")):
                for key in (
                    "aeldari_fate_inescapable_active",
                    "aeldari_fate_inescapable_expires_phase",
                    "aeldari_fate_inescapable_turn_owner",
                    "aeldari_fate_inescapable_turn",
                    "aeldari_fate_inescapable_source",
                    "aeldari_fate_inescapable_critical_ap_bonus",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("aeldari_psychic_shield_active")):
                for key in (
                    "aeldari_psychic_shield_active",
                    "aeldari_psychic_shield_targeting_range",
                    "aeldari_psychic_shield_expires_phase",
                    "aeldari_psychic_shield_turn_owner",
                    "aeldari_psychic_shield_turn",
                    "aeldari_psychic_shield_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("aeldari_outcast_ambush_active")):
                for key in (
                    "aeldari_outcast_ambush_active",
                    "aeldari_outcast_ambush_expires_phase",
                    "aeldari_outcast_ambush_turn_owner",
                    "aeldari_outcast_ambush_turn",
                    "aeldari_outcast_ambush_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("aeldari_no_prey_too_big_active")):
                for key in (
                    "aeldari_no_prey_too_big_active",
                    "aeldari_no_prey_too_big_wound_bonus",
                    "aeldari_no_prey_too_big_expires_phase",
                    "aeldari_no_prey_too_big_turn_owner",
                    "aeldari_no_prey_too_big_turn",
                    "aeldari_no_prey_too_big_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("aeldari_blades_of_asuryan_active")):
                for key in (
                    "aeldari_blades_of_asuryan_active",
                    "aeldari_blades_of_asuryan_expires_phase",
                    "aeldari_blades_of_asuryan_turn_owner",
                    "aeldari_blades_of_asuryan_turn",
                    "aeldari_blades_of_asuryan_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "MOVEMENT_PHASE":
                adv_effects = list(sr.get("advance_no_roll_effects", []) or [])
                filtered_effects = [
                    effect
                    for effect in adv_effects
                    if not (
                        isinstance(effect, dict)
                        and str(effect.get("tag", "") or "") == "stratagem:aeldari_time_to_strike"
                    )
                ]
                if len(filtered_effects) != len(adv_effects):
                    if filtered_effects:
                        sr["advance_no_roll_effects"] = filtered_effects
                    else:
                        sr.pop("advance_no_roll_effects", None)
                    changed = True

            if bool(sr.get("aeldari_warding_salvoes_active")):
                expires = str(sr.get("aeldari_warding_salvoes_expires_phase", "") or "").strip().upper()
                if not expires or expires == phase_key:
                    for key in (
                        "aeldari_warding_salvoes_active",
                        "aeldari_warding_salvoes_expires_phase",
                        "aeldari_warding_salvoes_turn_owner",
                        "aeldari_warding_salvoes_turn",
                        "aeldari_warding_salvoes_source",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True

            if phase_key == "FIGHT_PHASE" and bool(sr.get("aeldari_pirates_due_active")):
                for key in (
                    "aeldari_pirates_due_active",
                    "aeldari_pirates_due_expires_phase",
                    "aeldari_pirates_due_turn_owner",
                    "aeldari_pirates_due_turn",
                    "aeldari_pirates_due_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "FIGHT_PHASE" and bool(sr.get("aeldari_emissaries_of_ynnead_active")):
                for key in (
                    "aeldari_emissaries_of_ynnead_active",
                    "aeldari_emissaries_of_ynnead_expires_phase",
                    "aeldari_emissaries_of_ynnead_owner",
                    "aeldari_emissaries_of_ynnead_turn",
                    "aeldari_emissaries_of_ynnead_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "FIGHT_PHASE" and bool(sr.get("aeldari_parting_the_veil_active")):
                for key in (
                    "aeldari_parting_the_veil_active",
                    "aeldari_parting_the_veil_expires_phase",
                    "aeldari_parting_the_veil_owner",
                    "aeldari_parting_the_veil_turn",
                    "aeldari_parting_the_veil_source",
                    "aeldari_parting_the_veil_automatic",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                self._aeldari_clear_melee_fight_on_death_cache(root)

            if phase_key == "FIGHT_PHASE" and bool(sr.get("aeldari_heroes_fall_active")):
                for key in (
                    "aeldari_heroes_fall_active",
                    "aeldari_heroes_fall_expires_phase",
                    "aeldari_heroes_fall_owner",
                    "aeldari_heroes_fall_turn",
                    "aeldari_heroes_fall_source",
                    "aeldari_heroes_fall_threshold",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                self._aeldari_clear_melee_fight_on_death_cache(root)

            if bool(sr.get("aeldari_ruthless_killers_active")):
                ruthless_exp = str(sr.get("aeldari_ruthless_killers_expires_phase", "") or "").strip().upper()
                if not ruthless_exp or ruthless_exp == phase_key:
                    for key in (
                        "aeldari_ruthless_killers_active",
                        "aeldari_ruthless_killers_damage_bonus",
                        "aeldari_ruthless_killers_expires_phase",
                        "aeldari_ruthless_killers_turn_owner",
                        "aeldari_ruthless_killers_turn",
                        "aeldari_ruthless_killers_source",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True

            if phase_key == "MOVEMENT_PHASE":
                if (
                    "cloudstrike_temp_deep_strike" in sr
                    or "cloudstrike_deep_strike_min_distance" in sr
                    or "cloudstrike_expires_phase" in sr
                ):
                    for key in (
                        "cloudstrike_temp_deep_strike",
                        "cloudstrike_deep_strike_min_distance",
                        "cloudstrike_expires_phase",
                        "cloudstrike_source",
                        "cloudstrike_no_charge_on_arrival",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
                    try:
                        if hasattr(root, "_ability_cache") and isinstance(root._ability_cache, dict):
                            root._ability_cache.pop("deep_strike", None)
                    except Exception:
                        pass

            if phase_key == "CHARGE_PHASE" and current_owner == self_owner:
                for key in (
                    "cloudstrike_no_charge_turn_owner",
                    "cloudstrike_no_charge_turn",
                    "swift_deployment_no_charge_turn_owner",
                    "swift_deployment_no_charge_turn",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "FIGHT_PHASE" and current_owner == self_owner:
                for key in (
                    "vectored_engines_active",
                    "vectored_engines_turn_owner",
                    "vectored_engines_turn",
                    "vectored_engines_source",
                    "aeldari_lethal_ruse_charge_after_fall_back_active",
                    "aeldari_lethal_ruse_turn_owner",
                    "aeldari_lethal_ruse_turn",
                    "aeldari_lethal_ruse_source",
                    "swift_deployment_active",
                    "swift_deployment_turn_owner",
                    "swift_deployment_turn",
                    "swift_deployment_expires_phase",
                    "swift_deployment_source",
                    "cloudstrike_transport_disembark_min_enemy_distance",
                    "cloudstrike_transport_no_charge_disembark",
                    "cloudstrike_transport_disembark_turn_owner",
                    "cloudstrike_transport_disembark_turn",
                    "cloudstrike_transport_disembark_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            fnp_entries = sr.get("bearer_unit_fnp")
            if isinstance(fnp_entries, list):
                keep = []
                removed = False
                for entry in fnp_entries:
                    if not isinstance(entry, dict):
                        keep.append(entry)
                        continue
                    if str(entry.get("source_key", "") or "") != "aeldari_layered_wards":
                        keep.append(entry)
                        continue
                    exp = str(entry.get("expires_phase", "") or "").strip().upper()
                    if exp and exp != phase_key:
                        keep.append(entry)
                        continue
                    removed = True
                if removed:
                    changed = True
                if keep:
                    sr["bearer_unit_fnp"] = keep
                else:
                    sr.pop("bearer_unit_fnp", None)

            if changed:
                root.special_rules = sr

        if phase_key == "SHOOTING_PHASE":
            snapshot = getattr(self, "_aeldari_corsair_models_before_shooting", None)
            if isinstance(snapshot, dict):
                snapshot.clear()
            into_breach = getattr(self, "_aeldari_corsair_into_the_breach_ready", None)
            if isinstance(into_breach, dict):
                into_breach.clear()

        if phase_key == "MOVEMENT_PHASE":
            fall_back_tracker = getattr(self, "_aeldari_corsair_fall_back_start_engagements", None)
            if isinstance(fall_back_tracker, dict):
                fall_back_tracker.clear()

        if phase_key == "CHARGE_PHASE" and game is not None:
            for p in list(getattr(game, "players", []) or []):
                p_army = getattr(p, "get_army", lambda: None)()
                for unit in list(getattr(p_army, "units", []) or []):
                    root = self._aeldari_root(unit)
                    if root is None:
                        continue
                    sr = getattr(root, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    mods = sr.get("charge_roll_modifiers")
                    if not isinstance(mods, list):
                        continue
                    keep = []
                    removed = False
                    for item in mods:
                        if not isinstance(item, dict):
                            keep.append(item)
                            continue
                        source_key = str(item.get("source_key", "") or "")
                        if source_key not in {"aeldari_anti_grav_repulsion", "aeldari_impeding_fire"}:
                            keep.append(item)
                            continue
                        exp = str(item.get("expires_phase", "") or "").strip().upper()
                        if exp and exp != phase_key:
                            keep.append(item)
                            continue
                        removed = True
                    if removed:
                        if keep:
                            sr["charge_roll_modifiers"] = keep
                        else:
                            sr.pop("charge_roll_modifiers", None)
                        root.special_rules = sr

    def _cleanup_aeldari_serpents_phase_end_effects(self, *, phase) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE", "CHARGE_PHASE"}:
            return
        if not self._is_serpents_brood_detachment():
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            if phase_key == "FIGHT_PHASE":
                for key in (
                    "serpents_brood_fangs_of_the_brood_active",
                    "serpents_brood_fangs_of_the_brood_turn_owner",
                    "serpents_brood_fangs_of_the_brood_turn",
                    "serpents_brood_fangs_of_the_brood_expires_phase",
                    "serpents_brood_fangs_of_the_brood_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "SHOOTING_PHASE":
                for key in (
                    "serpents_brood_venomous_wrath_active",
                    "serpents_brood_venomous_wrath_turn_owner",
                    "serpents_brood_venomous_wrath_turn",
                    "serpents_brood_venomous_wrath_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "CHARGE_PHASE":
                for key in (
                    "serpents_brood_striking_stride_active",
                    "serpents_brood_striking_stride_turn_owner",
                    "serpents_brood_striking_stride_turn",
                    "serpents_brood_striking_stride_expires_phase",
                    "serpents_brood_striking_stride_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if changed:
                root.special_rules = sr

    def _use_aeldari_armoured_warhost_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_armoured_warhost_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u in ("ANTI-GRAV REPULSION",):
            return self._use_aeldari_armoured_anti_grav_repulsion(stratagem, **kwargs)
        if name_u == "CLOUDSTRIKE":
            return self._use_aeldari_armoured_cloudstrike(stratagem, **kwargs)
        if name_u == "LAYERED WARDS":
            return self._use_aeldari_armoured_layered_wards(stratagem, **kwargs)
        if name_u == "SOULSIGHT":
            return self._use_aeldari_armoured_soulsight(stratagem, **kwargs)
        if name_u == "SWIFT DEPLOYMENT":
            return self._use_aeldari_armoured_swift_deployment(stratagem, **kwargs)
        if name_u == "VECTORED ENGINES":
            return self._use_aeldari_armoured_vectored_engines(stratagem, **kwargs)
        return None

    def _use_aeldari_armoured_anti_grav_repulsion(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: ANTI-GRAV REPULSION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: ANTI-GRAV REPULSION: not opponent's turn")
            return False
        charging_unit = context.get("charging_unit") or context.get("enemy_unit") or context.get("attacker_unit")
        charging_root = self._aeldari_root(charging_unit)
        if charging_root is None:
            logger.error("ERROR: ANTI-GRAV REPULSION: missing charging unit")
            return False
        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        candidates = self._aeldari_armoured_anti_grav_targets(target_units)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ANTI-GRAV REPULSION: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: ANTI-GRAV REPULSION: target was not selected as a charge target")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=charging_root):
            return False
        sr = getattr(charging_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        mods = sr.get("charge_roll_modifiers")
        if not isinstance(mods, list):
            mods = []
        target_id = self._aeldari_sort_key(target_root)
        mods.append(
            {
                "value": -2,
                "source": str(getattr(stratagem, "name", "ANTI-GRAV REPULSION") or "ANTI-GRAV REPULSION"),
                "source_key": "aeldari_anti_grav_repulsion",
                "expires_phase": "CHARGE_PHASE",
                "target_unit_ids": [target_id] if target_id else [],
            }
        )
        sr["charge_roll_modifiers"] = mods
        charging_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_armoured_cloudstrike(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: CLOUDSTRIKE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: CLOUDSTRIKE: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_armoured_cloudstrike_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: CLOUDSTRIKE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: CLOUDSTRIKE: target must be an AELDARI VEHICLE FLY unit in Strategic Reserves")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["cloudstrike_temp_deep_strike"] = True
        sr["cloudstrike_deep_strike_min_distance"] = 6.0
        sr["cloudstrike_expires_phase"] = "MOVEMENT_PHASE"
        sr["cloudstrike_source"] = str(getattr(stratagem, "name", "CLOUDSTRIKE") or "CLOUDSTRIKE")
        sr["cloudstrike_no_charge_on_arrival"] = True
        if owner:
            sr["cloudstrike_turn_owner"] = owner
        if turn:
            sr["cloudstrike_turn"] = turn
        if bool(getattr(target_root, "is_transport", False)):
            sr["cloudstrike_transport_disembark_min_enemy_distance"] = 6.0
            sr["cloudstrike_transport_no_charge_disembark"] = True
            if owner:
                sr["cloudstrike_transport_disembark_turn_owner"] = owner
            if turn:
                sr["cloudstrike_transport_disembark_turn"] = turn
            sr["cloudstrike_transport_disembark_source"] = str(
                getattr(stratagem, "name", "CLOUDSTRIKE") or "CLOUDSTRIKE"
            )
        target_root.special_rules = sr
        try:
            if hasattr(target_root, "_ability_cache") and isinstance(target_root._ability_cache, dict):
                target_root._ability_cache.pop("deep_strike", None)
        except Exception:
            pass
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_armoured_layered_wards(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            logger.error("ERROR: LAYERED WARDS: missing target unit")
            return False
        candidates = self._aeldari_armoured_vehicle_candidates(
            require_fly=False,
            require_transport=False,
            require_on_battlefield=True,
        )
        if target_root not in candidates:
            logger.error("ERROR: LAYERED WARDS: target must be an AELDARI VEHICLE")
            return False
        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=context.get("attacker_unit"),
        ):
            return False
        game = getattr(self, "game", None)
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if not phase_key:
            phase_key = "ANY_PHASE"
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        existing = list(sr.get("bearer_unit_fnp", []) or [])
        keep = []
        for entry in existing:
            if not isinstance(entry, dict):
                keep.append(entry)
                continue
            if str(entry.get("source_key", "") or "") != "aeldari_layered_wards":
                keep.append(entry)
                continue
            exp = str(entry.get("expires_phase", "") or "").strip().upper()
            if exp != phase_key:
                keep.append(entry)
        keep.append(
            {
                "value": 5,
                "condition": "against mortal wounds",
                "source": str(getattr(stratagem, "name", "LAYERED WARDS") or "LAYERED WARDS"),
                "source_key": "aeldari_layered_wards",
                "expires_phase": phase_key,
            }
        )
        sr["bearer_unit_fnp"] = keep
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_armoured_soulsight(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SOULSIGHT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: SOULSIGHT: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_armoured_soulsight_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: SOULSIGHT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: SOULSIGHT: target must be an AELDARI VEHICLE that has not shot")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["soulsight_active"] = True
        sr["soulsight_expires_phase"] = "SHOOTING_PHASE"
        sr["soulsight_source"] = str(getattr(stratagem, "name", "SOULSIGHT") or "SOULSIGHT")
        if owner:
            sr["soulsight_owner"] = owner
        if turn:
            sr["soulsight_turn"] = turn
        target_root.special_rules = sr
        try:
            models = list(target_root.get_attached_unit_models() or [])
        except (AttributeError, TypeError, ValueError):
            models = list(getattr(target_root, "models", []) or [])
        for model in list(models or []):
            try:
                if not getattr(model, "is_alive", False):
                    continue
            except Exception:
                continue
            grant = getattr(model, "grant_selected_to_shoot_rerolls", None)
            if callable(grant):
                try:
                    grant(hit=True, wound=True, damage=True, source=stratagem.name or "SOULSIGHT")
                except Exception:
                    continue
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_armoured_swift_deployment(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: SWIFT DEPLOYMENT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: SWIFT DEPLOYMENT: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit") or context.get("transport_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_armoured_vehicle_candidates(
            require_fly=False,
            require_transport=True,
            require_on_battlefield=True,
        )
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: SWIFT DEPLOYMENT: missing target transport")
                return False
        if target_root not in candidates:
            logger.error("ERROR: SWIFT DEPLOYMENT: target must be an AELDARI TRANSPORT")
            return False
        if not bool(getattr(getattr(target_root, "round_state", None), "advanced_this_round", False)):
            logger.error("ERROR: SWIFT DEPLOYMENT: target transport has not Advanced")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["swift_deployment_active"] = True
        sr["swift_deployment_expires_phase"] = "MOVEMENT_PHASE"
        sr["swift_deployment_source"] = str(getattr(stratagem, "name", "SWIFT DEPLOYMENT") or "SWIFT DEPLOYMENT")
        if owner:
            sr["swift_deployment_turn_owner"] = owner
        if turn:
            sr["swift_deployment_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_armoured_vectored_engines(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: VECTORED ENGINES: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: VECTORED ENGINES: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_armoured_vehicle_candidates(
            require_fly=True,
            require_transport=False,
            require_on_battlefield=True,
        )
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: VECTORED ENGINES: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: VECTORED ENGINES: target must be an AELDARI VEHICLE that can FLY")
            return False
        if not bool(getattr(getattr(target_root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: VECTORED ENGINES: target unit has not Fallen Back")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["vectored_engines_active"] = True
        sr["vectored_engines_source"] = str(getattr(stratagem, "name", "VECTORED ENGINES") or "VECTORED ENGINES")
        if owner:
            sr["vectored_engines_turn_owner"] = owner
        if turn:
            sr["vectored_engines_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_seer_council_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_seer_council_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "PRESENTIMENT OF DREAD":
            return self._use_aeldari_seer_presentiment_of_dread(stratagem, **kwargs)
        if name_u == "FOREWARNED":
            return self._use_aeldari_seer_forewarned(stratagem, **kwargs)
        if name_u == "FATE INESCAPABLE":
            return self._use_aeldari_seer_fate_inescapable(stratagem, **kwargs)
        if name_u == "UNSHROUDED TRUTH":
            return self._use_aeldari_seer_unshrouded_truth(stratagem, **kwargs)
        if name_u in {"ISHA'S FURY", "ISHA’S FURY"}:
            return self._use_aeldari_seer_ishas_fury(stratagem, **kwargs)
        if name_u == "PSYCHIC SHIELD":
            return self._use_aeldari_seer_psychic_shield(stratagem, **kwargs)
        return None

    def _use_aeldari_seer_presentiment_of_dread(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: PRESENTIMENT OF DREAD: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False

        source_unit = context.get("unit") or context.get("target_unit")
        source_root = self._aeldari_root(source_unit) if source_unit is not None else None
        source_candidates = list(context.get("candidates") or [])
        if not source_candidates:
            source_candidates = self._aeldari_seer_presentiment_psyker_candidates()
        if source_root is None:
            if len(source_candidates) == 1:
                source_root = source_candidates[0]
            else:
                logger.error("ERROR: PRESENTIMENT OF DREAD: missing ASURYANI PSYKER source model")
                return False
        if source_root not in source_candidates:
            logger.error("ERROR: PRESENTIMENT OF DREAD: source must be an eligible ASURYANI PSYKER model")
            return False

        enemy_unit = context.get("enemy_unit") or context.get("target_enemy_unit")
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        enemy_candidates = list(context.get("enemy_candidates") or [])
        if not enemy_candidates:
            enemy_candidates = self._aeldari_seer_presentiment_enemy_candidates(source_root)
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: PRESENTIMENT OF DREAD: missing enemy target unit")
                return False
        if enemy_root not in enemy_candidates:
            logger.error("ERROR: PRESENTIMENT OF DREAD: enemy target must be visible and within 18\" of source model")
            return False

        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=source_root, enemy_unit=enemy_root):
            return False

        sr = getattr(enemy_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["battle_shock_test_modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0) - 1
        reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
        reasons.append(str(getattr(stratagem, "name", "PRESENTIMENT OF DREAD") or "PRESENTIMENT OF DREAD"))
        sr["battle_shock_test_modifier_reasons"] = reasons
        enemy_root.special_rules = sr

        take_test = getattr(enemy_root, "take_battle_shock_test", None)
        if callable(take_test):
            take_test(int(getattr(game, "turn", 0) or 0))

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: PRESENTIMENT OF DREAD: %s takes a Battle-shock test at -1.",
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_aeldari_seer_forewarned(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: FOREWARNED: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False

        attacking_unit = context.get("attacking_unit") or context.get("enemy_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        if attacking_root is not None:
            try:
                if attacking_root.get_parent_army().player is self.player:
                    logger.error("ERROR: FOREWARNED: attacking unit must be enemy")
                    return False
            except (AttributeError, TypeError, ValueError):
                return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        target_window = list(context.get("target_units") or [])
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_seer_forewarned_candidates(target_units=target_window)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: FOREWARNED: missing target unit")
                return False
        if target_root not in candidates:
            logger.error(
                "ERROR: FOREWARNED: target must be an eligible ASURYANI INFANTRY non-WRAITH CONSTRUCT unit selected as an enemy fight target and within 9\" of a friendly ASURYANI PSYKER"
            )
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False

        source_name = str(getattr(stratagem, "name", "FOREWARNED") or "FOREWARNED")
        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "FIGHT_PHASE",
            "source": source_name,
        }
        self._append_defensive_effect(target_root, "defensive_hit_mods", dict(entry))
        self._append_defensive_effect(target_root, "defensive_wound_mods", dict(entry))

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: FOREWARNED: attacks targeting %s are -1 to Hit and -1 to Wound this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_seer_fate_inescapable(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FATE INESCAPABLE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: FATE INESCAPABLE: not your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_seer_fate_inescapable_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: FATE INESCAPABLE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error(
                "ERROR: FATE INESCAPABLE: target must be an eligible ASURYANI INFANTRY non-WRAITH CONSTRUCT unit that has not shot"
            )
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        effect_owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        source_name = str(getattr(stratagem, "name", "FATE INESCAPABLE") or "FATE INESCAPABLE")
        try:
            members = list(target_root.get_attached_unit_members() or [])
        except (AttributeError, TypeError, ValueError):
            members = [target_root]
        if not members:
            members = [target_root]
        for unit in members:
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["aeldari_fate_inescapable_active"] = True
            sr["aeldari_fate_inescapable_expires_phase"] = "SHOOTING_PHASE"
            sr["aeldari_fate_inescapable_turn_owner"] = effect_owner
            sr["aeldari_fate_inescapable_turn"] = int(turn)
            sr["aeldari_fate_inescapable_source"] = source_name
            sr["aeldari_fate_inescapable_critical_ap_bonus"] = 1
            unit.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: FATE INESCAPABLE: %s gains [IGNORES COVER], and on Critical Wounds improves AP by 1 this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_seer_unshrouded_truth(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: UNSHROUDED TRUTH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: UNSHROUDED TRUTH: not your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_seer_unshrouded_truth_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: UNSHROUDED TRUTH: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: UNSHROUDED TRUTH: target must be an eligible ASURYANI INFANTRY unit")
            return False

        unit_id = str(get_entity_id(target_root) or "")
        if not unit_id:
            logger.error("ERROR: UNSHROUDED TRUTH: target unit id missing")
            return False
        allowed_ids = [str(get_entity_id(model) or "") for model in list(getattr(target_root, "models", []) or [])]
        allowed_ids = [model_id for model_id in allowed_ids if model_id]
        if not allowed_ids:
            logger.error("ERROR: UNSHROUDED TRUTH: target unit has no models to place")
            return False
        request_decision = getattr(game, "request_decision", None)
        if not callable(request_decision):
            logger.error("ERROR: UNSHROUDED TRUTH: move decision queue unavailable")
            return False
        from ..engine.decision_kinds import DECISION_MOVE_UNIT
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != str(DECISION_MOVE_UNIT):
                    continue
                req_ctx = dict(getattr(req, "context", {}) or {})
                if str(req_ctx.get("placement_kind", "") or "") != "aeldari_unshrouded_truth":
                    continue
                if str(req_ctx.get("unit_id", "") or "") != unit_id:
                    continue
                logger.error("ERROR: UNSHROUDED TRUTH: placement decision already queued for target unit")
                return False

        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        for member in list(getattr(target_root, "get_attached_unit_members", lambda: [target_root])() or [target_root]):
            round_state = getattr(member, "round_state", None)
            if round_state is None:
                continue
            round_state.moved_this_round = True
            round_state.remained_stationary_this_round = False

        request = DecisionRequest.create(
            DECISION_MOVE_UNIT,
            f"{getattr(stratagem, 'name', 'UNSHROUDED TRUTH')}: set up {getattr(target_root, 'name', 'Unit')}",
            player_id=getattr(self.player, "id", None),
            options=[
                DecisionOption.create(
                    "Confirm",
                    payload={"unit_id": unit_id, "movement_type": "deploy", "action": "confirm"},
                )
            ],
            context={
                "unit_id": unit_id,
                "movement_type": "deploy",
                "placement_kind": "aeldari_unshrouded_truth",
                "allowed_model_ids": list(allowed_ids),
                "allow_skip": False,
                "ability_name": str(getattr(stratagem, "name", "UNSHROUDED TRUTH") or "UNSHROUDED TRUTH"),
            },
        )
        request_decision(request)
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: UNSHROUDED TRUTH: %s must be set up again more than 9\" horizontally from enemy models.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_seer_ishas_fury(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: ISHA'S FURY: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: ISHA'S FURY: not opponent's turn")
            return False

        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key and action_key not in {"move", "normal move", "advance", "fall back", "fallback"}:
            logger.error("ERROR: ISHA'S FURY: wrong trigger")
            return False

        enemy_unit = context.get("enemy_unit") or context.get("attacking_unit") or context.get("moving_unit")
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            logger.error("ERROR: ISHA'S FURY: missing enemy unit")
            return False
        try:
            if enemy_root.get_parent_army().player is self.player:
                logger.error("ERROR: ISHA'S FURY: enemy unit is not hostile")
                return False
        except (AttributeError, TypeError, ValueError):
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_seer_ishas_fury_candidates(enemy_unit=enemy_root)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ISHA'S FURY: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: ISHA'S FURY: target must be an ASURYANI PSYKER within 9\" of the moved enemy unit")
            return False

        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=enemy_root,
        ):
            return False

        mortal_wounds = context.get("mortal_wounds")
        if mortal_wounds is None:
            mortal_wounds = self._roll_aeldari_ishas_fury_mortal_wounds(target_root, enemy_root)
        try:
            mortal_wounds = int(mortal_wounds or 0)
        except (TypeError, ValueError):
            mortal_wounds = 0
        if mortal_wounds > 0:
            apply_mortals = getattr(enemy_root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                try:
                    apply_mortals(enemy_root, int(mortal_wounds), game_map=getattr(game, "map", None))
                except TypeError:
                    apply_mortals(target_unit=enemy_root, amount=int(mortal_wounds), game_map=getattr(game, "map", None))
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: ISHA'S FURY: %s deals %d mortal wound(s) to %s.",
            getattr(target_root, "name", "Unit"),
            int(mortal_wounds),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_aeldari_seer_psychic_shield(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PSYCHIC SHIELD: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: PSYCHIC SHIELD: not opponent's turn")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit") or context.get("enemy_unit")
        attacking_root = self._aeldari_root(attacking_unit)
        if attacking_root is None:
            logger.error("ERROR: PSYCHIC SHIELD: missing attacking unit context")
            return False
        try:
            if attacking_root.get_parent_army().player is self.player:
                logger.error("ERROR: PSYCHIC SHIELD: attacker is not enemy")
                return False
        except (AttributeError, TypeError, ValueError):
            logger.error("ERROR: PSYCHIC SHIELD: attacker is invalid")
            return False

        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_seer_psychic_shield_candidates(target_units=list(context.get("target_units") or []))
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PSYCHIC SHIELD: missing target unit")
                return False
        if target_root not in candidates:
            logger.error(
                "ERROR: PSYCHIC SHIELD: target must be an eligible ASURYANI INFANTRY non-WRAITH CONSTRUCT unit selected as an attack target and within 9\" of a friendly ASURYANI PSYKER"
            )
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False

        effect_owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        source_name = str(getattr(stratagem, "name", "PSYCHIC SHIELD") or "PSYCHIC SHIELD")
        try:
            members = list(target_root.get_attached_unit_members() or [])
        except (AttributeError, TypeError, ValueError):
            members = [target_root]
        if not members:
            members = [target_root]
        for unit in members:
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["aeldari_psychic_shield_active"] = True
            sr["aeldari_psychic_shield_targeting_range"] = 18
            sr["aeldari_psychic_shield_expires_phase"] = "SHOOTING_PHASE"
            sr["aeldari_psychic_shield_turn_owner"] = effect_owner
            sr["aeldari_psychic_shield_turn"] = int(turn)
            sr["aeldari_psychic_shield_source"] = source_name
            unit.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: PSYCHIC SHIELD: %s can only be targeted by ranged attacks from within 18\" this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_guardian_battlehost_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_guardian_battlehost_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "TIME TO STRIKE":
            return self._use_aeldari_guardian_time_to_strike(stratagem, **kwargs)
        if name_u == "BLADES OF ASURYAN":
            return self._use_aeldari_guardian_blades_of_asuryan(stratagem, **kwargs)
        if name_u == "COST OF VICTORY":
            return self._use_aeldari_guardian_cost_of_victory(stratagem, **kwargs)
        if name_u == "WARDING SALVOES":
            return self._use_aeldari_guardian_warding_salvoes(stratagem, **kwargs)
        if name_u == "SHIELD NODES":
            return self._use_aeldari_guardian_shield_nodes(stratagem, **kwargs)
        if name_u == "VAUL'S VENGEANCE":
            return self._use_aeldari_guardian_vauls_vengeance(stratagem, **kwargs)
        return None

    def _use_aeldari_guardian_time_to_strike(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: TIME TO STRIKE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: TIME TO STRIKE: not your Movement phase")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_guardian_time_to_strike_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: TIME TO STRIKE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: TIME TO STRIKE: target must be an eligible Storm Guardians unit")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: TIME TO STRIKE: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_guardian_is_storm_guardians(target_root):
            logger.error("ERROR: TIME TO STRIKE: target must be a Storm Guardians unit")
            return False
        if self._aeldari_selected_to_move_this_phase(target_root):
            logger.error("ERROR: TIME TO STRIKE: target has already been selected to move this phase")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        source = str(getattr(stratagem, "name", "TIME TO STRIKE") or "TIME TO STRIKE")
        tag = "stratagem:aeldari_time_to_strike"
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        effects = list(sr.get("advance_no_roll_effects", []) or [])
        effects = [entry for entry in effects if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == tag)]
        effects.append(
            {
                "distance": 6,
                "source": source,
                "tag": tag,
                "expires_phase": "MOVEMENT_PHASE",
            }
        )
        sr["advance_no_roll_effects"] = effects
        sr["aeldari_time_to_strike_active"] = True
        sr["aeldari_time_to_strike_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_time_to_strike_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_time_to_strike_source"] = source
        target_root.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: TIME TO STRIKE: %s gains fixed Advance distance 6 and can shoot/charge after advancing this turn.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_guardian_blades_of_asuryan(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: BLADES OF ASURYAN: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: BLADES OF ASURYAN: not your Shooting phase")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_guardian_dire_avengers_or_guardians_candidates(
                require_not_shot=True,
                require_not_fought=False,
            )
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: BLADES OF ASURYAN: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: BLADES OF ASURYAN: target must be an eligible Dire Avengers or Guardians unit")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: BLADES OF ASURYAN: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_guardian_is_dire_avengers_or_guardians(target_root):
            logger.error("ERROR: BLADES OF ASURYAN: target must be Dire Avengers or Guardians")
            return False
        if bool(getattr(getattr(target_root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: BLADES OF ASURYAN: target has already been selected to shoot this phase")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        source = str(getattr(stratagem, "name", "BLADES OF ASURYAN") or "BLADES OF ASURYAN")
        phase_key = "SHOOTING_PHASE"
        for model_index, model in enumerate(list(getattr(target_root, "get_attached_unit_models", lambda: [])() or [])):
            if model is None or not bool(getattr(model, "is_alive", True)):
                continue
            model_id = str(get_entity_id(model) or model_index)
            for wargear_index, wargear in enumerate(list(getattr(model, "wargear", []) or [])):
                if wargear is None:
                    continue
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                key_base = f"aeldari_blades_of_asuryan:{model_id}:{wargear_index}:{weapon_name}".lower()
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=key_base,
                        weapon_name=weapon_name,
                        keywords=["PISTOL"],
                        source=source,
                        expires_phase=phase_key,
                        attack_type="ranged",
                    )
                else:
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        effects = {}
                        model._temporary_effects = effects
                    effects[key_base] = {
                        "expires_phase": phase_key,
                        "weapon_keyword_bonuses": {weapon_name: ["PISTOL"]},
                        "weapon_keyword_bonuses_source": source,
                        "weapon_keyword_bonuses_attack_type": "ranged",
                    }

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aeldari_blades_of_asuryan_active"] = True
        sr["aeldari_blades_of_asuryan_expires_phase"] = phase_key
        sr["aeldari_blades_of_asuryan_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_blades_of_asuryan_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_blades_of_asuryan_source"] = source
        target_root.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: BLADES OF ASURYAN: %s gains [PISTOL] on ranged weapons this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_guardian_warding_salvoes(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: WARDING SALVOES: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: WARDING SALVOES: only usable in your Shooting phase")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_guardian_dire_avengers_or_guardians_candidates(
                require_not_shot=phase_name == "shooting phase",
                require_not_fought=phase_name == "fight phase",
            )
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: WARDING SALVOES: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: WARDING SALVOES: target must be an eligible Dire Avengers or Guardians unit")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: WARDING SALVOES: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_guardian_is_dire_avengers_or_guardians(target_root):
            logger.error("ERROR: WARDING SALVOES: target must be Dire Avengers or Guardians")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aeldari_warding_salvoes_active"] = True
        sr["aeldari_warding_salvoes_expires_phase"] = phase_key
        sr["aeldari_warding_salvoes_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_warding_salvoes_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_warding_salvoes_source"] = str(getattr(stratagem, "name", "WARDING SALVOES") or "WARDING SALVOES")
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: WARDING SALVOES: %s can re-roll Wound rolls against targets within objective range this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_guardian_shield_nodes(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: SHIELD NODES: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: SHIELD NODES: not your opponent's phase")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("enemy_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        if attacking_root is not None:
            try:
                if attacking_root.get_parent_army().player is self.player:
                    logger.error("ERROR: SHIELD NODES: attacking unit must be enemy")
                    return False
            except (AttributeError, TypeError, ValueError):
                return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        target_window = list(context.get("target_units") or [])
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_guardian_shield_nodes_candidates(target_units=target_window)
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: SHIELD NODES: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: SHIELD NODES: target must have been selected as an enemy attack target")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: SHIELD NODES: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_guardian_is_dire_avengers_or_guardians(target_root):
            logger.error("ERROR: SHIELD NODES: target must be Dire Avengers or Guardians")
            return False
        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=attacking_root,
        ):
            return False

        if self._aeldari_guardian_unit_within_objective_range(target_root):
            phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
            self._append_defensive_effect(
                target_root,
                "defensive_wound_mods",
                {
                    "value": 1,
                    "attack_type": "any",
                    "expires_phase": phase_key,
                    "source": str(getattr(stratagem, "name", "SHIELD NODES") or "SHIELD NODES"),
                },
            )
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_guardian_vauls_vengeance(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: VAUL'S VENGEANCE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: VAUL'S VENGEANCE: not your opponent's phase")
            return False
        if self._aeldari_guardian_vauls_vengeance_used_this_round():
            logger.error("ERROR: VAUL'S VENGEANCE: already used this battle round")
            return False

        enemy_unit = context.get("enemy_unit") or context.get("destroyed_by_unit") or context.get("attacking_unit")
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            logger.error("ERROR: VAUL'S VENGEANCE: missing enemy unit that destroyed the trigger unit")
            return False
        try:
            if enemy_root.get_parent_army().player is self.player:
                logger.error("ERROR: VAUL'S VENGEANCE: enemy trigger unit is not hostile")
                return False
        except (AttributeError, TypeError, ValueError):
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_guardian_war_walkers_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: VAUL'S VENGEANCE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: VAUL'S VENGEANCE: target must be a War Walkers unit")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: VAUL'S VENGEANCE: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_guardian_is_war_walkers(target_root):
            logger.error("ERROR: VAUL'S VENGEANCE: target must be War Walkers")
            return False

        queue_fn = getattr(game, "_queue_setup_reactive_shooting_decision", None)
        if not callable(queue_fn):
            logger.error("ERROR: VAUL'S VENGEANCE: reactive shooting queue unavailable")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        request = queue_fn(
            player=self.player,
            unit=target_root,
            target_unit=enemy_root,
            source=str(getattr(stratagem, "name", "VAUL'S VENGEANCE") or "VAUL'S VENGEANCE"),
        )
        if request is None:
            logger.error("ERROR: VAUL'S VENGEANCE: failed to queue reactive shooting decision")
            return False
        self._aeldari_guardian_mark_vauls_vengeance_used_round()
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_guardian_cost_of_victory(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: COST OF VICTORY: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: COST OF VICTORY: not opponent's turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_guardian_cost_of_victory_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: COST OF VICTORY: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: COST OF VICTORY: target is not currently eligible")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: COST OF VICTORY: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_guardian_is_guardians_unit(target_root):
            logger.error("ERROR: COST OF VICTORY: target must be a Guardians unit")
            return False
        if self._aeldari_in_engagement_range(target_root):
            logger.error("ERROR: COST OF VICTORY: target must not be within Engagement Range")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        if not self._aeldari_place_unit_into_strategic_reserves(
            target_root,
            reason=str(getattr(stratagem, "name", "COST OF VICTORY") or "COST OF VICTORY"),
        ):
            logger.error("ERROR: COST OF VICTORY: failed to place target into Strategic Reserves")
            return False

        returned = 0
        destroyed_pool = list(getattr(target_root, "models_lost", []) or [])
        returnable = [model for model in destroyed_pool if self._aeldari_model_has_keyword(model, "GUARDIANS")]
        if returnable:
            if hasattr(target_root, "models_lost"):
                remaining = [model for model in destroyed_pool if model not in returnable]
                target_root.models_lost = list(returnable) + remaining
            return_full = getattr(self, "_return_destroyed_models_full", None)
            if callable(return_full):
                returned = int(
                    return_full(
                        target_root,
                        amount=len(returnable),
                        game_map=getattr(game, "map", None),
                        skip_character=False,
                    )
                    or 0
                )

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: COST OF VICTORY: %s entered Strategic Reserves and returned %d GUARDIANS model(s).",
            getattr(target_root, "name", "Unit"),
            int(returned),
        )
        return True

    def _use_aeldari_ghosts_of_the_webway_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_ghosts_of_the_webway_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "BLOODY DANCE":
            return self._use_aeldari_ghosts_bloody_dance(stratagem, **kwargs)
        if name_u == "EXIT THE STAGE":
            return self._use_aeldari_ghosts_exit_the_stage(stratagem, **kwargs)
        if name_u == "MOCKING FLIGHT":
            return self._use_aeldari_ghosts_mocking_flight(stratagem, **kwargs)
        if name_u == "STAGED DEATH":
            return self._use_aeldari_ghosts_staged_death(stratagem, **kwargs)
        if name_u in {"TRICKSTERS' RETORT", "TRICKSTERS\u2019 RETORT"}:
            return self._use_aeldari_ghosts_tricksters_retort(stratagem, **kwargs)
        if name_u in {"HEROES' FALL", "HEROES\u2019 FALL"}:
            return self._use_aeldari_ghosts_heroes_fall(stratagem, **kwargs)
        return None

    def _use_aeldari_spirit_conclave_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_spirit_conclave_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "SPIRIT TOKEN":
            return self._use_aeldari_spirit_token(stratagem, **kwargs)
        if name_u == "SOUL BRIDGE":
            return self._use_aeldari_soul_bridge(stratagem, **kwargs)
        if name_u == "WRAITHBONE ARMOUR":
            return self._use_aeldari_spirit_wraithbone_armour(stratagem, **kwargs)
        if name_u in {"SEER'S EYE", "SEER\u2019S EYE"}:
            return self._use_aeldari_spirit_seers_eye(stratagem, **kwargs)
        return None

    def _use_aeldari_spirit_token(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: SPIRIT TOKEN: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: SPIRIT TOKEN: not your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_spirit_wraithblades_or_guard_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: SPIRIT TOKEN: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: SPIRIT TOKEN: target must be WRAITHBLADES or WRAITHGUARD")
            return False
        if not self._aeldari_spirit_is_wraithblades_or_wraithguard(target_root):
            logger.error("ERROR: SPIRIT TOKEN: target must be WRAITHBLADES or WRAITHGUARD")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: SPIRIT TOKEN: target must be on the battlefield and targetable")
            return False

        objective = context.get("objective") or context.get("objective_marker")
        objective_candidates = list(context.get("objective_candidates") or [])
        if not objective_candidates:
            objective_map = context.get("objective_candidates_by_unit")
            if isinstance(objective_map, dict):
                key = self._aeldari_sort_key(target_root)
                objective_candidates = list(objective_map.get(key) or [])
        if not objective_candidates:
            objective_candidates = self._aeldari_spirit_token_objective_candidates(target_root)
        if objective is None:
            if len(objective_candidates) == 1:
                objective = objective_candidates[0]
            else:
                logger.error("ERROR: SPIRIT TOKEN: missing objective marker selection")
                return False
        if objective_candidates and objective not in list(objective_candidates or []):
            logger.error("ERROR: SPIRIT TOKEN: selected objective is not eligible")
            return False

        loc = getattr(objective, "location", None)
        if loc is None:
            loc = objective
        if loc is None:
            logger.error("ERROR: SPIRIT TOKEN: objective marker location unavailable")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        set_sticky = getattr(loc, "set_sticky_control", None)
        if callable(set_sticky):
            set_sticky(self.player, source="aeldari_spirit_token")
        else:
            loc.sticky_controller = self.player
            loc.sticky_source = "aeldari_spirit_token"
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: SPIRIT TOKEN: selected objective remains under your control until opponent control becomes greater.",
        )
        return True

    def _use_aeldari_soul_bridge(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: SOUL BRIDGE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: SOUL BRIDGE: not your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_spirit_wraith_target_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: SOUL BRIDGE: missing WRAITH target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: SOUL BRIDGE: target must be WRAITHBLADES, WRAITHGUARD, or WRAITHLORD")
            return False
        if not self._aeldari_spirit_is_wraith_target(target_root):
            logger.error("ERROR: SOUL BRIDGE: target must be WRAITHBLADES, WRAITHGUARD, or WRAITHLORD")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: SOUL BRIDGE: WRAITH target must be on the battlefield and targetable")
            return False

        source_unit = (
            context.get("source_unit")
            or context.get("source_psyker_unit")
            or context.get("psyker_unit")
        )
        source_root = self._aeldari_root(source_unit) if source_unit is not None else None
        psyker_candidates = list(context.get("psyker_candidates") or [])
        if not psyker_candidates:
            psyker_candidates = self._aeldari_spirit_soul_bridge_psyker_candidates(target_unit=target_root)
        psyker_roots = [self._aeldari_root(unit) for unit in list(psyker_candidates or [])]
        psyker_roots = [unit for unit in psyker_roots if unit is not None]
        if source_root is None:
            if len(psyker_roots) == 1:
                source_root = psyker_roots[0]
            else:
                logger.error("ERROR: SOUL BRIDGE: missing ASURYANI PSYKER source unit")
                return False
        if psyker_roots and source_root not in psyker_roots:
            logger.error("ERROR: SOUL BRIDGE: source must be an eligible ASURYANI PSYKER")
            return False
        if not self._aeldari_on_battlefield(source_root, require_targetable=True):
            logger.error("ERROR: SOUL BRIDGE: PSYKER source must be on the battlefield and targetable")
            return False
        if not self._aeldari_has_keyword(source_root, "ASURYANI") or not self._aeldari_has_keyword(source_root, "PSYKER"):
            logger.error("ERROR: SOUL BRIDGE: source must be an ASURYANI PSYKER")
            return False

        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=None,
        ):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aeldari_soul_bridge_active"] = True
        sr["aeldari_soul_bridge_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_soul_bridge_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_soul_bridge_source"] = str(getattr(stratagem, "name", "SOUL BRIDGE") or "SOUL BRIDGE")
        sr["aeldari_soul_bridge_psyker_unit_id"] = str(get_entity_id(source_root) or "")
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: SOUL BRIDGE: %s is treated as within 12\" of %s for Psychic Guidance and Spirit Guides until your next Command phase.",
            getattr(target_root, "name", "Unit"),
            getattr(source_root, "name", "Psyker"),
        )
        return True

    def _use_aeldari_spirit_wraithbone_armour(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: WRAITHBONE ARMOUR: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: WRAITHBONE ARMOUR: only usable in opponent Shooting phase")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit") or context.get("enemy_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        if attacking_root is not None:
            try:
                if attacking_root.get_parent_army().player is self.player:
                    logger.error("ERROR: WRAITHBONE ARMOUR: attacking unit must be enemy")
                    return False
            except (AttributeError, TypeError, ValueError):
                return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        target_window = list(context.get("target_units") or [])
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_spirit_wraithbone_armour_candidates(target_units=target_window)
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: WRAITHBONE ARMOUR: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: WRAITHBONE ARMOUR: target must have been selected by the attacking unit")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: WRAITHBONE ARMOUR: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_spirit_is_wraith_construct(target_root, exclude_titanic=True):
            logger.error("ERROR: WRAITHBONE ARMOUR: target must be a non-TITANIC WRAITH CONSTRUCT unit")
            return False
        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=attacking_root,
        ):
            return False

        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        self._append_defensive_effect(
            target_root,
            "defensive_damage_reductions",
            {
                "value": 1,
                "attack_type": "any",
                "expires_phase": phase_key,
                "source": str(getattr(stratagem, "name", "WRAITHBONE ARMOUR") or "WRAITHBONE ARMOUR"),
            },
        )
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_spirit_seers_eye(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: SEER'S EYE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: SEER'S EYE: only usable in your Shooting phase")
            return False

        source_unit = (
            context.get("source_unit")
            or context.get("source_psyker_unit")
            or context.get("psyker_unit")
        )
        source_root = self._aeldari_root(source_unit) if source_unit is not None else None
        psyker_candidates = list(context.get("psyker_candidates") or [])
        if not psyker_candidates:
            for psyker in self._aeldari_spirit_psyker_candidates():
                if self._aeldari_spirit_seers_eye_wraith_candidates(psyker) and self._aeldari_spirit_visible_enemy_candidates(psyker):
                    psyker_candidates.append(psyker)
        psyker_roots = [self._aeldari_root(unit) for unit in list(psyker_candidates or [])]
        psyker_roots = [unit for unit in psyker_roots if unit is not None]
        if source_root is None:
            if len(psyker_roots) == 1:
                source_root = psyker_roots[0]
            else:
                logger.error("ERROR: SEER'S EYE: missing AELDARI PSYKER source unit")
                return False
        if psyker_roots and source_root not in psyker_roots:
            logger.error("ERROR: SEER'S EYE: source must be an eligible AELDARI PSYKER")
            return False
        if not self._aeldari_on_battlefield(source_root, require_targetable=True):
            logger.error("ERROR: SEER'S EYE: source must be on the battlefield and targetable")
            return False
        if not self._aeldari_has_keyword(source_root, "AELDARI") or not self._aeldari_has_keyword(source_root, "PSYKER"):
            logger.error("ERROR: SEER'S EYE: source must be an AELDARI PSYKER")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        wraith_candidates = list(context.get("candidates") or context.get("wraith_candidates") or [])
        if not wraith_candidates:
            by_psyker = context.get("wraith_candidates_by_psyker")
            if isinstance(by_psyker, dict):
                wraith_candidates = list(by_psyker.get(self._aeldari_sort_key(source_root)) or [])
        if not wraith_candidates:
            wraith_candidates = self._aeldari_spirit_seers_eye_wraith_candidates(source_root)
        wraith_roots = [self._aeldari_root(unit) for unit in list(wraith_candidates or [])]
        wraith_roots = [unit for unit in wraith_roots if unit is not None]
        if target_root is None:
            if len(wraith_roots) == 1:
                target_root = wraith_roots[0]
            else:
                logger.error("ERROR: SEER'S EYE: missing WRAITH CONSTRUCT target unit")
                return False
        if wraith_roots and target_root not in wraith_roots:
            logger.error("ERROR: SEER'S EYE: target must be within 12\" of the selected PSYKER and not selected to shoot/fight")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: SEER'S EYE: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_spirit_is_wraith_construct(target_root, exclude_titanic=False):
            logger.error("ERROR: SEER'S EYE: target must be a WRAITH CONSTRUCT unit")
            return False
        if bool(getattr(getattr(target_root, "round_state", None), "shot_this_round", False)) or bool(
            getattr(getattr(target_root, "round_state", None), "fought_this_phase", False)
        ):
            logger.error("ERROR: SEER'S EYE: target has already been selected to shoot or fight this phase")
            return False

        from ..utility.aura_utils import unit_within_range_of_unit

        if not unit_within_range_of_unit(source_root, target_root, 12.0, use_attached_aggregate=True):
            logger.error("ERROR: SEER'S EYE: target must be within 12\" of the selected PSYKER")
            return False

        enemy_unit = context.get("enemy_unit") or context.get("target_enemy_unit")
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        enemy_candidates = list(context.get("enemy_candidates") or [])
        if not enemy_candidates:
            by_psyker = context.get("enemy_candidates_by_psyker")
            if isinstance(by_psyker, dict):
                enemy_candidates = list(by_psyker.get(self._aeldari_sort_key(source_root)) or [])
        if not enemy_candidates:
            enemy_candidates = self._aeldari_spirit_visible_enemy_candidates(source_root)
        enemy_roots = [self._aeldari_root(unit) for unit in list(enemy_candidates or [])]
        enemy_roots = [unit for unit in enemy_roots if unit is not None]
        if enemy_root is None:
            if len(enemy_roots) == 1:
                enemy_root = enemy_roots[0]
            else:
                logger.error("ERROR: SEER'S EYE: missing visible enemy target for selected PSYKER")
                return False
        if enemy_roots and enemy_root not in enemy_roots:
            logger.error("ERROR: SEER'S EYE: selected enemy must be visible to the selected PSYKER")
            return False
        if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
            logger.error("ERROR: SEER'S EYE: selected enemy must be on the battlefield")
            return False

        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=enemy_root,
        ):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aeldari_spirit_seers_eye_active"] = True
        sr["aeldari_spirit_seers_eye_expires_phase"] = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr["aeldari_spirit_seers_eye_source"] = str(getattr(stratagem, "name", "SEER'S EYE") or "SEER'S EYE")
        sr["aeldari_spirit_seers_eye_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_spirit_seers_eye_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_spirit_seers_eye_enemy_unit_id"] = str(get_entity_id(enemy_root) or "")
        sr["aeldari_spirit_seers_eye_psyker_unit_id"] = str(get_entity_id(source_root) or "")
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_eldritch_raiders_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_eldritch_raiders_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "YRIEL'S EXAMPLE":
            return self._use_aeldari_eldritch_yriels_example(stratagem, **kwargs)
        if name_u == "WITHDRAW AND REINFORCE":
            return self._use_aeldari_eldritch_withdraw_and_reinforce(stratagem, **kwargs)
        if name_u == "RUTHLESS KILLERS":
            return self._use_aeldari_eldritch_ruthless_killers(stratagem, **kwargs)
        if name_u == "NO PREY TOO BIG":
            return self._use_aeldari_eldritch_no_prey_too_big(stratagem, **kwargs)
        if name_u in {"RAIDERS' SPOILS", "RAIDERS\u2019 SPOILS"}:
            return self._use_aeldari_eldritch_raiders_spoils(stratagem, **kwargs)
        if name_u == "IMPEDING FIRE":
            return self._use_aeldari_eldritch_impeding_fire(stratagem, **kwargs)
        return None

    def _use_aeldari_serpents_brood_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_serpents_brood_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "VENOMOUS WRATH":
            return self._use_aeldari_serpents_venomous_wrath(stratagem, **kwargs)
        if name_u == "FANGS OF THE BROOD":
            return self._use_aeldari_serpents_fangs_of_the_brood(stratagem, **kwargs)
        if name_u == "STRIKING STRIDE":
            return self._use_aeldari_serpents_striking_stride(stratagem, **kwargs)
        if name_u == "WEAVING STRIDE":
            return self._use_aeldari_serpents_weaving_stride(stratagem, **kwargs)
        if name_u == "SKYWARD LUNGE":
            return self._use_aeldari_serpents_skyward_lunge(stratagem, **kwargs)
        if name_u in {"WEAVERS' COILS", "WEAVERS\u2019 COILS"}:
            return self._use_aeldari_serpents_weavers_coils(stratagem, **kwargs)
        return None

    def _use_aeldari_serpents_fangs_of_the_brood(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: FANGS OF THE BROOD: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_serpents_fangs_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: FANGS OF THE BROOD: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: FANGS OF THE BROOD: target must be an eligible TROUPE unit")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: FANGS OF THE BROOD: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_is_troupe(target_root):
            logger.error("ERROR: FANGS OF THE BROOD: target must be a TROUPE unit")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["serpents_brood_fangs_of_the_brood_active"] = True
        sr["serpents_brood_fangs_of_the_brood_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["serpents_brood_fangs_of_the_brood_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["serpents_brood_fangs_of_the_brood_expires_phase"] = "FIGHT_PHASE"
        sr["serpents_brood_fangs_of_the_brood_source"] = str(getattr(stratagem, "name", "FANGS OF THE BROOD") or "FANGS OF THE BROOD")
        target_root.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: FANGS OF THE BROOD: %s can gain all three Dance of Death abilities this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_serpents_venomous_wrath(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VENOMOUS WRATH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: VENOMOUS WRATH: not your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_serpents_venomous_wrath_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: VENOMOUS WRATH: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: VENOMOUS WRATH: target is not currently eligible")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: VENOMOUS WRATH: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_is_harlequins(target_root) or not self._aeldari_has_keyword(target_root, "VEHICLE"):
            logger.error("ERROR: VENOMOUS WRATH: target must be HARLEQUINS VEHICLE")
            return False
        if bool(getattr(getattr(target_root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: VENOMOUS WRATH: target has already been selected to shoot this phase")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        source = str(getattr(stratagem, "name", "VENOMOUS WRATH") or "VENOMOUS WRATH")
        sr["serpents_brood_venomous_wrath_active"] = True
        sr["serpents_brood_venomous_wrath_turn_owner"] = owner
        sr["serpents_brood_venomous_wrath_turn"] = int(turn)
        sr["serpents_brood_venomous_wrath_source"] = source
        sr["serpents_brood_venomous_wrath_no_charge_turn_owner"] = owner
        sr["serpents_brood_venomous_wrath_no_charge_turn"] = int(turn)
        target_root.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: VENOMOUS WRATH: %s can make a Normal move up to 6\" after it shoots if not in Engagement Range, and cannot declare a charge this turn.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_serpents_striking_stride(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: STRIKING STRIDE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: STRIKING STRIDE: not your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_serpents_striking_stride_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: STRIKING STRIDE: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: STRIKING STRIDE: target is not currently eligible")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: STRIKING STRIDE: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_is_harlequins(target_root):
            logger.error("ERROR: STRIKING STRIDE: target must be HARLEQUINS")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["serpents_brood_striking_stride_active"] = True
        sr["serpents_brood_striking_stride_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["serpents_brood_striking_stride_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["serpents_brood_striking_stride_expires_phase"] = "CHARGE_PHASE"
        sr["serpents_brood_striking_stride_source"] = str(getattr(stratagem, "name", "STRIKING STRIDE") or "STRIKING STRIDE")
        target_root.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: STRIKING STRIDE: %s can declare a charge in a turn in which it Advanced this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_serpents_weaving_stride(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: WEAVING STRIDE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: WEAVING STRIDE: not opponent's turn")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key and action_key not in {"move", "normal", "normal move", "advance", "fall back", "fallback"}:
            logger.error("ERROR: WEAVING STRIDE: wrong trigger")
            return False

        enemy_unit = (
            context.get("enemy_unit")
            or context.get("attacking_unit")
            or context.get("trigger_unit")
            or context.get("moved_unit")
        )
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            logger.error("ERROR: WEAVING STRIDE: missing enemy trigger unit")
            return False
        try:
            if enemy_root.get_parent_army().player is self.player:
                logger.error("ERROR: WEAVING STRIDE: trigger unit must be enemy")
                return False
        except (AttributeError, TypeError, ValueError):
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_serpents_weaving_stride_candidates(enemy_unit=enemy_root)
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: WEAVING STRIDE: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: WEAVING STRIDE: target must be an eligible HARLEQUINS INFANTRY unit within 9\"")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: WEAVING STRIDE: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_is_harlequins(target_root) or not self._aeldari_has_keyword(target_root, "INFANTRY"):
            logger.error("ERROR: WEAVING STRIDE: target must be HARLEQUINS INFANTRY")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False

        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: WEAVING STRIDE: reactive move queue unavailable")
            return False
        request = queue_move(
            player=self.player,
            unit=target_root,
            attacker_unit=enemy_root,
            max_distance=6,
            kind="weaving_stride",
            movement_type="move",
            source=str(getattr(stratagem, "name", "WEAVING STRIDE") or "WEAVING STRIDE"),
            allow_skip=True,
        )
        if request is None:
            logger.error("ERROR: WEAVING STRIDE: failed to queue movement decision")
            return False

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: WEAVING STRIDE: %s can make a Normal move up to 6\".",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_serpents_skyward_lunge(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SKYWARD LUNGE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: SKYWARD LUNGE: not opponent's turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_serpents_skyward_lunge_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: SKYWARD LUNGE: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: SKYWARD LUNGE: target is not currently eligible")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: SKYWARD LUNGE: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_is_harlequins(target_root):
            logger.error("ERROR: SKYWARD LUNGE: target must be HARLEQUINS")
            return False
        if not (self._aeldari_has_keyword(target_root, "VEHICLE") or self._aeldari_has_keyword(target_root, "MOUNTED")):
            logger.error("ERROR: SKYWARD LUNGE: target must be HARLEQUINS VEHICLE or HARLEQUINS MOUNTED")
            return False
        if self._aeldari_in_engagement_range(target_root):
            logger.error("ERROR: SKYWARD LUNGE: target must not be within Engagement Range")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        if not self._aeldari_place_unit_into_strategic_reserves(
            target_root,
            reason=str(getattr(stratagem, "name", "SKYWARD LUNGE") or "SKYWARD LUNGE"),
        ):
            logger.error("ERROR: SKYWARD LUNGE: failed to place target into Strategic Reserves")
            return False
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: SKYWARD LUNGE: %s entered Strategic Reserves.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_serpents_weavers_coils(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: WEAVERS' COILS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: WEAVERS' COILS: not your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_serpents_weavers_coils_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: WEAVERS' COILS: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: WEAVERS' COILS: target is not currently eligible")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: WEAVERS' COILS: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_is_harlequins(target_root):
            logger.error("ERROR: WEAVERS' COILS: target must be HARLEQUINS")
            return False
        if not self._aeldari_has_keyword(target_root, "MOUNTED"):
            logger.error("ERROR: WEAVERS' COILS: target must be HARLEQUINS MOUNTED")
            return False
        round_state = getattr(target_root, "round_state", None)
        was_eligible = bool(getattr(round_state, "eligible_to_fight_this_phase", False))
        if not was_eligible and bool(getattr(round_state, "fought_this_phase", False)):
            was_eligible = True
        if not was_eligible:
            logger.error("ERROR: WEAVERS' COILS: target must have been eligible to fight this phase")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        engaged = self._aeldari_in_engagement_range(target_root)
        movement_type = "fall_back" if engaged else "move"
        max_distance = 6 if engaged else int(self._aeldari_serpents_normal_move_distance(target_root) or 0)
        if max_distance <= 0:
            logger.error("ERROR: WEAVERS' COILS: movement distance is invalid")
            return False

        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: WEAVERS' COILS: reactive move queue unavailable")
            return False
        request = queue_move(
            player=self.player,
            unit=target_root,
            max_distance=int(max_distance),
            kind="weavers_coils",
            movement_type=movement_type,
            source=str(getattr(stratagem, "name", "WEAVERS' COILS") or "WEAVERS' COILS"),
            allow_skip=True,
        )
        if request is None:
            logger.error("ERROR: WEAVERS' COILS: failed to queue movement decision")
            return False

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: WEAVERS' COILS: %s can make a %s move up to %d\".",
            getattr(target_root, "name", "Unit"),
            "Fall Back" if engaged else "Normal",
            int(max_distance),
        )
        return True

    def _use_aeldari_ghosts_bloody_dance(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: BLOODY DANCE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: BLOODY DANCE: not opponent's turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        enemy_by_unit = context.get("enemy_by_unit")
        if not isinstance(enemy_by_unit, dict):
            enemy_by_unit = {}
        if not candidates:
            candidates, enemy_by_unit = self._aeldari_ghosts_bloody_dance_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: BLOODY DANCE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: BLOODY DANCE: target must be an eligible HARLEQUINS INFANTRY or MOUNTED unit")
            return False

        root_id = self._aeldari_sort_key(target_root)
        valid_enemies = list(enemy_by_unit.get(root_id) or self._aeldari_ghosts_bloody_dance_enemy_candidates_for_unit(target_root))
        enemy_unit = (
            context.get("enemy_unit")
            or context.get("attacking_unit")
            or context.get("trigger_unit")
            or context.get("target_enemy_unit")
        )
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(valid_enemies) == 1:
                enemy_root = valid_enemies[0]
            elif valid_enemies:
                enemy_root = valid_enemies[0]
            else:
                logger.error("ERROR: BLOODY DANCE: no eligible enemy charge target")
                return False
        if enemy_root not in valid_enemies:
            logger.error("ERROR: BLOODY DANCE: selected enemy target is not eligible")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        ok = bool(game.attempt_charge(target_root, enemy_root, out_of_turn=True, count_as_charged=False))
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        if not ok:
            logger.error("ERROR: BLOODY DANCE: charge failed")
        else:
            logger.info(
                "INFO: BLOODY DANCE: %s declared an out-of-turn charge against %s (no charge bonus).",
                getattr(target_root, "name", "Unit"),
                getattr(enemy_root, "name", "Enemy Unit"),
            )
        return True

    def _use_aeldari_ghosts_staged_death(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        root = self._aeldari_root(
            context.get("destroyed_unit")
            or context.get("unit")
            or context.get("target_unit")
        )
        model = context.get("destroyed_model") or context.get("model")
        if root is None or model is None:
            logger.error("ERROR: STAGED DEATH: missing destroyed model context")
            return False
        try:
            if root.get_parent_army().player is not self.player:
                logger.error("ERROR: STAGED DEATH: target must be from your army")
                return False
        except (AttributeError, TypeError, ValueError):
            return False
        if not self._aeldari_ghosts_staged_death_model_eligible(unit=root, model=model):
            logger.error("ERROR: STAGED DEATH: target must be a just-destroyed HARLEQUINS CHARACTER model")
            return False
        model_id = str(get_entity_id(model) or "")
        if model_id and model_id in self._aeldari_ghosts_staged_death_used_model_ids():
            logger.error("ERROR: STAGED DEATH: this model has already used STAGED DEATH this battle")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=root):
            return False

        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip()
        phase_key = self._aeldari_phase_key_from_name(phase_name)
        destroyed_position = context.get("destroyed_position")
        if destroyed_position is None:
            get_location = getattr(model, "get_location", None)
            if callable(get_location):
                try:
                    pos = get_location()
                except (AttributeError, TypeError, ValueError):
                    pos = None
                if isinstance(pos, (list, tuple)) and len(pos) >= 4:
                    destroyed_position = (float(pos[0]), float(pos[1]), float(pos[2]), float(pos[3]))

        self._aeldari_ghosts_staged_death_pending_returns().append(
            {
                "unit": root,
                "model": model,
                "destroyed_position": destroyed_position,
                "trigger_phase_name": phase_name,
                "trigger_phase_key": phase_key,
                "source": str(getattr(stratagem, "name", "STAGED DEATH") or "STAGED DEATH"),
            }
        )
        if model_id:
            self._aeldari_ghosts_staged_death_used_model_ids().add(model_id)
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: STAGED DEATH: %s will return at phase end with half starting wounds.",
            getattr(model, "name", "Model"),
        )
        return True

    def _use_aeldari_ghosts_exit_the_stage(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: EXIT THE STAGE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: EXIT THE STAGE: not opponent's turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_ghosts_exit_the_stage_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: EXIT THE STAGE: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: EXIT THE STAGE: target is not currently eligible")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: EXIT THE STAGE: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_is_harlequins(target_root):
            logger.error("ERROR: EXIT THE STAGE: target must be HARLEQUINS")
            return False
        if self._aeldari_in_engagement_range(target_root):
            logger.error("ERROR: EXIT THE STAGE: target must not be within Engagement Range")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        if not self._aeldari_place_unit_into_strategic_reserves(
            target_root,
            reason=str(getattr(stratagem, "name", "EXIT THE STAGE") or "EXIT THE STAGE"),
        ):
            logger.error("ERROR: EXIT THE STAGE: failed to place target into Strategic Reserves")
            return False
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: EXIT THE STAGE: %s entered Strategic Reserves.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_ghosts_heroes_fall(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: HEROES' FALL: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        if attacking_root is None:
            logger.error("ERROR: HEROES' FALL: missing attacking unit")
            return False
        try:
            if attacking_root.get_parent_army().player is self.player:
                logger.error("ERROR: HEROES' FALL: attacking unit must be enemy")
                return False
        except (AttributeError, TypeError, ValueError):
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        target_window = list(context.get("target_units") or [])
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_ghosts_heroes_fall_candidates(target_units=target_window)
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: HEROES' FALL: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: HEROES' FALL: target must be selected as an enemy fight target")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: HEROES' FALL: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_is_harlequins(target_root):
            logger.error("ERROR: HEROES' FALL: target must be HARLEQUINS")
            return False
        if target_window:
            selected_roots = [self._aeldari_root(unit) for unit in list(target_window or [])]
            selected_roots = [unit for unit in selected_roots if unit is not None]
            if selected_roots and target_root not in selected_roots:
                logger.error("ERROR: HEROES' FALL: target must be selected by the attacking unit")
                return False
        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=attacking_root,
        ):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_heroes_fall_active"] = True
        sr["aeldari_heroes_fall_expires_phase"] = "FIGHT_PHASE"
        sr["aeldari_heroes_fall_source"] = str(getattr(stratagem, "name", "HEROES' FALL") or "HEROES' FALL")
        sr["aeldari_heroes_fall_threshold"] = 4
        if owner:
            sr["aeldari_heroes_fall_owner"] = owner
        if turn:
            sr["aeldari_heroes_fall_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_clear_melee_fight_on_death_cache(target_root)
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_ghosts_mocking_flight(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: MOCKING FLIGHT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: MOCKING FLIGHT: not your turn")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key and action_key not in {"fall back", "fallback"}:
            logger.error("ERROR: MOCKING FLIGHT: wrong trigger")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_ghosts_mocking_flight_candidates(moved_unit=target_root)
            if not candidates:
                candidates = self._aeldari_ghosts_mocking_flight_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: MOCKING FLIGHT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: MOCKING FLIGHT: target must be a HARLEQUINS unit that Fell Back this phase")
            return False
        if not self._aeldari_is_harlequins(target_root):
            logger.error("ERROR: MOCKING FLIGHT: target must be HARLEQUINS")
            return False
        if not bool(getattr(getattr(target_root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: MOCKING FLIGHT: target has not Fallen Back")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["feigned_retreat_active"] = True
        sr["feigned_retreat_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["feigned_retreat_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["feigned_retreat_source"] = str(getattr(stratagem, "name", "MOCKING FLIGHT") or "MOCKING FLIGHT")
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: MOCKING FLIGHT: %s can shoot and charge after Falling Back this turn.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_ghosts_tricksters_retort(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: TRICKSTERS' RETORT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: TRICKSTERS' RETORT: not opponent's turn")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key and action_key not in {"move", "normal", "advance", "fall back", "fallback"}:
            logger.error("ERROR: TRICKSTERS' RETORT: wrong trigger")
            return False

        enemy_unit = (
            context.get("enemy_unit")
            or context.get("attacking_unit")
            or context.get("trigger_unit")
            or context.get("moved_unit")
        )
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            logger.error("ERROR: TRICKSTERS' RETORT: missing enemy trigger unit")
            return False
        try:
            if enemy_root.get_parent_army().player is self.player:
                logger.error("ERROR: TRICKSTERS' RETORT: trigger unit must be enemy")
                return False
        except (AttributeError, TypeError, ValueError):
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_ghosts_tricksters_retort_candidates(enemy_unit=enemy_root)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: TRICKSTERS' RETORT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: TRICKSTERS' RETORT: target must be a TROUPE unit within 9\" of the enemy trigger unit")
            return False
        if not self._aeldari_is_troupe(target_root):
            logger.error("ERROR: TRICKSTERS' RETORT: target must be a TROUPE unit")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False

        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if callable(queue_move):
            queue_move(
                player=self.player,
                unit=target_root,
                attacker_unit=enemy_root,
                max_distance=6,
                kind="tricksters_retort",
                movement_type="reactive",
                source=str(getattr(stratagem, "name", "TRICKSTERS' RETORT") or "TRICKSTERS' RETORT"),
            )

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: TRICKSTERS' RETORT: %s can make a reactive Normal move up to 6\".",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_eldritch_yriels_example(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: YRIEL'S EXAMPLE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        if attacking_root is not None:
            try:
                if attacking_root.get_parent_army().player is self.player:
                    logger.error("ERROR: YRIEL'S EXAMPLE: attacking unit must be enemy")
                    return False
            except (AttributeError, TypeError, ValueError):
                return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        target_window = list(context.get("target_units") or [])
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_eldritch_yriels_example_candidates(target_units=target_window)
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: YRIEL'S EXAMPLE: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: YRIEL'S EXAMPLE: target must be selected as an enemy fight target")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: YRIEL'S EXAMPLE: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_has_keyword(target_root, "AELDARI") or not self._aeldari_has_keyword(target_root, "INFANTRY"):
            logger.error("ERROR: YRIEL'S EXAMPLE: target must be AELDARI INFANTRY")
            return False
        if self._aeldari_has_keyword(target_root, "WRAITH CONSTRUCT"):
            logger.error("ERROR: YRIEL'S EXAMPLE: WRAITH CONSTRUCT units are ineligible")
            return False
        if target_window:
            selected_roots = [self._aeldari_root(unit) for unit in list(target_window or [])]
            selected_roots = [unit for unit in selected_roots if unit is not None]
            if selected_roots and target_root not in selected_roots:
                logger.error("ERROR: YRIEL'S EXAMPLE: target was not selected by that attacker")
                return False
        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=attacking_root,
        ):
            return False
        self._append_defensive_effect(
            target_root,
            "defensive_fnp_overrides",
            {
                "value": 5,
                "attack_type": "any",
                "expires_phase": "FIGHT_PHASE",
                "source": str(getattr(stratagem, "name", "YRIEL'S EXAMPLE") or "YRIEL'S EXAMPLE"),
            },
        )
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_eldritch_withdraw_and_reinforce(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: WITHDRAW AND REINFORCE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: WITHDRAW AND REINFORCE: not opponent's turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_eldritch_withdraw_and_reinforce_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: WITHDRAW AND REINFORCE: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: WITHDRAW AND REINFORCE: target is not currently eligible")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: WITHDRAW AND REINFORCE: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_is_anhrathe(target_root):
            logger.error("ERROR: WITHDRAW AND REINFORCE: target must be ANHRATHE")
            return False
        if self._aeldari_in_engagement_range(target_root):
            logger.error("ERROR: WITHDRAW AND REINFORCE: target must not be within Engagement Range")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        if not self._aeldari_place_unit_into_strategic_reserves(
            target_root,
            reason=str(getattr(stratagem, "name", "WITHDRAW AND REINFORCE") or "WITHDRAW AND REINFORCE"),
        ):
            logger.error("ERROR: WITHDRAW AND REINFORCE: failed to place target into Strategic Reserves")
            return False

        returned = 0
        below_starting_fn = getattr(target_root, "is_below_starting_strength", None)
        below_starting = bool(below_starting_fn()) if callable(below_starting_fn) else False
        if below_starting:
            destroyed_pool = list(getattr(target_root, "models_lost", []) or [])
            returnable = [model for model in destroyed_pool if not bool(getattr(model, "is_character", False))]
            if returnable:
                return_full = getattr(self, "_return_destroyed_models_full", None)
                if callable(return_full):
                    returned = int(
                        return_full(
                            target_root,
                            amount=len(returnable),
                            game_map=getattr(game, "map", None),
                            skip_character=True,
                        )
                        or 0
                    )

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: WITHDRAW AND REINFORCE: %s entered Strategic Reserves and returned %d model(s).",
            getattr(target_root, "name", "Unit"),
            int(returned),
        )
        return True

    def _use_aeldari_eldritch_ruthless_killers(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: RUTHLESS KILLERS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: RUTHLESS KILLERS: Shooting phase use is only on your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_eldritch_ruthless_killers_candidates(phase_name=phase_name)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: RUTHLESS KILLERS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: RUTHLESS KILLERS: target must be an eligible CORSAIR VOIDSCARRED unit")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        expires_phase = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aeldari_ruthless_killers_active"] = True
        sr["aeldari_ruthless_killers_damage_bonus"] = 1
        sr["aeldari_ruthless_killers_expires_phase"] = expires_phase
        sr["aeldari_ruthless_killers_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_ruthless_killers_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_ruthless_killers_source"] = str(getattr(stratagem, "name", "RUTHLESS KILLERS") or "RUTHLESS KILLERS")
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: RUTHLESS KILLERS: %s gains +1 Damage until end of %s.",
            getattr(target_root, "name", "Unit"),
            "Shooting phase" if expires_phase == "SHOOTING_PHASE" else "Fight phase",
        )
        return True

    def _use_aeldari_eldritch_no_prey_too_big(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: NO PREY TOO BIG: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: NO PREY TOO BIG: not your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_eldritch_no_prey_too_big_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: NO PREY TOO BIG: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: NO PREY TOO BIG: target must be ANHRATHE, Rangers, or Shroud Runners and not yet selected to shoot")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aeldari_no_prey_too_big_active"] = True
        sr["aeldari_no_prey_too_big_wound_bonus"] = 1
        sr["aeldari_no_prey_too_big_expires_phase"] = "SHOOTING_PHASE"
        sr["aeldari_no_prey_too_big_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_no_prey_too_big_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_no_prey_too_big_source"] = str(getattr(stratagem, "name", "NO PREY TOO BIG") or "NO PREY TOO BIG")
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: NO PREY TOO BIG: %s gains +1 to wound when its attack Strength is lower than the target unit's highest Toughness this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_eldritch_raiders_spoils(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: RAIDERS' SPOILS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_eldritch_raiders_spoils_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: RAIDERS' SPOILS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: RAIDERS' SPOILS: target must be an ANHRATHE unit within Engagement Range")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        from ..utility.modifiers import Modifier, ModifierOp

        source_key = "stratagem:aeldari_raiders_spoils"
        try:
            members = list(target_root.get_attached_unit_members() or [])
        except (AttributeError, TypeError, ValueError):
            members = [target_root]
        if not members:
            members = [target_root]
        for member in members:
            if member is None:
                continue
            add_mod = getattr(member, "add_characteristic_modifier", None)
            if callable(add_mod):
                add_mod(
                    "objective_control",
                    Modifier(ModifierOp.ADD, 1, source=source_key),
                )
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["aeldari_raiders_spoils_active"] = True
            sr["aeldari_raiders_spoils_owner"] = str(getattr(self.player, "id", "") or "")
            sr["aeldari_raiders_spoils_turn"] = int(getattr(game, "turn", 0) or 0)
            sr["aeldari_raiders_spoils_source"] = str(getattr(stratagem, "name", "RAIDERS' SPOILS") or "RAIDERS' SPOILS")
            sr["aeldari_raiders_spoils_expires_trigger"] = "NEXT_COMMAND_PHASE_START"
            member.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: RAIDERS' SPOILS: %s gains +1 Objective Control until the start of the next Command phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_eldritch_impeding_fire(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: IMPEDING FIRE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: IMPEDING FIRE: not opponent's turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        source_candidates = list(context.get("candidates") or [])
        if not source_candidates:
            source_candidates = self._aeldari_eldritch_impeding_fire_source_candidates()
        if target_root is None:
            if len(source_candidates) == 1:
                target_root = source_candidates[0]
            else:
                logger.error("ERROR: IMPEDING FIRE: missing source unit")
                return False
        if target_root not in source_candidates:
            logger.error("ERROR: IMPEDING FIRE: source unit must be Rangers, Shroud Runners, or Starfangs")
            return False

        enemy_unit = context.get("enemy_unit") or context.get("target_enemy_unit") or context.get("attacking_unit")
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        enemy_candidates = list(context.get("enemy_candidates") or [])
        if not enemy_candidates:
            enemy_candidates = self._aeldari_eldritch_impeding_fire_enemy_candidates(target_root)
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: IMPEDING FIRE: missing enemy target")
                return False
        if enemy_candidates and enemy_root not in enemy_candidates:
            logger.error("ERROR: IMPEDING FIRE: selected enemy is not visible and within 36\" of source unit")
            return False
        if self._aeldari_has_keyword(enemy_root, "TITANIC"):
            logger.error("ERROR: IMPEDING FIRE: TITANIC units are ineligible")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False

        sr = getattr(enemy_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        mods = list(sr.get("charge_roll_modifiers", []) or [])
        mods.append(
            {
                "value": -2,
                "source": str(getattr(stratagem, "name", "IMPEDING FIRE") or "IMPEDING FIRE"),
                "source_key": "aeldari_impeding_fire",
                "expires_phase": "CHARGE_PHASE",
            }
        )
        sr["charge_roll_modifiers"] = mods
        enemy_root.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: IMPEDING FIRE: %s suffers -2 to Charge rolls this phase (non-cumulative with other negative modifiers).",
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_aeldari_devoted_of_ynnead_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_devoted_of_ynnead_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "EMISSARIES OF YNNEAD":
            return self._use_aeldari_devoted_emissaries_of_ynnead(stratagem, **kwargs)
        if name_u == "PARTING THE VEIL":
            return self._use_aeldari_devoted_parting_the_veil(stratagem, **kwargs)
        if name_u == "MACABRE RESILIENCE":
            return self._use_aeldari_devoted_macabre_resilience(stratagem, **kwargs)
        if name_u == "PALL OF DREAD":
            return self._use_aeldari_devoted_pall_of_dread(stratagem, **kwargs)
        if name_u == "SOULSIGHT":
            return self._use_aeldari_devoted_soulsight(stratagem, **kwargs)
        if name_u == "DEATH ANSWERS DEATH":
            return self._use_aeldari_devoted_death_answers_death(stratagem, **kwargs)
        return None

    def _use_aeldari_devoted_emissaries_of_ynnead(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: EMISSARIES OF YNNEAD: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        attacking_unit = context.get("attacking_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        if attacking_root is not None:
            try:
                if attacking_root.get_parent_army().player is not self.player:
                    logger.error("ERROR: EMISSARIES OF YNNEAD: attacking unit is not friendly")
                    return False
            except (AttributeError, TypeError, ValueError):
                return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_devoted_emissaries_candidates(attacking_unit=attacking_root)
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if attacking_root is not None:
                target_root = attacking_root
            elif len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: EMISSARIES OF YNNEAD: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: EMISSARIES OF YNNEAD: target must be the attacking YNNARI INFANTRY unit")
            return False
        if attacking_root is not None and target_root is not attacking_root:
            logger.error("ERROR: EMISSARIES OF YNNEAD: target must be the attacking unit")
            return False
        if not self._aeldari_has_keyword(target_root, "INFANTRY"):
            logger.error("ERROR: EMISSARIES OF YNNEAD: target must be INFANTRY")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: EMISSARIES OF YNNEAD: target must be on the battlefield and targetable")
            return False
        if bool(getattr(getattr(target_root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: EMISSARIES OF YNNEAD: target has already fought this phase")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_emissaries_of_ynnead_active"] = True
        sr["aeldari_emissaries_of_ynnead_expires_phase"] = "FIGHT_PHASE"
        sr["aeldari_emissaries_of_ynnead_source"] = str(
            getattr(stratagem, "name", "EMISSARIES OF YNNEAD") or "EMISSARIES OF YNNEAD"
        )
        if owner:
            sr["aeldari_emissaries_of_ynnead_owner"] = owner
        if turn:
            sr["aeldari_emissaries_of_ynnead_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_devoted_parting_the_veil(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: PARTING THE VEIL: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        attacking_unit = context.get("attacking_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        if attacking_root is None:
            logger.error("ERROR: PARTING THE VEIL: missing attacking unit")
            return False
        try:
            if attacking_root.get_parent_army().player is self.player:
                logger.error("ERROR: PARTING THE VEIL: attacking unit must be an enemy unit")
                return False
        except (AttributeError, TypeError, ValueError):
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        target_window = list(context.get("target_units") or [])
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_devoted_parting_the_veil_candidates(target_units=target_window)
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: PARTING THE VEIL: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: PARTING THE VEIL: target must have been selected as an enemy attack target")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: PARTING THE VEIL: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=attacking_root,
        ):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_parting_the_veil_active"] = True
        sr["aeldari_parting_the_veil_expires_phase"] = "FIGHT_PHASE"
        sr["aeldari_parting_the_veil_source"] = str(getattr(stratagem, "name", "PARTING THE VEIL") or "PARTING THE VEIL")
        sr["aeldari_parting_the_veil_automatic"] = True
        if owner:
            sr["aeldari_parting_the_veil_owner"] = owner
        if turn:
            sr["aeldari_parting_the_veil_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_clear_melee_fight_on_death_cache(target_root)
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_devoted_macabre_resilience(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            logger.error("ERROR: MACABRE RESILIENCE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        if phase_name == "shooting phase":
            active_player = getattr(game, "get_current_player", lambda: None)()
            if active_player is self.player:
                logger.error("ERROR: MACABRE RESILIENCE: not opponent's Shooting phase")
                return False
        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        if attacking_root is not None:
            try:
                if attacking_root.get_parent_army().player is self.player:
                    logger.error("ERROR: MACABRE RESILIENCE: attacking unit must be enemy")
                    return False
            except (AttributeError, TypeError, ValueError):
                return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        target_window = list(context.get("target_units") or [])
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_devoted_macabre_resilience_candidates(target_units=target_window)
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: MACABRE RESILIENCE: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: MACABRE RESILIENCE: target must be selected by the attacking unit")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: MACABRE RESILIENCE: target must be on the battlefield and targetable")
            return False
        if self._aeldari_has_keyword(target_root, "WRAITH CONSTRUCT"):
            logger.error("ERROR: MACABRE RESILIENCE: WRAITH CONSTRUCT units are ineligible")
            return False
        if not (self._aeldari_has_keyword(target_root, "INFANTRY") or self._aeldari_has_keyword(target_root, "MOUNTED")):
            logger.error("ERROR: MACABRE RESILIENCE: target must be INFANTRY or MOUNTED")
            return False
        if not self._aeldari_devoted_unit_counts_as_ynnari(target_root):
            logger.error("ERROR: MACABRE RESILIENCE: target must be a YNNARI unit")
            return False
        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=attacking_root,
        ):
            return False
        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE",
            "source": str(getattr(stratagem, "name", "MACABRE RESILIENCE") or "MACABRE RESILIENCE"),
        }
        self._append_defensive_effect(target_root, "defensive_wound_mods", entry)
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_devoted_pall_of_dread(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        game = getattr(self, "game", None)
        if game is None:
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            logger.error("ERROR: PALL OF DREAD: missing target unit")
            return False
        try:
            if target_root.get_parent_army().player is not self.player:
                logger.error("ERROR: PALL OF DREAD: target unit is not friendly")
                return False
        except (AttributeError, TypeError, ValueError):
            return False
        if not self._aeldari_devoted_unit_counts_as_ynnari(target_root):
            logger.error("ERROR: PALL OF DREAD: target must be a YNNARI unit")
            return False
        objective = context.get("objective") or context.get("objective_marker")
        objective_candidates = list(context.get("objective_candidates") or [])
        if not objective_candidates:
            objective_candidates = self._aeldari_devoted_pall_of_dread_objective_candidates(
                unit=target_root,
                last_model=context.get("last_model"),
            )
        if objective is None:
            if len(objective_candidates) == 1:
                objective = objective_candidates[0]
            else:
                logger.error("ERROR: PALL OF DREAD: missing objective marker selection")
                return False
        if objective_candidates and objective not in list(objective_candidates or []):
            logger.error("ERROR: PALL OF DREAD: selected objective is not eligible")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        loc = getattr(objective, "location", None)
        if loc is None:
            logger.error("ERROR: PALL OF DREAD: objective marker location unavailable")
            return False
        if hasattr(loc, "set_sticky_control"):
            loc.set_sticky_control(self.player, source="aeldari_pall_of_dread")
        else:
            loc.sticky_controller = self.player
            loc.sticky_source = "aeldari_pall_of_dread"
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_devoted_soulsight(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: DEVOTED SOULSIGHT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: DEVOTED SOULSIGHT: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_devoted_soulsight_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: DEVOTED SOULSIGHT: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: DEVOTED SOULSIGHT: target must be a YNNARI unit that has not shot")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: DEVOTED SOULSIGHT: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_devoted_soulsight_active"] = True
        sr["aeldari_devoted_soulsight_expires_phase"] = "SHOOTING_PHASE"
        sr["aeldari_devoted_soulsight_source"] = str(getattr(stratagem, "name", "SOULSIGHT") or "SOULSIGHT")
        if owner:
            sr["aeldari_devoted_soulsight_owner"] = owner
        if turn:
            sr["aeldari_devoted_soulsight_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_devoted_death_answers_death(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: DEATH ANSWERS DEATH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: DEATH ANSWERS DEATH: not opponent's turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_devoted_death_answers_death_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: DEATH ANSWERS DEATH: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: DEATH ANSWERS DEATH: target did not lose models this phase")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: DEATH ANSWERS DEATH: target must be on the battlefield and targetable")
            return False
        queue_fn = getattr(game, "_queue_shoot_again_decision", None)
        if not callable(queue_fn):
            logger.error("ERROR: DEATH ANSWERS DEATH: shoot-again decision queue unavailable")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        request = queue_fn(
            player=self.player,
            unit=target_root,
            source=str(getattr(stratagem, "name", "DEATH ANSWERS DEATH") or "DEATH ANSWERS DEATH"),
        )
        if request is None:
            logger.error("ERROR: DEATH ANSWERS DEATH: failed to queue shoot-again decision")
            return False
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    @staticmethod
    def _aeldari_phase_key_from_name(phase_name: str) -> str:
        return str(phase_name or "").strip().upper().replace(" ", "_")

    @staticmethod
    def _aeldari_is_character_model(model: Any) -> bool:
        if model is None:
            return False
        if bool(getattr(model, "is_character", False)):
            return True
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("CHARACTER")):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        has_kw = getattr(model, "has_keyword", None)
        if callable(has_kw):
            try:
                if bool(has_kw("Character")) or bool(has_kw("CHARACTER")):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        return False

    @staticmethod
    def _aeldari_model_has_keyword(model: Any, keyword: str) -> bool:
        if model is None:
            return False
        wanted = str(keyword or "").strip().upper()
        if not wanted:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any(wanted)):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        has_kw = getattr(model, "has_keyword", None)
        if callable(has_kw):
            try:
                if bool(has_kw(wanted)) or bool(has_kw(wanted.title())):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        for attr in ("keywords", "faction_keywords"):
            values = list(getattr(model, attr, []) or [])
            normalized = {str(v or "").strip().upper() for v in values if str(v or "").strip()}
            if wanted in normalized:
                return True
        return False

    def _aeldari_ghosts_staged_death_pending_returns(self) -> List[Dict[str, Any]]:
        pending = getattr(self, "_aeldari_ghosts_staged_death_pending", None)
        if not isinstance(pending, list):
            pending = []
            self._aeldari_ghosts_staged_death_pending = pending
        return pending

    def _aeldari_ghosts_staged_death_used_model_ids(self) -> set[str]:
        used = getattr(self, "_aeldari_ghosts_staged_death_used_model_id_set", None)
        if not isinstance(used, set):
            used = set()
            self._aeldari_ghosts_staged_death_used_model_id_set = used
        return used

    def _aeldari_ghosts_staged_death_model_eligible(self, *, unit: Any, model: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None or model is None:
            return False
        if not self._aeldari_is_harlequins(root):
            return False
        if not self._aeldari_is_character_model(model) and not self._aeldari_has_keyword(root, "CHARACTER"):
            return False
        model_alive = getattr(model, "is_alive", None)
        if callable(model_alive):
            try:
                if bool(model_alive()):
                    return False
            except (AttributeError, TypeError, ValueError):
                pass
        else:
            if bool(model_alive):
                return False
        return True

    @staticmethod
    def _aeldari_models_alive(unit: Any) -> int:
        if unit is None:
            return 0
        try:
            models = list(unit.get_attached_unit_models() or [])
        except (AttributeError, TypeError, ValueError):
            models = list(getattr(unit, "models", []) or [])
        return int(sum(1 for model in models if bool(getattr(model, "is_alive", False))))

    def _aeldari_is_aeldari_infantry(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if not callable(has_any):
            return False
        return bool(has_any("AELDARI") and has_any("INFANTRY"))

    def _aeldari_on_battlefield(self, unit: Any, *, require_targetable: bool = False) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if not self._aeldari_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._aeldari_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        if require_targetable and not self._aeldari_is_targetable(root):
            return False
        return True

    def _aeldari_is_battle_shocked(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        check = getattr(root, "is_battle_shocked", None)
        if callable(check):
            try:
                return bool(check())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(getattr(root, "battle_shocked", False))

    def _aeldari_in_engagement_range(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        in_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(in_engagement):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._aeldari_root(enemy)
            if enemy_root is None:
                continue
            if not self._aeldari_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if self._aeldari_in_reserves(enemy_root):
                continue
            try:
                if bool(in_engagement(root, enemy_root)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _aeldari_controlled_objective_locations(self) -> List[Any]:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        controlled: List[Any] = []
        for objective in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(objective, "location", None)
            if loc is None:
                loc = objective
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            update_control = getattr(loc, "update_control", None)
            if callable(update_control):
                try:
                    update_control(game)
                except (AttributeError, TypeError, ValueError):
                    continue
            if getattr(loc, "controlling_player", None) is self.player:
                controlled.append(loc)
        return controlled

    def _aeldari_within_controlled_objective(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        within_objective = getattr(root, "is_within_objective_range", None)
        if not callable(within_objective):
            return False
        for location in self._aeldari_controlled_objective_locations():
            try:
                if bool(within_objective(location)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _aeldari_has_keyword(self, unit: Any, keyword: str) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if not callable(has_any):
            return False
        try:
            return bool(has_any(str(keyword or "")))
        except (AttributeError, TypeError, ValueError):
            return False

    def _aeldari_is_anhrathe(self, unit: Any) -> bool:
        return self._aeldari_has_keyword(unit, "ANHRATHE")

    def _aeldari_is_harlequins(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if self._aeldari_has_keyword(root, "HARLEQUINS"):
            return True
        try:
            name = str(getattr(root, "name", "") or "").strip().lower()
        except (AttributeError, TypeError, ValueError):
            name = ""
        return "harlequin" in name

    def _aeldari_is_troupe(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if self._aeldari_has_keyword(root, "TROUPE"):
            return True
        try:
            name = str(getattr(root, "name", "") or "").strip().lower()
        except (AttributeError, TypeError, ValueError):
            name = ""
        return name in {"troupe", "troupes"}

    def _aeldari_serpents_venomous_wrath_candidates(self) -> List[Any]:
        if not self._is_serpents_brood_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_harlequins(root):
                continue
            if not self._aeldari_has_keyword(root, "VEHICLE"):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_serpents_fangs_candidates(self) -> List[Any]:
        if not self._is_serpents_brood_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_troupe(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_serpents_striking_stride_candidates(self) -> List[Any]:
        if not self._is_serpents_brood_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_harlequins(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_serpents_skyward_lunge_candidates(self) -> List[Any]:
        if not self._is_serpents_brood_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_harlequins(root):
                continue
            if not (self._aeldari_has_keyword(root, "VEHICLE") or self._aeldari_has_keyword(root, "MOUNTED")):
                continue
            if self._aeldari_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_serpents_weavers_coils_candidates(self) -> List[Any]:
        if not self._is_serpents_brood_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_harlequins(root):
                continue
            if not self._aeldari_has_keyword(root, "MOUNTED"):
                continue
            round_state = getattr(root, "round_state", None)
            was_eligible = bool(getattr(round_state, "eligible_to_fight_this_phase", False))
            if not was_eligible and bool(getattr(round_state, "fought_this_phase", False)):
                was_eligible = True
            if not was_eligible:
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_serpents_weaving_stride_candidates(self, *, enemy_unit: Any) -> List[Any]:
        if not self._is_serpents_brood_detachment():
            return []
        enemy_root = self._aeldari_root(enemy_unit)
        if enemy_root is None:
            return []
        try:
            if enemy_root.get_parent_army().player is self.player:
                return []
        except (AttributeError, TypeError, ValueError):
            return []
        if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
            return []

        from ..utility.aura_utils import unit_within_range_of_unit

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_harlequins(root):
                continue
            if not self._aeldari_has_keyword(root, "INFANTRY"):
                continue
            if not unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_serpents_normal_move_distance(self, unit: Any) -> int:
        root = self._aeldari_root(unit)
        if root is None:
            return 0
        game_map = getattr(getattr(self, "game", None), "map", None)
        model = None
        models = list(getattr(root, "get_attached_unit_models", lambda: [])() or [])
        if not models:
            models = list(getattr(root, "models", []) or [])
        for member in list(models or []):
            try:
                alive = getattr(member, "is_alive", True)
                if callable(alive):
                    alive = alive()
            except (AttributeError, TypeError, ValueError):
                alive = True
            if bool(alive):
                model = member
                break
        get_effective = getattr(root, "get_effective_model_characteristic", None)
        if model is not None and callable(get_effective):
            try:
                distance = int(get_effective(model, "movement", game_map=game_map) or 0)
            except (AttributeError, TypeError, ValueError):
                distance = 0
            if distance > 0:
                return int(distance)
        try:
            distance = int(getattr(root, "movement", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            distance = 0
        if distance > 0:
            return int(distance)
        if model is not None:
            try:
                distance = int(getattr(model, "movement", getattr(model, "_movement", 0)) or 0)
            except (AttributeError, TypeError, ValueError):
                distance = 0
            if distance > 0:
                return int(distance)
        return 0

    def _aeldari_ghosts_bloody_dance_enemy_candidates_for_unit(self, unit: Any) -> List[Any]:
        if not self._is_ghosts_of_the_webway_detachment():
            return []
        root = self._aeldari_root(unit)
        if root is None:
            return []
        if not self._aeldari_on_battlefield(root, require_targetable=True):
            return []
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []

        from ..utility.aura_utils import unit_within_range_of_unit

        out: List[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._aeldari_root(enemy)
            if enemy_root is None:
                continue
            eid = self._aeldari_sort_key(enemy_root)
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
                continue
            if not unit_within_range_of_unit(root, enemy_root, 6.0, use_attached_aggregate=True):
                continue
            can_charge = getattr(root, "can_declare_charge_against", None)
            if not callable(can_charge):
                continue
            try:
                if not bool(can_charge(enemy_root, self.game, out_of_turn=True)):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            out.append(enemy_root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_ghosts_bloody_dance_candidates(self) -> tuple[List[Any], Dict[str, List[Any]]]:
        if not self._is_ghosts_of_the_webway_detachment():
            return [], {}
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return [], {}
        out: List[Any] = []
        enemy_by_unit: Dict[str, List[Any]] = {}
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_harlequins(root):
                continue
            if not (self._aeldari_has_keyword(root, "INFANTRY") or self._aeldari_has_keyword(root, "MOUNTED")):
                continue
            enemies = self._aeldari_ghosts_bloody_dance_enemy_candidates_for_unit(root)
            if not enemies:
                continue
            out.append(root)
            if uid:
                enemy_by_unit[uid] = enemies
        return sorted(out, key=self._aeldari_sort_key), enemy_by_unit

    def _aeldari_is_rangers_or_shroud_runners(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if self._aeldari_has_keyword(root, "RANGERS") or self._aeldari_has_keyword(root, "SHROUD RUNNERS"):
            return True
        try:
            name = str(getattr(root, "name", "") or "").strip().lower()
        except (AttributeError, TypeError, ValueError):
            name = ""
        return name in {"rangers", "shroud runners"}

    def _aeldari_is_rangers_shroud_or_starfangs(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if (
            self._aeldari_has_keyword(root, "RANGERS")
            or self._aeldari_has_keyword(root, "SHROUD RUNNERS")
            or self._aeldari_has_keyword(root, "STARFANG")
            or self._aeldari_has_keyword(root, "STARFANGS")
        ):
            return True
        try:
            name = str(getattr(root, "name", "") or "").strip().lower()
        except (AttributeError, TypeError, ValueError):
            name = ""
        return name in {"rangers", "shroud runners", "starfang", "starfangs"}

    def _aeldari_is_corsair_voidscarred(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if self._aeldari_has_keyword(root, "CORSAIR VOIDSCARRED"):
            return True
        try:
            name = str(getattr(root, "name", "") or "").strip().lower()
        except (AttributeError, TypeError, ValueError):
            name = ""
        return name == "corsair voidscarred"

    def _aeldari_ghosts_exit_the_stage_candidates(self) -> List[Any]:
        if not self._is_ghosts_of_the_webway_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_harlequins(root):
                continue
            if self._aeldari_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_ghosts_heroes_fall_candidates(self, *, target_units: List[Any]) -> List[Any]:
        if not self._is_ghosts_of_the_webway_detachment():
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if not self._aeldari_is_harlequins(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_ghosts_mocking_flight_candidates(self, *, moved_unit: Any = None) -> List[Any]:
        if not self._is_ghosts_of_the_webway_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        scope = [moved_unit] if moved_unit is not None else list(getattr(army, "units", []) or [])
        for unit in scope:
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_harlequins(root):
                continue
            if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_ghosts_tricksters_retort_candidates(self, *, enemy_unit: Any) -> List[Any]:
        if not self._is_ghosts_of_the_webway_detachment():
            return []
        enemy_root = self._aeldari_root(enemy_unit)
        if enemy_root is None:
            return []
        try:
            if enemy_root.get_parent_army().player is self.player:
                return []
        except (AttributeError, TypeError, ValueError):
            return []
        if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
            return []

        from ..utility.aura_utils import unit_within_range_of_unit

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_troupe(root):
                continue
            if not unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_eldritch_yriels_example_candidates(self, *, target_units: List[Any]) -> List[Any]:
        if not self._is_eldritch_raiders_detachment():
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "AELDARI"):
                continue
            if not self._aeldari_has_keyword(root, "INFANTRY"):
                continue
            if self._aeldari_has_keyword(root, "WRAITH CONSTRUCT"):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_eldritch_withdraw_and_reinforce_candidates(self) -> List[Any]:
        if not self._is_eldritch_raiders_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_anhrathe(root):
                continue
            if self._aeldari_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_eldritch_ruthless_killers_candidates(self, *, phase_name: str) -> List[Any]:
        if not self._is_eldritch_raiders_detachment():
            return []
        phase_key = str(phase_name or "").strip().lower()
        require_not_shot = phase_key == "shooting phase"
        require_not_fought = phase_key == "fight phase"
        game = getattr(self, "game", None)
        fight_mgr = getattr(game, "fight_phase_manager", None) if game is not None else None
        fought_units = set(getattr(fight_mgr, "fought_units", set()) or set()) if fight_mgr is not None else set()

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_corsair_voidscarred(root):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought:
                if bool(getattr(getattr(root, "round_state", None), "has_fought_this_round", False)):
                    continue
                if root in fought_units:
                    continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_eldritch_no_prey_too_big_candidates(self) -> List[Any]:
        if not self._is_eldritch_raiders_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if not (self._aeldari_is_anhrathe(root) or self._aeldari_is_rangers_or_shroud_runners(root)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_eldritch_raiders_spoils_candidates(self) -> List[Any]:
        if not self._is_eldritch_raiders_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_anhrathe(root):
                continue
            if not self._aeldari_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_eldritch_impeding_fire_source_candidates(self) -> List[Any]:
        if not self._is_eldritch_raiders_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_rangers_shroud_or_starfangs(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_eldritch_impeding_fire_enemy_candidates(self, source_unit: Any) -> List[Any]:
        source_root = self._aeldari_root(source_unit)
        if source_root is None:
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        get_enemy = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy):
            return []

        from ..utility.aura_utils import unit_within_range_of_unit

        can_see_fn = getattr(game, "_model_can_see_unit", None)
        source_models = list(getattr(source_root, "get_attached_unit_models", lambda: [])() or [])
        out: List[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy(source_root) or []):
            enemy_root = self._aeldari_root(enemy)
            if enemy_root is None:
                continue
            uid = self._aeldari_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
                continue
            if self._aeldari_in_reserves(enemy_root):
                continue
            if self._aeldari_has_keyword(enemy_root, "TITANIC"):
                continue
            if not unit_within_range_of_unit(source_root, enemy_root, 36.0, use_attached_aggregate=True):
                continue
            if callable(can_see_fn):
                visible = False
                for model in source_models:
                    try:
                        alive = getattr(model, "is_alive", True)
                        if callable(alive):
                            alive = alive()
                        if not bool(alive):
                            continue
                        if bool(can_see_fn(model, enemy_root, game_map=game_map)):
                            visible = True
                            break
                    except Exception:
                        continue
                if not visible:
                    continue
            out.append(enemy_root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_corsair_outcast_ambush_candidates(self, *, require_not_shot: bool = True) -> List[Any]:
        if not self._is_corsair_coterie_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_rangers_or_shroud_runners(root):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_corsair_pirates_due_candidates(self, *, require_not_fought: bool = True) -> List[Any]:
        if not self._is_corsair_coterie_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        game = getattr(self, "game", None)
        fight_mgr = getattr(game, "fight_phase_manager", None) if game is not None else None
        fought_units = set(getattr(fight_mgr, "fought_units", set()) or set()) if fight_mgr is not None else set()

        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "AELDARI"):
                continue
            if require_not_fought:
                round_state = getattr(root, "round_state", None)
                if bool(getattr(round_state, "fought_this_phase", False)) or bool(getattr(round_state, "fought_this_round", False)):
                    continue
                if root in fought_units:
                    continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_corsair_lethal_ruse_candidates(self, *, require_fell_back: bool = True) -> List[Any]:
        if not self._is_corsair_coterie_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "AELDARI"):
                continue
            if require_fell_back and not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _capture_aeldari_corsair_movement_phase_start_engagements(self, *, player, phase) -> None:
        tracker = getattr(self, "_aeldari_corsair_fall_back_start_engagements", None)
        if not isinstance(tracker, dict):
            tracker = {}
            self._aeldari_corsair_fall_back_start_engagements = tracker
        else:
            tracker.clear()

        if not self._is_corsair_coterie_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        if player is not self.player:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return

        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=False):
                continue
            enemy_roots: List[Any] = []
            enemy_seen: set[str] = set()
            get_enemy_units = getattr(game_map, "get_enemy_units", None)
            is_engaged = getattr(game_map, "is_within_engagement_range", None)
            if not callable(get_enemy_units) or not callable(is_engaged):
                continue
            for enemy in list(get_enemy_units(root) or []):
                enemy_root = self._aeldari_root(enemy)
                if enemy_root is None:
                    continue
                enemy_uid = self._aeldari_sort_key(enemy_root)
                if enemy_uid and enemy_uid in enemy_seen:
                    continue
                if enemy_uid:
                    enemy_seen.add(enemy_uid)
                if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
                    continue
                try:
                    if bool(is_engaged(root, enemy_root)):
                        enemy_roots.append(enemy_root)
                except (AttributeError, TypeError, ValueError):
                    continue
            if not enemy_roots:
                continue
            attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(root)
            if not attacker_key:
                continue
            tracker[str(attacker_key)] = {
                "unit": root,
                "enemy_units": sorted(enemy_roots, key=self._aeldari_sort_key),
                "turn": int(getattr(game, "turn", 0) or 0),
                "owner": str(getattr(self.player, "id", "") or ""),
                "phase": "MOVEMENT_PHASE",
            }

    def _aeldari_corsair_start_phase_engaged_enemy_candidates(self, unit: Any) -> List[Any]:
        root = self._aeldari_root(unit)
        if root is None:
            return []
        attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(root)
        if not attacker_key:
            return []
        tracker = getattr(self, "_aeldari_corsair_fall_back_start_engagements", None)
        if not isinstance(tracker, dict):
            return []
        entry = tracker.get(str(attacker_key))
        if not isinstance(entry, dict):
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase = str(entry.get("phase", "") or "").strip().upper()
        if phase and phase != "MOVEMENT_PHASE":
            return []
        owner = str(entry.get("owner", "") or "")
        if owner and owner != str(getattr(self.player, "id", "") or ""):
            return []
        try:
            marked_turn = int(entry.get("turn", 0) or 0)
        except (TypeError, ValueError):
            marked_turn = 0
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for enemy in list(entry.get("enemy_units") or []):
            enemy_root = self._aeldari_root(enemy)
            if enemy_root is None:
                continue
            enemy_uid = self._aeldari_sort_key(enemy_root)
            if enemy_uid and enemy_uid in seen:
                continue
            if enemy_uid:
                seen.add(enemy_uid)
            if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
                continue
            try:
                if enemy_root.get_parent_army().player is self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            out.append(enemy_root)
        return sorted(out, key=self._aeldari_sort_key)

    def _capture_aeldari_corsair_into_the_breach_destroyed_enemy(self, *, destroyed_by_unit: Any) -> None:
        if destroyed_by_unit is None or not self._is_corsair_coterie_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        attacker_root = self._aeldari_root(destroyed_by_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if not self._aeldari_is_anhrathe(attacker_root):
            return
        if not self._aeldari_on_battlefield(attacker_root, require_targetable=True):
            return
        attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(attacker_root)
        if not attacker_key:
            return
        tracker = getattr(self, "_aeldari_corsair_into_the_breach_ready", None)
        if not isinstance(tracker, dict):
            tracker = {}
            self._aeldari_corsair_into_the_breach_ready = tracker
        tracker[str(attacker_key)] = {
            "unit": attacker_root,
            "turn": int(getattr(game, "turn", 0) or 0),
            "owner": str(getattr(self.player, "id", "") or ""),
            "phase": "SHOOTING_PHASE",
        }

    def _aeldari_corsair_into_the_breach_trigger_ready(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(root)
        if not attacker_key:
            return False
        tracker = getattr(self, "_aeldari_corsair_into_the_breach_ready", None)
        if not isinstance(tracker, dict):
            return False
        entry = tracker.get(str(attacker_key))
        if not isinstance(entry, dict):
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        phase = str(entry.get("phase", "") or "").strip().upper()
        if phase and phase != "SHOOTING_PHASE":
            return False
        owner = str(entry.get("owner", "") or "")
        if owner and owner != str(getattr(self.player, "id", "") or ""):
            return False
        try:
            marked_turn = int(entry.get("turn", 0) or 0)
        except (TypeError, ValueError):
            marked_turn = 0
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            return False
        return True

    def _aeldari_corsair_targeted_infantry_candidates(
        self,
        *,
        attacking_unit: Any,
        target_units: List[Any],
        require_controlled_objective: bool,
    ) -> List[Any]:
        if attacking_unit is None:
            return []
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return []
        try:
            if attacker_root.get_parent_army().player is self.player:
                return []
        except (AttributeError, TypeError, ValueError):
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_aeldari_infantry(root):
                continue
            if require_controlled_objective and not self._aeldari_within_controlled_objective(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_corsair_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        enemy_unit: Any = None,
    ) -> bool:
        expected_name = self._aeldari_norm_name(stratagem_name)
        expected_phase = str(phase_name or "").strip().lower()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name or ""):
                continue
            if self._aeldari_norm_name(reaction.get("stratagem", "")) != expected_name:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != expected_phase:
                continue
            if enemy_unit is not None and reaction.get("enemy_unit") is not enemy_unit:
                continue
            return True
        return False

    def _queue_aeldari_corsair_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or not self._is_corsair_coterie_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        root = self._aeldari_root(unit)
        if root is None:
            return
        try:
            if root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in ("fall back", "fallback"):
            return
        stratagem = self.get_by_name("LETHAL RUSE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_corsair_lethal_ruse_candidates(require_fell_back=True)
        if root not in candidates:
            return
        if self._aeldari_reaction_exists("unit_move_ended", stratagem.name, unit=root):
            return
        payload: Dict[str, Any] = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "action": action,
            "unit": root,
            "target_unit": root,
            "candidates": [root],
        }
        if self._aeldari_is_anhrathe(root):
            enemy_candidates = self._aeldari_corsair_start_phase_engaged_enemy_candidates(root)
            if enemy_candidates:
                payload["enemy_candidates"] = enemy_candidates
                payload["start_phase_enemy_candidates"] = enemy_candidates
                if len(enemy_candidates) == 1:
                    payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload)

    def _queue_aeldari_corsair_shooting_reactions(self, *, attacking_unit: Any, target_units: List[Any]) -> None:
        if attacking_unit is None or not self._is_corsair_coterie_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        active_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
        if active_player is self.player:
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return

        stratagem = self.get_by_name("CLOAK AND SHADOW")
        if (
            stratagem is not None
            and int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(stratagem, "cp_cost", 0) or 0)
            and self._aeldari_norm_name(stratagem.name) not in getattr(self, "_used_stratagems_this_phase", set())
        ):
            candidates = self._aeldari_corsair_targeted_infantry_candidates(
                attacking_unit=attacker_root,
                target_units=list(target_units or []),
                require_controlled_objective=True,
            )
            if candidates and not self._aeldari_corsair_reaction_already_queued(
                event_name="shooting_targets_selected",
                stratagem_name=stratagem.name,
                phase_name="Shooting phase",
                enemy_unit=attacker_root,
            ):
                payload: Dict[str, Any] = {
                    "event": "shooting_targets_selected",
                    "phase_name": "Shooting phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "enemy_unit": attacker_root,
                    "attacking_unit": attacker_root,
                    "target_units": list(target_units or []),
                    "candidates": candidates,
                }
                if len(candidates) == 1:
                    payload["target_unit"] = candidates[0]
                self._queue_reaction(payload)

        vengeful = self.get_by_name("VENGEFUL SORROW")
        if vengeful is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(vengeful, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(vengeful.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        tracked_candidates = self._aeldari_corsair_targeted_infantry_candidates(
            attacking_unit=attacker_root,
            target_units=list(target_units or []),
            require_controlled_objective=False,
        )
        snapshot: Dict[str, Dict[str, Any]] = {}
        for candidate in tracked_candidates:
            uid = self._aeldari_sort_key(candidate)
            if not uid:
                continue
            snapshot[uid] = {
                "unit": candidate,
                "models_before": self._aeldari_models_alive(candidate),
            }
        if not snapshot:
            return
        attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(attacker_root)
        if not attacker_key:
            return
        by_attacker = getattr(self, "_aeldari_corsair_models_before_shooting", None)
        if not isinstance(by_attacker, dict):
            by_attacker = {}
            self._aeldari_corsair_models_before_shooting = by_attacker
        by_attacker[str(attacker_key)] = snapshot

    def _queue_aeldari_corsair_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Any = None,
    ) -> None:
        if attacker_unit is None or not self._is_corsair_coterie_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        active_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
        attacker_root = self._aeldari_root(attacker_unit)
        if attacker_root is None:
            return
        attacker_is_friendly = False
        try:
            attacker_is_friendly = attacker_root.get_parent_army().player is self.player
        except (AttributeError, TypeError, ValueError):
            return

        if active_player is self.player:
            if not attacker_is_friendly:
                return
            stratagem = self.get_by_name("INTO THE BREACH")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            if not self._aeldari_is_anhrathe(attacker_root):
                return
            if not self._aeldari_on_battlefield(attacker_root, require_targetable=True):
                return
            if not self._aeldari_corsair_into_the_breach_trigger_ready(attacker_root):
                return
            if self._aeldari_corsair_reaction_already_queued(
                event_name="unit_shooting_resolved",
                stratagem_name=stratagem.name,
                phase_name="Shooting phase",
                enemy_unit=attacker_root,
            ):
                return
            self._queue_reaction(
                {
                    "event": "unit_shooting_resolved",
                    "phase_name": "Shooting phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "attacker_unit": attacker_root,
                    "attacking_unit": attacker_root,
                    "enemy_unit": attacker_root,
                    "hits_by_target": hits_by_target,
                    "candidates": [attacker_root],
                    "target_unit": attacker_root,
                }
            )
            return

        if attacker_is_friendly:
            return

        stratagem = self.get_by_name("VENGEFUL SORROW")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return

        by_attacker = getattr(self, "_aeldari_corsair_models_before_shooting", None)
        if not isinstance(by_attacker, dict):
            return
        attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(attacker_root)
        if not attacker_key:
            return
        snapshot = by_attacker.pop(str(attacker_key), {})
        if not isinstance(snapshot, dict) or not snapshot:
            return

        candidates: List[Any] = []
        models_before_by_unit: Dict[str, int] = {}
        for uid, entry in snapshot.items():
            if not isinstance(entry, dict):
                continue
            root = self._aeldari_root(entry.get("unit"))
            if root is None:
                continue
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_aeldari_infantry(root):
                continue
            if self._aeldari_is_battle_shocked(root):
                continue
            if self._aeldari_in_engagement_range(root):
                continue
            try:
                before = int(entry.get("models_before", 0) or 0)
            except (TypeError, ValueError):
                before = 0
            after = self._aeldari_models_alive(root)
            if after >= before:
                continue
            candidates.append(root)
            models_before_by_unit[str(uid)] = int(before)
        candidates = sorted(candidates, key=self._aeldari_sort_key)
        if not candidates:
            return
        if self._aeldari_corsair_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_root,
        ):
            return
        payload: Dict[str, Any] = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "hits_by_target": hits_by_target,
            "candidates": candidates,
            "models_before_by_unit": models_before_by_unit,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _roll_aeldari_vengeful_sorrow_distance(self, unit: Any) -> int:
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice

        base_roll = int(get_roll("D6") or 0)
        max_distance = int(base_roll + 1)
        player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
        if player is not None:
            append_dice(
                player,
                f"Vengeful Sorrow roll: {int(base_roll or 0)} (move {int(max_distance)}\") for {getattr(unit, 'name', 'Unit')}",
            )
        return int(max_distance)

    def _roll_aeldari_into_the_breach_distance(self, unit: Any) -> int:
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice

        base_roll = int(get_roll("D6") or 0)
        max_distance = int(base_roll + 1)
        player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
        if player is not None:
            append_dice(
                player,
                f"Into the Breach roll: {int(base_roll or 0)} (move {int(max_distance)}\") for {getattr(unit, 'name', 'Unit')}",
            )
        return int(max_distance)

    def _roll_aeldari_lethal_ruse_mortal_wounds(self, unit: Any, enemy_unit: Any) -> int:
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice

        rolls = [int(get_roll("D6") or 0) for _ in range(6)]
        mortals = int(sum(1 for roll in rolls if int(roll or 0) >= 4))
        player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
        if player is not None:
            append_dice(
                player,
                (
                    f"Lethal Ruse rolls for {getattr(unit, 'name', 'Unit')} vs {getattr(enemy_unit, 'name', 'Enemy')}: "
                    f"{rolls} => {int(mortals)} mortal wounds"
                ),
            )
        return int(mortals)

    def _roll_aeldari_ishas_fury_mortal_wounds(self, psyker_unit: Any, enemy_unit: Any) -> int:
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice

        rolls = [int(get_roll("D6") or 0) for _ in range(6)]
        mortals = int(sum(1 for roll in rolls if int(roll or 0) >= 3))
        player = getattr(psyker_unit.get_parent_army(), "player", None) if psyker_unit is not None else None
        if player is not None:
            append_dice(
                player,
                (
                    f"Isha's Fury rolls for {getattr(psyker_unit, 'name', 'Unit')} vs {getattr(enemy_unit, 'name', 'Enemy')}: "
                    f"{rolls} => {int(mortals)} mortal wounds"
                ),
            )
        return int(mortals)

    def _use_aeldari_corsair_coterie_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_corsair_coterie_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "OUTCAST AMBUSH":
            return self._use_aeldari_corsair_outcast_ambush(stratagem, **kwargs)
        if name_u == "INTO THE BREACH":
            return self._use_aeldari_corsair_into_the_breach(stratagem, **kwargs)
        if name_u == "LETHAL RUSE":
            return self._use_aeldari_corsair_lethal_ruse(stratagem, **kwargs)
        if name_u == "PIRATES' DUE":
            return self._use_aeldari_corsair_pirates_due(stratagem, **kwargs)
        if name_u == "CLOAK AND SHADOW":
            return self._use_aeldari_corsair_cloak_and_shadow(stratagem, **kwargs)
        if name_u == "VENGEFUL SORROW":
            return self._use_aeldari_corsair_vengeful_sorrow(stratagem, **kwargs)
        return None

    def _use_aeldari_corsair_outcast_ambush(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: OUTCAST AMBUSH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: OUTCAST AMBUSH: not your turn")
            return False

        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_corsair_outcast_ambush_candidates(require_not_shot=True)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: OUTCAST AMBUSH: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: OUTCAST AMBUSH: target must be a Rangers or Shroud Runners unit that has not shot")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        source = str(getattr(stratagem, "name", "OUTCAST AMBUSH") or "OUTCAST AMBUSH")
        try:
            members = list(target_root.get_attached_unit_members() or [])
        except (AttributeError, TypeError, ValueError):
            members = [target_root]
        if not members:
            members = [target_root]
        for unit in members:
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["aeldari_outcast_ambush_active"] = True
            sr["aeldari_outcast_ambush_expires_phase"] = "SHOOTING_PHASE"
            sr["aeldari_outcast_ambush_turn_owner"] = owner
            sr["aeldari_outcast_ambush_turn"] = int(turn or 0)
            sr["aeldari_outcast_ambush_source"] = source
            unit.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: OUTCAST AMBUSH: %s gains [IGNORES COVER], [RAPID FIRE 1], and AP improves by 1 this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_corsair_into_the_breach(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: INTO THE BREACH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: INTO THE BREACH: not your turn")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates and attacking_root is not None:
            if self._aeldari_corsair_into_the_breach_trigger_ready(attacking_root):
                candidates = [attacking_root]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: INTO THE BREACH: missing target unit")
                return False
        if candidates and target_root not in candidates:
            logger.error("ERROR: INTO THE BREACH: target was not selected")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: INTO THE BREACH: target must be on the battlefield")
            return False
        if not self._aeldari_is_anhrathe(target_root):
            logger.error("ERROR: INTO THE BREACH: target must be ANHRATHE")
            return False
        if not self._aeldari_corsair_into_the_breach_trigger_ready(target_root):
            logger.error("ERROR: INTO THE BREACH: target did not destroy an enemy unit this phase")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        max_distance = kwargs.get("max_distance")
        if max_distance is None:
            max_distance = self._roll_aeldari_into_the_breach_distance(target_root)
        try:
            max_distance = int(max_distance or 0)
        except (TypeError, ValueError):
            max_distance = 0
        if max_distance <= 0:
            logger.error("ERROR: INTO THE BREACH: movement distance roll failed")
            return False

        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if callable(queue_move):
            queue_move(
                player=self.player,
                unit=target_root,
                attacker_unit=target_root,
                max_distance=int(max_distance),
                kind="into_the_breach",
                movement_type="reactive",
                source=str(getattr(stratagem, "name", "INTO THE BREACH") or "INTO THE BREACH"),
            )

        tracker = getattr(self, "_aeldari_corsair_into_the_breach_ready", None)
        if isinstance(tracker, dict):
            attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(target_root)
            if attacker_key:
                tracker.pop(str(attacker_key), None)
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: INTO THE BREACH: %s can make a Normal move up to %d\".",
            getattr(target_root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_aeldari_corsair_lethal_ruse(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: LETHAL RUSE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: LETHAL RUSE: not your turn")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key and action_key not in ("fall back", "fallback"):
            logger.error("ERROR: LETHAL RUSE: wrong trigger")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_corsair_lethal_ruse_candidates(require_fell_back=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: LETHAL RUSE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: LETHAL RUSE: target must be an AELDARI unit that Fell Back this phase")
            return False
        if not bool(getattr(getattr(target_root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: LETHAL RUSE: target has not Fallen Back")
            return False

        enemy_candidates = list(context.get("enemy_candidates") or context.get("start_phase_enemy_candidates") or [])
        if not enemy_candidates:
            enemy_candidates = self._aeldari_corsair_start_phase_engaged_enemy_candidates(target_root)
        enemy_unit = (
            context.get("enemy_unit")
            or context.get("target_enemy_unit")
            or context.get("enemy_target")
            or context.get("attacking_unit")
        )
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        if self._aeldari_is_anhrathe(target_root):
            if enemy_root is None:
                if len(enemy_candidates) == 1:
                    enemy_root = self._aeldari_root(enemy_candidates[0])
                elif len(enemy_candidates) > 1:
                    logger.error("ERROR: LETHAL RUSE: missing selected enemy unit")
                    return False
            if enemy_root is not None:
                enemy_roots = [self._aeldari_root(enemy) for enemy in list(enemy_candidates or [])]
                enemy_roots = [enemy for enemy in enemy_roots if enemy is not None]
                if enemy_roots and enemy_root not in enemy_roots:
                    logger.error("ERROR: LETHAL RUSE: selected enemy was not in Engagement Range at start of phase")
                    return False
                try:
                    if enemy_root.get_parent_army().player is self.player:
                        logger.error("ERROR: LETHAL RUSE: selected enemy is not an enemy unit")
                        return False
                except (AttributeError, TypeError, ValueError):
                    logger.error("ERROR: LETHAL RUSE: selected enemy is invalid")
                    return False

        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aeldari_lethal_ruse_charge_after_fall_back_active"] = True
        sr["aeldari_lethal_ruse_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_lethal_ruse_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_lethal_ruse_source"] = str(getattr(stratagem, "name", "LETHAL RUSE") or "LETHAL RUSE")
        target_root.special_rules = sr

        if self._aeldari_is_anhrathe(target_root) and enemy_root is not None:
            mortal_wounds = self._roll_aeldari_lethal_ruse_mortal_wounds(target_root, enemy_root)
            if mortal_wounds > 0:
                apply_mortals = getattr(enemy_root, "_apply_mortal_wounds_to_unit", None)
                if callable(apply_mortals):
                    try:
                        apply_mortals(enemy_root, int(mortal_wounds), game_map=getattr(game, "map", None))
                    except TypeError:
                        apply_mortals(target_unit=enemy_root, amount=int(mortal_wounds), game_map=getattr(game, "map", None))
            logger.info(
                "INFO: LETHAL RUSE: %s can charge after Falling Back; %s suffers %d mortal wounds.",
                getattr(target_root, "name", "Unit"),
                getattr(enemy_root, "name", "Enemy"),
                int(mortal_wounds),
            )
        else:
            logger.info(
                "INFO: LETHAL RUSE: %s can charge after Falling Back this turn.",
                getattr(target_root, "name", "Unit"),
            )

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_corsair_pirates_due(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: PIRATES' DUE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_corsair_pirates_due_candidates(require_not_fought=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PIRATES' DUE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: PIRATES' DUE: target must be an AELDARI unit that has not been selected to fight")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aeldari_pirates_due_active"] = True
        sr["aeldari_pirates_due_expires_phase"] = "FIGHT_PHASE"
        sr["aeldari_pirates_due_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_pirates_due_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_pirates_due_source"] = str(getattr(stratagem, "name", "PIRATES' DUE") or "PIRATES' DUE")
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: PIRATES' DUE: %s re-rolls Wound rolls of 1 in this Fight phase (ANHRATHE gains full re-rolls vs targets within objective range).",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_corsair_cloak_and_shadow(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CLOAK AND SHADOW: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: CLOAK AND SHADOW: not opponent's turn")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit") or context.get("enemy_unit")
        attacking_root = self._aeldari_root(attacking_unit)
        if attacking_root is None:
            logger.error("ERROR: CLOAK AND SHADOW: missing attacking unit context")
            return False
        try:
            if attacking_root.get_parent_army().player is self.player:
                logger.error("ERROR: CLOAK AND SHADOW: attacker is not enemy")
                return False
        except (AttributeError, TypeError, ValueError):
            logger.error("ERROR: CLOAK AND SHADOW: attacker is invalid")
            return False

        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_corsair_targeted_infantry_candidates(
                attacking_unit=attacking_root,
                target_units=list(context.get("target_units") or []),
                require_controlled_objective=True,
            )
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: CLOAK AND SHADOW: missing target unit")
                return False
        if target_root not in candidates:
            logger.error(
                "ERROR: CLOAK AND SHADOW: target must be AELDARI INFANTRY selected by attacker and within range of a controlled objective"
            )
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False

        owner_id = str(getattr(active_player, "id", "") or "")
        effect_owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        try:
            members = list(target_root.get_attached_unit_members() or [])
        except (AttributeError, TypeError, ValueError):
            members = [target_root]
        if not members:
            members = [target_root]
        for unit in members:
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["opponent_shooting_phase_stealth_active"] = True
            sr["opponent_shooting_phase_stealth_owner"] = owner_id
            sr["opponent_shooting_phase_stealth_turn"] = int(turn or 0)
            sr["opponent_shooting_phase_stealth_source"] = str(getattr(stratagem, "name", "CLOAK AND SHADOW") or "CLOAK AND SHADOW")
            sr["opponent_shooting_phase_stealth_expires_phase"] = "SHOOTING_PHASE"
            sr["aeldari_cloak_and_shadow_active"] = True
            sr["aeldari_cloak_and_shadow_targeting_range"] = 18
            sr["aeldari_cloak_and_shadow_expires_phase"] = "SHOOTING_PHASE"
            sr["aeldari_cloak_and_shadow_turn_owner"] = effect_owner_id
            sr["aeldari_cloak_and_shadow_turn"] = int(turn or 0)
            sr["aeldari_cloak_and_shadow_source"] = str(getattr(stratagem, "name", "CLOAK AND SHADOW") or "CLOAK AND SHADOW")
            unit.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: CLOAK AND SHADOW: %s gains Stealth and can only be targeted by ranged attacks from within 18\" this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_corsair_vengeful_sorrow(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VENGEFUL SORROW: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: VENGEFUL SORROW: not opponent's turn")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit") or context.get("enemy_unit")
        attacking_root = self._aeldari_root(attacking_unit)
        if attacking_root is None:
            logger.error("ERROR: VENGEFUL SORROW: missing attacking unit context")
            return False
        try:
            if attacking_root.get_parent_army().player is self.player:
                logger.error("ERROR: VENGEFUL SORROW: attacker is not enemy")
                return False
        except (AttributeError, TypeError, ValueError):
            logger.error("ERROR: VENGEFUL SORROW: attacker is invalid")
            return False

        candidates = list(context.get("candidates") or [])
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: VENGEFUL SORROW: missing target unit")
                return False
        if candidates and target_root not in candidates:
            logger.error("ERROR: VENGEFUL SORROW: target was not selected")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: VENGEFUL SORROW: target must be on the battlefield")
            return False
        if not self._aeldari_is_aeldari_infantry(target_root):
            logger.error("ERROR: VENGEFUL SORROW: target must be AELDARI INFANTRY")
            return False
        if self._aeldari_is_battle_shocked(target_root):
            logger.error("ERROR: VENGEFUL SORROW: target is Battle-shocked")
            return False
        if self._aeldari_in_engagement_range(target_root):
            logger.error("ERROR: VENGEFUL SORROW: target is within Engagement Range")
            return False

        models_before_by_unit = dict(context.get("models_before_by_unit") or {})
        if models_before_by_unit:
            uid = self._aeldari_sort_key(target_root)
            before = int(models_before_by_unit.get(uid, 0) or 0)
            after = self._aeldari_models_alive(target_root)
            if before and after >= before:
                logger.error("ERROR: VENGEFUL SORROW: target did not lose models from this attack")
                return False

        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False
        max_distance = kwargs.get("max_distance")
        if max_distance is None:
            max_distance = self._roll_aeldari_vengeful_sorrow_distance(target_root)
        try:
            max_distance = int(max_distance or 0)
        except (TypeError, ValueError):
            max_distance = 0
        if max_distance <= 0:
            logger.error("ERROR: VENGEFUL SORROW: movement distance roll failed")
            return False

        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if callable(queue_move):
            queue_move(
                player=self.player,
                unit=target_root,
                attacker_unit=attacking_root,
                max_distance=int(max_distance),
                kind="vengeful_sorrow",
                movement_type="blood_surge",
                source=str(getattr(stratagem, "name", "VENGEFUL SORROW") or "VENGEFUL SORROW"),
            )

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: VENGEFUL SORROW: %s can make a Surge move up to %d\".",
            getattr(target_root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _aeldari_aspect_warriors_avatar_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_on_battlefield: bool = True,
    ) -> List[Any]:
        if not self._is_aspect_host_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._aeldari_detachment_mgr()
        aspect_checker = getattr(mgr, "_unit_is_aspect_warriors", None) if mgr is not None else None
        avatar_checker = getattr(mgr, "_unit_is_avatar_of_khaine", None) if mgr is not None else None
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_alive(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if require_on_battlefield:
                if not bool(getattr(root, "deployed", False)):
                    continue
                if self._aeldari_in_reserves(root):
                    continue
                if not self._aeldari_is_targetable(root):
                    continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            is_aspect = bool(aspect_checker(root)) if callable(aspect_checker) else bool(
                getattr(root, "has_any_keyword", lambda _k: False)("ASPECT WARRIORS")
            )
            is_avatar = bool(avatar_checker(root)) if callable(avatar_checker) else bool(
                getattr(root, "has_any_keyword", lambda _k: False)("AVATAR OF KHAINE")
            )
            if not (is_aspect or is_avatar):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_aspect_warriors_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_on_battlefield: bool = True,
    ) -> List[Any]:
        mgr = self._aeldari_detachment_mgr()
        aspect_checker = getattr(mgr, "_unit_is_aspect_warriors", None) if mgr is not None else None
        out: List[Any] = []
        for unit in self._aeldari_aspect_warriors_avatar_candidates(
            require_not_shot=require_not_shot,
            require_not_fought=require_not_fought,
            require_on_battlefield=require_on_battlefield,
        ):
            is_aspect = bool(aspect_checker(unit)) if callable(aspect_checker) else bool(
                getattr(unit, "has_any_keyword", lambda _k: False)("ASPECT WARRIORS")
            )
            if is_aspect:
                out.append(unit)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_avatar_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_on_battlefield: bool = True,
    ) -> List[Any]:
        mgr = self._aeldari_detachment_mgr()
        avatar_checker = getattr(mgr, "_unit_is_avatar_of_khaine", None) if mgr is not None else None
        out: List[Any] = []
        for unit in self._aeldari_aspect_warriors_avatar_candidates(
            require_not_shot=require_not_shot,
            require_not_fought=require_not_fought,
            require_on_battlefield=require_on_battlefield,
        ):
            is_avatar = bool(avatar_checker(unit)) if callable(avatar_checker) else bool(
                getattr(unit, "has_any_keyword", lambda _k: False)("AVATAR OF KHAINE")
            )
            if is_avatar:
                out.append(unit)
        return sorted(out, key=self._aeldari_sort_key)

    def _queue_aeldari_aspect_host_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_aspect_host_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_key == "SHOOTING_PHASE" and active_player is self.player:
            definitions = (
                ("WARRIOR FOCUS", self._aeldari_aspect_warriors_avatar_candidates(require_not_shot=True)),
                ("PRETERNATURAL PRECISION", self._aeldari_aspect_warriors_candidates(require_not_shot=True)),
                ("DOOM INESCAPABLE", self._aeldari_avatar_candidates(require_not_shot=True)),
            )
            for strat_name, candidates in definitions:
                stratagem = self.get_by_name(strat_name)
                if stratagem is None:
                    continue
                if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                    continue
                if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                    continue
                if not candidates:
                    continue
                if self._aeldari_reaction_exists("phase_start", stratagem.name):
                    continue
                payload: Dict[str, Any] = {
                    "event": "phase_start",
                    "phase": "Shooting phase",
                    "phase_name": "Shooting phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "candidates": candidates,
                }
                if len(candidates) == 1:
                    payload["unit"] = candidates[0]
                    payload["target_unit"] = candidates[0]
                self._queue_reaction(payload, use_timer=False)
            return

        if phase_key == "FIGHT_PHASE":
            stratagem = self.get_by_name("WARRIOR FOCUS")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_aspect_warriors_avatar_candidates(require_not_fought=True)
            if not candidates:
                return
            if self._aeldari_reaction_exists("phase_start", stratagem.name):
                return
            payload = {
                "event": "phase_start",
                "phase": "Fight phase",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_aspect_host_move_start_reactions(self, *, unit, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_aspect_host_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in ("fall back", "fallback"):
            return
        enemy_root = self._aeldari_root(unit)
        if enemy_root is None:
            return
        try:
            if enemy_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if bool(getattr(enemy_root, "has_any_keyword", lambda _k: False)("MONSTER")):
            return
        if bool(getattr(enemy_root, "has_any_keyword", lambda _k: False)("VEHICLE")):
            return
        stratagem = self.get_by_name("KHAINE'S VENGEANCE") or self.get_by_name("KHAINE\u2019S VENGEANCE")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return
        candidates: List[Any] = []
        for candidate in self._aeldari_aspect_warriors_avatar_candidates(require_on_battlefield=True):
            try:
                if game_map.is_within_engagement_range(candidate, enemy_root):
                    candidates.append(candidate)
            except (AttributeError, TypeError, ValueError):
                continue
        if not candidates:
            return
        if self._aeldari_reaction_exists("unit_move_started", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "action": action,
            "enemy_unit": enemy_root,
            "candidates": sorted(candidates, key=self._aeldari_sort_key),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_aspect_host_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_aspect_host_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("TO THEIR FINAL BREATH")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        eligible_candidates = self._aeldari_aspect_warriors_avatar_candidates(require_not_fought=True)
        candidates: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if root not in eligible_candidates:
                continue
            candidates.append(root)
        if not candidates:
            return
        if self._aeldari_reaction_exists("fight_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": sorted(candidates, key=self._aeldari_sort_key),
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_aspect_host_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_aspect_host_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("SKYBORNE SANCTUARY")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        if self._aeldari_reaction_exists("phase_end", stratagem.name):
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return
        candidates: List[Any] = []
        transports_by_unit: Dict[Any, List[Any]] = {}
        seen: set[str] = set()
        for unit in list(getattr(getattr(self.player, "get_army", lambda: None)(), "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_alive(root):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            if self._aeldari_in_reserves(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if not self._aeldari_is_targetable(root):
                continue
            if not bool(getattr(root, "has_any_keyword", lambda _k: False)("ASURYANI")):
                continue
            engaged = False
            try:
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
            except (AttributeError, TypeError, ValueError):
                engaged = True
            if engaged:
                continue
            transports = list(getattr(self, "_skyborne_transport_candidates", lambda _u: [])(root) or [])
            if not transports:
                continue
            candidates.append(root)
            transports_by_unit[root] = sorted(transports, key=self._aeldari_sort_key)
        if not candidates:
            return
        payload: Dict[str, Any] = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": sorted(candidates, key=self._aeldari_sort_key),
            "transport_candidates_by_unit": transports_by_unit,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
            tx = list(transports_by_unit.get(candidates[0], []) or [])
            if len(tx) == 1:
                payload["transport_unit"] = tx[0]
                payload["transport"] = tx[0]
        self._queue_reaction(payload, use_timer=False)

    @staticmethod
    def _aeldari_aspect_precision_choice(value: str) -> str:
        text = str(value or "").strip().upper().replace("\u2019", "'")
        text = " ".join(text.split())
        if text == "SUSTAINED HITS":
            return "SUSTAINED HITS 1"
        return text

    def _aeldari_clear_melee_fight_on_death_cache(self, root: Any) -> None:
        cache = getattr(root, "_ability_cache", None)
        if not isinstance(cache, dict):
            return
        for key in list(cache.keys()):
            if str(key).startswith("melee_fight_on_death_after_attacks:"):
                cache.pop(key, None)

    def _cleanup_aeldari_aspect_host_phase_end_effects(self, *, phase) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_key:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        units = list(getattr(army, "units", []) or []) if army is not None else []
        seen: set[str] = set()
        roots: list[Any] = []
        for unit in units:
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            roots.append(root)

        for root in roots:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False

            wf_exp = str(sr.get("aeldari_warrior_focus_expires_phase", "") or "").strip().upper()
            if wf_exp and wf_exp == phase_key:
                for key in (
                    "aeldari_warrior_focus_active",
                    "aeldari_warrior_focus_expires_phase",
                    "aeldari_warrior_focus_owner",
                    "aeldari_warrior_focus_turn",
                    "aeldari_warrior_focus_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            pp_exp = str(sr.get("aeldari_preternatural_precision_expires_phase", "") or "").strip().upper()
            if pp_exp and pp_exp == phase_key:
                for key in (
                    "aeldari_preternatural_precision_active",
                    "aeldari_preternatural_precision_expires_phase",
                    "aeldari_preternatural_precision_owner",
                    "aeldari_preternatural_precision_turn",
                    "aeldari_preternatural_precision_source",
                    "aeldari_preternatural_precision_keywords",
                    "aeldari_preternatural_precision_token_spent",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            doom_exp = str(sr.get("aeldari_doom_inescapable_expires_phase", "") or "").strip().upper()
            if doom_exp and doom_exp == phase_key:
                for key in (
                    "aeldari_doom_inescapable_active",
                    "aeldari_doom_inescapable_expires_phase",
                    "aeldari_doom_inescapable_owner",
                    "aeldari_doom_inescapable_turn",
                    "aeldari_doom_inescapable_source",
                    "aeldari_doom_inescapable_weapon_range_overrides",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                try:
                    models = list(root.get_attached_unit_models() or [])
                except (AttributeError, TypeError, ValueError):
                    models = list(getattr(root, "models", []) or [])
                for model in list(models or []):
                    eff = getattr(model, "_temporary_effects", None)
                    if isinstance(eff, dict) and "aeldari_doom_inescapable" in eff:
                        eff.pop("aeldari_doom_inescapable", None)

            tfb_exp = str(sr.get("aeldari_to_their_final_breath_expires_phase", "") or "").strip().upper()
            if tfb_exp and tfb_exp == phase_key:
                for key in (
                    "aeldari_to_their_final_breath_active",
                    "aeldari_to_their_final_breath_expires_phase",
                    "aeldari_to_their_final_breath_owner",
                    "aeldari_to_their_final_breath_turn",
                    "aeldari_to_their_final_breath_source",
                    "aeldari_to_their_final_breath_threshold",
                    "aeldari_to_their_final_breath_token_spent",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                self._aeldari_clear_melee_fight_on_death_cache(root)

            if changed:
                root.special_rules = sr

    def _use_aeldari_aspect_host_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_aspect_host_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "DOOM INESCAPABLE":
            return self._use_aeldari_aspect_host_doom_inescapable(stratagem, **kwargs)
        if name_u in ("KHAINE'S VENGEANCE",):
            return self._use_aeldari_aspect_host_khaines_vengeance(stratagem, **kwargs)
        if name_u == "PRETERNATURAL PRECISION":
            return self._use_aeldari_aspect_host_preternatural_precision(stratagem, **kwargs)
        if name_u == "SKYBORNE SANCTUARY":
            return self._use_aeldari_aspect_host_skyborne_sanctuary(stratagem, **kwargs)
        if name_u == "TO THEIR FINAL BREATH":
            return self._use_aeldari_aspect_host_to_their_final_breath(stratagem, **kwargs)
        if name_u == "WARRIOR FOCUS":
            return self._use_aeldari_aspect_host_warrior_focus(stratagem, **kwargs)
        return None

    def _use_aeldari_aspect_host_warrior_focus(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            logger.error("ERROR: WARRIOR FOCUS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: WARRIOR FOCUS: not your Shooting phase")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if phase_name == "shooting phase":
            candidates = self._aeldari_aspect_warriors_avatar_candidates(require_not_shot=True)
        else:
            candidates = self._aeldari_aspect_warriors_avatar_candidates(require_not_fought=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: WARRIOR FOCUS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: WARRIOR FOCUS: invalid target")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        exp = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr["aeldari_warrior_focus_active"] = True
        sr["aeldari_warrior_focus_expires_phase"] = exp
        sr["aeldari_warrior_focus_source"] = str(getattr(stratagem, "name", "WARRIOR FOCUS") or "WARRIOR FOCUS")
        if owner:
            sr["aeldari_warrior_focus_owner"] = owner
        if turn:
            sr["aeldari_warrior_focus_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_aspect_host_preternatural_precision(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PRETERNATURAL PRECISION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: PRETERNATURAL PRECISION: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_aspect_warriors_candidates(require_not_shot=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PRETERNATURAL PRECISION: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: PRETERNATURAL PRECISION: target must be ASPECT WARRIORS and not yet selected to shoot")
            return False

        requested = context.get("selected_abilities")
        if requested is None:
            requested = context.get("selected_keywords")
        if requested is None:
            requested = context.get("keywords")
        if isinstance(requested, str):
            requested_list = [requested]
        elif isinstance(requested, (list, tuple, set)):
            requested_list = list(requested)
        else:
            requested_list = []
        selected = [self._aeldari_aspect_precision_choice(item) for item in requested_list]
        selected = [item for item in selected if item]
        deduped: List[str] = []
        seen: set[str] = set()
        for item in selected:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        selected = deduped

        allowed = {"IGNORES COVER", "LETHAL HITS", "SUSTAINED HITS 1"}
        if any(item not in allowed for item in selected):
            logger.error("ERROR: PRETERNATURAL PRECISION: invalid keyword selection")
            return False
        spend_token = bool(context.get("spend_aspect_shrine_token", False))
        if (not spend_token) and len(selected) > 1:
            spend_token = True
        token_spent = False
        if spend_token:
            spend_fn = getattr(target_root, "spend_aspect_shrine_token", None)
            if not callable(spend_fn) or not bool(spend_fn(1)):
                logger.error("ERROR: PRETERNATURAL PRECISION: cannot remove Aspect Shrine token")
                return False
            token_spent = True
        max_picks = 2 if token_spent else 1
        if len(selected) > max_picks:
            logger.error("ERROR: PRETERNATURAL PRECISION: too many keyword selections")
            return False
        if not selected:
            defaults = ["LETHAL HITS", "SUSTAINED HITS 1", "IGNORES COVER"]
            selected = defaults[:max_picks]

        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            if token_spent:
                used = int(getattr(target_root, "_aspect_shrine_tokens_used", 0) or 0)
                if used > 0:
                    target_root._aspect_shrine_tokens_used = used - 1
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_preternatural_precision_active"] = True
        sr["aeldari_preternatural_precision_expires_phase"] = "SHOOTING_PHASE"
        sr["aeldari_preternatural_precision_source"] = str(
            getattr(stratagem, "name", "PRETERNATURAL PRECISION") or "PRETERNATURAL PRECISION"
        )
        sr["aeldari_preternatural_precision_keywords"] = list(selected)
        sr["aeldari_preternatural_precision_token_spent"] = bool(token_spent)
        if owner:
            sr["aeldari_preternatural_precision_owner"] = owner
        if turn:
            sr["aeldari_preternatural_precision_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_aspect_host_doom_inescapable(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: DOOM INESCAPABLE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: DOOM INESCAPABLE: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_avatar_candidates(require_not_shot=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: DOOM INESCAPABLE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: DOOM INESCAPABLE: target must be AVATAR OF KHAINE model")
            return False

        target_model = context.get("model") or context.get("target_model")
        if target_model is None:
            try:
                models = list(target_root.get_attached_unit_models() or [])
            except (AttributeError, TypeError, ValueError):
                models = list(getattr(target_root, "models", []) or [])
            for model in models:
                if bool(getattr(model, "is_alive", False)):
                    target_model = model
                    break
        if target_model is None:
            logger.error("ERROR: DOOM INESCAPABLE: missing target model")
            return False

        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_doom_inescapable_active"] = True
        sr["aeldari_doom_inescapable_expires_phase"] = "SHOOTING_PHASE"
        sr["aeldari_doom_inescapable_source"] = str(getattr(stratagem, "name", "DOOM INESCAPABLE") or "DOOM INESCAPABLE")
        sr["aeldari_doom_inescapable_weapon_range_overrides"] = {"WAILING DOOM": 18}
        if owner:
            sr["aeldari_doom_inescapable_owner"] = owner
        if turn:
            sr["aeldari_doom_inescapable_turn"] = turn
        target_root.special_rules = sr

        set_damage = getattr(target_model, "set_temporary_weapon_damage_override", None)
        if callable(set_damage):
            set_damage(
                key="aeldari_doom_inescapable",
                weapon_name="Wailing Doom",
                damage_value=8,
                source=stratagem.name,
                expires_phase="SHOOTING_PHASE",
            )
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_aspect_host_to_their_final_breath(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: TO THEIR FINAL BREATH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_aspect_warriors_avatar_candidates(require_not_fought=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: TO THEIR FINAL BREATH: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: TO THEIR FINAL BREATH: invalid target")
            return False
        targets_window = list(context.get("target_units") or [])
        if targets_window:
            target_roots = [self._aeldari_root(item) for item in targets_window]
            if target_root not in target_roots:
                logger.error("ERROR: TO THEIR FINAL BREATH: unit was not selected as a target")
                return False

        spend_token = bool(context.get("spend_aspect_shrine_token", False))
        token_spent = False
        if spend_token:
            spend_fn = getattr(target_root, "spend_aspect_shrine_token", None)
            if not callable(spend_fn) or not bool(spend_fn(1)):
                logger.error("ERROR: TO THEIR FINAL BREATH: cannot remove Aspect Shrine token")
                return False
            token_spent = True
        threshold = 3 if token_spent else 4

        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=context.get("attacking_unit"),
        ):
            if token_spent:
                used = int(getattr(target_root, "_aspect_shrine_tokens_used", 0) or 0)
                if used > 0:
                    target_root._aspect_shrine_tokens_used = used - 1
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_to_their_final_breath_active"] = True
        sr["aeldari_to_their_final_breath_expires_phase"] = "FIGHT_PHASE"
        sr["aeldari_to_their_final_breath_source"] = str(
            getattr(stratagem, "name", "TO THEIR FINAL BREATH") or "TO THEIR FINAL BREATH"
        )
        sr["aeldari_to_their_final_breath_threshold"] = int(threshold)
        sr["aeldari_to_their_final_breath_token_spent"] = bool(token_spent)
        if owner:
            sr["aeldari_to_their_final_breath_owner"] = owner
        if turn:
            sr["aeldari_to_their_final_breath_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_clear_melee_fight_on_death_cache(target_root)
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_aspect_host_khaines_vengeance(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: KHAINE'S VENGEANCE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: KHAINE'S VENGEANCE: not opponent's turn")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key and action_key not in ("fall back", "fallback"):
            logger.error("ERROR: KHAINE'S VENGEANCE: wrong trigger")
            return False
        enemy_unit = context.get("enemy_unit") or context.get("attacking_unit")
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            logger.error("ERROR: KHAINE'S VENGEANCE: missing enemy unit")
            return False
        try:
            if enemy_root.get_parent_army().player is self.player:
                logger.error("ERROR: KHAINE'S VENGEANCE: enemy unit belongs to your army")
                return False
        except (AttributeError, TypeError, ValueError):
            return False
        if bool(getattr(enemy_root, "has_any_keyword", lambda _k: False)("MONSTER")):
            logger.error("ERROR: KHAINE'S VENGEANCE: enemy MONSTER units are ineligible")
            return False
        if bool(getattr(enemy_root, "has_any_keyword", lambda _k: False)("VEHICLE")):
            logger.error("ERROR: KHAINE'S VENGEANCE: enemy VEHICLE units are ineligible")
            return False
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        candidates: List[Any] = []
        for candidate in self._aeldari_aspect_warriors_avatar_candidates(require_on_battlefield=True):
            try:
                if game_map.is_within_engagement_range(candidate, enemy_root):
                    candidates.append(candidate)
            except (AttributeError, TypeError, ValueError):
                continue
        if not candidates:
            logger.error("ERROR: KHAINE'S VENGEANCE: no eligible friendly unit in Engagement Range")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: KHAINE'S VENGEANCE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: KHAINE'S VENGEANCE: selected unit is not in Engagement Range of that enemy")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        is_battle_shocked = False
        try:
            shock_fn = getattr(enemy_root, "is_battle_shocked", None)
            if callable(shock_fn):
                is_battle_shocked = bool(shock_fn())
        except (AttributeError, TypeError, ValueError):
            is_battle_shocked = False
        if not is_battle_shocked:
            is_battle_shocked = bool(getattr(getattr(enemy_root, "round_state", None), "battle_shocked", False))
        roll_modifier = -1 if is_battle_shocked else 0
        test_fn = getattr(enemy_root, "take_desperate_escape_test", None)
        if callable(test_fn):
            test_fn(
                game_map=game_map,
                roll_modifier=int(roll_modifier),
                reason=str(getattr(stratagem, "name", "KHAINE'S VENGEANCE")),
            )
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_aspect_host_skyborne_sanctuary(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SKYBORNE SANCTUARY: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            candidates = list(context.get("candidates") or [])
            candidates = [self._aeldari_root(c) for c in candidates]
            candidates = [c for c in candidates if c is not None]
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: SKYBORNE SANCTUARY: missing target unit")
                return False
        if not self._aeldari_is_alive(target_root):
            return False
        if not bool(getattr(target_root, "deployed", False)):
            return False
        if self._aeldari_in_reserves(target_root):
            return False
        if bool(getattr(target_root, "is_embarked", False)) or bool(getattr(target_root, "embarked_in", None)):
            return False
        if not self._aeldari_is_targetable(target_root):
            return False
        if not bool(getattr(target_root, "has_any_keyword", lambda _k: False)("ASURYANI")):
            return False
        try:
            for enemy in list(game_map.get_enemy_units(target_root) or []):
                if not getattr(enemy, "is_alive", lambda: True)():
                    continue
                if not getattr(enemy, "deployed", True):
                    continue
                if game_map.is_within_engagement_range(target_root, enemy):
                    logger.error("ERROR: SKYBORNE SANCTUARY: target unit is in Engagement Range")
                    return False
        except (AttributeError, TypeError, ValueError):
            return False

        transport_unit = context.get("transport_unit") or context.get("transport")
        if transport_unit is None:
            mapping = context.get("transport_candidates_by_unit") or {}
            if isinstance(mapping, dict):
                options = list(mapping.get(target_root) or [])
                if len(options) == 1:
                    transport_unit = options[0]
        if transport_unit is None:
            transports = list(getattr(self, "_skyborne_transport_candidates", lambda _u: [])(target_root) or [])
            if len(transports) == 1:
                transport_unit = transports[0]
        if transport_unit is None:
            logger.error("ERROR: SKYBORNE SANCTUARY: missing target transport")
            return False
        if not self._aeldari_is_alive(transport_unit):
            return False
        if not bool(getattr(transport_unit, "deployed", False)):
            return False
        if not bool(getattr(transport_unit, "is_transport", False)):
            return False
        can_transport = getattr(transport_unit, "can_transport", None)
        if not callable(can_transport) or not bool(can_transport(target_root)):
            return False
        try:
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
            if not unit_wholly_within_range_of_unit(transport_unit, target_root, 6.0, use_attached_aggregate=True):
                return False
        except (AttributeError, TypeError, ValueError):
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        embark_fn = getattr(transport_unit, "add_passenger", None)
        if not callable(embark_fn):
            return False
        if not bool(embark_fn(target_root, game_map=game_map)):
            logger.error("ERROR: SKYBORNE SANCTUARY: embark failed")
            return False
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True
