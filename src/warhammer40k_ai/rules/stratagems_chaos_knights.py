from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class ChaosKnightsStratagemMixin:
    @staticmethod
    def _chaos_knights_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                root = get_root()
            except Exception:
                return unit
            if root is not None:
                return root
        return unit

    @staticmethod
    def _chaos_knights_sort_key(unit: Any) -> str:
        try:
            return str(get_entity_id(unit) or "")
        except Exception:
            return ""

    @staticmethod
    def _chaos_knights_normalize_name(value: str) -> str:
        return (
            str(value or "")
            .replace("\u2019", "'")
            .replace("\u2018", "'")
            .replace("\u2010", "-")
            .replace("\u2011", "-")
            .replace("\u2012", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
            .strip()
            .upper()
        )

    @staticmethod
    def _chaos_knights_phase_label(phase_key: str) -> str:
        key = str(phase_key or "").strip().upper()
        if key == "COMMAND_PHASE":
            return "Command phase"
        if key == "MOVEMENT_PHASE":
            return "Movement phase"
        if key == "SHOOTING_PHASE":
            return "Shooting phase"
        if key == "CHARGE_PHASE":
            return "Charge phase"
        if key == "FIGHT_PHASE":
            return "Fight phase"
        return str(phase_key or "").strip().replace("_", " ").title()

    def _chaos_knights_army(self):
        get_army = getattr(self.player, "get_army", None)
        return get_army() if callable(get_army) else getattr(self.player, "army", None)

    def _chaos_knights_detachment_manager(self):
        army = self._chaos_knights_army()
        if army is None:
            return None
        mgr = getattr(army, "chaos_knights_detachments", None)
        if mgr is None or not hasattr(mgr, "is_infernal_lance"):
            return None
        return mgr

    def _infernal_lance_detachment_manager(self):
        mgr = self._chaos_knights_detachment_manager()
        if mgr is None:
            return None
        return mgr if self._is_infernal_lance_detachment() else None

    def _is_houndpack_lance_detachment(self) -> bool:
        mgr = self._chaos_knights_detachment_manager()
        checker = getattr(mgr, "is_houndpack_lance", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_infernal_lance_detachment(self) -> bool:
        mgr = self._chaos_knights_detachment_manager()
        checker = getattr(mgr, "is_infernal_lance", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_iconoclast_fiefdom(self) -> bool:
        mgr = self._chaos_knights_detachment_manager()
        checker = getattr(mgr, "is_iconoclast_fiefdom", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _chaos_knights_current_turn_key(self) -> str:
        if self.game is None:
            return ""
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        active_player_id = str(getattr(active_player, "id", "") or "").strip()
        try:
            current_turn = int(getattr(self.game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if not current_turn and not active_player_id:
            return ""
        return f"{current_turn}:{active_player_id}"

    def _houndpack_vox_howl_used_this_turn(self) -> bool:
        used_turn_key = str(getattr(self, "_houndpack_vox_howl_turn_key", "") or "")
        current_turn_key = self._chaos_knights_current_turn_key()
        return bool(used_turn_key and current_turn_key and used_turn_key == current_turn_key)

    def _mark_houndpack_vox_howl_used_this_turn(self) -> None:
        current_turn_key = self._chaos_knights_current_turn_key()
        if current_turn_key:
            setattr(self, "_houndpack_vox_howl_turn_key", current_turn_key)

    @staticmethod
    def _chaos_knights_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _chaos_knights_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "is_alive", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                return False
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _chaos_knights_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                return False
        return bool(getattr(unit, "reserve_status", "") not in ("", "deployed"))

    def _chaos_knights_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        if not self._chaos_knights_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._chaos_knights_is_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _is_chaos_knights_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        army = self._chaos_knights_army()
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
        return root_faction_id == "QT"

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

    def _is_chaos_knights_war_dog_unit(self, unit: Any) -> bool:
        if not self._is_chaos_knights_unit(unit):
            return False
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        has_any_kw = getattr(root, "has_any_keyword", None)
        if callable(has_any_kw) and has_any_kw("WAR DOG"):
            return True
        return "WAR DOG" in self._chaos_knights_normalize_name(getattr(root, "name", ""))

    def _chaos_knights_pending_context(self, stratagem_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        wanted = self._chaos_knights_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._chaos_knights_normalize_name(reaction.get("stratagem", "")) != wanted:
                continue
            merged.update(dict(reaction))
            break
        for key, value in dict(kwargs or {}).items():
            if value is not None:
                merged[key] = value
        return merged

    def _chaos_knights_reaction_exists(
        self,
        event_name: str,
        stratagem_name: str,
        *,
        unit: Any = None,
        enemy_unit: Any = None,
    ) -> bool:
        wanted = self._chaos_knights_normalize_name(stratagem_name)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            try:
                if str(reaction.get("event", "") or "") != str(event_name or ""):
                    continue
                if self._chaos_knights_normalize_name(reaction.get("stratagem", "")) != wanted:
                    continue
                if unit is not None:
                    if reaction.get("unit") is not unit and reaction.get("target_unit") is not unit:
                        continue
                if enemy_unit is not None and reaction.get("enemy_unit") is not enemy_unit:
                    continue
                return True
            except Exception:
                continue
        return False

    def _chaos_knights_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        try:
            if hasattr(self.player, "apply_stratagem_cp_cost"):
                payload = self.player.apply_stratagem_cp_cost(stratagem, target_unit=target_unit)
                cost = int(payload.get("cost", cost) or cost)
        except Exception:
            return int(cost)
        return int(cost)

    def _chaos_knights_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cost = self._chaos_knights_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                int(cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Stratagem')}",
                source="stratagem",
            )
        )

    def _chaos_knights_enemy_roots(self) -> List[Any]:
        game = getattr(self, "game", None)
        if game is None:
            return []
        roots: List[Any] = []
        seen: set[str] = set()

        def add_candidate(unit: Any) -> None:
            root = self._chaos_knights_root(unit)
            if root is None:
                return
            rid = self._chaos_knights_sort_key(root)
            if rid and rid in seen:
                return
            if rid:
                seen.add(rid)
            if not self._chaos_knights_is_alive(root):
                return
            if not bool(getattr(root, "deployed", False)):
                return
            if self._chaos_knights_is_in_reserves(root):
                return
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                return
            roots.append(root)

        get_enemy_units = getattr(game, "get_enemy_units", None)
        if callable(get_enemy_units):
            try:
                for unit in list(get_enemy_units(self.player) or []):
                    add_candidate(unit)
            except Exception:
                pass
        if roots:
            return sorted(roots, key=self._chaos_knights_sort_key)
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is self.player:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                add_candidate(unit)
        return sorted(roots, key=self._chaos_knights_sort_key)

    def _chaos_knights_distance_between_units(self, source_unit: Any, target_unit: Any) -> Optional[float]:
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None or source_unit is None or target_unit is None:
            return None
        root = self._chaos_knights_root(source_unit)
        target_root = self._chaos_knights_root(target_unit)
        if root is None or target_root is None:
            return None
        distance_fn = getattr(game_map, "get_distance_between_units", None)
        if not callable(distance_fn):
            return None
        try:
            distance = distance_fn(root, target_root)
        except Exception:
            return None
        if distance is None:
            return None
        try:
            return float(distance)
        except Exception:
            return None

    def _chaos_knights_in_engagement_range(self, unit: Any) -> bool:
        root = self._chaos_knights_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or game_map is None:
            return False
        within_fn = getattr(game_map, "is_within_engagement_range", None)
        if not callable(within_fn):
            return False
        for enemy_root in list(self._chaos_knights_enemy_roots() or []):
            try:
                if within_fn(root, enemy_root):
                    return True
            except Exception:
                continue
        return False

    def _chaos_knights_resolve_unit(self, unit_id: str) -> Any:
        key = str(unit_id or "").strip()
        if not key:
            return None
        registry = getattr(getattr(self, "game", None), "entity_registry", None)
        if registry is not None and hasattr(registry, "get"):
            try:
                unit = registry.get(key, kind="unit")
            except Exception:
                unit = None
            if unit is not None:
                return self._chaos_knights_root(unit)
        for army in [self._chaos_knights_army()]:
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                root = self._chaos_knights_root(unit)
                if self._chaos_knights_sort_key(root) == key:
                    return root
        for unit in list(self._chaos_knights_enemy_roots() or []):
            if self._chaos_knights_sort_key(unit) == key:
                return unit
        return None

    def _chaos_knights_unit_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_empowered: bool = False,
        require_character: bool = False,
        require_war_dog: bool = False,
        require_fell_back: bool = False,
        require_not_in_engagement: bool = False,
    ) -> List[Any]:
        mgr = self._chaos_knights_detachment_manager()
        if require_not_empowered and mgr is None:
            return []
        army = self._chaos_knights_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in units:
            root = self._chaos_knights_root(unit)
            if root is None:
                continue
            uid = self._chaos_knights_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._chaos_knights_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_chaos_knights_unit(root):
                continue
            if require_character and not self._is_chaos_knights_character_unit(root):
                continue
            if require_war_dog and not self._is_chaos_knights_war_dog_unit(root):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_fell_back and not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            if require_not_in_engagement and self._chaos_knights_in_engagement_range(root):
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
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

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
        if self._infernal_lance_detachment_manager() is None:
            return []
        return self._chaos_knights_unit_candidates(
            require_not_shot=require_not_shot,
            require_not_empowered=require_not_empowered,
            require_character=require_character,
        )

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

    def _houndpack_vox_howl_candidates(self) -> List[Any]:
        if not self._is_houndpack_lance_detachment():
            return []
        return self._chaos_knights_unit_candidates(require_character=True, require_war_dog=True)

    def _houndpack_cunning_hunter_candidates(self) -> List[Any]:
        if not self._is_houndpack_lance_detachment():
            return []
        return self._chaos_knights_unit_candidates(require_war_dog=True, require_fell_back=True)

    def _houndpack_harrying_hounds_candidates(self, enemy_unit: Any) -> List[Any]:
        if not self._is_houndpack_lance_detachment():
            return []
        enemy_root = self._chaos_knights_root(enemy_unit)
        if enemy_root is None:
            return []
        candidates: List[Any] = []
        for root in list(
            self._chaos_knights_unit_candidates(require_war_dog=True, require_not_in_engagement=True) or []
        ):
            distance = self._chaos_knights_distance_between_units(root, enemy_root)
            if distance is None or distance > 9.0 + 1e-6:
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _houndpack_encircling_pack_candidates(self) -> List[Any]:
        if not self._is_houndpack_lance_detachment():
            return []
        candidates: List[Any] = []
        within_edge_fn = getattr(self, "_unit_wholly_within_battlefield_edge_distance", None)
        for root in list(
            self._chaos_knights_unit_candidates(require_war_dog=True, require_not_in_engagement=True) or []
        ):
            if not callable(within_edge_fn):
                continue
            try:
                if not bool(within_edge_fn(root, 12.0)):
                    continue
            except Exception:
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _houndpack_hungry_for_combat_groups(self) -> List[Dict[str, Any]]:
        if not self._is_houndpack_lance_detachment() or self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        within_fn = getattr(game_map, "is_within_engagement_range", None)
        if not callable(within_fn):
            return []
        war_dogs = list(self._chaos_knights_unit_candidates(require_war_dog=True) or [])
        groups: List[Dict[str, Any]] = []
        for enemy_root in list(self._chaos_knights_enemy_roots() or []):
            matching_units: List[Any] = []
            for war_dog_root in list(war_dogs or []):
                try:
                    if within_fn(war_dog_root, enemy_root):
                        matching_units.append(war_dog_root)
                except Exception:
                    continue
            if len(matching_units) < 2:
                continue
            matching_units.sort(key=self._chaos_knights_sort_key)
            groups.append(
                {
                    "enemy_unit": enemy_root,
                    "enemy_unit_id": self._chaos_knights_sort_key(enemy_root),
                    "enemy_name": str(getattr(enemy_root, "name", "Enemy Unit") or "Enemy Unit"),
                    "units": list(matching_units),
                    "unit_ids": [self._chaos_knights_sort_key(unit) for unit in list(matching_units)],
                }
            )
        groups.sort(key=lambda group: str(group.get("enemy_unit_id", "") or ""))
        return groups

    def _houndpack_hungry_for_combat_group_for_enemy(self, enemy_unit: Any) -> Optional[Dict[str, Any]]:
        enemy_root = self._chaos_knights_root(enemy_unit)
        enemy_id = self._chaos_knights_sort_key(enemy_root)
        for group in list(self._houndpack_hungry_for_combat_groups() or []):
            if str(group.get("enemy_unit_id", "") or "") == enemy_id:
                return group
        return None

    def _houndpack_hungry_for_combat_reaction_payload(self, groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"enemy_candidates": []}
        for group in list(groups or []):
            enemy_unit = group.get("enemy_unit")
            if enemy_unit is None:
                continue
            payload["enemy_candidates"].append(
                {
                    "enemy_unit": enemy_unit,
                    "enemy_unit_id": str(group.get("enemy_unit_id", "") or ""),
                    "enemy_name": str(group.get("enemy_name", "") or getattr(enemy_unit, "name", "Enemy Unit")),
                    "candidate_unit_ids": list(group.get("unit_ids", []) or []),
                }
            )
        if len(groups) == 1:
            group = groups[0]
            payload["enemy_unit"] = group.get("enemy_unit")
            payload["enemy_unit_id"] = group.get("enemy_unit_id")
            payload["candidate_unit_ids"] = list(group.get("unit_ids", []) or [])
            if len(payload["candidate_unit_ids"]) == 2:
                payload["selected_unit_ids"] = list(payload["candidate_unit_ids"])
        return payload

    def _resolve_houndpack_hungry_selected_units(self, values: Any) -> List[Any]:
        selected: List[Any] = []
        seen: set[str] = set()
        for value in list(values or []):
            if value is None:
                continue
            root = value if not isinstance(value, str) else self._chaos_knights_resolve_unit(value)
            root = self._chaos_knights_root(root)
            if root is None:
                continue
            root_id = self._chaos_knights_sort_key(root)
            if not root_id or root_id in seen:
                continue
            seen.add(root_id)
            selected.append(root)
        selected.sort(key=self._chaos_knights_sort_key)
        return selected

    def _clear_houndpack_hungry_for_combat_effects(self) -> None:
        army = self._chaos_knights_army()
        if army is None:
            return
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_knights_root(unit)
            if root is None:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in (
                "houndpack_hungry_for_combat_active",
                "houndpack_hungry_for_combat_target_id",
                "houndpack_hungry_for_combat_target_lock",
                "houndpack_hungry_for_combat_crit_threshold",
                "houndpack_hungry_for_combat_expires_phase",
                "houndpack_hungry_for_combat_turn",
                "houndpack_hungry_for_combat_turn_owner",
                "houndpack_hungry_for_combat_source",
            ):
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr

    def _queue_houndpack_lance_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_houndpack_lance_detachment() or self.game is None:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        phase_name = self._chaos_knights_phase_label(phase_key)
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return

        vox_howl = self.get_by_name("VOX-HOWL")
        if vox_howl is not None:
            if not self._houndpack_vox_howl_used_this_turn():
                if (vox_howl.name or "").strip().upper() not in self._used_stratagems_this_phase:
                    if int(getattr(self.player, "command_points", 0) or 0) >= self._chaos_knights_effective_cp_cost(vox_howl):
                        candidates = list(self._houndpack_vox_howl_candidates() or [])
                        if candidates and not self._chaos_knights_reaction_exists("phase_start", vox_howl.name):
                            payload = {
                                "event": "phase_start",
                                "phase_name": phase_name,
                                "stratagem": vox_howl.name,
                                "cp_cost": vox_howl.cp_cost,
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["unit"] = candidates[0]
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload, use_timer=False)

        if phase_key != "FIGHT_PHASE":
            return
        hungry = self.get_by_name("HUNGRY FOR COMBAT")
        if hungry is None:
            return
        if (hungry.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._chaos_knights_effective_cp_cost(hungry):
            return
        groups = list(self._houndpack_hungry_for_combat_groups() or [])
        if not groups:
            return
        if self._chaos_knights_reaction_exists("phase_start", hungry.name):
            return
        payload = {
            "event": "phase_start",
            "phase_name": phase_name,
            "stratagem": hungry.name,
            "cp_cost": hungry.cp_cost,
        }
        payload.update(self._houndpack_hungry_for_combat_reaction_payload(groups))
        self._queue_reaction(payload, use_timer=False)

    def _queue_houndpack_lance_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_houndpack_lance_detachment() or self.game is None:
            return
        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        moving_root = self._chaos_knights_root(unit)

        if active_player is self.player:
            if action_key not in {"fall back", "fallback"}:
                return
            cunning_hunter = self.get_by_name("CUNNING HUNTER")
            if cunning_hunter is None:
                return
            if moving_root is None or moving_root.get_parent_army().player is not self.player:
                return
            if moving_root not in list(self._houndpack_cunning_hunter_candidates() or []):
                return
            if self._chaos_knights_reaction_exists("unit_move_ended", cunning_hunter.name, unit=moving_root):
                return
            if (cunning_hunter.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._chaos_knights_effective_cp_cost(
                cunning_hunter,
                target_unit=moving_root,
            ):
                return
            self._queue_reaction(
                {
                    "event": "unit_move_ended",
                    "phase_name": "Movement phase",
                    "stratagem": cunning_hunter.name,
                    "cp_cost": cunning_hunter.cp_cost,
                    "unit": moving_root,
                    "target_unit": moving_root,
                    "action": action,
                },
                use_timer=False,
            )
            return

        if action_key not in {"move", "normal", "normal move", "advance", "fall back", "fallback"}:
            return
        if moving_root is None:
            return
        try:
            if moving_root.get_parent_army().player is self.player:
                return
        except Exception:
            return
        harrying_hounds = self.get_by_name("HARRYING HOUNDS")
        if harrying_hounds is None:
            return
        if (harrying_hounds.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = list(self._houndpack_harrying_hounds_candidates(moving_root) or [])
        if not candidates:
            return
        if self._chaos_knights_reaction_exists(
            "unit_move_ended",
            harrying_hounds.name,
            enemy_unit=moving_root,
        ):
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._chaos_knights_effective_cp_cost(
            harrying_hounds,
            target_unit=candidates[0],
        ):
            return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": harrying_hounds.name,
            "cp_cost": harrying_hounds.cp_cost,
            "enemy_unit": moving_root,
            "candidates": candidates,
            "action": action,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_houndpack_lance_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_houndpack_lance_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key == "FIGHT_PHASE":
            self._clear_houndpack_hungry_for_combat_effects()

        if self.game is None or player is self.player or phase_key != "FIGHT_PHASE":
            return
        encircling_pack = self.get_by_name("ENCIRCLING PACK")
        if encircling_pack is None:
            return
        if (encircling_pack.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = list(self._houndpack_encircling_pack_candidates() or [])
        if not candidates:
            return
        if self._chaos_knights_reaction_exists("phase_end", encircling_pack.name):
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._chaos_knights_effective_cp_cost(
            encircling_pack,
            target_unit=candidates[0],
        ):
            return
        payload = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": encircling_pack.name,
            "cp_cost": encircling_pack.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _houndpack_animalistic_rage_has_pending_decision(self, game: Any, *, unit_id: str, model_id: str) -> bool:
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_FRENZY_TARGET

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_FRENZY_TARGET:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "chaos_knights_animalistic_rage":
                continue
            if str(ctx.get("unit_id", "") or "") != str(unit_id or ""):
                continue
            if str(ctx.get("model_id", "") or "") != str(model_id or ""):
                continue
            return True
        return False

    def _houndpack_animalistic_rage_shoot_declarations(self, unit: Any, enemy_unit: Any) -> List[dict]:
        if unit is None or enemy_unit is None or self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        root = self._chaos_knights_root(unit)
        enemy_root = self._chaos_knights_root(enemy_unit)
        if root is None or enemy_root is None:
            return []
        declarations: List[dict] = []
        for model in list(getattr(root, "models", []) or []):
            alive_attr = getattr(model, "is_alive", True)
            try:
                alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                alive = False
            if not alive:
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged):
                    continue
                try:
                    if not bool(is_ranged()):
                        continue
                except Exception:
                    continue
                profiles = getattr(wargear, "profiles", {}) or {}
                for profile in list(profiles.values()):
                    if profile is None:
                        continue
                    can_shoot = getattr(root, "_can_model_shoot_weapon_at_target", None)
                    if callable(can_shoot):
                        try:
                            if not bool(can_shoot(model, profile, enemy_root, game_map)):
                                continue
                        except Exception:
                            continue
                    declarations.append(
                        {
                            "weapon_profile": profile,
                            "target_unit": enemy_root,
                            "models": [model],
                        }
                    )
        return declarations

    def _houndpack_animalistic_rage_available_actions(
        self,
        unit: Any,
        enemy_unit: Any,
        *,
        phase_name: str = "",
    ) -> List[str]:
        actions: List[str] = []
        root = self._chaos_knights_root(unit)
        enemy_root = self._chaos_knights_root(enemy_unit)
        if root is None or enemy_root is None or self.game is None:
            return actions
        if self._houndpack_animalistic_rage_shoot_declarations(root, enemy_root):
            actions.append("shoot")
        can_fight = getattr(self.game, "_frenzy_can_fight_target", None)
        if callable(can_fight):
            try:
                if bool(can_fight(root, enemy_root, phase_name=phase_name)):
                    actions.append("fight")
            except Exception:
                pass
        return actions

    def queue_houndpack_animalistic_rage(self, unit: Any, model: Any, *, game_map: Any = None, phase_name: str = "") -> bool:
        if not self._is_houndpack_lance_detachment() or self.game is None:
            return False
        root = self._chaos_knights_root(unit)
        if root is None or model is None:
            return False
        if not self._is_chaos_knights_war_dog_unit(root):
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            return False

        current_phase = str(phase_name or getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if current_phase == "SHOOTING_PHASE" and active_player is self.player:
            return False
        if current_phase not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return False

        enemy_root = self._chaos_knights_root(getattr(root, "_last_destroyed_by_unit", None))
        if enemy_root is None:
            return False
        try:
            if enemy_root.get_parent_army().player is self.player:
                return False
        except Exception:
            return False

        stratagem = self.get_by_name("ANIMALISTIC RAGE")
        if stratagem is None:
            return False
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return False
        if int(getattr(self.player, "command_points", 0) or 0) < self._chaos_knights_effective_cp_cost(
            stratagem,
            target_unit=root,
        ):
            return False

        actions = list(self._houndpack_animalistic_rage_available_actions(root, enemy_root, phase_name=current_phase))
        if not actions:
            return False

        model_id = str(get_entity_id(model) or "")
        unit_id = str(get_entity_id(root) or "")
        enemy_id = str(get_entity_id(enemy_root) or "")
        if not unit_id or not model_id or not enemy_id:
            return False
        if self._houndpack_animalistic_rage_has_pending_decision(self.game, unit_id=unit_id, model_id=model_id):
            return True

        from ..engine.decision_kinds import DECISION_CHOOSE_FRENZY_TARGET
        from ..engine.decisions import DecisionOption, DecisionRequest

        options: List[Any] = []
        if "shoot" in actions:
            options.append(DecisionOption.create("Shoot", payload={"action": "shoot"}))
        if "fight" in actions:
            options.append(DecisionOption.create("Fight", payload={"action": "fight"}))
        options.append(DecisionOption.create("None", payload={"action": "skip", "skip": True}))

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["houndpack_animalistic_rage_pending"] = True
        sr["houndpack_animalistic_rage_model_id"] = model_id
        sr["houndpack_animalistic_rage_enemy_unit_id"] = enemy_id
        sr["houndpack_animalistic_rage_phase_name"] = current_phase
        sr["houndpack_animalistic_rage_available_actions"] = list(actions)
        sr["houndpack_animalistic_rage_turn"] = int(getattr(self.game, "turn", 0) or 0)
        sr["houndpack_animalistic_rage_turn_owner"] = str(getattr(active_player, "id", "") or "")
        root.special_rules = sr

        request = DecisionRequest.create(
            DECISION_CHOOSE_FRENZY_TARGET,
            "ANIMALISTIC RAGE: choose shoot, fight, or skip before Deadly Demise.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "chaos_knights_animalistic_rage",
                "ability_name": "ANIMALISTIC RAGE",
                "stratagem_name": "ANIMALISTIC RAGE",
                "unit_id": unit_id,
                "model_id": model_id,
                "target_unit_id": enemy_id,
                "phase_name": current_phase,
                "available_actions": list(actions),
            },
        )
        request_fn = getattr(self.game, "request_decision", None)
        if callable(request_fn):
            request_fn(request)
        else:
            queue = getattr(self.game, "decision_queue", None)
            if queue is not None and hasattr(queue, "add"):
                queue.add(request)
        return True

    def resolve_houndpack_animalistic_rage_choice(self, unit: Any, *, choice: str) -> bool:
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("houndpack_animalistic_rage_pending")):
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False

        model_id = str(sr.get("houndpack_animalistic_rage_model_id", "") or "")
        enemy_unit_id = str(sr.get("houndpack_animalistic_rage_enemy_unit_id", "") or "")
        phase_name = str(sr.get("houndpack_animalistic_rage_phase_name", "") or "").strip().upper()
        available_actions = {
            str(value or "").strip().lower()
            for value in list(sr.get("houndpack_animalistic_rage_available_actions", []) or [])
            if str(value or "").strip()
        }
        enemy_root = self._chaos_knights_resolve_unit(enemy_unit_id)
        model = None
        for candidate in list(getattr(root, "models", []) or []):
            if str(get_entity_id(candidate) or "") == model_id:
                model = candidate
                break
        selected_choice = str(choice or "").strip().lower()
        executed = False

        if selected_choice in {"shoot", "fight"} and selected_choice in available_actions and enemy_root is not None:
            stratagem = self.get_by_name("ANIMALISTIC RAGE")
            if stratagem is not None and self._chaos_knights_spend_cp(stratagem, target_unit=root):
                if selected_choice == "shoot":
                    declarations = self._houndpack_animalistic_rage_shoot_declarations(root, enemy_root)
                    execute = getattr(root, "execute_shooting_declarations", None)
                    if declarations and callable(execute):
                        executed = bool(execute(declarations, getattr(game, "map", None), out_of_phase=True))
                elif selected_choice == "fight":
                    execute = getattr(game, "_execute_frenzy_fight", None)
                    if callable(execute):
                        executed = bool(execute(root, enemy_root, phase_name=phase_name))
                self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
                logger.info(
                    "INFO: ANIMALISTIC RAGE: %s resolves a %s attack sequence before Deadly Demise.",
                    getattr(root, "name", "Unit"),
                    selected_choice,
                )

        finalize = getattr(root, "resolve_houndpack_animalistic_rage_pending", None)
        if callable(finalize):
            finalize(game_map=getattr(game, "map", None))
        return executed

    def _use_houndpack_vox_howl(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_houndpack_lance_detachment():
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            logger.error("ERROR: VOX-HOWL: no target unit provided")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: VOX-HOWL: wrong phase")
            return False
        if root not in list(self._houndpack_vox_howl_candidates() or []):
            logger.error("ERROR: VOX-HOWL: target is not an eligible WAR DOG CHARACTER unit")
            return False
        if self._houndpack_vox_howl_used_this_turn():
            logger.error("ERROR: VOX-HOWL: can only be used once per turn")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False

        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        enemy_tested = 0
        for enemy_root in list(self._chaos_knights_enemy_roots() or []):
            distance = self._chaos_knights_distance_between_units(root, enemy_root)
            if distance is None or distance > 6.0 + 1e-6:
                continue
            test_fn = getattr(enemy_root, "take_battle_shock_test", None)
            if callable(test_fn):
                try:
                    test_fn(int(current_turn or 1))
                    enemy_tested += 1
                except Exception:
                    continue

        cleared = 0
        army = self._chaos_knights_army()
        for unit in list(getattr(army, "units", []) or []):
            war_dog_root = self._chaos_knights_root(unit)
            if war_dog_root is None:
                continue
            if not self._is_chaos_knights_war_dog_unit(war_dog_root):
                continue
            if not self._chaos_knights_on_battlefield(war_dog_root, require_targetable=False):
                continue
            distance = self._chaos_knights_distance_between_units(root, war_dog_root)
            if distance is None or distance > 6.0 + 1e-6:
                continue
            is_bs = getattr(war_dog_root, "is_battle_shocked", None)
            if not callable(is_bs):
                continue
            try:
                if not bool(is_bs()):
                    continue
            except Exception:
                continue
            test_fn = getattr(war_dog_root, "pass_leadership_check", None)
            clear_fn = getattr(war_dog_root, "clear_battle_shock", None)
            try:
                if callable(test_fn) and bool(test_fn()) and callable(clear_fn):
                    if bool(clear_fn()):
                        cleared += 1
            except Exception:
                continue

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        self._mark_houndpack_vox_howl_used_this_turn()
        logger.info(
            "INFO: VOX-HOWL: %s forced %d enemy Battle-shock test(s) and cleared %d friendly WAR DOG unit(s).",
            getattr(root, "name", "Unit"),
            int(enemy_tested),
            int(cleared),
        )
        return True

    def _use_houndpack_hungry_for_combat(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_houndpack_lance_detachment():
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: HUNGRY FOR COMBAT: wrong phase")
            return False

        enemy_root = self._chaos_knights_root(merged.get("enemy_unit"))
        if enemy_root is None:
            enemy_root = self._chaos_knights_resolve_unit(str(merged.get("enemy_unit_id", "") or ""))
        if enemy_root is None:
            enemy_candidates = list(merged.get("enemy_candidates", []) or [])
            if len(enemy_candidates) == 1:
                enemy_root = self._chaos_knights_root(enemy_candidates[0].get("enemy_unit"))
        if enemy_root is None:
            logger.error("ERROR: HUNGRY FOR COMBAT: no enemy target provided")
            return False

        group = self._houndpack_hungry_for_combat_group_for_enemy(enemy_root)
        if group is None:
            logger.error("ERROR: HUNGRY FOR COMBAT: no eligible WAR DOG group is engaging that enemy")
            return False

        selected_units = self._resolve_houndpack_hungry_selected_units(
            merged.get("units")
            or merged.get("selected_units")
            or merged.get("unit_ids")
            or merged.get("selected_unit_ids")
        )
        if not selected_units:
            selected_units = list(group.get("units", []) or [])
        selected_ids = {self._chaos_knights_sort_key(unit) for unit in list(selected_units or [])}
        allowed_ids = {str(value or "") for value in list(group.get("unit_ids", []) or []) if str(value or "")}
        if len(selected_ids) < 2 or not selected_ids.issubset(allowed_ids):
            logger.error("ERROR: HUNGRY FOR COMBAT: must select two or more eligible WAR DOG units")
            return False

        first_target = selected_units[0] if selected_units else None
        if not self._chaos_knights_spend_cp(stratagem, target_unit=first_target):
            return False

        target_id = self._chaos_knights_sort_key(enemy_root)
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        current_owner = str(getattr(getattr(self.game, "get_current_player", lambda: None)(), "id", "") or "")
        for unit_root in list(selected_units or []):
            sr = getattr(unit_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["houndpack_hungry_for_combat_active"] = True
            sr["houndpack_hungry_for_combat_target_id"] = target_id
            sr["houndpack_hungry_for_combat_target_lock"] = True
            sr["houndpack_hungry_for_combat_crit_threshold"] = 5
            sr["houndpack_hungry_for_combat_expires_phase"] = "FIGHT_PHASE"
            sr["houndpack_hungry_for_combat_turn"] = int(current_turn or 0)
            sr["houndpack_hungry_for_combat_turn_owner"] = current_owner
            sr["houndpack_hungry_for_combat_source"] = str(getattr(stratagem, "name", "") or "HUNGRY FOR COMBAT")
            unit_root.special_rules = sr

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: HUNGRY FOR COMBAT: %d WAR DOG unit(s) are locked onto %s and score critical hits on 5+ in melee.",
            int(len(selected_units)),
            getattr(enemy_root, "name", "Enemy Unit"),
        )
        return True

    def _use_houndpack_cunning_hunter(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_houndpack_lance_detachment():
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            logger.error("ERROR: CUNNING HUNTER: no target unit provided")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: CUNNING HUNTER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
        if active_player is not self.player:
            logger.error("ERROR: CUNNING HUNTER: not your turn")
            return False
        action_key = str(merged.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key not in {"", "fall back", "fallback"}:
            logger.error("ERROR: CUNNING HUNTER: invalid trigger")
            return False
        if root not in list(self._houndpack_cunning_hunter_candidates() or []):
            logger.error("ERROR: CUNNING HUNTER: target is not an eligible WAR DOG unit")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["cunning_hunter_active"] = True
        sr["cunning_hunter_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["cunning_hunter_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        root.special_rules = sr

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: CUNNING HUNTER: %s can shoot and charge after Falling Back this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_houndpack_harrying_hounds(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_houndpack_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        enemy_root = self._chaos_knights_root(merged.get("enemy_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None or enemy_root is None:
            logger.error("ERROR: HARRYING HOUNDS: target unit or enemy trigger unit missing")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: HARRYING HOUNDS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: HARRYING HOUNDS: only usable in your opponent's Movement phase")
            return False
        action_key = str(merged.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key not in {"move", "normal", "normal move", "advance", "fall back", "fallback"}:
            logger.error("ERROR: HARRYING HOUNDS: invalid trigger action")
            return False
        if root not in list(self._houndpack_harrying_hounds_candidates(enemy_root) or []):
            logger.error("ERROR: HARRYING HOUNDS: target is not an eligible WAR DOG unit")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: HARRYING HOUNDS: reactive move queue unavailable")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind="chaos_knights_harrying_hounds",
            movement_type="move",
            reactive_movement_type="harrying_hounds",
            source=str(getattr(stratagem, "name", "HARRYING HOUNDS") or "HARRYING HOUNDS"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            range_value=9,
        )
        if request is None:
            logger.error("ERROR: HARRYING HOUNDS: failed to queue reactive move")
            return False
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: HARRYING HOUNDS: %s can make a Normal move of up to 6\".",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_houndpack_encircling_pack(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_houndpack_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: ENCIRCLING PACK: no target unit provided")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: ENCIRCLING PACK: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: ENCIRCLING PACK: only usable at the end of your opponent's Fight phase")
            return False
        if root not in list(self._houndpack_encircling_pack_candidates() or []):
            logger.error("ERROR: ENCIRCLING PACK: target is not an eligible WAR DOG unit")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        place_fn = getattr(root, "enter_strategic_reserves_midgame", None)
        if not callable(place_fn):
            logger.error("ERROR: ENCIRCLING PACK: Strategic Reserves placement helper unavailable")
            return False
        if not bool(place_fn(game=self.game, game_map=getattr(self.game, "map", None), reason=stratagem.name)):
            logger.error("ERROR: ENCIRCLING PACK: failed to place target into Strategic Reserves")
            return False
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: ENCIRCLING PACK: %s enters Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _is_chaos_knights_damned_unit(self, unit: Any) -> bool:
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        army = self._chaos_knights_army()
        if army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        if parent_army is not army:
            return False
        mgr = self._chaos_knights_detachment_manager()
        checker = getattr(mgr, "_unit_is_damned", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker(root))
            except Exception:
                return False
        has_any_kw = getattr(root, "has_any_keyword", None)
        return bool(has_any_kw("DAMNED")) if callable(has_any_kw) else False

    def _chaos_knights_is_battle_shocked(self, unit: Any) -> bool:
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        checker = getattr(root, "is_battle_shocked", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                return False
        return bool(getattr(root, "battle_shocked", False))

    def _chaos_knights_alive_models(self, unit: Any) -> List[Any]:
        root = self._chaos_knights_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        alive_models: List[Any] = []
        for model in list(models or []):
            if model is None:
                continue
            alive_value = getattr(model, "is_alive", True)
            try:
                alive = bool(alive_value() if callable(alive_value) else alive_value)
            except Exception:
                alive = False
            if alive:
                alive_models.append(model)
        alive_models.sort(key=lambda model: str(get_entity_id(model) or ""))
        return alive_models

    def _chaos_knights_unit_contains_character_member(self, unit: Any) -> bool:
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        has_any_kw = getattr(root, "has_any_keyword", None)
        if callable(has_any_kw) and bool(has_any_kw("CHARACTER")):
            return True
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        for member in list(members or []):
            has_any_kw = getattr(member, "has_any_keyword", None)
            if callable(has_any_kw) and bool(has_any_kw("CHARACTER")):
                return True
        return False

    def _iconoclast_is_accursed_cultists_unit(self, unit: Any) -> bool:
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        return "ACCURSED CULTISTS" in self._chaos_knights_normalize_name(getattr(root, "name", "") or "")

    def _chaos_knights_heal_lost_wounds(self, unit: Any, amount: int) -> int:
        root = self._chaos_knights_root(unit)
        if root is None:
            return 0
        try:
            remaining = max(0, int(amount or 0))
        except Exception:
            remaining = 0
        if remaining <= 0:
            return 0
        healed = 0
        for model in list(self._chaos_knights_alive_models(root) or []):
            base_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)) or 0)
            current_wounds = int(getattr(model, "wounds", 0) or 0)
            lost = max(0, int(base_wounds - current_wounds))
            if lost <= 0:
                continue
            heal_now = min(int(remaining), int(lost))
            if heal_now <= 0:
                continue
            heal_fn = getattr(model, "heal", None)
            if callable(heal_fn):
                try:
                    heal_fn(int(heal_now))
                except Exception:
                    continue
            else:
                model.wounds = min(base_wounds, current_wounds + heal_now)
            healed += int(heal_now)
            remaining -= int(heal_now)
            if remaining <= 0:
                break
        return int(healed)

    def _chaos_knights_copy_model_wargear(self, source_unit: Any, target_unit: Any) -> None:
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

    def _clone_iconoclast_wretched_masses_unit(self, unit: Any) -> Any:
        if unit is None:
            return None
        clone_hook = getattr(unit, "clone_for_cult_ambush", None)
        if callable(clone_hook):
            return clone_hook()
        try:
            from ..units.unit import Unit as UnitClass
        except ImportError:
            return None
        datasheet = getattr(unit, "_datasheet", None)
        if datasheet is None:
            return None
        count = int(getattr(unit, "starting_model_count", 0) or 0)
        if count <= 0:
            count = len(list(getattr(unit, "models", []) or []))
        if count <= 0:
            count = len(list(getattr(unit, "models_lost", []) or []))
        if count <= 0:
            return None
        try:
            new_unit = UnitClass(datasheet, quantity=count, enhancement=getattr(unit, "enhancement", None))
        except TypeError:
            new_unit = UnitClass(datasheet, quantity=count)
        self._chaos_knights_copy_model_wargear(unit, new_unit)
        new_unit.is_warlord = bool(getattr(unit, "is_warlord", False))
        return new_unit

    def _prepare_iconoclast_wretched_masses_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        army = self._chaos_knights_army()
        if army is None:
            return False
        set_parent = getattr(unit, "set_parent_army", None)
        if callable(set_parent):
            set_parent(army)
        else:
            unit.parent_army = army
        set_reserve = getattr(unit, "set_reserve_status", None)
        if callable(set_reserve):
            set_reserve("strategic_reserves")
        else:
            unit.reserve_status = "strategic_reserves"
        mark_midgame = getattr(unit, "mark_entered_reserves_midgame", None)
        if callable(mark_midgame):
            mark_midgame(game=self.game)
        unit.deployed = True
        unit.reserve_turn_deployed = None
        unit.arrived_from_reserves_this_turn = False
        if hasattr(army, "add_unit"):
            army.add_unit(unit)
        else:
            army.units.append(unit)
        rebuild_registry = getattr(self.game, "rebuild_entity_registry", None) if self.game is not None else None
        if callable(rebuild_registry):
            rebuild_registry()
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is not None and isinstance(getattr(game_map, "units", None), list) and unit in game_map.units:
            game_map.units.remove(unit)
        return True

    def _iconoclast_unrestrained_rage_candidates(self, *, require_advanced: bool = False, require_fell_back: bool = False) -> List[Any]:
        if not self._is_iconoclast_fiefdom():
            return []
        candidates: List[Any] = []
        for root in list(self._chaos_knights_unit_candidates() or []):
            round_state = getattr(root, "round_state", None)
            if require_advanced and not bool(getattr(round_state, "advanced_this_round", False)):
                continue
            if require_fell_back and not bool(getattr(round_state, "fell_back_this_round", False)):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _iconoclast_preserve_the_idols_pairs(self, enemy_unit: Any) -> List[Dict[str, Any]]:
        if not self._is_iconoclast_fiefdom() or self.game is None:
            return []
        enemy_root = self._chaos_knights_root(enemy_unit)
        if enemy_root is None:
            return []
        source_units: List[Any] = []
        for root in list(self._chaos_knights_unit_candidates() or []):
            distance = self._chaos_knights_distance_between_units(root, enemy_root)
            if distance is None or distance > 9.0 + 1e-6:
                continue
            source_units.append(root)
        if not source_units:
            return []
        army = self._chaos_knights_army()
        if army is None:
            return []
        pair_by_unit_id: Dict[str, Dict[str, Any]] = {}
        seen_roots: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            damned_root = self._chaos_knights_root(unit)
            if damned_root is None:
                continue
            damned_id = self._chaos_knights_sort_key(damned_root)
            if not damned_id or damned_id in seen_roots:
                continue
            seen_roots.add(damned_id)
            if not self._is_chaos_knights_damned_unit(damned_root):
                continue
            if not self._chaos_knights_on_battlefield(damned_root, require_targetable=True):
                continue
            if self._chaos_knights_is_battle_shocked(damned_root):
                continue
            if self._chaos_knights_in_engagement_range(damned_root):
                continue
            chosen_source = None
            chosen_source_id = ""
            for source_root in list(source_units or []):
                distance = self._chaos_knights_distance_between_units(damned_root, source_root)
                if distance is None or distance > 6.0 + 1e-6:
                    continue
                source_id = self._chaos_knights_sort_key(source_root)
                if chosen_source is None or source_id < chosen_source_id:
                    chosen_source = source_root
                    chosen_source_id = source_id
            if chosen_source is None:
                continue
            pair_by_unit_id[damned_id] = {
                "unit": damned_root,
                "unit_id": damned_id,
                "source_unit": chosen_source,
                "source_unit_id": chosen_source_id,
            }
        pairs = list(pair_by_unit_id.values())
        pairs.sort(key=lambda item: (str(item.get("unit_id", "") or ""), str(item.get("source_unit_id", "") or "")))
        return pairs

    def _iconoclast_worthless_chattel_has_pending_decision(self, *, unit_id: str) -> bool:
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
            if str(ctx.get("target_unit_id", "") or "") != str(unit_id or ""):
                continue
            return True
        return False

    def _queue_iconoclast_fiefdom_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_iconoclast_fiefdom() or self.game is None:
            return
        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        moving_root = self._chaos_knights_root(unit)

        if active_player is self.player:
            if action_key not in {"advance", "fall back", "fallback"}:
                return
            stratagem = self.get_by_name("UNRESTRAINED RAGE")
            if stratagem is None or moving_root is None:
                return
            if not self._chaos_knights_owned_by_player(moving_root, self.player):
                return
            if action_key == "advance":
                if moving_root not in list(self._iconoclast_unrestrained_rage_candidates(require_advanced=True) or []):
                    return
            else:
                if moving_root not in list(self._iconoclast_unrestrained_rage_candidates(require_fell_back=True) or []):
                    return
            if self._chaos_knights_reaction_exists("unit_move_ended", stratagem.name):
                return
            if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._chaos_knights_effective_cp_cost(
                stratagem,
                target_unit=moving_root,
            ):
                return
            self._queue_reaction(
                {
                    "event": "unit_move_ended",
                    "phase_name": "Movement phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "unit": moving_root,
                    "target_unit": moving_root,
                    "action": action,
                },
                use_timer=False,
            )
            return

        if action_key not in {"move", "normal", "normal move", "advance", "fall back", "fallback"}:
            return
        if moving_root is None:
            return
        try:
            if moving_root.get_parent_army().player is self.player:
                return
        except Exception:
            return
        stratagem = self.get_by_name("PRESERVE THE IDOLS")
        if stratagem is None:
            return
        if self._chaos_knights_reaction_exists("unit_move_ended", stratagem.name):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        pairs = list(self._iconoclast_preserve_the_idols_pairs(moving_root) or [])
        if not pairs:
            return
        first_target = pairs[0].get("source_unit") or pairs[0].get("unit")
        if int(getattr(self.player, "command_points", 0) or 0) < self._chaos_knights_effective_cp_cost(
            stratagem,
            target_unit=first_target,
        ):
            return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": moving_root,
            "candidates": [pair["unit"] for pair in list(pairs or [])],
            "candidate_source_unit_ids": {
                str(pair.get("unit_id", "") or ""): str(pair.get("source_unit_id", "") or "")
                for pair in list(pairs or [])
                if str(pair.get("unit_id", "") or "") and str(pair.get("source_unit_id", "") or "")
            },
            "action": action,
        }
        if len(pairs) == 1:
            payload["unit"] = pairs[0]["unit"]
            payload["target_unit"] = pairs[0]["unit"]
            payload["source_unit_id"] = pairs[0]["source_unit_id"]
        self._queue_reaction(payload, use_timer=False)

    def _queue_iconoclast_fiefdom_unit_destroyed_reactions(
        self,
        *,
        destroyed_unit: Any,
        destroyed_by_unit: Any = None,
    ) -> None:
        if not self._is_iconoclast_fiefdom() or self.game is None:
            return
        root = self._chaos_knights_root(destroyed_unit)
        if root is None or not self._chaos_knights_owned_by_player(root, self.player):
            return
        phase_name = str(self._current_phase_name or "").strip() or self._chaos_knights_phase_label(
            str(getattr(getattr(self.game, "phase", None), "name", "") or "")
        )

        avenge = self.get_by_name("AVENGE THE MASTERS!")
        destroyer_root = self._chaos_knights_root(destroyed_by_unit)
        if (
            avenge is not None
            and self._is_chaos_knights_unit(root)
            and destroyer_root is not None
            and not self._chaos_knights_owned_by_player(destroyer_root, self.player)
            and not self._chaos_knights_reaction_exists("unit_destroyed", avenge.name)
            and (avenge.name or "").strip().upper() not in self._used_stratagems_this_phase
            and int(getattr(self.player, "command_points", 0) or 0)
            >= self._chaos_knights_effective_cp_cost(avenge, target_unit=root)
        ):
            self._queue_reaction(
                {
                    "event": "unit_destroyed",
                    "phase_name": phase_name,
                    "stratagem": avenge.name,
                    "cp_cost": avenge.cp_cost,
                    "unit": root,
                    "target_unit": root,
                    "enemy_unit": destroyer_root,
                },
                use_timer=False,
            )

        wretched = self.get_by_name("WRETCHED MASSES")
        if wretched is None:
            return
        if bool(getattr(self, "_iconoclast_wretched_masses_used", False)):
            return
        if not self._is_chaos_knights_damned_unit(root):
            return
        if self._iconoclast_is_accursed_cultists_unit(root):
            return
        if self._chaos_knights_is_alive(root):
            return
        if self._chaos_knights_reaction_exists("unit_destroyed", wretched.name):
            return
        if (wretched.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._chaos_knights_effective_cp_cost(
            wretched,
            target_unit=root,
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": phase_name,
                "stratagem": wretched.name,
                "cp_cost": wretched.cp_cost,
                "unit": root,
                "target_unit": root,
            },
            use_timer=False,
        )

    def _queue_iconoclast_fiefdom_fight_attacks_resolved_reactions(
        self,
        *,
        unit: Any,
        target_unit: Any = None,
        killing_models_by_target: Any = None,
    ) -> None:
        del target_unit
        if not self._is_iconoclast_fiefdom() or self.game is None:
            return
        if (self._current_phase_name or "").strip().lower() != "fight phase":
            return
        root = self._chaos_knights_root(unit)
        if root is None or not self._chaos_knights_owned_by_player(root, self.player):
            return
        if not self._is_chaos_knights_unit(root):
            return
        kill_map = killing_models_by_target if isinstance(killing_models_by_target, dict) else {}
        if not kill_map:
            return
        battle_shocked_kills = False
        destroyed_any = False
        for target in sorted(list(kill_map), key=self._chaos_knights_sort_key):
            target_root = self._chaos_knights_root(target)
            if target_root is None or self._chaos_knights_owned_by_player(target_root, self.player):
                continue
            killed_models = kill_map.get(target)
            if not killed_models:
                continue
            destroyed_any = True
            if self._chaos_knights_is_battle_shocked(target_root):
                battle_shocked_kills = True
                break
        if not destroyed_any:
            return
        stratagem = self.get_by_name("SOUL HUNGER")
        if stratagem is None:
            return
        if self._chaos_knights_reaction_exists("fight_attacks_resolved", stratagem.name):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._chaos_knights_effective_cp_cost(
            stratagem,
            target_unit=root,
        ):
            return
        self._queue_reaction(
            {
                "event": "fight_attacks_resolved",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "battle_shocked_kills": bool(battle_shocked_kills),
            },
            use_timer=False,
        )

    def _resolve_iconoclast_worthless_chattel_after_shooting(
        self,
        *,
        attacker_unit: Any,
        damage_by_target_while_engaged: dict[Any, int] | None,
    ) -> None:
        if not self._is_iconoclast_fiefdom() or self.game is None:
            return
        if (self._current_phase_name or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._chaos_knights_root(attacker_unit)
        if attacker_root is None or not self._chaos_knights_owned_by_player(attacker_root, self.player):
            return
        if not self._is_chaos_knights_damned_unit(attacker_root):
            return
        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("iconoclast_worthless_chattel_active"):
            return
        exp = str(sr.get("iconoclast_worthless_chattel_expires_phase", "") or "").strip().upper()
        if exp and exp != "SHOOTING_PHASE":
            return
        owner = str(sr.get("iconoclast_worthless_chattel_turn_owner", "") or "")
        if owner and owner != str(getattr(self.player, "id", "") or ""):
            return
        damage_map = damage_by_target_while_engaged if isinstance(damage_by_target_while_engaged, dict) else {}
        if not damage_map:
            return
        total_rolls = 0
        for target in sorted(list(damage_map), key=self._chaos_knights_sort_key):
            target_root = self._chaos_knights_root(target)
            if target_root is None or self._chaos_knights_owned_by_player(target_root, self.player):
                continue
            try:
                total_rolls += max(0, int(damage_map.get(target, 0) or 0))
            except (TypeError, ValueError):
                continue
        if total_rolls <= 0:
            return
        destroy_count = 0
        for _ in range(int(total_rolls)):
            roll = int(get_roll("D6") or 0)
            if roll >= 4:
                destroy_count += 1
        alive_models = list(self._chaos_knights_alive_models(attacker_root) or [])
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
                    f"{getattr(attacker_root, 'name', 'Unit')}: Worthless Chattel destroys 1 model after shooting.",
                )
            return
        unit_id = self._chaos_knights_sort_key(attacker_root)
        if self._iconoclast_worthless_chattel_has_pending_decision(unit_id=unit_id):
            return
        from ..engine.decision_kinds import DECISION_SELECT_TARGET_MODEL
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [
            DecisionOption.create(
                str(getattr(model, "name", "Model") or "Model"),
                payload={"model_id": get_entity_id(model)},
            )
            for model in list(alive_models or [])
        ]
        if not options:
            return
        request = DecisionRequest.create(
            DECISION_SELECT_TARGET_MODEL,
            f"Worthless Chattel: select a model to destroy ({int(destroy_count)} remaining).",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "selection_kind": "worthless_chattel_destroy",
                "target_unit_id": unit_id,
                "destroy_remaining": int(destroy_count),
                "ability_name": "Worthless Chattel",
            },
        )
        try:
            self.game.request_decision(request)
        except Exception:
            queue = getattr(self.game, "decision_queue", None)
            if queue is not None and hasattr(queue, "add"):
                queue.add(request)

    def _use_iconoclast_avenge_the_masters(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_iconoclast_fiefdom():
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        enemy_root = self._chaos_knights_root(merged.get("enemy_unit"))
        if root is None:
            logger.error("ERROR: AVENGE THE MASTERS!: no destroyed CHAOS KNIGHTS unit provided")
            return False
        if enemy_root is None:
            logger.error("ERROR: AVENGE THE MASTERS!: destroying enemy unit is missing")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: AVENGE THE MASTERS!: target must be a CHAOS KNIGHTS unit")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: AVENGE THE MASTERS!: target unit is not yours")
            return False
        if self._chaos_knights_is_alive(root):
            logger.error("ERROR: AVENGE THE MASTERS!: target unit was not destroyed")
            return False
        if self._chaos_knights_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: AVENGE THE MASTERS!: destroying unit must be an enemy unit")
            return False
        mgr = self._chaos_knights_detachment_manager()
        if mgr is None:
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        mark_enemy = getattr(mgr, "mark_iconoclast_avenged_enemy", None)
        if not callable(mark_enemy) or not bool(mark_enemy(enemy_root)):
            logger.error("ERROR: AVENGE THE MASTERS!: failed to mark the destroying enemy unit")
            return False
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: AVENGE THE MASTERS!: %s is Marked until the end of the battle.",
            getattr(enemy_root, "name", "Enemy Unit"),
        )
        return True

    def _use_iconoclast_wretched_masses(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_iconoclast_fiefdom():
            return False
        if bool(getattr(self, "_iconoclast_wretched_masses_used", False)):
            logger.error("ERROR: WRETCHED MASSES: already used this battle")
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            logger.error("ERROR: WRETCHED MASSES: no target unit provided")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: WRETCHED MASSES: target unit is not yours")
            return False
        if self._chaos_knights_is_alive(root):
            logger.error("ERROR: WRETCHED MASSES: target unit was not destroyed")
            return False
        if not self._is_chaos_knights_damned_unit(root):
            logger.error("ERROR: WRETCHED MASSES: target must be a DAMNED unit")
            return False
        if self._iconoclast_is_accursed_cultists_unit(root):
            logger.error("ERROR: WRETCHED MASSES: ACCURSED CULTISTS are excluded")
            return False
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if len(members) > 1 and self._chaos_knights_unit_contains_character_member(root):
            logger.error("ERROR: WRETCHED MASSES: cannot return destroyed CHARACTER Attached units")
            return False
        cloned = self._clone_iconoclast_wretched_masses_unit(root)
        if cloned is None:
            logger.error("ERROR: WRETCHED MASSES: failed to clone destroyed unit")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        if not self._prepare_iconoclast_wretched_masses_unit(cloned):
            logger.error("ERROR: WRETCHED MASSES: failed to place cloned unit into Strategic Reserves")
            return False
        self._iconoclast_wretched_masses_used = True
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: WRETCHED MASSES: added a new %s unit to Strategic Reserves at Starting Strength.",
            getattr(cloned, "name", "Unit"),
        )
        return True

    def _use_iconoclast_soul_hunger(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_iconoclast_fiefdom():
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            logger.error("ERROR: SOUL HUNGER: no target unit provided")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: SOUL HUNGER: target unit is not yours")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: SOUL HUNGER: target must be a CHAOS KNIGHTS unit")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SOUL HUNGER: wrong phase")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SOUL HUNGER: target unit is not on the battlefield")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        heal_amount = int(get_roll("D3") or 0)
        if bool(merged.get("battle_shocked_kills", False)):
            heal_amount += 2
        healed = self._chaos_knights_heal_lost_wounds(root, heal_amount)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: SOUL HUNGER: %s regains up to %d lost wound(s) (%d restored).",
            getattr(root, "name", "Unit"),
            int(heal_amount),
            int(healed),
        )
        return True

    def _use_iconoclast_unrestrained_rage(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_iconoclast_fiefdom() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            logger.error("ERROR: UNRESTRAINED RAGE: no target unit provided")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: UNRESTRAINED RAGE: target unit is not yours")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: UNRESTRAINED RAGE: target must be a CHAOS KNIGHTS unit")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: UNRESTRAINED RAGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: UNRESTRAINED RAGE: not your turn")
            return False
        action_key = str(merged.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key not in {"advance", "fall back", "fallback"}:
            logger.error("ERROR: UNRESTRAINED RAGE: invalid trigger action")
            return False
        if action_key == "advance":
            if root not in list(self._iconoclast_unrestrained_rage_candidates(require_advanced=True) or []):
                logger.error("ERROR: UNRESTRAINED RAGE: target unit did not Advance")
                return False
            move_mode = "advance"
        else:
            if root not in list(self._iconoclast_unrestrained_rage_candidates(require_fell_back=True) or []):
                logger.error("ERROR: UNRESTRAINED RAGE: target unit did not Fall Back")
                return False
            move_mode = "fall_back"
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["iconoclast_unrestrained_rage_active"] = True
        sr["iconoclast_unrestrained_rage_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["iconoclast_unrestrained_rage_turn"] = int(getattr(self.game, "turn", 0) or 0)
        sr["iconoclast_unrestrained_rage_move_mode"] = move_mode
        sr["iconoclast_unrestrained_rage_source"] = str(getattr(stratagem, "name", "") or "UNRESTRAINED RAGE")
        root.special_rules = sr
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: UNRESTRAINED RAGE: %s can shoot and charge after %s this turn.",
            getattr(root, "name", "Unit"),
            "Advancing" if move_mode == "advance" else "Falling Back",
        )
        return True

    def _use_iconoclast_worthless_chattel(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_iconoclast_fiefdom() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: WORTHLESS CHATTEL: no target unit provided")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: WORTHLESS CHATTEL: target unit is not yours")
            return False
        if not self._is_chaos_knights_damned_unit(root):
            logger.error("ERROR: WORTHLESS CHATTEL: target must be a DAMNED unit")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: WORTHLESS CHATTEL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: WORTHLESS CHATTEL: not your turn")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: WORTHLESS CHATTEL: target must be an eligible battlefield unit")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["iconoclast_worthless_chattel_active"] = True
        sr["iconoclast_worthless_chattel_expires_phase"] = "SHOOTING_PHASE"
        sr["iconoclast_worthless_chattel_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["iconoclast_worthless_chattel_turn"] = int(getattr(self.game, "turn", 0) or 0)
        sr["iconoclast_worthless_chattel_source"] = str(getattr(stratagem, "name", "") or "WORTHLESS CHATTEL")
        root.special_rules = sr
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: WORTHLESS CHATTEL: %s ignores its own Engagement Range for ranged target selection this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_iconoclast_preserve_the_idols(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_iconoclast_fiefdom() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        enemy_root = self._chaos_knights_root(merged.get("enemy_unit"))
        if root is None or enemy_root is None:
            logger.error("ERROR: PRESERVE THE IDOLS: target unit or enemy trigger unit missing")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: PRESERVE THE IDOLS: target unit is not yours")
            return False
        if not self._is_chaos_knights_damned_unit(root):
            logger.error("ERROR: PRESERVE THE IDOLS: selected moving unit must be a DAMNED unit")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: PRESERVE THE IDOLS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: PRESERVE THE IDOLS: only usable in your opponent's Movement phase")
            return False
        action_key = str(merged.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key not in {"move", "normal", "normal move", "advance", "fall back", "fallback"}:
            logger.error("ERROR: PRESERVE THE IDOLS: invalid trigger action")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: PRESERVE THE IDOLS: selected DAMNED unit is not eligible")
            return False
        if self._chaos_knights_is_battle_shocked(root):
            logger.error("ERROR: PRESERVE THE IDOLS: selected DAMNED unit is Battle-shocked")
            return False
        if self._chaos_knights_in_engagement_range(root):
            logger.error("ERROR: PRESERVE THE IDOLS: selected DAMNED unit is within Engagement Range")
            return False
        unit_id = self._chaos_knights_sort_key(root)
        candidate_source_ids = dict(merged.get("candidate_source_unit_ids", {}) or {})
        source_unit_id = str(
            merged.get("source_unit_id")
            or candidate_source_ids.get(unit_id, "")
            or ""
        ).strip()
        source_root = self._chaos_knights_root(merged.get("source_unit"))
        if source_root is None and source_unit_id:
            source_root = self._chaos_knights_resolve_unit(source_unit_id)
        if source_root is None:
            logger.error("ERROR: PRESERVE THE IDOLS: source CHAOS KNIGHTS unit is missing")
            return False
        if not self._chaos_knights_owned_by_player(source_root, self.player):
            logger.error("ERROR: PRESERVE THE IDOLS: source unit is not yours")
            return False
        if not self._is_chaos_knights_unit(source_root):
            logger.error("ERROR: PRESERVE THE IDOLS: source unit must be a CHAOS KNIGHTS unit")
            return False
        if not self._chaos_knights_on_battlefield(source_root, require_targetable=True):
            logger.error("ERROR: PRESERVE THE IDOLS: source CHAOS KNIGHTS unit is not eligible")
            return False
        source_distance = self._chaos_knights_distance_between_units(source_root, enemy_root)
        if source_distance is None or source_distance > 9.0 + 1e-6:
            logger.error("ERROR: PRESERVE THE IDOLS: source unit must be within 9\" of the enemy trigger unit")
            return False
        damned_distance = self._chaos_knights_distance_between_units(root, source_root)
        if damned_distance is None or damned_distance > 6.0 + 1e-6:
            logger.error("ERROR: PRESERVE THE IDOLS: selected DAMNED unit must be within 6\" of the source unit")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: PRESERVE THE IDOLS: reactive move queue unavailable")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=source_root):
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind="chaos_knights_preserve_the_idols",
            movement_type="move",
            reactive_movement_type="preserve_the_idols",
            source=str(getattr(stratagem, "name", "PRESERVE THE IDOLS") or "PRESERVE THE IDOLS"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            range_value=9,
            allow_engagement_range=False,
            extra_context={
                "preserve_the_idols_enemy_unit_id": self._chaos_knights_sort_key(enemy_root),
                "preserve_the_idols_source_unit_id": self._chaos_knights_sort_key(source_root),
            },
        )
        if request is None:
            logger.error("ERROR: PRESERVE THE IDOLS: failed to queue reactive move")
            return False
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: PRESERVE THE IDOLS: %s can make a Normal move of up to 6\".",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_chaos_knights_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_key = self._chaos_knights_normalize_name(getattr(stratagem, "name", "") or "")
        if name_key == "VOX-HOWL":
            return self._use_houndpack_vox_howl(stratagem, **kwargs)
        if name_key == "HUNGRY FOR COMBAT":
            return self._use_houndpack_hungry_for_combat(stratagem, **kwargs)
        if name_key == "CUNNING HUNTER":
            return self._use_houndpack_cunning_hunter(stratagem, **kwargs)
        if name_key == "HARRYING HOUNDS":
            return self._use_houndpack_harrying_hounds(stratagem, **kwargs)
        if name_key == "ENCIRCLING PACK":
            return self._use_houndpack_encircling_pack(stratagem, **kwargs)
        if name_key == "AVENGE THE MASTERS!":
            return self._use_iconoclast_avenge_the_masters(stratagem, **kwargs)
        if name_key == "WRETCHED MASSES":
            return self._use_iconoclast_wretched_masses(stratagem, **kwargs)
        if name_key == "SOUL HUNGER":
            return self._use_iconoclast_soul_hunger(stratagem, **kwargs)
        if name_key == "UNRESTRAINED RAGE":
            return self._use_iconoclast_unrestrained_rage(stratagem, **kwargs)
        if name_key == "WORTHLESS CHATTEL":
            return self._use_iconoclast_worthless_chattel(stratagem, **kwargs)
        if name_key == "PRESERVE THE IDOLS":
            return self._use_iconoclast_preserve_the_idols(stratagem, **kwargs)
        return None
