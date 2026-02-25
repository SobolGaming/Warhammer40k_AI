from __future__ import annotations

from typing import Any, List

from ..utility import dice as dice_module
from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
from ..utility.entity_ids import get_entity_id


class ChaosDaemonsStratagemMixin:
    @staticmethod
    def _chaos_daemons_normalize_stratagem_name(name: str) -> str:
        text = str(name or "")
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
        return text.strip().upper()

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

    def _is_blood_legion_detachment(self) -> bool:
        if self.player is None:
            return False
        army = self.player.get_army()
        if army is None:
            return False
        mgr = getattr(army, "chaos_daemons_detachments", None)
        if mgr is not None and hasattr(mgr, "is_blood_legion_detachment"):
            return bool(mgr.is_blood_legion_detachment())
        det = " ".join(str(getattr(army, "detachment_type", "") or "").lower().split())
        return det == "blood legion"

    def _is_shadow_legion_detachment(self) -> bool:
        if self.player is None:
            return False
        army = self.player.get_army()
        if army is None:
            return False
        mgr = getattr(army, "chaos_daemons_detachments", None)
        if mgr is not None and hasattr(mgr, "is_shadow_legion_detachment"):
            return bool(mgr.is_shadow_legion_detachment())
        det = " ".join(str(getattr(army, "detachment_type", "") or "").lower().split())
        return det == "shadow legion"

    def _is_legion_of_excess_detachment(self) -> bool:
        if self.player is None:
            return False
        army = self.player.get_army()
        if army is None:
            return False
        mgr = getattr(army, "chaos_daemons_detachments", None)
        if mgr is not None and hasattr(mgr, "is_legion_of_excess_detachment"):
            return bool(mgr.is_legion_of_excess_detachment())
        det = " ".join(str(getattr(army, "detachment_type", "") or "").lower().split())
        return det == "legion of excess"

    def _is_khorne_legiones_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        if not self._is_legiones_daemonica_unit(root):
            return False
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if not callable(has_any_keyword):
            return False
        return bool(has_any_keyword("KHORNE"))

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

    def _is_slaanesh_legiones_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        if not self._is_legiones_daemonica_unit(root):
            return False
        try:
            return bool(root.has_any_keyword("SLAANESH"))
        except Exception:
            return False

    def _is_shadow_legion_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if not callable(has_any_keyword):
            return False
        return bool(has_any_keyword("SHADOW LEGION"))

    def _is_shadow_legion_heretic_astartes_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if not callable(has_any_keyword):
            return False
        return bool(has_any_keyword("HERETIC ASTARTES") and has_any_keyword("SHADOW LEGION"))

    def _is_shadow_legion_legiones_daemonica_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        if not self._is_legiones_daemonica_unit(root):
            return False
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if not callable(has_any_keyword):
            return False
        return bool(has_any_keyword("SHADOW LEGION"))

    @staticmethod
    def _shadow_legion_unit_selected_to_fight_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        if round_state is None:
            return False
        return bool(getattr(round_state, "fought_this_phase", False))

    def _shadow_legion_battlefield_unit_candidates(
        self,
        *,
        require_heretic_astartes: bool = False,
        require_legiones_daemonica: bool = False,
        require_not_engaged: bool = False,
        require_not_fought: bool = False,
    ) -> List[Any]:
        if self.player is None:
            return []
        if not self._is_shadow_legion_detachment():
            return []
        army = self.player.get_army()
        if army is None:
            return []
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if require_not_engaged and game_map is None:
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
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(root, "is_alive", True)):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            in_reserves = getattr(root, "is_in_reserves", None)
            if callable(in_reserves) and bool(in_reserves()):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_shadow_legion_unit(root):
                continue
            if require_heretic_astartes and not self._is_shadow_legion_heretic_astartes_unit(root):
                continue
            if require_legiones_daemonica and not self._is_shadow_legion_legiones_daemonica_unit(root):
                continue
            if require_not_fought and self._shadow_legion_unit_selected_to_fight_this_phase(root):
                continue
            if require_not_engaged and self._blood_legion_unit_is_engaged(root):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _shadow_legion_channelled_wrath_candidates(self) -> List[Any]:
        return self._shadow_legion_battlefield_unit_candidates(require_not_fought=True)

    def _shadow_legion_binding_shadow_heretic_candidates(self) -> List[Any]:
        return self._shadow_legion_battlefield_unit_candidates(
            require_heretic_astartes=True,
            require_not_engaged=True,
        )

    def _shadow_legion_binding_shadow_daemon_candidates(self) -> List[Any]:
        return self._shadow_legion_battlefield_unit_candidates(
            require_legiones_daemonica=True,
            require_not_engaged=True,
        )

    def _shadow_legion_binding_shadow_candidate_union(self) -> List[Any]:
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(self._shadow_legion_binding_shadow_heretic_candidates()) + list(
            self._shadow_legion_binding_shadow_daemon_candidates()
        ):
            uid = self._chaos_daemons_sort_key(unit)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            candidates.append(unit)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _shadow_legion_arrived_from_reserves_candidates(
        self,
        *,
        require_heretic_astartes: bool = False,
        require_legiones_daemonica: bool = False,
    ) -> List[Any]:
        candidates = self._shadow_legion_battlefield_unit_candidates(
            require_heretic_astartes=require_heretic_astartes,
            require_legiones_daemonica=require_legiones_daemonica,
        )
        arrived: List[Any] = []
        for unit in list(candidates or []):
            if bool(getattr(unit, "arrived_from_reserves_this_turn", False)):
                arrived.append(unit)
        arrived.sort(key=self._chaos_daemons_sort_key)
        return arrived

    def _shadow_legion_encroaching_darkness_heretic_candidates(self) -> List[Any]:
        return self._shadow_legion_arrived_from_reserves_candidates(require_heretic_astartes=True)

    def _shadow_legion_encroaching_darkness_daemon_candidates(self) -> List[Any]:
        return self._shadow_legion_arrived_from_reserves_candidates(require_legiones_daemonica=True)

    def _shadow_legion_encroaching_darkness_candidate_union(self) -> List[Any]:
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(self._shadow_legion_encroaching_darkness_heretic_candidates()) + list(
            self._shadow_legion_encroaching_darkness_daemon_candidates()
        ):
            uid = self._chaos_daemons_sort_key(unit)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            candidates.append(unit)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _shadow_legion_shade_path_candidates(self, target_units: List[Any]) -> List[Any]:
        target_ids: set[str] = set()
        for entry in list(target_units or []):
            root = self._chaos_daemons_root(entry)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
            if uid:
                target_ids.add(uid)
        if not target_ids:
            return []
        candidates: List[Any] = []
        for unit in self._shadow_legion_battlefield_unit_candidates():
            uid = self._chaos_daemons_sort_key(unit)
            if uid and uid in target_ids:
                candidates.append(unit)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _shadow_legion_spiteful_demise_enemy_candidates(
        self,
        *,
        destroyed_unit: Any,
        last_model: Any = None,
        destroyed_model_base: Any = None,
    ) -> List[Any]:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return []
        source_base = destroyed_model_base
        if source_base is None and last_model is not None:
            source_base = getattr(last_model, "model_base", None)
        if source_base is None:
            return []
        source_root = self._chaos_daemons_root(destroyed_unit)
        if source_root is None:
            return []
        source_army = getattr(source_root, "get_parent_army", lambda: None)()
        source_player = getattr(source_army, "player", None) if source_army is not None else None
        if source_player is None:
            return []

        candidates: List[Any] = []
        seen: set[str] = set()
        for enemy in list(getattr(game_map, "units", []) or []):
            enemy_root = self._chaos_daemons_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._chaos_daemons_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            enemy_army = getattr(enemy_root, "get_parent_army", lambda: None)()
            if enemy_army is None or getattr(enemy_army, "player", None) is source_player:
                continue
            is_alive = getattr(enemy_root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(enemy_root, "is_alive", True)):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            in_reserves = getattr(enemy_root, "is_in_reserves", None)
            if callable(in_reserves) and bool(in_reserves()):
                continue
            has_engagement = False
            for enemy_model in list(getattr(enemy_root, "models", []) or []):
                if enemy_model is None:
                    continue
                enemy_alive = getattr(enemy_model, "is_alive", None)
                if callable(enemy_alive):
                    if not bool(enemy_alive()):
                        continue
                elif enemy_alive is not None and not bool(enemy_alive):
                    continue
                enemy_base = getattr(enemy_model, "model_base", None)
                if enemy_base is None:
                    continue
                try:
                    horizontal = float(horizontal_distance_between_bases_2d(source_base, enemy_base))
                    vertical = float(vertical_distance_between_bases(source_base, enemy_base))
                except (AttributeError, TypeError, ValueError):
                    continue
                if horizontal <= float(ENGAGEMENT_RANGE_HORIZONTAL) + 1e-6 and vertical <= float(ENGAGEMENT_RANGE_VERTICAL) + 1e-6:
                    has_engagement = True
                    break
            if has_engagement:
                candidates.append(enemy_root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _queue_shadow_legion_charge_declared_reactions(
        self,
        *,
        charging_unit: Any,
        target_units: List[Any],
    ) -> None:
        if self.player is None or self.game is None:
            return
        if not self._is_shadow_legion_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "charge phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        charging_root = self._chaos_daemons_root(charging_unit)
        if charging_root is None:
            return
        enemy_army = getattr(charging_root, "get_parent_army", lambda: None)()
        if enemy_army is None or getattr(enemy_army, "player", None) is self.player:
            return
        is_alive = getattr(charging_root, "is_alive", None)
        if callable(is_alive):
            if not bool(is_alive()):
                return
        elif not bool(getattr(charging_root, "is_alive", True)):
            return
        if not bool(getattr(charging_root, "deployed", True)):
            return
        stratagem = self.get_by_name("SHADE PATH")
        if stratagem is None:
            return
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        if int(getattr(self.player, "command_points", 0) or 0) < cp_cost:
            return
        if (stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        resolved_targets: List[Any] = []
        seen_targets: set[str] = set()
        for target in list(target_units or []):
            root = self._chaos_daemons_root(target)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
            if uid and uid in seen_targets:
                continue
            if uid:
                seen_targets.add(uid)
            resolved_targets.append(root)
        candidates = self._shadow_legion_shade_path_candidates(resolved_targets)
        if not candidates:
            return
        charging_id = self._chaos_daemons_sort_key(charging_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "charge_declared":
                continue
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != "SHADE PATH":
                continue
            pending_charging_id = self._chaos_daemons_sort_key(self._chaos_daemons_root(reaction.get("charging_unit")))
            if pending_charging_id and pending_charging_id == charging_id:
                return
        payload = {
            "event": "charge_declared",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": cp_cost,
            "charging_unit": charging_root,
            "enemy_unit": charging_root,
            "target_units": resolved_targets,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_shadow_legion_unit_destroyed_reactions(
        self,
        *,
        unit: Any,
        last_model: Any = None,
        destroyed_by_unit: Any = None,
    ) -> None:
        if self.player is None or self.game is None:
            return
        if not self._is_shadow_legion_detachment():
            return
        root = self._chaos_daemons_root(unit)
        if root is None:
            return
        army = getattr(root, "get_parent_army", lambda: None)()
        if army is None or getattr(army, "player", None) is not self.player:
            return
        if not self._is_shadow_legion_unit(root):
            return
        stratagem = self.get_by_name("SPITEFUL DEMISE")
        if stratagem is None:
            return
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        if int(getattr(self.player, "command_points", 0) or 0) < cp_cost:
            return
        if (stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        destroyed_model_base = getattr(last_model, "model_base", None) if last_model is not None else None
        enemy_candidates = self._shadow_legion_spiteful_demise_enemy_candidates(
            destroyed_unit=root,
            last_model=last_model,
            destroyed_model_base=destroyed_model_base,
        )
        if not enemy_candidates:
            return
        root_id = self._chaos_daemons_sort_key(root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_destroyed":
                continue
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != "SPITEFUL DEMISE":
                continue
            pending_id = self._chaos_daemons_sort_key(self._chaos_daemons_root(reaction.get("unit")))
            if pending_id and pending_id == root_id:
                return
        payload = {
            "event": "unit_destroyed",
            "phase_name": str(getattr(self, "_current_phase_name", "") or ""),
            "stratagem": stratagem.name,
            "cp_cost": cp_cost,
            "unit": root,
            "target_unit": root,
            "destroyed_unit": root,
            "last_model": last_model,
            "destroyed_model_base": destroyed_model_base,
            "destroyed_by_unit": destroyed_by_unit,
            "enemy_unit": destroyed_by_unit,
            "enemy_candidates": enemy_candidates,
        }
        self._queue_reaction(payload)

    def _queue_shadow_legion_binding_shadow_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if self.player is None or self.game is None:
            return
        if not self._is_shadow_legion_detachment():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        if player is self.player:
            return
        stratagem = self.get_by_name("BINDING SHADOW")
        if stratagem is None:
            return
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        if int(getattr(self.player, "command_points", 0) or 0) < cp_cost:
            return
        if (stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        heretic_candidates = self._shadow_legion_binding_shadow_heretic_candidates()
        daemon_candidates = self._shadow_legion_binding_shadow_daemon_candidates()
        if not heretic_candidates and not daemon_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_end":
                continue
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != "BINDING SHADOW":
                continue
            if str(reaction.get("phase", "") or "").strip().lower() != "fight phase":
                continue
            return
        self._queue_reaction(
            {
                "event": "phase_end",
                "phase": "Fight phase",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": cp_cost,
                "candidates": self._shadow_legion_binding_shadow_candidate_union(),
                "heretic_candidates": heretic_candidates,
                "daemon_candidates": daemon_candidates,
                "max_units": 2,
                "max_heretic_units": 1,
                "max_daemon_units": 1,
            },
            use_timer=False,
        )

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

    def _legion_of_excess_slaanesh_battlefield_unit_candidates(self, *, require_monster: bool = False) -> List[Any]:
        if self.player is None:
            return []
        if not self._is_legion_of_excess_detachment():
            return []
        army = self.player.get_army()
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
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(root, "is_alive", True)):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            in_reserves = getattr(root, "is_in_reserves", None)
            if callable(in_reserves) and bool(in_reserves()):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_slaanesh_legiones_unit(root):
                continue
            if require_monster and not bool(getattr(root, "has_any_keyword", lambda *_: False)("MONSTER")):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _legion_of_excess_cavalcade_enemy_candidates(self, source_unit: Any) -> List[Any]:
        source_root = self._chaos_daemons_root(source_unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if source_root is None or game_map is None:
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        candidates: List[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy_units(source_root) or []):
            enemy_root = self._chaos_daemons_root(enemy)
            if enemy_root is None:
                continue
            uid = self._chaos_daemons_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            is_alive = getattr(enemy_root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(enemy_root, "is_alive", True)):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if not bool(game_map.is_within_engagement_range(source_root, enemy_root)):
                continue
            candidates.append(enemy_root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _legion_of_excess_models_within_engagement_count(self, source_unit: Any, enemy_unit: Any) -> int:
        source_root = self._chaos_daemons_root(source_unit)
        enemy_root = self._chaos_daemons_root(enemy_unit)
        if source_root is None or enemy_root is None:
            return 0
        source_models = list(getattr(source_root, "get_attached_unit_models", lambda: [])() or [])
        if not source_models:
            source_models = list(getattr(source_root, "models", []) or [])
        enemy_models = list(getattr(enemy_root, "get_attached_unit_models", lambda: [])() or [])
        if not enemy_models:
            enemy_models = list(getattr(enemy_root, "models", []) or [])
        engaged_count = 0
        for source_model in source_models:
            if source_model is None:
                continue
            source_alive = getattr(source_model, "is_alive", None)
            if callable(source_alive):
                if not bool(source_alive()):
                    continue
            elif source_alive is not None and not bool(source_alive):
                continue
            source_base = getattr(source_model, "model_base", None)
            if source_base is None:
                continue
            in_engagement = False
            for enemy_model in enemy_models:
                if enemy_model is None:
                    continue
                enemy_alive = getattr(enemy_model, "is_alive", None)
                if callable(enemy_alive):
                    if not bool(enemy_alive()):
                        continue
                elif enemy_alive is not None and not bool(enemy_alive):
                    continue
                enemy_base = getattr(enemy_model, "model_base", None)
                if enemy_base is None:
                    continue
                try:
                    horizontal = float(horizontal_distance_between_bases_2d(source_base, enemy_base))
                    vertical = float(vertical_distance_between_bases(source_base, enemy_base))
                except (AttributeError, TypeError, ValueError):
                    continue
                if horizontal <= float(ENGAGEMENT_RANGE_HORIZONTAL) + 1e-6 and vertical <= float(ENGAGEMENT_RANGE_VERTICAL) + 1e-6:
                    in_engagement = True
                    break
            if in_engagement:
                engaged_count += 1
        return int(engaged_count)

    def _legion_of_excess_thieves_of_pain_source_candidates(self) -> List[Any]:
        candidates: List[Any] = []
        for root in list(self._legion_of_excess_slaanesh_battlefield_unit_candidates() or []):
            has_any_keyword = getattr(root, "has_any_keyword", None)
            if not callable(has_any_keyword):
                continue
            if bool(has_any_keyword("MONSTER")):
                continue
            if bool(has_any_keyword("VEHICLE")):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _legion_of_excess_thieves_of_pain_redirect_candidates(self, source_unit: Any) -> List[Any]:
        source_root = self._chaos_daemons_root(source_unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if source_root is None or game_map is None:
            return []
        source_id = self._chaos_daemons_sort_key(source_root)
        candidates: List[Any] = []
        seen: set[str] = set()
        for candidate in list(self._legion_of_excess_slaanesh_battlefield_unit_candidates() or []):
            candidate_root = self._chaos_daemons_root(candidate)
            if candidate_root is None:
                continue
            candidate_id = self._chaos_daemons_sort_key(candidate_root)
            if candidate_id and candidate_id in seen:
                continue
            if candidate_id:
                seen.add(candidate_id)
            if candidate_id and source_id and candidate_id == source_id:
                continue
            try:
                distance = float(game_map.get_distance_between_units(source_root, candidate_root))
            except (AttributeError, TypeError, ValueError):
                continue
            if distance > 9.0 + 1e-6:
                continue
            if not self._chaos_daemons_source_can_see_unit(source_root, candidate_root):
                continue
            candidates.append(candidate_root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _legion_of_excess_sensory_excruciation_targets(self) -> List[Any]:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return []
        targets: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(game_map, "units", []) or []):
            root = self._chaos_daemons_root(unit)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(root, "is_alive", True)):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            in_reserves = getattr(root, "is_in_reserves", None)
            if callable(in_reserves) and bool(in_reserves()):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if not self._unit_within_shadow_of_chaos(root):
                continue
            targets.append(root)
        targets.sort(key=self._chaos_daemons_sort_key)
        return targets

    def _blood_legion_khorne_battlefield_unit_candidates(self) -> List[Any]:
        if self.player is None:
            return []
        if not self._is_blood_legion_detachment():
            return []
        army = self.player.get_army()
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
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(root, "is_alive", True)):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            in_reserves = getattr(root, "is_in_reserves", None)
            if callable(in_reserves) and bool(in_reserves()):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_khorne_legiones_unit(root):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _blood_legion_blood_begets_skulls_candidates(self) -> List[Any]:
        candidates: List[Any] = []
        for root in self._blood_legion_khorne_battlefield_unit_candidates():
            if bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _blood_legion_fools_flight_candidates(self, enemy_unit: Any) -> List[Any]:
        if self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        enemy_root = self._chaos_daemons_root(enemy_unit)
        if enemy_root is None:
            return []
        enemy_army = getattr(enemy_root, "get_parent_army", lambda: None)()
        if enemy_army is None or getattr(enemy_army, "player", None) is self.player:
            return []
        is_alive = getattr(enemy_root, "is_alive", None)
        if callable(is_alive):
            if not bool(is_alive()):
                return []
        elif not bool(getattr(enemy_root, "is_alive", True)):
            return []
        if not bool(getattr(enemy_root, "deployed", False)):
            return []
        candidates: List[Any] = []
        for root in self._blood_legion_khorne_battlefield_unit_candidates():
            try:
                distance = float(game_map.get_distance_between_units(root, enemy_root))
            except (AttributeError, TypeError, ValueError):
                continue
            if distance > 6.0:
                continue
            can_charge = getattr(root, "can_declare_charge_against", None)
            if not callable(can_charge):
                continue
            if not bool(can_charge(enemy_root, self.game, out_of_turn=True)):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _blood_legion_unit_is_engaged(self, unit: Any) -> bool:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        root = self._chaos_daemons_root(unit)
        if game_map is None or root is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._chaos_daemons_root(enemy)
            if enemy_root is None:
                continue
            is_alive = getattr(enemy_root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(enemy_root, "is_alive", True)):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if bool(game_map.is_within_engagement_range(root, enemy_root)):
                return True
        return False

    def _blood_legion_enemy_engaged_with_friendly(self, enemy_unit: Any) -> bool:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        enemy_root = self._chaos_daemons_root(enemy_unit)
        if game_map is None or enemy_root is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return False
        for other in list(get_enemy_units(enemy_root) or []):
            other_root = self._chaos_daemons_root(other)
            if other_root is None:
                continue
            parent_army = getattr(other_root, "get_parent_army", lambda: None)()
            if parent_army is None or getattr(parent_army, "player", None) is not self.player:
                continue
            is_alive = getattr(other_root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(other_root, "is_alive", True)):
                continue
            if not bool(getattr(other_root, "deployed", False)):
                continue
            if bool(game_map.is_within_engagement_range(enemy_root, other_root)):
                return True
        return False

    def _chaos_daemons_source_can_see_unit(self, source_unit: Any, target_unit: Any) -> bool:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        source_root = self._chaos_daemons_root(source_unit)
        target_root = self._chaos_daemons_root(target_unit)
        if game_map is None or source_root is None or target_root is None:
            return False
        source_models = list(getattr(source_root, "get_attached_unit_models", lambda: [])() or [])
        can_see_unit = getattr(game, "_model_can_see_unit", None)
        if callable(can_see_unit):
            for model in source_models:
                is_alive = getattr(model, "is_alive", True)
                if callable(is_alive):
                    if not bool(is_alive()):
                        continue
                elif not bool(is_alive):
                    continue
                if bool(can_see_unit(model, target_root, game_map=game_map)):
                    return True
            return False
        has_los = getattr(source_root, "_has_line_of_sight_to_target", None)
        if callable(has_los):
            for model in source_models:
                is_alive = getattr(model, "is_alive", True)
                if callable(is_alive):
                    if not bool(is_alive()):
                        continue
                elif not bool(is_alive):
                    continue
                if bool(has_los(model, target_root, game_map)):
                    return True
            return False
        can_model_see_model = getattr(game_map, "can_model_see_model", None)
        if callable(can_model_see_model):
            target_models = list(getattr(target_root, "get_alive_models", lambda: [])() or [])
            for source_model in source_models:
                source_alive = getattr(source_model, "is_alive", True)
                if callable(source_alive):
                    if not bool(source_alive()):
                        continue
                elif not bool(source_alive):
                    continue
                for target_model in target_models:
                    target_alive = getattr(target_model, "is_alive", True)
                    if callable(target_alive):
                        if not bool(target_alive()):
                            continue
                    elif not bool(target_alive):
                        continue
                    if bool(can_model_see_model(source_model, target_model)):
                        return True
            return False
        return True

    def _blood_legion_source_can_see_enemy(self, source_unit: Any, enemy_unit: Any) -> bool:
        return self._chaos_daemons_source_can_see_unit(source_unit, enemy_unit)

    def _is_khorne_legiones_infantry_or_mounted_unit(self, unit: Any) -> bool:
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        if not self._is_khorne_legiones_unit(root):
            return False
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if not callable(has_any_keyword):
            return False
        return bool(has_any_keyword("INFANTRY") or has_any_keyword("MOUNTED"))

    def _blood_legion_skulls_beget_blood_source_candidates(self) -> List[Any]:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return []
        candidates: List[Any] = []
        for root in self._blood_legion_khorne_battlefield_unit_candidates():
            if not self._is_khorne_legiones_infantry_or_mounted_unit(root):
                continue
            if bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            if self._blood_legion_unit_is_engaged(root):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _blood_legion_skulls_beget_blood_enemy_candidates(self, source_unit: Any) -> List[Any]:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        source_root = self._chaos_daemons_root(source_unit)
        if game_map is None or source_root is None:
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        candidates: List[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy_units(source_root) or []):
            enemy_root = self._chaos_daemons_root(enemy)
            if enemy_root is None:
                continue
            uid = self._chaos_daemons_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            is_alive = getattr(enemy_root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(enemy_root, "is_alive", True)):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if self._blood_legion_enemy_engaged_with_friendly(enemy_root):
                continue
            distance = float(game_map.get_distance_between_units(source_root, enemy_root))
            if distance > 8.0:
                continue
            if not self._blood_legion_source_can_see_enemy(source_root, enemy_root):
                continue
            candidates.append(enemy_root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _blood_legion_sheathed_in_brass_candidates(self, *, attacking_unit: Any, target_units: List[Any]) -> List[Any]:
        attacker_root = self._chaos_daemons_root(attacking_unit)
        if attacker_root is None:
            return []
        attacker_army = getattr(attacker_root, "get_parent_army", lambda: None)()
        if attacker_army is None or getattr(attacker_army, "player", None) is self.player:
            return []
        valid_ids = {self._chaos_daemons_sort_key(candidate) for candidate in self._blood_legion_khorne_battlefield_unit_candidates()}
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._chaos_daemons_root(unit)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if uid not in valid_ids:
                continue
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(root, "is_alive", True)):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            parent_army = getattr(root, "get_parent_army", lambda: None)()
            if parent_army is None or getattr(parent_army, "player", None) is not self.player:
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _blood_legion_wrath_undeniable_candidates(self, *, attacking_unit: Any, target_units: List[Any]) -> List[Any]:
        attacker_root = self._chaos_daemons_root(attacking_unit)
        if attacker_root is None:
            return []
        attacker_army = getattr(attacker_root, "get_parent_army", lambda: None)()
        if attacker_army is None or getattr(attacker_army, "player", None) is self.player:
            return []
        valid_ids = {self._chaos_daemons_sort_key(candidate) for candidate in self._blood_legion_khorne_battlefield_unit_candidates()}
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._chaos_daemons_root(unit)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if uid not in valid_ids:
                continue
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(root, "is_alive", True)):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            parent_army = getattr(root, "get_parent_army", lambda: None)()
            if parent_army is None or getattr(parent_army, "player", None) is not self.player:
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _queue_blood_legion_shooting_target_reactions(self, *, attacking_unit: Any, target_units: List[Any]) -> None:
        if self.player is None or self.game is None:
            return
        if not self._is_blood_legion_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("SHEATHED IN BRASS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if (stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._blood_legion_sheathed_in_brass_candidates(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "shooting_targets_selected":
                continue
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != "SHEATHED IN BRASS":
                continue
            if reaction.get("attacking_unit") is attacking_unit:
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_blood_legion_fight_target_reactions(self, *, attacking_unit: Any, target_units: List[Any]) -> None:
        if self.player is None or self.game is None:
            return
        if not self._is_blood_legion_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacker_root = self._chaos_daemons_root(attacking_unit)
        if attacker_root is None:
            return
        attacker_army = getattr(attacker_root, "get_parent_army", lambda: None)()
        if attacker_army is None or getattr(attacker_army, "player", None) is self.player:
            return
        stratagem = self.get_by_name("WRATH UNDENIABLE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if (stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._blood_legion_wrath_undeniable_candidates(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != "WRATH UNDENIABLE":
                continue
            if reaction.get("attacking_unit") is attacking_unit:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_legion_of_excess_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower() != "charge":
            return
        if self.player is None or self.game is None:
            return
        if not self._is_legion_of_excess_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        source_root = self._chaos_daemons_root(unit)
        if source_root is None:
            return
        source_army = getattr(source_root, "get_parent_army", lambda: None)()
        if source_army is None or getattr(source_army, "player", None) is not self.player:
            return
        valid_ids = {
            self._chaos_daemons_sort_key(candidate)
            for candidate in self._legion_of_excess_slaanesh_battlefield_unit_candidates()
        }
        source_id = self._chaos_daemons_sort_key(source_root)
        if source_id not in valid_ids:
            return
        stratagem = self.get_by_name("CAVALCADE OF BLADES")
        if stratagem is None:
            return
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        if int(getattr(self.player, "command_points", 0) or 0) < cp_cost:
            return
        if (stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        enemy_candidates = self._legion_of_excess_cavalcade_enemy_candidates(source_root)
        if not enemy_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != "CAVALCADE OF BLADES":
                continue
            pending_id = self._chaos_daemons_sort_key(self._chaos_daemons_root(reaction.get("unit")))
            if pending_id and pending_id == source_id:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": cp_cost,
            "action": "charge",
            "unit": source_root,
            "target_unit": source_root,
            "candidates": [source_root],
            "enemy_candidates": enemy_candidates,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload)

    def _queue_legion_of_excess_allocation_reactions(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any = None,
        target_model: Any = None,
        phase_name: str = "",
        trigger_event: str = "",
    ) -> None:
        if self.player is None or self.game is None:
            return
        if not self._is_legion_of_excess_detachment():
            return
        event_name = str(trigger_event or "attack_allocated").strip().lower()
        if event_name not in {"attack_allocated", "mortal_wound_allocated"}:
            event_name = "attack_allocated"
        source_root = self._chaos_daemons_root(target_unit)
        if source_root is None:
            return
        source_army = getattr(source_root, "get_parent_army", lambda: None)()
        if source_army is None or getattr(source_army, "player", None) is not self.player:
            return
        valid_source_ids = {
            self._chaos_daemons_sort_key(candidate)
            for candidate in self._legion_of_excess_thieves_of_pain_source_candidates()
        }
        source_id = self._chaos_daemons_sort_key(source_root)
        if source_id not in valid_source_ids:
            return
        stratagem = self.get_by_name("THIEVES OF PAIN")
        if stratagem is None:
            return
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        if int(getattr(self.player, "command_points", 0) or 0) < cp_cost:
            return
        if (stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        redirect_candidates = self._legion_of_excess_thieves_of_pain_redirect_candidates(source_root)
        if not redirect_candidates:
            return
        if not phase_name:
            phase_name = str(getattr(self, "_current_phase_name", "") or "")
        if not phase_name:
            phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
            phase_name = {
                "COMMAND_PHASE": "Command phase",
                "MOVEMENT_PHASE": "Movement phase",
                "SHOOTING_PHASE": "Shooting phase",
                "CHARGE_PHASE": "Charge phase",
                "FIGHT_PHASE": "Fight phase",
            }.get(phase_key, phase_key.title().replace("_", " ")) if phase_key else ""
        if not phase_name:
            phase_name = "Any phase"
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip().lower() != event_name:
                continue
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != "THIEVES OF PAIN":
                continue
            pending_source = self._chaos_daemons_root(reaction.get("target_unit") or reaction.get("unit"))
            if self._chaos_daemons_sort_key(pending_source) == source_id:
                return
        payload = {
            "event": event_name,
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": cp_cost,
            "target_unit": source_root,
            "unit": source_root,
            "attacking_unit": attacker_unit,
            "target_model": target_model,
            "candidates": [source_root],
            "redirect_candidates": redirect_candidates,
            "attack_allocated": bool(event_name == "attack_allocated"),
            "mortal_wound_allocated": bool(event_name == "mortal_wound_allocated"),
        }
        if len(redirect_candidates) == 1:
            payload["redirect_unit"] = redirect_candidates[0]
            payload["selected_unit"] = redirect_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_blood_legion_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower() != "fall_back":
            return
        if self.player is None or self.game is None:
            return
        if not self._is_blood_legion_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        enemy_root = self._chaos_daemons_root(unit)
        if enemy_root is None:
            return
        enemy_army = getattr(enemy_root, "get_parent_army", lambda: None)()
        if enemy_army is None or getattr(enemy_army, "player", None) is self.player:
            return
        stratagem = self.get_by_name("FOOLS' FLIGHT")
        if stratagem is None:
            return
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        if int(getattr(self.player, "command_points", 0) or 0) < cp_cost:
            return
        if (stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._blood_legion_fools_flight_candidates(enemy_root)
        if not candidates:
            return
        enemy_id = self._chaos_daemons_sort_key(enemy_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != "FOOLS' FLIGHT":
                continue
            pending_enemy_id = self._chaos_daemons_sort_key(self._chaos_daemons_root(reaction.get("enemy_unit")))
            if pending_enemy_id and pending_enemy_id == enemy_id:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": cp_cost,
            "enemy_unit": enemy_root,
            "candidates": candidates,
            "action": "fall_back",
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _chaos_daemons_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _use_chaos_daemons_shadow_legion_stratagem(self, stratagem: Any, **kwargs) -> bool | None:
        name_u = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
        if name_u == "SPITEFUL DEMISE":
            return self._use_shadow_legion_spiteful_demise(stratagem, **kwargs)
        if name_u == "SHADE PATH":
            return self._use_shadow_legion_shade_path(stratagem, **kwargs)
        if name_u == "DEATH DENIED":
            return self._use_shadow_legion_death_denied(stratagem, **kwargs)
        if name_u == "ENCROACHING DARKNESS":
            return self._use_shadow_legion_encroaching_darkness(stratagem, **kwargs)
        if name_u == "CHANNELLED WRATH":
            return self._use_shadow_legion_channelled_wrath(stratagem, **kwargs)
        if name_u == "BINDING SHADOW":
            return self._use_shadow_legion_binding_shadow(stratagem, **kwargs)
        return None

    def _resolve_shadow_legion_selected_units(self, **kwargs) -> List[Any]:
        selected = (
            kwargs.get("units")
            or kwargs.get("target_units")
            or kwargs.get("selected_units")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        extras = [kwargs.get("heretic_unit"), kwargs.get("daemon_unit")]
        if selected is None:
            selected = []
        if not isinstance(selected, (list, tuple)):
            selected = [selected]
        selected = [entry for entry in list(selected or []) if entry is not None]
        selected.extend(entry for entry in extras if entry is not None)
        resolved: List[Any] = []
        seen: set[str] = set()
        resolver = getattr(self.game, "_resolve_unit_by_id", None) if self.game is not None else None
        for entry in selected:
            unit = entry
            if isinstance(entry, str) and callable(resolver):
                unit = resolver(entry)
            root = self._chaos_daemons_root(unit)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            resolved.append(root)
        resolved.sort(key=self._chaos_daemons_sort_key)
        return resolved

    @staticmethod
    def _shadow_legion_model_is_character(model: Any) -> bool:
        char_attr = getattr(model, "is_character", None)
        if bool(char_attr() if callable(char_attr) else char_attr):
            return True
        keywords = list(getattr(model, "keywords", []) or [])
        if any(str(keyword or "").strip().upper() == "CHARACTER" for keyword in keywords):
            return True
        parent = getattr(model, "parent_unit", None)
        if parent is None:
            return False
        has_any_keyword = getattr(parent, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                return bool(has_any_keyword("CHARACTER"))
            except Exception:
                return False
        return False

    def _use_shadow_legion_death_denied(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_shadow_legion_detachment():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "command phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(root) not in candidate_ids:
                return False
        valid_ids = {self._chaos_daemons_sort_key(candidate) for candidate in self._shadow_legion_battlefield_unit_candidates()}
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False

        models = list(getattr(root, "get_attached_unit_models", lambda: [])() or [])
        if not models:
            models = list(getattr(root, "models", []) or [])

        def _model_is_alive(model: Any) -> bool:
            alive_attr = getattr(model, "is_alive", True)
            return bool(alive_attr() if callable(alive_attr) else alive_attr)

        def _missing_wounds(model: Any) -> int:
            base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
            current_wounds = int(getattr(model, "wounds", 0) or 0)
            return max(0, int(base_wounds - current_wounds))

        wounded_models = [
            model for model in models if _model_is_alive(model) and _missing_wounds(model) > 0
        ]
        wounded_models = sorted(wounded_models, key=lambda model: str(get_entity_id(model) or ""))
        heal_model = kwargs.get("model") or kwargs.get("target_model")
        if heal_model is None and wounded_models:
            heal_model = wounded_models[0]

        if heal_model is not None and heal_model not in models:
            return False

        return_model = None
        if self._is_tzeentch_legiones_unit(root):
            destroyed_pool = list(getattr(root, "models_lost", []) or [])
            can_return = getattr(root, "_horrors_can_return_model", None)
            return_candidates: List[Any] = []
            for model in list(destroyed_pool or []):
                if model is None:
                    continue
                if self._shadow_legion_model_is_character(model):
                    continue
                if callable(can_return) and not bool(can_return(model)):
                    continue
                return_candidates.append(model)
            return_candidates = sorted(return_candidates, key=lambda model: str(get_entity_id(model) or ""))
            return_model = kwargs.get("return_model") or kwargs.get("target_return_model")
            if return_model is None and return_candidates:
                return_model = return_candidates[0]
            if return_model is not None and return_model not in return_candidates:
                return False

        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False

        if heal_model is not None:
            heal_amount = 3
            heal_fn = getattr(heal_model, "heal", None)
            if callable(heal_fn):
                heal_fn(int(heal_amount))
            else:
                base_wounds = int(getattr(heal_model, "_base_wounds", getattr(heal_model, "base_wounds", 0)) or 0)
                current_wounds = int(getattr(heal_model, "wounds", 0) or 0)
                heal_model.wounds = min(base_wounds, current_wounds + int(heal_amount))

        if return_model is not None:
            root.return_destroyed_bodyguard_models(
                1,
                game_map=getattr(self.game, "map", None),
                chosen_models=[return_model],
                wounds=None,
                placement_source=stratagem.name,
            )

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_shadow_legion_encroaching_darkness(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_shadow_legion_detachment():
            return False
        selected_units = self._resolve_shadow_legion_selected_units(**kwargs)
        if not selected_units:
            return False
        if len(selected_units) > 2:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False
        valid_heretic_ids = {
            self._chaos_daemons_sort_key(unit) for unit in self._shadow_legion_encroaching_darkness_heretic_candidates()
        }
        valid_daemon_ids = {
            self._chaos_daemons_sort_key(unit) for unit in self._shadow_legion_encroaching_darkness_daemon_candidates()
        }
        selected_heretic = 0
        selected_daemon = 0
        for root in selected_units:
            unit_id = self._chaos_daemons_sort_key(root)
            qualifies_heretic = unit_id in valid_heretic_ids
            qualifies_daemon = unit_id in valid_daemon_ids
            if not (qualifies_heretic or qualifies_daemon):
                return False
            if qualifies_heretic and selected_heretic < 1:
                selected_heretic += 1
                continue
            if qualifies_daemon and selected_daemon < 1:
                selected_daemon += 1
                continue
            if qualifies_heretic and qualifies_daemon:
                if selected_heretic < 1:
                    selected_heretic += 1
                    continue
                if selected_daemon < 1:
                    selected_daemon += 1
                    continue
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=selected_units[0])
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        for root in selected_units:
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                special_rules = {}
            special_rules["shadow_legion_encroaching_darkness_active"] = True
            special_rules["shadow_legion_encroaching_darkness_ignores_cover_active"] = True
            special_rules["shadow_legion_encroaching_darkness_expires_phase"] = "SHOOTING_PHASE"
            special_rules["shadow_legion_encroaching_darkness_turn"] = turn
            special_rules["shadow_legion_encroaching_darkness_source"] = str(getattr(stratagem, "name", "") or "ENCROACHING DARKNESS")
            root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_shadow_legion_shade_path(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_shadow_legion_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return False

        charging_unit = kwargs.get("charging_unit") or kwargs.get("enemy_unit") or kwargs.get("attacking_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        unit = kwargs.get("unit") or kwargs.get("target_unit")

        normalized_name = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != normalized_name:
                continue
            if charging_unit is None:
                charging_unit = reaction.get("charging_unit") or reaction.get("enemy_unit") or reaction.get("attacking_unit")
            if not target_units:
                target_units = list(reaction.get("target_units") or [])
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if unit is None:
                unit = reaction.get("unit") or reaction.get("target_unit")
            break

        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        target_root = self._chaos_daemons_root(unit)
        if target_root is None:
            return False
        charging_root = self._chaos_daemons_root(charging_unit)
        if charging_root is None:
            return False
        charging_army = getattr(charging_root, "get_parent_army", lambda: None)()
        if charging_army is None or getattr(charging_army, "player", None) is self.player:
            return False
        charging_alive = getattr(charging_root, "is_alive", None)
        if callable(charging_alive):
            if not bool(charging_alive()):
                return False
        elif not bool(getattr(charging_root, "is_alive", True)):
            return False
        if not bool(getattr(charging_root, "deployed", True)):
            return False

        valid_candidates = self._shadow_legion_shade_path_candidates(target_units)
        if not valid_candidates and candidates:
            valid_candidates = self._resolve_shadow_legion_selected_units(candidates=candidates)
        valid_ids = {self._chaos_daemons_sort_key(entry) for entry in list(valid_candidates or [])}
        target_id = self._chaos_daemons_sort_key(target_root)
        if target_id not in valid_ids:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(entry)) for entry in candidates}
            if target_id not in candidate_ids:
                return False

        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=target_root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False

        charging_rules = getattr(charging_root, "special_rules", None)
        if not isinstance(charging_rules, dict):
            charging_rules = {}
        mods = list(charging_rules.get("charge_roll_modifiers", []) or [])
        kept_mods: List[Any] = []
        for entry in mods:
            if not isinstance(entry, dict):
                kept_mods.append(entry)
                continue
            if str(entry.get("source_key", "") or "") != "shadow_legion_shade_path":
                kept_mods.append(entry)
                continue
            existing_targets = {str(value).strip() for value in list(entry.get("target_unit_ids", []) or []) if str(value).strip()}
            if target_id and existing_targets and target_id not in existing_targets:
                kept_mods.append(entry)
        kept_mods.append(
            {
                "value": -2,
                "source": str(getattr(stratagem, "name", "") or "SHADE PATH"),
                "source_key": "shadow_legion_shade_path",
                "expires_phase": "CHARGE_PHASE",
                "target_unit_ids": [target_id] if target_id else [],
            }
        )
        charging_rules["charge_roll_modifiers"] = kept_mods
        charging_root.special_rules = charging_rules

        if bool(getattr(target_root, "has_any_keyword", lambda *_: False)("NURGLE")):
            take_test = getattr(charging_root, "take_battle_shock_test", None)
            if callable(take_test):
                take_test(int(getattr(self.game, "turn", 0) or 0))

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_shadow_legion_spiteful_demise(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_shadow_legion_detachment():
            return False
        destroyed_unit = kwargs.get("destroyed_unit") or kwargs.get("unit") or kwargs.get("target_unit")
        last_model = kwargs.get("last_model") or kwargs.get("destroyed_model")
        destroyed_model_base = kwargs.get("destroyed_model_base")
        enemy_candidates = list(kwargs.get("enemy_candidates") or [])

        normalized_name = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != normalized_name:
                continue
            if destroyed_unit is None:
                destroyed_unit = reaction.get("destroyed_unit") or reaction.get("unit") or reaction.get("target_unit")
            if last_model is None:
                last_model = reaction.get("last_model") or reaction.get("destroyed_model")
            if destroyed_model_base is None:
                destroyed_model_base = reaction.get("destroyed_model_base")
            if not enemy_candidates:
                enemy_candidates = list(reaction.get("enemy_candidates") or [])
            break

        root = self._chaos_daemons_root(destroyed_unit)
        if root is None:
            return False
        army = getattr(root, "get_parent_army", lambda: None)()
        if army is None or getattr(army, "player", None) is not self.player:
            return False
        if not self._is_shadow_legion_unit(root):
            return False

        if not enemy_candidates:
            enemy_candidates = self._shadow_legion_spiteful_demise_enemy_candidates(
                destroyed_unit=root,
                last_model=last_model,
                destroyed_model_base=destroyed_model_base,
            )
        if not enemy_candidates:
            return False

        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False

        bonus = 2 if bool(getattr(root, "has_any_keyword", lambda *_: False)("SLAANESH")) else 0
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        for enemy in list(enemy_candidates or []):
            enemy_root = self._chaos_daemons_root(enemy)
            if enemy_root is None:
                continue
            enemy_army = getattr(enemy_root, "get_parent_army", lambda: None)()
            if enemy_army is None or getattr(enemy_army, "player", None) is self.player:
                continue
            enemy_alive = getattr(enemy_root, "is_alive", None)
            if callable(enemy_alive):
                if not bool(enemy_alive()):
                    continue
            elif not bool(getattr(enemy_root, "is_alive", True)):
                continue
            if not bool(getattr(enemy_root, "deployed", True)):
                continue
            roll = int(dice_module.get_roll("D6") or 0) + int(bonus)
            mortal_wounds = 0
            if roll >= 6:
                mortal_wounds = 3
            elif roll >= 4:
                mortal_wounds = int(dice_module.get_roll("D3") or 0)
            if mortal_wounds <= 0:
                continue
            root._apply_mortal_wounds_to_unit(
                enemy_root,
                int(mortal_wounds),
                game_map=game_map,
                attacker_unit=root,
            )

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_shadow_legion_channelled_wrath(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_shadow_legion_detachment():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(root) not in candidate_ids:
                return False
        valid_ids = {self._chaos_daemons_sort_key(candidate) for candidate in self._shadow_legion_channelled_wrath_candidates()}
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["shadow_legion_channelled_wrath_active"] = True
        special_rules["shadow_legion_channelled_wrath_lance_active"] = True
        special_rules["shadow_legion_channelled_wrath_expires_phase"] = "FIGHT_PHASE"
        special_rules["shadow_legion_channelled_wrath_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        special_rules["shadow_legion_channelled_wrath_source"] = str(getattr(stratagem, "name", "") or "CHANNELLED WRATH")
        if bool(getattr(root, "has_any_keyword", lambda *_: False)("KHORNE")):
            special_rules["shadow_legion_channelled_wrath_ap_bonus"] = 1
        else:
            special_rules.pop("shadow_legion_channelled_wrath_ap_bonus", None)
        root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_shadow_legion_binding_shadow(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_shadow_legion_detachment():
            return False
        selected_units = self._resolve_shadow_legion_selected_units(**kwargs)
        if not selected_units:
            normalized_name = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != normalized_name:
                    continue
                selected_units = self._resolve_shadow_legion_selected_units(**reaction)
                break
        if not selected_units:
            return False
        if len(selected_units) > 2:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return False
        valid_heretic_ids = {
            self._chaos_daemons_sort_key(unit) for unit in self._shadow_legion_binding_shadow_heretic_candidates()
        }
        valid_daemon_ids = {
            self._chaos_daemons_sort_key(unit) for unit in self._shadow_legion_binding_shadow_daemon_candidates()
        }
        selected_heretic = 0
        selected_daemon = 0
        for root in selected_units:
            unit_id = self._chaos_daemons_sort_key(root)
            qualifies_heretic = unit_id in valid_heretic_ids
            qualifies_daemon = unit_id in valid_daemon_ids
            if not (qualifies_heretic or qualifies_daemon):
                return False
            if qualifies_heretic and selected_heretic < 1:
                selected_heretic += 1
                continue
            if qualifies_daemon and selected_daemon < 1:
                selected_daemon += 1
                continue
            if qualifies_heretic and qualifies_daemon:
                if selected_heretic < 1:
                    selected_heretic += 1
                    continue
                if selected_daemon < 1:
                    selected_daemon += 1
                    continue
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=selected_units[0])
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        for root in selected_units:
            root.enter_strategic_reserves_midgame(
                game=self.game,
                game_map=getattr(self.game, "map", None),
                reason=stratagem.name,
            )
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_chaos_daemons_legion_of_excess_stratagem(self, stratagem: Any, **kwargs) -> bool | None:
        name_u = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
        if name_u == "SENSORY EXCRUCIATION":
            return self._use_legion_of_excess_sensory_excruciation(stratagem, **kwargs)
        if name_u == "THIEVES OF PAIN":
            return self._use_legion_of_excess_thieves_of_pain(stratagem, **kwargs)
        if name_u == "PHANTASMAL LONGING":
            return self._use_legion_of_excess_phantasmal_longing(stratagem, **kwargs)
        if name_u == "CAVALCADE OF BLADES":
            return self._use_legion_of_excess_cavalcade_of_blades(stratagem, **kwargs)
        return None

    def _use_legion_of_excess_phantasmal_longing(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_legion_of_excess_detachment():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in ("movement phase", "charge phase"):
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(root) not in candidate_ids:
                return False
        valid_ids = {
            self._chaos_daemons_sort_key(candidate)
            for candidate in self._legion_of_excess_slaanesh_battlefield_unit_candidates()
        }
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        move_types = {"charge"} if phase_name == "charge phase" else {"move", "advance", "fall_back"}
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        current = set(special_rules.get("bearer_unit_phase_move_terrain_only_types") or [])
        added = set()
        for move_type in move_types:
            if move_type not in current:
                current.add(move_type)
                added.add(move_type)
        if current:
            special_rules["bearer_unit_phase_move_terrain_only_types"] = sorted(current)
        if added:
            special_rules["legion_of_excess_phantasmal_longing_added_phase_move_terrain_only_types"] = sorted(added)
        special_rules["legion_of_excess_phantasmal_longing_active"] = True
        special_rules["legion_of_excess_phantasmal_longing_expires_phase"] = (
            "CHARGE_PHASE" if phase_name == "charge phase" else "MOVEMENT_PHASE"
        )
        special_rules["legion_of_excess_phantasmal_longing_turn_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["legion_of_excess_phantasmal_longing_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        special_rules["legion_of_excess_phantasmal_longing_source"] = str(getattr(stratagem, "name", "") or "PHANTASMAL LONGING")
        root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_legion_of_excess_sensory_excruciation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_legion_of_excess_detachment():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "command phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(root) not in candidate_ids:
                return False
        valid_ids = {
            self._chaos_daemons_sort_key(candidate)
            for candidate in self._legion_of_excess_slaanesh_battlefield_unit_candidates(require_monster=True)
        }
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        for target in list(self._legion_of_excess_sensory_excruciation_targets() or []):
            target_root = self._chaos_daemons_root(target)
            if target_root is None:
                continue
            take_test = getattr(target_root, "take_battle_shock_test", None)
            if not callable(take_test):
                continue
            special_rules = getattr(target_root, "special_rules", None)
            if not isinstance(special_rules, dict):
                special_rules = {}
            is_below_half = False
            below_half_fn = getattr(target_root, "is_below_half_strength", None)
            if callable(below_half_fn):
                is_below_half = bool(below_half_fn())
            if is_below_half:
                current = int(special_rules.get("battle_shock_test_modifier", 0) or 0)
                special_rules["battle_shock_test_modifier"] = int(current - 1)
                reasons = list(special_rules.get("battle_shock_test_modifier_reasons", []) or [])
                reasons.append("Sensory Excruciation (below half-strength)")
                special_rules["battle_shock_test_modifier_reasons"] = reasons
            suppress_phase = str(special_rules.get("battle_shock_suppress_other_tests_phase", "") or "").strip().upper()
            if suppress_phase == "COMMAND_PHASE":
                special_rules["battle_shock_allow_suppressed_test"] = True
            target_root.special_rules = special_rules
            take_test(turn)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_legion_of_excess_thieves_of_pain(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_legion_of_excess_detachment():
            return False
        source_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        redirect_unit = (
            kwargs.get("redirect_unit")
            or kwargs.get("selected_unit")
            or kwargs.get("secondary_unit")
            or kwargs.get("support_unit")
        )
        redirect_candidates = list(kwargs.get("redirect_candidates") or [])
        from_pending = False
        if source_unit is None or (redirect_unit is None and not redirect_candidates):
            normalized_name = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != normalized_name:
                    continue
                from_pending = True
                if source_unit is None:
                    source_unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if redirect_unit is None:
                    redirect_unit = (
                        reaction.get("redirect_unit")
                        or reaction.get("selected_unit")
                        or reaction.get("secondary_unit")
                        or reaction.get("support_unit")
                    )
                if not redirect_candidates:
                    redirect_candidates = list(reaction.get("redirect_candidates") or [])
                kwargs.setdefault("attack_allocated", reaction.get("attack_allocated"))
                kwargs.setdefault("mortal_wound_allocated", reaction.get("mortal_wound_allocated"))
                kwargs.setdefault("phase_name", reaction.get("phase_name"))
                break
        if source_unit is None and len(candidates) == 1:
            source_unit = candidates[0]
        if source_unit is None:
            return False
        source_root = self._chaos_daemons_root(source_unit)
        if source_root is None:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(source_root) not in candidate_ids:
                return False
        valid_source_ids = {
            self._chaos_daemons_sort_key(candidate)
            for candidate in self._legion_of_excess_thieves_of_pain_source_candidates()
        }
        source_id = self._chaos_daemons_sort_key(source_root)
        if source_id not in valid_source_ids:
            return False
        trigger_name = str(kwargs.get("trigger", "") or "").strip().lower()
        has_attack_trigger = bool(kwargs.get("attack_allocated", False))
        has_mortal_trigger = bool(kwargs.get("mortal_wound_allocated", False))
        if (
            not has_attack_trigger
            and not has_mortal_trigger
            and trigger_name not in {"attack_allocated", "mortal_wound_allocated"}
        ):
            normalized_name = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != normalized_name:
                    continue
                pending_source = self._chaos_daemons_root(reaction.get("unit") or reaction.get("target_unit"))
                if self._chaos_daemons_sort_key(pending_source) != source_id:
                    continue
                has_attack_trigger = bool(reaction.get("attack_allocated", False))
                has_mortal_trigger = bool(reaction.get("mortal_wound_allocated", False))
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                if not redirect_candidates:
                    redirect_candidates = list(reaction.get("redirect_candidates") or [])
                if redirect_unit is None:
                    redirect_unit = (
                        reaction.get("redirect_unit")
                        or reaction.get("selected_unit")
                        or reaction.get("secondary_unit")
                        or reaction.get("support_unit")
                    )
                from_pending = True
                break
        if (
            not from_pending
            and not has_attack_trigger
            and not has_mortal_trigger
            and trigger_name not in {"attack_allocated", "mortal_wound_allocated"}
        ):
            return False
        if not redirect_candidates:
            redirect_candidates = self._legion_of_excess_thieves_of_pain_redirect_candidates(source_root)
        if redirect_unit is None and len(redirect_candidates) == 1:
            redirect_unit = redirect_candidates[0]
        if redirect_unit is None:
            return False
        redirect_root = self._chaos_daemons_root(redirect_unit)
        if redirect_root is None:
            return False
        redirect_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in redirect_candidates}
        redirect_id = self._chaos_daemons_sort_key(redirect_root)
        if redirect_id not in redirect_ids:
            return False
        if source_id and redirect_id and source_id == redirect_id:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        phase_key = self._phase_key_from_name(phase_name)
        if not phase_key:
            phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if not phase_key:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=source_root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        special_rules = getattr(source_root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["legion_of_excess_thieves_of_pain_active"] = True
        special_rules["legion_of_excess_thieves_of_pain_expires_phase"] = str(phase_key).strip().upper()
        special_rules["legion_of_excess_thieves_of_pain_redirect_unit_id"] = str(redirect_id or "")
        special_rules["legion_of_excess_thieves_of_pain_turn_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["legion_of_excess_thieves_of_pain_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        special_rules["legion_of_excess_thieves_of_pain_source"] = str(getattr(stratagem, "name", "") or "THIEVES OF PAIN")
        source_root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_legion_of_excess_cavalcade_of_blades(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_legion_of_excess_detachment():
            return False
        source_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("enemy_unit")
        enemy_candidates = list(kwargs.get("enemy_candidates") or [])
        if source_unit is None or (enemy_unit is None and not enemy_candidates):
            normalized_name = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != normalized_name:
                    continue
                if source_unit is None:
                    source_unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit")
                if not enemy_candidates:
                    enemy_candidates = list(reaction.get("enemy_candidates") or [])
                break
        if source_unit is None and len(candidates) == 1:
            source_unit = candidates[0]
        if source_unit is None:
            return False
        source_root = self._chaos_daemons_root(source_unit)
        if source_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(source_root) not in candidate_ids:
                return False
        valid_source_ids = {
            self._chaos_daemons_sort_key(candidate)
            for candidate in self._legion_of_excess_slaanesh_battlefield_unit_candidates()
        }
        if self._chaos_daemons_sort_key(source_root) not in valid_source_ids:
            return False
        if not enemy_candidates:
            enemy_candidates = self._legion_of_excess_cavalcade_enemy_candidates(source_root)
        if enemy_unit is None and len(enemy_candidates) == 1:
            enemy_unit = enemy_candidates[0]
        if enemy_unit is None:
            return False
        enemy_root = self._chaos_daemons_root(enemy_unit)
        if enemy_root is None:
            return False
        enemy_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in enemy_candidates}
        if self._chaos_daemons_sort_key(enemy_root) not in enemy_ids:
            return False
        is_monster = bool(getattr(source_root, "is_monster", False))
        if not is_monster:
            is_monster = bool(getattr(source_root, "has_any_keyword", lambda *_: False)("MONSTER"))
        roll_count = 6 if is_monster else self._legion_of_excess_models_within_engagement_count(source_root, enemy_root)
        if int(roll_count) <= 0:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=source_root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        rolls = [int(dice_module.get_roll("D6") or 0) for _ in range(int(roll_count))]
        mortal_wounds = int(sum(1 for roll in rolls if int(roll or 0) >= 4))
        if mortal_wounds > 0:
            apply_mortal_wounds = getattr(source_root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal_wounds):
                apply_mortal_wounds(enemy_root, int(mortal_wounds), game_map=getattr(self.game, "map", None))
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_chaos_daemons_blood_legion_stratagem(self, stratagem: Any, **kwargs) -> bool | None:
        name_u = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
        if name_u == "BLOOD BEGETS SKULLS":
            return self._use_blood_legion_blood_begets_skulls(stratagem, **kwargs)
        if name_u == "WRATH UNDENIABLE":
            return self._use_blood_legion_wrath_undeniable(stratagem, **kwargs)
        if name_u == "SKULLS BEGET BLOOD":
            return self._use_blood_legion_skulls_beget_blood(stratagem, **kwargs)
        if name_u == "SHEATHED IN BRASS":
            return self._use_blood_legion_sheathed_in_brass(stratagem, **kwargs)
        if name_u == "GORE-HUNGRY ONSLAUGHT":
            return self._use_blood_legion_gore_hungry_onslaught(stratagem, **kwargs)
        if name_u == "FOOLS' FLIGHT":
            return self._use_blood_legion_fools_flight(stratagem, **kwargs)
        return None

    def _use_blood_legion_blood_begets_skulls(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_blood_legion_detachment():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(root) not in candidate_ids:
                return False
        valid_ids = {self._chaos_daemons_sort_key(candidate) for candidate in self._blood_legion_blood_begets_skulls_candidates()}
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        added_charge_after_advance = not bool(special_rules.get("warp_surge_charge_after_advance", False))
        special_rules["warp_surge_charge_after_advance"] = True
        if added_charge_after_advance:
            special_rules["blood_legion_blood_begets_skulls_added_charge_after_advance"] = True
        special_rules["blood_legion_blood_begets_skulls_active"] = True
        special_rules["blood_legion_blood_begets_skulls_expires_phase"] = "CHARGE_PHASE"
        special_rules["blood_legion_blood_begets_skulls_turn_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["blood_legion_blood_begets_skulls_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        special_rules["blood_legion_blood_begets_skulls_source"] = stratagem.name
        root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_blood_legion_wrath_undeniable(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_blood_legion_detachment():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        target_units = list(kwargs.get("target_units") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None or attacking_unit is None:
            normalized_name = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != normalized_name:
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                break
        if unit is None or attacking_unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            return False
        attacker_root = self._chaos_daemons_root(attacking_unit)
        if attacker_root is None:
            return False
        attacker_army = getattr(attacker_root, "get_parent_army", lambda: None)()
        if attacker_army is None or getattr(attacker_army, "player", None) is self.player:
            return False
        valid_ids = {
            self._chaos_daemons_sort_key(candidate)
            for candidate in self._blood_legion_wrath_undeniable_candidates(
                attacking_unit=attacker_root,
                target_units=list(target_units or candidates or [root]),
            )
        }
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["blood_legion_wrath_undeniable_active"] = True
        special_rules["blood_legion_wrath_undeniable_threshold"] = 4
        special_rules["blood_legion_wrath_undeniable_expires_phase"] = "FIGHT_PHASE"
        special_rules["blood_legion_wrath_undeniable_turn_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["blood_legion_wrath_undeniable_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        special_rules["blood_legion_wrath_undeniable_source"] = stratagem.name
        root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_blood_legion_skulls_beget_blood(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_blood_legion_detachment():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False
        source_ids = {self._chaos_daemons_sort_key(candidate) for candidate in self._blood_legion_skulls_beget_blood_source_candidates()}
        if self._chaos_daemons_sort_key(root) not in source_ids:
            return False
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("enemy_target") or kwargs.get("target_enemy")
        enemy_candidates = self._blood_legion_skulls_beget_blood_enemy_candidates(root)
        if enemy_unit is None and len(enemy_candidates) == 1:
            enemy_unit = enemy_candidates[0]
        if enemy_unit is None:
            return False
        enemy_root = self._chaos_daemons_root(enemy_unit)
        if enemy_root is None:
            return False
        enemy_ids = {self._chaos_daemons_sort_key(candidate) for candidate in enemy_candidates}
        if self._chaos_daemons_sort_key(enemy_root) not in enemy_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        rolls = [int(dice_module.get_roll("D6") or 0) for _ in range(6)]
        mortal_wounds = int(sum(1 for roll in rolls if int(roll or 0) >= 4))
        if mortal_wounds > 0:
            apply_mortal_wounds = getattr(root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal_wounds):
                apply_mortal_wounds(enemy_root, int(mortal_wounds), game_map=getattr(self.game, "map", None))
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_blood_legion_sheathed_in_brass(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_blood_legion_detachment():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        target_units = list(kwargs.get("target_units") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None or attacking_unit is None:
            normalized_name = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != normalized_name:
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                break
        if unit is None or attacking_unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return False
        valid_ids = {
            self._chaos_daemons_sort_key(candidate)
            for candidate in self._blood_legion_sheathed_in_brass_candidates(
                attacking_unit=attacking_unit,
                target_units=list(target_units or candidates or [root]),
            )
        }
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["blood_legion_sheathed_in_brass_active"] = True
        special_rules["blood_legion_sheathed_in_brass_save_characteristic"] = 3
        special_rules["blood_legion_sheathed_in_brass_expires_phase"] = "SHOOTING_PHASE"
        special_rules["blood_legion_sheathed_in_brass_turn_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["blood_legion_sheathed_in_brass_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        special_rules["blood_legion_sheathed_in_brass_source"] = stratagem.name
        root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_blood_legion_gore_hungry_onslaught(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        if not self._is_blood_legion_detachment():
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in ("movement phase", "charge phase"):
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(root) not in candidate_ids:
                return False
        valid_ids = {self._chaos_daemons_sort_key(candidate) for candidate in self._blood_legion_khorne_battlefield_unit_candidates()}
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        move_types = {"charge"} if phase_name == "charge phase" else {"move", "advance", "fall_back"}
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        current = set(special_rules.get("bearer_unit_phase_move_terrain_only_types") or [])
        added = set()
        for move_type in move_types:
            if move_type not in current:
                current.add(move_type)
                added.add(move_type)
        if current:
            special_rules["bearer_unit_phase_move_terrain_only_types"] = sorted(current)
        if added:
            special_rules["blood_legion_gore_hungry_onslaught_added_phase_move_terrain_only_types"] = sorted(added)
        special_rules["blood_legion_gore_hungry_onslaught_active"] = True
        special_rules["blood_legion_gore_hungry_onslaught_expires_phase"] = (
            "CHARGE_PHASE" if phase_name == "charge phase" else "MOVEMENT_PHASE"
        )
        special_rules["blood_legion_gore_hungry_onslaught_turn_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["blood_legion_gore_hungry_onslaught_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        special_rules["blood_legion_gore_hungry_onslaught_source"] = stratagem.name
        root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_blood_legion_fools_flight(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_blood_legion_detachment():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or enemy_unit is None:
            normalized_name = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != normalized_name:
                    continue
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                break
        if enemy_unit is None:
            return False
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        enemy_root = self._chaos_daemons_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(root) not in candidate_ids:
                return False
        valid_ids = {self._chaos_daemons_sort_key(candidate) for candidate in self._blood_legion_fools_flight_candidates(enemy_root)}
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        attempt_charge = getattr(self.game, "attempt_charge", None)
        if callable(attempt_charge):
            attempt_charge(root, enemy_root, out_of_turn=True, count_as_charged=False)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _cleanup_legion_of_excess_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name not in ("COMMAND_PHASE", "MOVEMENT_PHASE", "SHOOTING_PHASE", "CHARGE_PHASE", "FIGHT_PHASE"):
            return
        if self.player is None:
            return
        army = self.player.get_army()
        if army is None:
            return
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
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            changed = False
            if phase_name in ("MOVEMENT_PHASE", "CHARGE_PHASE"):
                expires_phase = str(special_rules.get("legion_of_excess_phantasmal_longing_expires_phase", "") or "").strip().upper()
                if special_rules.get("legion_of_excess_phantasmal_longing_active") and (not expires_phase or expires_phase == phase_name):
                    added = set(special_rules.get("legion_of_excess_phantasmal_longing_added_phase_move_terrain_only_types") or [])
                    if added:
                        current = list(special_rules.get("bearer_unit_phase_move_terrain_only_types") or [])
                        kept = [move_type for move_type in current if move_type not in added]
                        if kept:
                            special_rules["bearer_unit_phase_move_terrain_only_types"] = kept
                        else:
                            special_rules.pop("bearer_unit_phase_move_terrain_only_types", None)
                    for key in (
                        "legion_of_excess_phantasmal_longing_active",
                        "legion_of_excess_phantasmal_longing_expires_phase",
                        "legion_of_excess_phantasmal_longing_turn_owner",
                        "legion_of_excess_phantasmal_longing_turn",
                        "legion_of_excess_phantasmal_longing_source",
                        "legion_of_excess_phantasmal_longing_added_phase_move_terrain_only_types",
                    ):
                        special_rules.pop(key, None)
                    changed = True
            thieves_expires = str(special_rules.get("legion_of_excess_thieves_of_pain_expires_phase", "") or "").strip().upper()
            if special_rules.get("legion_of_excess_thieves_of_pain_active") and (not thieves_expires or thieves_expires == phase_name):
                for key in (
                    "legion_of_excess_thieves_of_pain_active",
                    "legion_of_excess_thieves_of_pain_expires_phase",
                    "legion_of_excess_thieves_of_pain_redirect_unit_id",
                    "legion_of_excess_thieves_of_pain_turn_owner",
                    "legion_of_excess_thieves_of_pain_turn",
                    "legion_of_excess_thieves_of_pain_source",
                ):
                    special_rules.pop(key, None)
                changed = True
            if changed:
                root.special_rules = special_rules

    def _cleanup_blood_legion_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name not in ("MOVEMENT_PHASE", "CHARGE_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"):
            return
        if self.player is None:
            return
        army = self.player.get_army()
        if army is None:
            return
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
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            changed = False
            if phase_name in ("MOVEMENT_PHASE", "CHARGE_PHASE"):
                expires_phase = str(special_rules.get("blood_legion_gore_hungry_onslaught_expires_phase", "") or "").strip().upper()
                if special_rules.get("blood_legion_gore_hungry_onslaught_active") and (not expires_phase or expires_phase == phase_name):
                    added = set(special_rules.get("blood_legion_gore_hungry_onslaught_added_phase_move_terrain_only_types") or [])
                    if added:
                        current = list(special_rules.get("bearer_unit_phase_move_terrain_only_types") or [])
                        kept = [move_type for move_type in current if move_type not in added]
                        if kept:
                            special_rules["bearer_unit_phase_move_terrain_only_types"] = kept
                        else:
                            special_rules.pop("bearer_unit_phase_move_terrain_only_types", None)
                    for key in (
                        "blood_legion_gore_hungry_onslaught_active",
                        "blood_legion_gore_hungry_onslaught_expires_phase",
                        "blood_legion_gore_hungry_onslaught_turn_owner",
                        "blood_legion_gore_hungry_onslaught_turn",
                        "blood_legion_gore_hungry_onslaught_source",
                        "blood_legion_gore_hungry_onslaught_added_phase_move_terrain_only_types",
                    ):
                        special_rules.pop(key, None)
                    changed = True
            if phase_name == "CHARGE_PHASE":
                expires_phase = str(special_rules.get("blood_legion_blood_begets_skulls_expires_phase", "") or "").strip().upper()
                if special_rules.get("blood_legion_blood_begets_skulls_active") and (not expires_phase or expires_phase == phase_name):
                    if bool(special_rules.get("blood_legion_blood_begets_skulls_added_charge_after_advance", False)):
                        special_rules.pop("warp_surge_charge_after_advance", None)
                    for key in (
                        "blood_legion_blood_begets_skulls_active",
                        "blood_legion_blood_begets_skulls_added_charge_after_advance",
                        "blood_legion_blood_begets_skulls_expires_phase",
                        "blood_legion_blood_begets_skulls_turn_owner",
                        "blood_legion_blood_begets_skulls_turn",
                        "blood_legion_blood_begets_skulls_source",
                    ):
                        special_rules.pop(key, None)
                    changed = True
            if phase_name == "SHOOTING_PHASE":
                expires_phase = str(special_rules.get("blood_legion_sheathed_in_brass_expires_phase", "") or "").strip().upper()
                if special_rules.get("blood_legion_sheathed_in_brass_active") and (not expires_phase or expires_phase == phase_name):
                    for key in (
                        "blood_legion_sheathed_in_brass_active",
                        "blood_legion_sheathed_in_brass_save_characteristic",
                        "blood_legion_sheathed_in_brass_expires_phase",
                        "blood_legion_sheathed_in_brass_turn_owner",
                        "blood_legion_sheathed_in_brass_turn",
                        "blood_legion_sheathed_in_brass_source",
                    ):
                        special_rules.pop(key, None)
                    changed = True
            if phase_name == "FIGHT_PHASE":
                expires_phase = str(special_rules.get("blood_legion_wrath_undeniable_expires_phase", "") or "").strip().upper()
                if special_rules.get("blood_legion_wrath_undeniable_active") and (not expires_phase or expires_phase == phase_name):
                    for key in (
                        "blood_legion_wrath_undeniable_active",
                        "blood_legion_wrath_undeniable_threshold",
                        "blood_legion_wrath_undeniable_expires_phase",
                        "blood_legion_wrath_undeniable_turn_owner",
                        "blood_legion_wrath_undeniable_turn",
                        "blood_legion_wrath_undeniable_source",
                    ):
                        special_rules.pop(key, None)
                    changed = True
                pending_models = getattr(root, "_blood_legion_wrath_undeniable_pending_models", None)
                if isinstance(pending_models, list) and pending_models:
                    root._blood_legion_wrath_undeniable_pending_models = []
            if changed:
                root.special_rules = special_rules

    def _cleanup_shadow_legion_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name not in {"CHARGE_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        game = getattr(self, "game", None)
        if game is None:
            return

        if phase_name == "CHARGE_PHASE":
            for player in list(getattr(game, "players", []) or []):
                army = getattr(player, "get_army", lambda: None)()
                if army is None:
                    continue
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
                    special_rules = getattr(root, "special_rules", None)
                    if not isinstance(special_rules, dict):
                        continue
                    mods = special_rules.get("charge_roll_modifiers")
                    if not isinstance(mods, list):
                        continue
                    kept: List[Any] = []
                    changed = False
                    for item in mods:
                        if not isinstance(item, dict):
                            kept.append(item)
                            continue
                        if str(item.get("source_key", "") or "") != "shadow_legion_shade_path":
                            kept.append(item)
                            continue
                        expires_phase = str(item.get("expires_phase", "") or "").strip().upper()
                        if expires_phase and expires_phase != phase_name:
                            kept.append(item)
                            continue
                        changed = True
                    if not changed:
                        continue
                    if kept:
                        special_rules["charge_roll_modifiers"] = kept
                    elif "charge_roll_modifiers" in special_rules:
                        special_rules.pop("charge_roll_modifiers", None)
                    root.special_rules = special_rules
            return

        if self.player is None:
            return
        army = self.player.get_army()
        if army is None:
            return
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
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            changed = False
            if phase_name == "SHOOTING_PHASE":
                expires_phase = str(special_rules.get("shadow_legion_encroaching_darkness_expires_phase", "") or "").strip().upper()
                if special_rules.get("shadow_legion_encroaching_darkness_active") and (not expires_phase or expires_phase == "SHOOTING_PHASE"):
                    for key in (
                        "shadow_legion_encroaching_darkness_active",
                        "shadow_legion_encroaching_darkness_ignores_cover_active",
                        "shadow_legion_encroaching_darkness_expires_phase",
                        "shadow_legion_encroaching_darkness_turn",
                        "shadow_legion_encroaching_darkness_source",
                    ):
                        special_rules.pop(key, None)
                    changed = True
            if phase_name == "FIGHT_PHASE":
                expires_phase = str(special_rules.get("shadow_legion_channelled_wrath_expires_phase", "") or "").strip().upper()
                if special_rules.get("shadow_legion_channelled_wrath_active") and (not expires_phase or expires_phase == "FIGHT_PHASE"):
                    for key in (
                        "shadow_legion_channelled_wrath_active",
                        "shadow_legion_channelled_wrath_lance_active",
                        "shadow_legion_channelled_wrath_ap_bonus",
                        "shadow_legion_channelled_wrath_expires_phase",
                        "shadow_legion_channelled_wrath_turn",
                        "shadow_legion_channelled_wrath_source",
                    ):
                        special_rules.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = special_rules
