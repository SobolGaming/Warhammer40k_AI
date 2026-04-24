from __future__ import annotations

import logging
import re
from types import SimpleNamespace
from typing import Any

from shapely.geometry import Point

from ..utility import dice as dice_module
from ..utility.aura_utils import (
    distance_between_models_bases_3d,
    horizontal_distance_between_bases_2d,
    unit_within_range_of_unit,
    unit_within_range_of_point_3d,
    vertical_distance_between_bases,
)
from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class DeathGuardStratagemMixin:
    @staticmethod
    def _dg_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _dg_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    @staticmethod
    def _dg_phase_key(value: Any) -> str:
        text = str(value or "").strip().upper().replace(" ", "_")
        return re.sub(r"\s+", "_", text)

    def _dg_current_phase_key(self) -> str:
        phase = getattr(self.game, "phase", None) if getattr(self, "game", None) is not None else None
        phase_name = getattr(phase, "name", phase)
        if phase_name:
            return self._dg_phase_key(phase_name)
        return self._dg_phase_key(getattr(self, "_current_phase_name", "") or "")

    def _dg_current_turn(self) -> int:
        return int(getattr(getattr(self, "game", None), "turn", 0) or 0)

    def _dg_turn_owner_id(self) -> str:
        game = getattr(self, "game", None)
        if game is None:
            return str(getattr(self.player, "id", "") or "")
        get_current_player = getattr(game, "get_current_player", None)
        current_player = get_current_player() if callable(get_current_player) else None
        current_owner = str(getattr(current_player, "id", "") or "")
        return current_owner or str(getattr(self.player, "id", "") or "")

    def _dg_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "death_guard_detachments", None)

    def _is_champions_of_contagion_detachment(self) -> bool:
        mgr = self._dg_detachment_mgr()
        checker = getattr(mgr, "is_champions_of_contagion", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_death_lords_chosen_detachment(self) -> bool:
        mgr = self._dg_detachment_mgr()
        checker = getattr(mgr, "is_death_lords_chosen", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_flyblown_host_detachment(self) -> bool:
        mgr = self._dg_detachment_mgr()
        checker = getattr(mgr, "is_flyblown_host", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_mortarions_hammer_detachment(self) -> bool:
        mgr = self._dg_detachment_mgr()
        checker = getattr(mgr, "is_mortarions_hammer", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_shamblerot_vectorium_detachment(self) -> bool:
        mgr = self._dg_detachment_mgr()
        checker = getattr(mgr, "is_shamblerot_vectorium", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tallyband_summoners_detachment(self) -> bool:
        mgr = self._dg_detachment_mgr()
        checker = getattr(mgr, "is_tallyband_summoners", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _dg_has_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        token = str(keyword or "").strip()
        if not token:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(token)):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and bool(has_kw(token)):
            return True
        return False

    def _dg_owned_by_player(self, unit: Any, player: Any) -> bool:
        root = self._dg_root(unit)
        if root is None or player is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        return getattr(army, "player", None) is player

    def _dg_is_death_guard_unit(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        if not self._dg_owned_by_player(root, self.player):
            return False
        return self._dg_has_keyword(root, "DEATH GUARD")

    def _dg_is_death_guard_character_unit(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        return self._dg_is_death_guard_unit(root) and self._dg_has_keyword(root, "CHARACTER")

    def _dg_is_attached_unit(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        members_fn = getattr(root, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [root]
        return len(list(members or [])) > 1

    def _dg_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        if require_targetable:
            active_fn = getattr(root, "is_active_for_rules", None)
            if callable(active_fn) and not bool(active_fn()):
                return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if str(getattr(root, "reserve_status", "deployed")) != "deployed":
            return False
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        return True

    def _dg_is_unit_engaged(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(within_engagement):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._dg_root(enemy)
            if enemy_root is None:
                continue
            if bool(within_engagement(root, enemy_root)):
                return True
        return False

    def _dg_unit_not_selected_for_phase_action(self, unit: Any, *, phase_key: str) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        phase_u = self._dg_phase_key(phase_key)
        if phase_u == "SHOOTING_PHASE":
            return not bool(getattr(round_state, "shot_this_round", False))
        if phase_u == "FIGHT_PHASE":
            return not bool(getattr(round_state, "fought_this_phase", False))
        return True

    @staticmethod
    def _dg_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    @staticmethod
    def _dg_selected_to_charge_this_phase(unit: Any) -> bool:
        return bool(getattr(getattr(unit, "round_state", None), "attempted_charge_this_round", False))

    def _dg_effective_cp_cost(self, stratagem, *, target_unit=None) -> int:
        cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        if hasattr(self.player, "apply_stratagem_cp_cost"):
            result = self.player.apply_stratagem_cp_cost(stratagem, target_unit=target_unit)
            cost = int(result.get("cost", cost))
        return int(cost)

    def _dg_finalize_use(self, stratagem, *, dequeue: bool) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    @staticmethod
    def _dg_merge_phase_move_types(
        special_rules: dict[str, Any],
        rule_key: str,
        added_key: str,
        values: set[str],
    ) -> None:
        current = set(special_rules.get(rule_key) or [])
        added = sorted([move_type for move_type in values if move_type not in current])
        merged = sorted(current.union(set(values)))
        if merged:
            special_rules[rule_key] = merged
        else:
            special_rules.pop(rule_key, None)
        if added:
            special_rules[added_key] = added
        else:
            special_rules.pop(added_key, None)

    @staticmethod
    def _dg_remove_phase_move_types(
        special_rules: dict[str, Any],
        rule_key: str,
        added_key: str,
    ) -> None:
        added = set(special_rules.get(added_key) or [])
        if not added:
            return
        current = list(special_rules.get(rule_key) or [])
        kept = [item for item in current if item not in added]
        if kept:
            special_rules[rule_key] = kept
        else:
            special_rules.pop(rule_key, None)
        special_rules.pop(added_key, None)

    def _dg_append_temp_effect(self, unit: Any, effect: dict) -> None:
        root = self._dg_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        existing = list(sr.get("death_guard_temp_effects", []) or [])
        effect_id = str(effect.get("id", "") or "").strip()
        kept: list[dict] = []
        for entry in list(existing or []):
            if not isinstance(entry, dict):
                continue
            if effect_id and str(entry.get("id", "") or "").strip() == effect_id:
                continue
            kept.append(dict(entry))
        kept.append(dict(effect))
        kept.sort(key=lambda entry: str(entry.get("id", "") or ""))
        sr["death_guard_temp_effects"] = kept
        root.special_rules = sr

    def _dg_apply_temp_effects(
        self,
        unit: Any,
        *,
        detachment: str,
        phase_key: str,
        effects: list[dict],
    ) -> None:
        owner_id = self._dg_turn_owner_id()
        turn = self._dg_current_turn()
        unit_id = self._dg_sort_key(self._dg_root(unit))
        for index, entry in enumerate(list(effects or [])):
            if not isinstance(entry, dict):
                continue
            payload = dict(entry)
            payload.setdefault("detachment", str(detachment or ""))
            payload.setdefault("expires_mode", "phase")
            payload.setdefault("turn_owner_id", owner_id)
            payload.setdefault("turn", int(turn))
            payload.setdefault("expires_phase", str(phase_key or ""))
            effect_id = str(payload.get("id", "") or "").strip()
            if not effect_id:
                source_key = str(payload.get("source", "death_guard_effect") or "death_guard_effect").strip().lower()
                source_key = re.sub(r"[^a-z0-9]+", "_", source_key).strip("_") or "death_guard_effect"
                effect_id = f"{source_key}:{unit_id}:{int(turn)}:{str(phase_key or '').lower()}:{index}"
            payload["id"] = effect_id
            self._dg_append_temp_effect(unit, payload)

    @staticmethod
    def _dg_normalize_name(text: str) -> str:
        value = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
        return re.sub(r"\s+", " ", value).strip()

    def _dg_unit_contains_named_member(self, unit: Any, token: str) -> bool:
        root = self._dg_root(unit)
        token_norm = self._dg_normalize_name(token)
        if root is None or not token_norm:
            return False
        names = [getattr(root, "name", "")]
        members_fn = getattr(root, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [root]
        for member in list(members or []):
            names.append(getattr(member, "name", ""))
        for name in list(names or []):
            if token_norm in self._dg_normalize_name(name):
                return True
        return False

    def _dg_named_member_unit(self, unit: Any, token: str) -> Any:
        root = self._dg_root(unit)
        token_norm = self._dg_normalize_name(token)
        if root is None or not token_norm:
            return None
        members_fn = getattr(root, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [root]
        members = sorted(list(members or []), key=self._dg_sort_key)
        for member in members:
            name_norm = self._dg_normalize_name(getattr(member, "name", "") or "")
            if token_norm and token_norm in name_norm:
                return member
        root_name = self._dg_normalize_name(getattr(root, "name", "") or "")
        if token_norm and token_norm in root_name:
            return root
        return None

    def _dg_resolve_unit_by_id(self, unit_id: str) -> Any:
        target = str(unit_id or "").strip()
        if not target:
            return None
        game = getattr(self, "game", None)
        resolver = getattr(game, "_resolve_unit_by_id", None) if game is not None else None
        if callable(resolver):
            resolved = resolver(target)
            root = self._dg_root(resolved)
            if root is not None:
                return root
        game_map = getattr(game, "map", None) if game is not None else None
        for unit in list(getattr(game_map, "units", []) or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            if self._dg_sort_key(root) == target:
                return root
        for player in list(getattr(game, "players", []) or []):
            army = getattr(player, "army", None)
            if army is None and hasattr(player, "get_army"):
                army = player.get_army()
            for unit in list(getattr(army, "units", []) or []):
                root = self._dg_root(unit)
                if root is None:
                    continue
                if self._dg_sort_key(root) == target:
                    return root
        return None

    def _dg_unit_is_poxwalkers(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        mgr = self._dg_detachment_mgr()
        checker = getattr(mgr, "_unit_is_poxwalkers", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker(root))
            except Exception:
                pass
        if self._dg_has_keyword(root, "POXWALKERS"):
            return True
        return "poxwalker" in self._dg_normalize_name(getattr(root, "name", "") or "")

    def _dg_unit_is_plague_legions(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        if not self._dg_owned_by_player(root, self.player):
            return False
        mgr = self._dg_detachment_mgr()
        checker = getattr(mgr, "_unit_is_plague_legions", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._dg_has_keyword(root, "PLAGUE LEGIONS")

    def _dg_unit_is_nurglings(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        if not self._dg_unit_is_plague_legions(root):
            return False
        if self._dg_has_keyword(root, "NURGLINGS"):
            return True
        return "nurgling" in self._dg_normalize_name(getattr(root, "name", "") or "")

    @staticmethod
    def _dg_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        alive_attr = getattr(model, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    def _dg_alive_models(self, unit: Any) -> list[Any]:
        root = self._dg_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(root, "models", []) or [])
        alive = [model for model in list(models or []) if self._dg_model_is_alive(model)]
        alive.sort(key=self._dg_sort_key)
        return alive

    def _dg_attached_unit_has_keyword(self, unit: Any, keyword: str) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        if self._dg_has_keyword(root, keyword):
            return True
        members_fn = getattr(root, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [root]
        for member in list(members or []):
            if self._dg_has_keyword(member, keyword):
                return True
        return False

    def _dg_death_lords_chosen_terminator_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> list[Any]:
        if not self._is_death_lords_chosen_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        candidates: list[Any] = []
        for entry in list(getattr(army, "units", []) or []):
            root = self._dg_root(entry)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_attached_unit_has_keyword(root, "TERMINATOR"):
                continue
            if not self._dg_on_battlefield(root, require_targetable=True):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if require_not_shot and not self._dg_unit_not_selected_for_phase_action(root, phase_key="SHOOTING_PHASE"):
                continue
            if require_not_fought and not self._dg_unit_not_selected_for_phase_action(root, phase_key="FIGHT_PHASE"):
                continue
            candidates.append(root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_flyblown_host_infantry_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_engaged: bool = False,
    ) -> list[Any]:
        if not self._is_flyblown_host_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        candidates: list[Any] = []
        for entry in list(getattr(army, "units", []) or []):
            root = self._dg_root(entry)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_attached_unit_has_keyword(root, "INFANTRY"):
                continue
            if not self._dg_on_battlefield(root, require_targetable=True):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if require_not_shot and not self._dg_unit_not_selected_for_phase_action(root, phase_key="SHOOTING_PHASE"):
                continue
            if require_not_fought and not self._dg_unit_not_selected_for_phase_action(root, phase_key="FIGHT_PHASE"):
                continue
            if require_engaged and not self._dg_is_unit_engaged(root):
                continue
            candidates.append(root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_death_guard_battlefield_unit_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        candidates: list[Any] = []
        for entry in list(getattr(army, "units", []) or []):
            root = self._dg_root(entry)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_on_battlefield(root, require_targetable=True):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if require_not_shot and not self._dg_unit_not_selected_for_phase_action(root, phase_key="SHOOTING_PHASE"):
                continue
            if require_not_fought and not self._dg_unit_not_selected_for_phase_action(root, phase_key="FIGHT_PHASE"):
                continue
            candidates.append(root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_mortarions_hammer_vehicle_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_selected_to_move: bool = False,
        require_not_selected_to_charge: bool = False,
    ) -> list[Any]:
        if not self._is_mortarions_hammer_detachment():
            return []
        candidates: list[Any] = []
        for root in self._dg_death_guard_battlefield_unit_candidates(require_not_shot=require_not_shot):
            if not self._dg_attached_unit_has_keyword(root, "VEHICLE"):
                continue
            if require_not_selected_to_move and self._dg_selected_to_move_this_phase(root):
                continue
            if require_not_selected_to_charge and self._dg_selected_to_charge_this_phase(root):
                continue
            candidates.append(root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_mortarions_hammer_tool_action_context(self, stratagem_name: str, *, phase_name: str) -> dict[str, Any]:
        name_u = str(stratagem_name or "").strip().upper()
        phase_key = self._dg_phase_key(phase_name)
        if name_u == "FONT OF FILTH":
            if phase_key != "SHOOTING_PHASE":
                return {"candidates": []}
            return {
                "candidates": self._dg_mortarions_hammer_vehicle_candidates(require_not_shot=True),
            }
        if name_u == "RELENTLESS GRIND":
            if phase_key not in {"MOVEMENT_PHASE", "CHARGE_PHASE"}:
                return {"candidates": []}
            return {
                "candidates": self._dg_mortarions_hammer_vehicle_candidates(
                    require_not_selected_to_move=phase_key == "MOVEMENT_PHASE",
                    require_not_selected_to_charge=phase_key == "CHARGE_PHASE",
                ),
            }
        return {}

    def _dg_can_use_mortarions_hammer_tool_action(self, stratagem_name: str, kwargs: dict[str, Any]) -> bool | None:
        name_u = str(stratagem_name or "").strip().upper()
        if name_u not in {"FONT OF FILTH", "RELENTLESS GRIND"}:
            return None
        root = self._dg_root((kwargs or {}).get("unit") or (kwargs or {}).get("target_unit"))
        if root is None:
            return False
        phase_key = self._dg_phase_key((kwargs or {}).get("phase_name") or self._current_phase_name)
        if name_u == "FONT OF FILTH":
            candidates = self._dg_mortarions_hammer_vehicle_candidates(require_not_shot=True)
        else:
            candidates = self._dg_mortarions_hammer_vehicle_candidates(
                require_not_selected_to_move=phase_key == "MOVEMENT_PHASE",
                require_not_selected_to_charge=phase_key == "CHARGE_PHASE",
            )
        candidate_ids = {self._dg_sort_key(candidate) for candidate in list(candidates or [])}
        return self._dg_sort_key(root) in candidate_ids

    def _dg_tallyband_plague_legions_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_engaged: bool = False,
        require_monster: bool = False,
        require_not_selected_to_move: bool = False,
        require_not_selected_to_charge: bool = False,
    ) -> list[Any]:
        if not self._is_tallyband_summoners_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        candidates: list[Any] = []
        for entry in list(getattr(army, "units", []) or []):
            root = self._dg_root(entry)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_unit_is_plague_legions(root):
                continue
            if not self._dg_on_battlefield(root, require_targetable=True):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if require_not_shot and not self._dg_unit_not_selected_for_phase_action(root, phase_key="SHOOTING_PHASE"):
                continue
            if require_engaged and not self._dg_is_unit_engaged(root):
                continue
            if require_monster and not self._dg_attached_unit_has_keyword(root, "MONSTER"):
                continue
            if require_not_selected_to_move and self._dg_selected_to_move_this_phase(root):
                continue
            if require_not_selected_to_charge and self._dg_selected_to_charge_this_phase(root):
                continue
            candidates.append(root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_tallyband_mireslick_candidates(self, enemy_unit: Any) -> list[Any]:
        enemy_root = self._dg_root(enemy_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
        if enemy_root is None or not callable(within_engagement):
            return []
        candidates: list[Any] = []
        for source_root in list(self._dg_tallyband_plague_legions_candidates(require_engaged=True) or []):
            if not bool(within_engagement(source_root, enemy_root)):
                continue
            candidates.append(source_root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_engagement_enemy_candidates(
        self,
        source_unit: Any,
        *,
        exclude_keywords_any: tuple[str, ...] = (),
    ) -> list[Any]:
        root = self._dg_root(source_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or game_map is None:
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(within_engagement):
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._dg_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._dg_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if self._dg_owned_by_player(enemy_root, self.player):
                continue
            if not self._dg_on_battlefield(enemy_root, require_targetable=False):
                continue
            if exclude_keywords_any and any(
                self._dg_has_keyword(enemy_root, keyword) for keyword in list(exclude_keywords_any or ())
            ):
                continue
            if not bool(within_engagement(root, enemy_root)):
                continue
            candidates.append(enemy_root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_enervating_onslaught_enemy_candidates(self, source_unit: Any) -> list[Any]:
        return self._dg_engagement_enemy_candidates(
            source_unit,
            exclude_keywords_any=("MONSTER", "VEHICLE"),
        )

    def _dg_nauseating_paroxysms_enemy_candidates(self, source_unit: Any) -> list[Any]:
        return self._dg_engagement_enemy_candidates(source_unit)

    def _dg_unit_within_range_of_friendly_named_unit(
        self,
        source_unit: Any,
        token: str,
        *,
        max_distance: float,
        exclude_self: bool = True,
    ) -> bool:
        source_root = self._dg_root(source_unit)
        if source_root is None:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        seen: set[str] = set()
        source_models = list(self._dg_alive_models(source_root) or [])
        if not source_models:
            return False
        for entry in list(getattr(army, "units", []) or []):
            other_root = self._dg_root(entry)
            if other_root is None:
                continue
            if exclude_self and other_root is source_root:
                continue
            other_id = self._dg_sort_key(other_root)
            if other_id and other_id in seen:
                continue
            if other_id:
                seen.add(other_id)
            if not self._dg_is_death_guard_unit(other_root):
                continue
            if not self._dg_on_battlefield(other_root, require_targetable=True):
                continue
            if not self._dg_unit_contains_named_member(other_root, token):
                continue
            target_models = list(self._dg_alive_models(other_root) or [])
            for source_model in list(source_models or []):
                for target_model in list(target_models or []):
                    try:
                        distance = float(distance_between_models_bases_3d(source_model, target_model))
                    except (AttributeError, TypeError, ValueError):
                        continue
                    if distance <= float(max_distance) + 1e-6:
                        return True
        return False

    def _dg_unit_is_within_myphitic_blight_hauler_range(self, source_unit: Any) -> bool:
        return self._dg_unit_within_range_of_friendly_named_unit(
            source_unit,
            "Myphitic Blight-hauler",
            max_distance=6.0,
            exclude_self=True,
        )

    def _dg_wargear_has_keyword(self, wargear: Any, keyword: str) -> bool:
        if wargear is None:
            return False
        target = str(keyword or "").strip().upper()
        if not target:
            return False
        has_keyword = getattr(wargear, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword(target)):
            return True
        tokens: list[str] = []
        get_keywords = getattr(wargear, "get_keywords", None)
        if callable(get_keywords):
            tokens.extend(list(get_keywords() or []))
        else:
            tokens.extend(list(getattr(wargear, "keywords", []) or []))
        profiles = getattr(wargear, "profiles", None)
        if isinstance(profiles, dict):
            for profile in list(profiles.values() or []):
                profile_get_keywords = getattr(profile, "get_keywords", None)
                if callable(profile_get_keywords):
                    tokens.extend(list(profile_get_keywords() or []))
                else:
                    tokens.extend(list(getattr(profile, "keywords", []) or []))
        normalized = {
            re.sub(r"^[\[\(]+|[\]\)]+$", "", str(token or "").strip()).upper()
            for token in list(tokens or [])
            if str(token or "").strip()
        }
        return target in normalized

    def _dg_signal_pox_objective_candidates(self, source_unit: Any) -> list[Any]:
        source_member = self._dg_named_member_unit(source_unit, "Lord of Virulence")
        if source_member is None:
            return []
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            if objective is None:
                continue
            objective_id = self._dg_sort_key(objective)
            if objective_id and objective_id in seen:
                continue
            if objective_id:
                seen.add(objective_id)
            loc = getattr(objective, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            point = (float(getattr(loc, "x", 0.0) or 0.0), float(getattr(loc, "y", 0.0) or 0.0))
            if not unit_within_range_of_point_3d(
                source_member,
                point,
                30.0,
                use_attached_aggregate=False,
            ):
                continue
            candidates.append(objective)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_unit_within_player_deployment_zone(self, unit: Any, player_id: str, *, game=None) -> bool:
        root = self._dg_root(unit)
        if root is None or not player_id:
            return False
        if game is None:
            game = getattr(getattr(self.player, "game", None), "game", None)
        if game is None:
            game = getattr(self.player, "game", None)
        in_zone = getattr(game, "is_position_in_deployment_zone", None) if game is not None else None
        if not callable(in_zone):
            return False
        for model in list(self._dg_alive_models(root) or []):
            location = getattr(model, "get_location", None)
            if not callable(location):
                continue
            pos = location()
            if not pos or len(pos) < 2:
                continue
            if in_zone(float(pos[0]), float(pos[1]), str(player_id)):
                return True
        return False

    def _dg_opponent_player_id(self) -> str:
        game = getattr(self, "game", None)
        if game is None:
            return ""
        for other_player in list(getattr(game, "players", []) or []):
            if other_player is None or other_player is self.player:
                continue
            return str(getattr(other_player, "id", "") or "")
        return ""

    @staticmethod
    def _dg_build_proxy_model(shape: Any, *, min_z: float, max_z: float) -> Any:
        class _ProxyBase:
            def __init__(self, footprint, *, z0: float, z1: float):
                self._footprint = footprint
                self._z0 = float(z0)
                self._z1 = float(max(z1, z0 + 0.01))

            def get_base_shape(self):
                return self._footprint

            def volume_z_bounds(self):
                return (float(self._z0), float(self._z1))

        return SimpleNamespace(
            model_base=_ProxyBase(shape, z0=min_z, z1=max_z),
            parent_unit=SimpleNamespace(is_aircraft=False, is_towering=False),
            is_alive=True,
        )

    def _dg_model_can_see_proxy_model(
        self,
        shooter_model: Any,
        target_proxy_model: Any,
        *,
        ignore_terrain: Any = None,
    ) -> bool:
        game_map = getattr(getattr(self, "game", None), "map", None)
        if shooter_model is None or target_proxy_model is None or game_map is None:
            return False
        sample_points = getattr(game_map, "_sample_model_points_3d", None)
        blocked = getattr(game_map, "_segment_blocked_by_terrain_feature", None)
        if not callable(sample_points) or not callable(blocked):
            return False
        shooter_points = list(sample_points(shooter_model, perimeter_points=8, z_levels=3) or [])
        target_points = list(sample_points(target_proxy_model, perimeter_points=8, z_levels=3) or [])
        if not shooter_points or not target_points:
            return False
        for shooter_point in shooter_points:
            for target_point in target_points:
                is_blocked = False
                for terrain in list(getattr(game_map, "terrain_features", []) or []):
                    if terrain is None or terrain is ignore_terrain:
                        continue
                    try:
                        if bool(blocked(shooter_point, target_point, terrain, shooter_model, target_proxy_model)):
                            is_blocked = True
                            break
                    except (AttributeError, TypeError, ValueError):
                        continue
                if not is_blocked:
                    return True
        return False

    def _dg_unit_visible_to_point(self, source_unit: Any, point: tuple[float, float], *, z: float = 0.0) -> bool:
        source_root = self._dg_root(source_unit)
        if source_root is None:
            return False
        proxy_shape = Point(float(point[0]), float(point[1])).buffer(0.05)
        proxy_model = self._dg_build_proxy_model(proxy_shape, min_z=float(z), max_z=float(z) + 0.05)
        for model in list(self._dg_alive_models(source_root) or []):
            if self._dg_model_can_see_proxy_model(model, proxy_model):
                return True
        return False

    def _dg_unit_visible_to_terrain_feature(self, source_unit: Any, terrain_feature: Any) -> bool:
        source_root = self._dg_root(source_unit)
        footprint = getattr(terrain_feature, "footprint", None) if terrain_feature is not None else None
        bbox = getattr(terrain_feature, "bounding_box", None) if terrain_feature is not None else None
        if source_root is None or footprint is None or not isinstance(bbox, dict):
            return False
        min_bounds = bbox.get("min", (0.0, 0.0, 0.0))
        max_bounds = bbox.get("max", (0.0, 0.0, 0.0))
        try:
            min_z = float(min_bounds[2])
            max_z = float(max_bounds[2])
        except (IndexError, TypeError, ValueError):
            min_z = 0.0
            max_z = 0.05
        proxy_model = self._dg_build_proxy_model(footprint, min_z=min_z, max_z=max_z)
        for model in list(self._dg_alive_models(source_root) or []):
            if self._dg_model_can_see_proxy_model(model, proxy_model, ignore_terrain=terrain_feature):
                return True
        return False

    def _dg_unit_visible_to_unit(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._dg_root(source_unit)
        target_root = self._dg_root(target_unit)
        if source_root is None or target_root is None:
            return False
        if source_root is target_root:
            return True
        game_map = getattr(getattr(self, "game", None), "map", None)
        can_see = getattr(game_map, "can_model_see_model", None) if game_map is not None else None
        if not callable(can_see):
            return False
        source_models = list(self._dg_alive_models(source_root) or [])
        target_models = list(self._dg_alive_models(target_root) or [])
        for source_model in list(source_models or []):
            for target_model in list(target_models or []):
                if bool(can_see(source_model, target_model)):
                    return True
        return False

    def _dg_shamblerot_poxwalker_candidates(
        self,
        *,
        require_on_battlefield: bool = False,
        require_in_strategic_reserves: bool = False,
        require_not_attached: bool = False,
    ) -> list[Any]:
        if not self._is_shamblerot_vectorium_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        candidates: list[Any] = []
        for entry in list(getattr(army, "units", []) or []):
            root = self._dg_root(entry)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_unit_is_poxwalkers(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                continue
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive) and not bool(is_alive()):
                continue
            if require_on_battlefield and not self._dg_on_battlefield(root, require_targetable=True):
                continue
            reserve_status = str(getattr(root, "reserve_status", "") or "").strip().lower()
            if require_in_strategic_reserves and reserve_status != "strategic_reserves":
                continue
            if require_not_attached and self._dg_is_attached_unit(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            candidates.append(root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_shamblerot_shambling_wall_support_candidates(
        self,
        protected_unit: Any,
        attacking_unit: Any,
    ) -> list[Any]:
        protected_root = self._dg_root(protected_unit)
        attacker_root = self._dg_root(attacking_unit)
        if protected_root is None or attacker_root is None:
            return []
        candidates: list[Any] = []
        for support_root in list(self._dg_shamblerot_poxwalker_candidates(require_on_battlefield=True) or []):
            if support_root is protected_root:
                continue
            if not unit_within_range_of_unit(
                support_root,
                protected_root,
                3.0,
                use_attached_aggregate=True,
            ):
                continue
            if not self._dg_unit_visible_to_unit(protected_root, support_root):
                continue
            if not self._dg_unit_visible_to_unit(attacker_root, support_root):
                continue
            candidates.append(support_root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_shamblerot_shambling_wall_candidate_map(
        self,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> dict[str, list[Any]]:
        if not self._is_shamblerot_vectorium_detachment():
            return {}
        attacker_root = self._dg_root(attacking_unit)
        if attacker_root is None or self._dg_owned_by_player(attacker_root, self.player):
            return {}
        candidates_by_unit: dict[str, list[Any]] = {}
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_on_battlefield(root, require_targetable=True):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            support_candidates = self._dg_shamblerot_shambling_wall_support_candidates(root, attacker_root)
            if support_candidates:
                candidates_by_unit[root_id] = support_candidates
        return {key: candidates_by_unit[key] for key in sorted(candidates_by_unit)}

    def _dg_shamblerot_note_fight_targets_selected(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_shamblerot_vectorium_detachment():
            return
        attacker_root = self._dg_root(attacking_unit)
        if attacker_root is None or self._dg_owned_by_player(attacker_root, self.player):
            return
        attacker_id = self._dg_sort_key(attacker_root)
        if not attacker_id:
            return
        turn = int(self._dg_current_turn() or 0)
        for unit in list(target_units or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_unit_is_poxwalkers(root):
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            existing = {
                str(entry or "").strip()
                for entry in list(sr.get("death_guard_shamblerot_smeared_with_filth_attacker_unit_ids", []) or [])
                if str(entry or "").strip()
            }
            existing.add(attacker_id)
            sr["death_guard_shamblerot_smeared_with_filth_attacker_unit_ids"] = sorted(existing)
            sr["death_guard_shamblerot_smeared_with_filth_phase"] = "FIGHT_PHASE"
            sr["death_guard_shamblerot_smeared_with_filth_turn"] = int(turn)
            root.special_rules = sr

    def _dg_shamblerot_smeared_with_filth_enemy_candidates(self, unit: Any) -> list[Any]:
        root = self._dg_root(unit)
        if root is None:
            return []
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return []
        if str(sr.get("death_guard_shamblerot_smeared_with_filth_phase", "") or "").strip().upper() != "FIGHT_PHASE":
            return []
        try:
            marked_turn = int(sr.get("death_guard_shamblerot_smeared_with_filth_turn", 0) or 0)
        except (TypeError, ValueError):
            marked_turn = 0
        current_turn = int(self._dg_current_turn() or 0)
        if marked_turn and current_turn and marked_turn != current_turn:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for attacker_id in list(sr.get("death_guard_shamblerot_smeared_with_filth_attacker_unit_ids", []) or []):
            enemy_root = self._dg_resolve_unit_by_id(str(attacker_id or ""))
            if enemy_root is None:
                continue
            enemy_id = self._dg_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if self._dg_owned_by_player(enemy_root, self.player):
                continue
            if not self._dg_on_battlefield(enemy_root, require_targetable=False):
                continue
            candidates.append(enemy_root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_eyestinger_storm_objective_candidates(self, source_unit: Any) -> list[Any]:
        source_root = self._dg_root(source_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if source_root is None or game_map is None:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            if objective is None:
                continue
            objective_id = self._dg_sort_key(objective)
            if objective_id and objective_id in seen:
                continue
            if objective_id:
                seen.add(objective_id)
            loc = getattr(objective, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            point = (float(getattr(loc, "x", 0.0) or 0.0), float(getattr(loc, "y", 0.0) or 0.0))
            if not self._dg_unit_visible_to_point(source_root, point, z=float(getattr(loc, "z", 0.0) or 0.0)):
                continue
            if not self._dg_afflicted_enemy_units_within_objective(objective):
                continue
            candidates.append(objective)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_blighted_land_terrain_candidates(self, source_unit: Any) -> list[Any]:
        source_root = self._dg_root(source_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if source_root is None or game_map is None:
            return []
        from .nurgles_gift import NurglesGiftManager

        candidates: list[Any] = []
        seen: set[str] = set()
        for terrain_feature in list(getattr(game_map, "terrain_features", []) or []):
            if terrain_feature is None:
                continue
            terrain_id = self._dg_sort_key(terrain_feature)
            if terrain_id and terrain_id in seen:
                continue
            if terrain_id:
                seen.add(terrain_id)
            if not bool(
                NurglesGiftManager.unit_within_range_of_terrain_feature(
                    source_root,
                    terrain_feature,
                    24.0,
                )
            ):
                continue
            if not self._dg_unit_visible_to_terrain_feature(source_root, terrain_feature):
                continue
            candidates.append(terrain_feature)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_resolve_terrain_candidate(self, selected: Any, candidates: list[Any]) -> Any:
        if selected is None:
            return None
        selected_id = str(getattr(selected, "id", "") or get_entity_id(selected) or "")
        for candidate in list(candidates or []):
            if candidate is selected:
                return candidate
            candidate_id = str(getattr(candidate, "id", "") or get_entity_id(candidate) or "")
            if selected_id and candidate_id and selected_id == candidate_id:
                return candidate
        return None

    def _dg_resolve_objective_candidate(self, selected: Any, candidates: list[Any]) -> Any:
        if selected is None:
            return None
        selected_id = str(getattr(selected, "id", "") or get_entity_id(selected) or "")
        selected_loc = getattr(selected, "location", None)
        selected_loc_id = str(get_entity_id(selected_loc) or "") if selected_loc is not None else ""
        for candidate in list(candidates or []):
            if candidate is selected:
                return candidate
            candidate_id = str(getattr(candidate, "id", "") or get_entity_id(candidate) or "")
            candidate_loc = getattr(candidate, "location", None)
            candidate_loc_id = str(get_entity_id(candidate_loc) or "") if candidate_loc is not None else ""
            if selected_id and candidate_id and selected_id == candidate_id:
                return candidate
            if selected_loc_id and candidate_loc_id and selected_loc_id == candidate_loc_id:
                return candidate
        return None

    def _dg_afflicted_enemy_units_within_objective(self, objective: Any) -> list[Any]:
        objective_location = getattr(objective, "location", None)
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if objective_location is None or game_map is None:
            return []
        from .nurgles_gift import NurglesGiftManager

        candidates: list[Any] = []
        seen: set[str] = set()
        for other_player in list(getattr(game, "players", []) or []):
            if other_player is None or other_player is self.player:
                continue
            army = getattr(other_player, "army", None)
            if army is None and hasattr(other_player, "get_army"):
                army = other_player.get_army()
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                root = self._dg_root(unit)
                if root is None:
                    continue
                root_id = self._dg_sort_key(root)
                if root_id and root_id in seen:
                    continue
                if root_id:
                    seen.add(root_id)
                if not self._dg_on_battlefield(root, require_targetable=False):
                    continue
                if NurglesGiftManager.get_afflicted_plague_for_unit(root, game=game, game_map=game_map) is None:
                    continue
                is_within_objective = getattr(root, "is_within_objective_range", None)
                if callable(is_within_objective):
                    if not bool(is_within_objective(objective_location)):
                        continue
                elif not unit_within_range_of_point_3d(
                    root,
                    (
                        float(getattr(objective_location, "x", 0.0) or 0.0),
                        float(getattr(objective_location, "y", 0.0) or 0.0),
                    ),
                    float(getattr(objective_location, "control_radius", 0.0) or 0.0),
                    use_attached_aggregate=True,
                ):
                    continue
                candidates.append(root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_sickening_impact_enemy_candidates(self, source_unit: Any) -> list[Any]:
        root = self._dg_root(source_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or game_map is None:
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(within_engagement):
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._dg_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._dg_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if self._dg_owned_by_player(enemy_root, self.player):
                continue
            if not self._dg_on_battlefield(enemy_root, require_targetable=False):
                continue
            if not bool(within_engagement(root, enemy_root)):
                continue
            candidates.append(enemy_root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_models_within_engagement_range_of_enemy(self, source_unit: Any, enemy_unit: Any) -> list[Any]:
        source_root = self._dg_root(source_unit)
        enemy_root = self._dg_root(enemy_unit)
        if source_root is None or enemy_root is None:
            return []
        source_models = list(self._dg_alive_models(source_root) or [])
        enemy_models = list(self._dg_alive_models(enemy_root) or [])
        engaged: list[Any] = []
        for source_model in list(source_models or []):
            source_base = getattr(source_model, "model_base", None)
            if source_base is None:
                continue
            for enemy_model in list(enemy_models or []):
                enemy_base = getattr(enemy_model, "model_base", None)
                if enemy_base is None:
                    continue
                try:
                    horizontal = float(horizontal_distance_between_bases_2d(source_base, enemy_base))
                    vertical = float(vertical_distance_between_bases(source_base, enemy_base))
                except (AttributeError, TypeError, ValueError):
                    continue
                if horizontal <= float(ENGAGEMENT_RANGE_HORIZONTAL) + 1e-6 and vertical <= float(ENGAGEMENT_RANGE_VERTICAL) + 1e-6:
                    engaged.append(source_model)
                    break
        engaged.sort(key=self._dg_sort_key)
        return engaged

    def _dg_unit_within_horizontal_vertical_of_unit(
        self,
        unit: Any,
        other_unit: Any,
        *,
        horizontal: float,
        vertical: float,
    ) -> bool:
        root = self._dg_root(unit)
        other_root = self._dg_root(other_unit)
        if root is None or other_root is None:
            return False
        source_models = list(self._dg_alive_models(root) or [])
        target_models = list(self._dg_alive_models(other_root) or [])
        if not source_models or not target_models:
            return False
        for source_model in list(source_models or []):
            source_base = getattr(source_model, "model_base", None)
            if source_base is None:
                continue
            for target_model in list(target_models or []):
                target_base = getattr(target_model, "model_base", None)
                if target_base is None:
                    continue
                try:
                    h = float(horizontal_distance_between_bases_2d(source_base, target_base))
                    v = float(vertical_distance_between_bases(source_base, target_base))
                except (AttributeError, TypeError, ValueError):
                    continue
                if h <= float(horizontal) + 1e-6 and v <= float(vertical) + 1e-6:
                    return True
        return False

    def _dg_visible_enemy_candidates(
        self,
        source_unit: Any,
        *,
        max_distance: float,
        exclude_keywords_any: tuple[str, ...] = (),
    ) -> list[Any]:
        source_root = self._dg_root(source_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if source_root is None or game_map is None:
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        los_check = getattr(source_root, "_attacking_unit_has_any_los_to_target_unit", None)
        seen: set[str] = set()
        candidates: list[Any] = []
        source_models = list(self._dg_alive_models(source_root) or [])
        for enemy in list(get_enemy_units(source_root) or []):
            enemy_root = self._dg_root(enemy)
            if enemy_root is None:
                continue
            if self._dg_owned_by_player(enemy_root, self.player):
                continue
            enemy_id = self._dg_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if not self._dg_on_battlefield(enemy_root, require_targetable=False):
                continue
            if exclude_keywords_any and any(self._dg_has_keyword(enemy_root, keyword) for keyword in list(exclude_keywords_any or ())):
                continue
            if callable(los_check):
                try:
                    if not bool(los_check(enemy_root, game_map)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            in_range = False
            for source_model in list(source_models or []):
                for target_model in list(self._dg_alive_models(enemy_root) or []):
                    try:
                        distance = float(distance_between_models_bases_3d(source_model, target_model))
                    except (AttributeError, TypeError, ValueError):
                        continue
                    if distance <= float(max_distance) + 1e-6:
                        in_range = True
                        break
                if in_range:
                    break
            if in_range:
                candidates.append(enemy_root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_deaths_heads_enemy_candidates(self, source_unit: Any) -> list[Any]:
        return self._dg_visible_enemy_candidates(
            source_unit,
            max_distance=8.0,
            exclude_keywords_any=("VEHICLE",),
        )

    def _dg_mobile_vector_bodyguard_candidates(self, source_unit: Any) -> list[Any]:
        source_root = self._dg_root(source_unit)
        if source_root is None:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        candidates: list[Any] = []
        for entry in list(getattr(army, "units", []) or []):
            root = self._dg_root(entry)
            if root is None or root is source_root:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_on_battlefield(root, require_targetable=True):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if self._dg_is_attached_unit(root):
                continue
            can_attach_to = getattr(source_root, "can_attach_to", None)
            if not callable(can_attach_to) or not bool(can_attach_to(root)):
                continue
            if not self._dg_unit_within_horizontal_vertical_of_unit(source_root, root, horizontal=2.0, vertical=5.0):
                continue
            candidates.append(root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_character_model_count(self, unit: Any) -> int:
        root = self._dg_root(unit)
        if root is None:
            return 0
        count = 0
        for model in list(self._dg_alive_models(root) or []):
            if bool(getattr(model, "is_character", False)):
                count += 1
                continue
            parent_unit = getattr(model, "parent_unit", None)
            if parent_unit is not None and self._dg_has_keyword(parent_unit, "CHARACTER"):
                count += 1
        return int(count)

    def _queue_champions_of_contagion_grotesque_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
        event_name: str,
    ) -> None:
        if not self._is_champions_of_contagion_detachment():
            return
        s = self.get_by_name("GROTESQUE FORTITUDE")
        if s is None:
            return
        if self.player.command_points < self._dg_effective_cp_cost(s):
            return
        if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        if attacking_unit is None:
            return
        attacker_root = self._dg_root(attacking_unit)
        if attacker_root is None or self._dg_owned_by_player(attacker_root, self.player):
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_is_attached_unit(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            candidates.append(root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == event_name
                and str(reaction.get("stratagem", "") or "").strip().upper() == "GROTESQUE FORTITUDE"
                and reaction.get("attacking_unit") is attacker_root
            ):
                return
        payload = {
            "event": event_name,
            "phase_name": str(phase_name or ""),
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "attacking_unit": attacker_root,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_shamblerot_grip_of_the_walking_pox_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
        event_name: str,
    ) -> None:
        if not self._is_shamblerot_vectorium_detachment():
            return
        if self._dg_phase_key(phase_name) != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("GRIP OF THE WALKING POX")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_root = self._dg_root(attacking_unit)
        if attacker_root is None or self._dg_owned_by_player(attacker_root, self.player):
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_unit_is_poxwalkers(root):
                continue
            candidates.append(root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == event_name
                and str(reaction.get("stratagem", "") or "").strip().upper() == "GRIP OF THE WALKING POX"
                and reaction.get("attacking_unit") is attacker_root
            ):
                return
        payload = {
            "event": event_name,
            "phase_name": str(phase_name or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_shamblerot_shambling_wall_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
        event_name: str,
    ) -> None:
        if not self._is_shamblerot_vectorium_detachment():
            return
        if self._dg_phase_key(phase_name) != "SHOOTING_PHASE":
            return
        stratagem = self.get_by_name("SHAMBLING WALL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_root = self._dg_root(attacking_unit)
        if attacker_root is None or self._dg_owned_by_player(attacker_root, self.player):
            return
        support_candidates_by_unit = self._dg_shamblerot_shambling_wall_candidate_map(attacker_root, list(target_units or []))
        if not support_candidates_by_unit:
            return
        candidates = [self._dg_resolve_unit_by_id(unit_id) for unit_id in list(support_candidates_by_unit)]
        candidates = [candidate for candidate in list(candidates or []) if candidate is not None]
        candidates.sort(key=self._dg_sort_key)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == event_name
                and str(reaction.get("stratagem", "") or "").strip().upper() == "SHAMBLING WALL"
                and reaction.get("attacking_unit") is attacker_root
            ):
                return
        payload = {
            "event": event_name,
            "phase_name": str(phase_name or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "candidates": list(candidates),
            "support_candidates_by_unit": dict(support_candidates_by_unit),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
            support_candidates = list(support_candidates_by_unit.get(self._dg_sort_key(candidates[0]), []) or [])
            if len(support_candidates) == 1:
                payload["support_unit"] = support_candidates[0]
        self._queue_reaction(payload)

    def _queue_shamblerot_smeared_with_filth_reaction(self, *, unit: Any) -> None:
        if not self._is_shamblerot_vectorium_detachment():
            return
        if self._dg_current_phase_key() != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("SMEARED WITH FILTH")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        root = self._dg_root(unit)
        if root is None or not self._dg_owned_by_player(root, self.player):
            return
        if not self._dg_is_death_guard_unit(root) or not self._dg_unit_is_poxwalkers(root):
            return
        enemy_candidates = self._dg_shamblerot_smeared_with_filth_enemy_candidates(root)
        if not enemy_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "unit_destroyed"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "SMEARED WITH FILTH"
                and self._dg_root(reaction.get("destroyed_unit") or reaction.get("unit")) is root
            ):
                return
        payload = {
            "event": "unit_destroyed",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "destroyed_unit": root,
            "enemy_candidates": list(enemy_candidates),
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
            payload["target_enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_tallyband_persistent_pests_reaction(self, *, unit: Any) -> None:
        if not self._is_tallyband_summoners_detachment():
            return
        stratagem = self.get_by_name("PERSISTENT PESTS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        root = self._dg_root(unit)
        if root is None or not self._dg_owned_by_player(root, self.player):
            return
        if not self._dg_unit_is_nurglings(root):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "unit_destroyed"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "PERSISTENT PESTS"
                and self._dg_root(reaction.get("destroyed_unit") or reaction.get("unit")) is root
            ):
                return
        payload = {
            "event": "unit_destroyed",
            "phase_name": str(getattr(getattr(self.game, "phase", None), "name", "") or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "destroyed_unit": root,
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_tallyband_mireslick_reaction(self, *, unit: Any, action: str) -> None:
        if not self._is_tallyband_summoners_detachment():
            return
        if str(action or "").strip().lower() != "fall_back":
            return
        if self._dg_current_phase_key() != "MOVEMENT_PHASE":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        stratagem = self.get_by_name("MIRESLICK")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        enemy_root = self._dg_root(unit)
        if enemy_root is None or self._dg_owned_by_player(enemy_root, self.player):
            return
        if self._dg_attached_unit_has_keyword(enemy_root, "MONSTER") or self._dg_attached_unit_has_keyword(enemy_root, "VEHICLE"):
            return
        candidates = self._dg_tallyband_mireslick_candidates(enemy_root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "unit_move_started"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "MIRESLICK"
                and self._dg_root(reaction.get("enemy_unit")) is enemy_root
            ):
                return
        payload = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "target_enemy_unit": enemy_root,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_death_guard_unit_destroyed_reactions(self, *, unit: Any, **_kwargs) -> None:
        self._queue_shamblerot_smeared_with_filth_reaction(unit=unit)
        self._queue_tallyband_persistent_pests_reaction(unit=unit)

    def _queue_death_guard_move_start_reactions(self, *, unit: Any, action: str) -> None:
        self._queue_tallyband_mireslick_reaction(unit=unit, action=action)

    def _resolve_tallyband_all_is_rot_shooting_resolved(
        self,
        *,
        attacker_unit: Any,
        damage_by_target_while_engaged: dict[Any, int] | None,
    ) -> None:
        if not self._is_tallyband_summoners_detachment():
            return
        attacker_root = self._dg_root(attacker_unit)
        if attacker_root is None or not self._dg_owned_by_player(attacker_root, self.player):
            return
        temp_effect_iter = getattr(attacker_root, "iter_active_death_guard_temp_effects", None)
        if not callable(temp_effect_iter):
            return
        if not any(
            temp_effect_iter(
                effect_type="all_is_rot",
                attack_type="any",
                require_target_match=False,
            )
        ):
            return
        damage_map = damage_by_target_while_engaged if isinstance(damage_by_target_while_engaged, dict) else {}
        if not damage_map:
            return
        total_rolls = 0
        for target in sorted(list(damage_map), key=self._dg_sort_key):
            target_root = self._dg_root(target)
            if target_root is None or self._dg_owned_by_player(target_root, self.player):
                continue
            try:
                total_rolls += max(0, int(damage_map.get(target, 0) or 0))
            except (TypeError, ValueError):
                continue
        if total_rolls <= 0:
            return
        mortal_wounds = 0
        for _ in range(int(total_rolls)):
            if int(dice_module.get_roll("D6") or 0) >= 5:
                mortal_wounds += 1
        if mortal_wounds <= 0:
            return
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        apply_mortals = getattr(attacker_root, "_apply_mortal_wounds_to_unit", None)
        if not callable(apply_mortals):
            return
        apply_mortals(
            attacker_root,
            int(mortal_wounds),
            game_map=game_map,
            attacker_unit=attacker_root,
            damage_source="death_guard_tallyband_all_is_rot",
        )
        logger.info(
            "INFO: ALL IS ROT: %s suffers %d mortal wound(s) after inflicting wounds in Engagement Range.",
            getattr(attacker_root, "name", "Unit"),
            int(mortal_wounds),
        )

    def _resolve_death_guard_shooting_resolved(
        self,
        *,
        attacker_unit: Any,
        damage_by_target_while_engaged: dict[Any, int] | None,
    ) -> None:
        self._resolve_tallyband_all_is_rot_shooting_resolved(
            attacker_unit=attacker_unit,
            damage_by_target_while_engaged=damage_by_target_while_engaged,
        )

    def _dg_spawn_tallyband_persistent_pests_unit(self, destroyed_unit: Any, *, game=None) -> Any:
        root = self._dg_root(destroyed_unit)
        if root is None:
            return None
        army = getattr(self.player, "army", None)
        if army is None:
            return None
        datasheet = getattr(root, "_datasheet", None)
        if datasheet is None:
            return None
        try:
            quantity = int(getattr(root, "starting_model_count", 0) or 0)
        except (TypeError, ValueError):
            quantity = 0
        if quantity <= 0:
            current_models = list(getattr(root, "models", []) or [])
            lost_models = list(getattr(root, "models_lost", []) or [])
            quantity = max(1, len(current_models) + len(lost_models))
        from ..units.unit import Unit as UnitClass

        try:
            new_unit = UnitClass(datasheet, quantity=int(quantity))
        except TypeError:
            new_unit = UnitClass(datasheet)
        new_unit.spawned_in_battle = True
        new_unit.starting_model_count = int(quantity)
        set_parent = getattr(new_unit, "set_parent_army", None)
        if callable(set_parent):
            set_parent(army)
        else:
            new_unit.parent_army = army
        set_reserve = getattr(new_unit, "set_reserve_status", None)
        if callable(set_reserve):
            set_reserve("strategic_reserves")
        else:
            new_unit.reserve_status = "strategic_reserves"
        mark_midgame = getattr(new_unit, "mark_entered_reserves_midgame", None)
        if callable(mark_midgame):
            mark_midgame(game=game)
        new_unit.deployed = True
        new_unit.reserve_turn_deployed = None
        new_unit.arrived_from_reserves_this_turn = False
        army.add_unit(new_unit)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is not None and hasattr(game_map, "units") and new_unit in game_map.units:
            game_map.units.remove(new_unit)
        if game is not None and hasattr(game, "rebuild_entity_registry"):
            game.rebuild_entity_registry()
        return new_unit

    def _resolve_shamblerot_grip_of_the_walking_pox(self, *, unit: Any) -> None:
        if not self._is_shamblerot_vectorium_detachment():
            return
        if self._dg_current_phase_key() != "FIGHT_PHASE":
            return
        attacker_root = self._dg_root(unit)
        if attacker_root is None or self._dg_owned_by_player(attacker_root, self.player):
            return
        attacker_id = self._dg_sort_key(attacker_root)
        if not attacker_id:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        current_turn = int(self._dg_current_turn() or 0)
        current_phase = self._dg_current_phase_key()
        seen: set[str] = set()
        for unit_entry in list(getattr(army, "units", []) or []):
            root = self._dg_root(unit_entry)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            pending_entries = list(sr.get("death_guard_shamblerot_grip_entries", []) or [])
            if not pending_entries:
                continue
            matched_entries: list[dict] = []
            kept_entries: list[dict] = []
            for entry in list(pending_entries or []):
                if not isinstance(entry, dict):
                    continue
                entry_attacker_id = str(entry.get("attacker_unit_id", "") or "").strip()
                entry_phase = str(entry.get("phase", "") or "").strip().upper()
                try:
                    entry_turn = int(entry.get("turn", 0) or 0)
                except (TypeError, ValueError):
                    entry_turn = 0
                if entry_attacker_id == attacker_id and entry_phase == current_phase and (not entry_turn or entry_turn == current_turn):
                    matched_entries.append(dict(entry))
                else:
                    kept_entries.append(dict(entry))
            if kept_entries:
                sr["death_guard_shamblerot_grip_entries"] = kept_entries
            else:
                sr.pop("death_guard_shamblerot_grip_entries", None)
            root.special_rules = sr
            if not matched_entries:
                continue
            is_attacker_alive = getattr(attacker_root, "is_alive", None)
            if callable(is_attacker_alive) and not bool(is_attacker_alive()):
                continue
            game_map = getattr(self.game, "map", None) if self.game is not None else None
            apply_mortals = getattr(root, "_apply_mortal_wounds_to_unit", None)
            if not callable(apply_mortals):
                continue
            for entry in list(matched_entries or []):
                try:
                    start_alive_models = int(entry.get("start_alive_models", 0) or 0)
                except (TypeError, ValueError):
                    start_alive_models = 0
                current_alive_models = len(list(self._dg_alive_models(root) or []))
                destroyed_models = max(0, int(start_alive_models) - int(current_alive_models))
                if destroyed_models <= 0:
                    continue
                mortal_wounds = 0
                for _ in range(int(destroyed_models)):
                    if int(dice_module.get_roll("D6") or 0) >= 6:
                        mortal_wounds += 1
                if mortal_wounds <= 0:
                    continue
                source_alive = getattr(root, "is_alive", None)
                should_count_for_curse = bool(callable(source_alive) and source_alive())
                source_sr = getattr(root, "special_rules", None)
                if not isinstance(source_sr, dict):
                    source_sr = {}
                previous_flag = bool(source_sr.get("curse_of_walking_pox_count_eater_plague", False))
                if should_count_for_curse:
                    source_sr["curse_of_walking_pox_count_eater_plague"] = True
                    root.special_rules = source_sr
                apply_mortals(
                    attacker_root,
                    int(mortal_wounds),
                    game_map=game_map,
                    attacker_unit=root,
                    damage_source="death_guard_shamblerot_grip_of_the_walking_pox",
                )
                if should_count_for_curse:
                    refreshed_sr = getattr(root, "special_rules", None)
                    if not isinstance(refreshed_sr, dict):
                        refreshed_sr = {}
                    if previous_flag:
                        refreshed_sr["curse_of_walking_pox_count_eater_plague"] = True
                    else:
                        refreshed_sr.pop("curse_of_walking_pox_count_eater_plague", None)
                    root.special_rules = refreshed_sr

    def _resolve_death_guard_fight_sequence_complete(self, *, unit: Any) -> None:
        self._resolve_shamblerot_grip_of_the_walking_pox(unit=unit)

    def _queue_death_guard_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
        event_name: str,
    ) -> None:
        phase_key = self._dg_phase_key(phase_name)
        if phase_key == "FIGHT_PHASE":
            self._dg_shamblerot_note_fight_targets_selected(
                attacking_unit=attacking_unit,
                target_units=list(target_units or []),
            )
            self._queue_shamblerot_grip_of_the_walking_pox_reaction(
                attacking_unit=attacking_unit,
                target_units=list(target_units or []),
                phase_name=phase_name,
                event_name=event_name,
            )
        if phase_key == "SHOOTING_PHASE":
            self._queue_shamblerot_shambling_wall_reaction(
                attacking_unit=attacking_unit,
                target_units=list(target_units or []),
                phase_name=phase_name,
                event_name=event_name,
            )
        self._queue_champions_of_contagion_grotesque_reaction(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
            phase_name=phase_name,
            event_name=event_name,
        )
        self._queue_death_lords_chosen_undying_spite_reaction(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
            phase_name=phase_name,
            event_name=event_name,
        )
        self._queue_flyblown_host_myphitic_invigoration_reaction(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
            phase_name=phase_name,
            event_name=event_name,
        )

    def _queue_death_guard_phase_start_reactions(self, *, player=None, phase=None) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key == "COMMAND_PHASE":
            self._queue_mortarions_hammer_eyestinger_storm_phase_start_reaction(player=player, phase=phase)
            return
        if phase_key == "CHARGE_PHASE":
            self._queue_mortarions_hammer_stinking_mire_phase_start_reaction(player=player, phase=phase)
            return
        if phase_key == "FIGHT_PHASE":
            self._queue_flyblown_host_nauseating_paroxysms_phase_start_reaction(player=player, phase=phase)

    def _queue_death_guard_phase_end_reactions(self, *, player=None, phase=None) -> None:
        self._queue_mortarions_hammer_blighted_land_phase_end_reaction(player=player, phase=phase)

    def _cleanup_death_guard_phase_end_effects(self, *, phase=None) -> None:
        self._cleanup_mortarions_hammer_phase_end_effects(phase=phase)
        self._cleanup_shamblerot_vectorium_phase_end_effects(phase=phase)
        self._cleanup_tallyband_summoners_phase_end_effects(phase=phase)

    def _cleanup_shamblerot_vectorium_phase_end_effects(self, *, phase=None) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"MOVEMENT_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            invalidate_cache = False
            if phase_key == "MOVEMENT_PHASE":
                expires_phase = str(
                    sr.get("death_guard_hidden_amongst_the_dead_expires_phase", "") or ""
                ).strip().upper()
                if bool(sr.get("death_guard_hidden_amongst_the_dead_temp_deep_strike", False)) and (
                    not expires_phase or expires_phase == phase_key
                ):
                    for key in (
                        "death_guard_hidden_amongst_the_dead_temp_deep_strike",
                        "death_guard_hidden_amongst_the_dead_turn_owner",
                        "death_guard_hidden_amongst_the_dead_turn",
                        "death_guard_hidden_amongst_the_dead_expires_phase",
                        "death_guard_hidden_amongst_the_dead_source",
                    ):
                        sr.pop(key, None)
                    changed = True
                    invalidate_cache = True
            if phase_key == "SHOOTING_PHASE":
                expires_phase = str(
                    sr.get("death_guard_shamblerot_shambling_wall_expires_phase", "") or ""
                ).strip().upper()
                if bool(sr.get("death_guard_shamblerot_shambling_wall_active", False)) and (
                    not expires_phase or expires_phase == phase_key
                ):
                    for key in (
                        "death_guard_shamblerot_shambling_wall_active",
                        "death_guard_shamblerot_shambling_wall_support_unit_id",
                        "death_guard_shamblerot_shambling_wall_attacker_unit_id",
                        "death_guard_shamblerot_shambling_wall_expires_phase",
                        "death_guard_shamblerot_shambling_wall_turn_owner",
                        "death_guard_shamblerot_shambling_wall_turn",
                        "death_guard_shamblerot_shambling_wall_source",
                    ):
                        sr.pop(key, None)
                    changed = True
            if phase_key == "FIGHT_PHASE":
                for key in (
                    "death_guard_shamblerot_grip_entries",
                    "death_guard_shamblerot_smeared_with_filth_attacker_unit_ids",
                    "death_guard_shamblerot_smeared_with_filth_phase",
                    "death_guard_shamblerot_smeared_with_filth_turn",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if changed:
                root.special_rules = sr
            if invalidate_cache:
                invalidate = getattr(root, "_invalidate_ability_cache", None)
                if callable(invalidate):
                    invalidate()

    def _queue_mortarions_hammer_eyestinger_storm_phase_start_reaction(self, *, player=None, phase=None) -> None:
        if not self._is_mortarions_hammer_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "COMMAND_PHASE":
            return
        if player is self.player:
            return
        stratagem = self.get_by_name("EYESTINGER STORM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = [
            unit
            for unit in self._dg_mortarions_hammer_vehicle_candidates()
            if self._dg_eyestinger_storm_objective_candidates(unit)
        ]
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "phase_start"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "EYESTINGER STORM"
                and str(reaction.get("phase_name", "") or "").strip().upper() == "COMMAND PHASE"
            ):
                return
        payload = {
            "event": "phase_start",
            "phase": "Command phase",
            "phase_name": "Command phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_mortarions_hammer_stinking_mire_phase_start_reaction(self, *, player=None, phase=None) -> None:
        if not self._is_mortarions_hammer_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "CHARGE_PHASE":
            return
        if player is self.player:
            return
        stratagem = self.get_by_name("STINKING MIRE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._dg_mortarions_hammer_vehicle_candidates()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "phase_start"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "STINKING MIRE"
                and str(reaction.get("phase_name", "") or "").strip().upper() == "CHARGE PHASE"
            ):
                return
        payload = {
            "event": "phase_start",
            "phase": "Charge phase",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_mortarions_hammer_blighted_land_phase_end_reaction(self, *, player=None, phase=None) -> None:
        if not self._is_mortarions_hammer_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        if player is not self.player:
            return
        stratagem = self.get_by_name("BLIGHTED LAND")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = [
            unit
            for unit in self._dg_mortarions_hammer_vehicle_candidates()
            if self._dg_blighted_land_terrain_candidates(unit)
        ]
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "phase_end"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "BLIGHTED LAND"
                and str(reaction.get("phase_name", "") or "").strip().upper() == "MOVEMENT PHASE"
            ):
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
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_mortarions_hammer_phase_end_effects(self, *, phase=None) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"MOVEMENT_PHASE", "CHARGE_PHASE"}:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if phase_key in {"MOVEMENT_PHASE", "CHARGE_PHASE"}:
                expires_phase = str(
                    sr.get("death_guard_mortarions_hammer_relentless_grind_expires_phase", "") or ""
                ).strip().upper()
                if sr.get("death_guard_mortarions_hammer_relentless_grind_active") is True and (
                    not expires_phase or expires_phase == phase_key
                ):
                    self._dg_remove_phase_move_types(
                        sr,
                        "bearer_unit_phase_move_terrain_only_types",
                        "death_guard_mortarions_hammer_relentless_grind_added_phase_move_terrain_only_types",
                    )
                    for key in (
                        "death_guard_mortarions_hammer_relentless_grind_active",
                        "death_guard_mortarions_hammer_relentless_grind_expires_phase",
                        "death_guard_mortarions_hammer_relentless_grind_turn_owner",
                        "death_guard_mortarions_hammer_relentless_grind_turn",
                        "death_guard_mortarions_hammer_relentless_grind_source",
                        "death_guard_mortarions_hammer_relentless_grind_added_phase_move_terrain_only_types",
                    ):
                        sr.pop(key, None)
            if phase_key == "CHARGE_PHASE":
                expires_phase = str(
                    sr.get("death_guard_mortarions_hammer_stinking_mire_expires_phase", "") or ""
                ).strip().upper()
                if sr.get("death_guard_mortarions_hammer_stinking_mire_active") is True and (
                    not expires_phase or expires_phase == phase_key
                ):
                    for key in (
                        "death_guard_mortarions_hammer_stinking_mire_active",
                        "death_guard_mortarions_hammer_stinking_mire_charge_modifier",
                        "death_guard_mortarions_hammer_stinking_mire_expires_phase",
                        "death_guard_mortarions_hammer_stinking_mire_turn_owner",
                        "death_guard_mortarions_hammer_stinking_mire_turn",
                        "death_guard_mortarions_hammer_stinking_mire_source",
                    ):
                        sr.pop(key, None)
            root.special_rules = sr

    def _queue_flyblown_host_nauseating_paroxysms_phase_start_reaction(self, *, player=None, phase=None) -> None:
        if not self._is_flyblown_host_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("NAUSEATING PAROXYSMS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._dg_flyblown_host_infantry_candidates(require_engaged=True)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "phase_start"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "NAUSEATING PAROXYSMS"
                and str(reaction.get("phase_name", "") or "").strip().upper() == "FIGHT PHASE"
            ):
                return
        payload = {
            "event": "phase_start",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_flyblown_host_myphitic_invigoration_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
        event_name: str,
    ) -> None:
        if not self._is_flyblown_host_detachment():
            return
        if self._dg_phase_key(phase_name) != "SHOOTING_PHASE":
            return
        stratagem = self.get_by_name("MYPHITIC INVIGORATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_root = self._dg_root(attacking_unit)
        if attacker_root is None or self._dg_owned_by_player(attacker_root, self.player):
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_attached_unit_has_keyword(root, "INFANTRY"):
                continue
            if not self._dg_on_battlefield(root, require_targetable=True):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._dg_unit_is_within_myphitic_blight_hauler_range(root):
                continue
            candidates.append(root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == event_name
                and str(reaction.get("stratagem", "") or "").strip().upper() == "MYPHITIC INVIGORATION"
                and reaction.get("attacking_unit") is attacker_root
            ):
                return
        payload = {
            "event": event_name,
            "phase_name": str(phase_name or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_death_lords_chosen_undying_spite_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
        event_name: str,
    ) -> None:
        if not self._is_death_lords_chosen_detachment():
            return
        stratagem = self.get_by_name("UNDYING SPITE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_root = self._dg_root(attacking_unit)
        if attacker_root is None or self._dg_owned_by_player(attacker_root, self.player):
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_attached_unit_has_keyword(root, "TERMINATOR"):
                continue
            if not self._dg_on_battlefield(root, require_targetable=True):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            candidates.append(root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == event_name
                and str(reaction.get("stratagem", "") or "").strip().upper() == "UNDYING SPITE"
                and reaction.get("attacking_unit") is attacker_root
            ):
                return
        payload = {
            "event": event_name,
            "phase_name": str(phase_name or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_death_guard_move_end_reactions(self, *, unit: Any, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        self._queue_flyblown_host_enervating_onslaught_reaction(unit=unit, action=action)
        self._queue_shamblerot_shock_and_horror_reaction(unit=unit, action=action)
        if not self._is_death_lords_chosen_detachment():
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"charge", "charge move"}:
            return
        root = self._dg_root(unit)
        if root is None or not self._dg_owned_by_player(root, self.player):
            return
        if root not in self._dg_death_lords_chosen_terminator_candidates():
            return
        stratagem = self.get_by_name("SICKENING IMPACT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem, target_unit=root):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        enemy_candidates = self._dg_sickening_impact_enemy_candidates(root)
        if not enemy_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "unit_move_ended"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "SICKENING IMPACT"
                and self._dg_root(reaction.get("unit")) is root
            ):
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "source_unit": root,
            "action": str(action or ""),
            "enemy_candidates": enemy_candidates,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
            payload["target_enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_shamblerot_shock_and_horror_reaction(self, *, unit: Any, action: str) -> None:
        if not self._is_shamblerot_vectorium_detachment():
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"charge", "charge move"}:
            return
        root = self._dg_root(unit)
        if root is None or not self._dg_owned_by_player(root, self.player):
            return
        if not self._dg_is_death_guard_unit(root):
            return
        if not self._dg_on_battlefield(root, require_targetable=True):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        stratagem = self.get_by_name("SHOCK AND HORROR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem, target_unit=root):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        enemy_candidates = [
            enemy
            for enemy in list(self._dg_sickening_impact_enemy_candidates(root) or [])
            if callable(getattr(enemy, "force_battle_shock_test", None))
        ]
        if not enemy_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "unit_move_ended"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "SHOCK AND HORROR"
                and self._dg_root(reaction.get("unit")) is root
            ):
                return
        self._queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Charge phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "source_unit": root,
                "action": str(action or ""),
                "enemy_candidates": enemy_candidates,
            },
            use_timer=False,
        )

    def _queue_flyblown_host_enervating_onslaught_reaction(self, *, unit: Any, action: str) -> None:
        if not self._is_flyblown_host_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"charge", "charge move"}:
            return
        root = self._dg_root(unit)
        if root is None or not self._dg_owned_by_player(root, self.player):
            return
        if root not in self._dg_flyblown_host_infantry_candidates():
            return
        stratagem = self.get_by_name("ENERVATING ONSLAUGHT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._dg_effective_cp_cost(stratagem, target_unit=root):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        enemy_candidates = self._dg_enervating_onslaught_enemy_candidates(root)
        if not enemy_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "unit_move_ended"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "ENERVATING ONSLAUGHT"
                and self._dg_root(reaction.get("unit")) is root
            ):
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "source_unit": root,
            "action": str(action or ""),
            "enemy_candidates": enemy_candidates,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
            payload["target_enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _clear_deaths_heads_if_expired(self, *, player=None, phase=None) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "COMMAND_PHASE":
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id or self.game is None:
            return
        for game_player in list(getattr(self.game, "players", []) or []):
            army = getattr(game_player, "army", None)
            units = list(getattr(army, "units", []) or []) if army is not None else []
            for unit in list(units or []):
                root = self._dg_root(unit)
                sr = getattr(root, "special_rules", None) if root is not None else None
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("deaths_heads_owner", "") or "") != owner_id:
                    continue
                if not bool(sr.get("deaths_heads_active", False)):
                    continue
                for key in (
                    "deaths_heads_active",
                    "deaths_heads_owner",
                    "deaths_heads_turn",
                    "deaths_heads_source",
                ):
                    sr.pop(key, None)
                root.special_rules = sr

    def _cleanup_tallyband_summoners_phase_end_effects(self, *, phase=None) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"MOVEMENT_PHASE", "CHARGE_PHASE"}:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            expires_phase = str(
                sr.get("death_guard_tallyband_fleshy_avalanche_expires_phase", "") or ""
            ).strip().upper()
            if not bool(sr.get("death_guard_tallyband_fleshy_avalanche_active", False)):
                continue
            if expires_phase and expires_phase != phase_key:
                continue
            self._dg_remove_phase_move_types(
                sr,
                "bearer_unit_phase_move_terrain_only_types",
                "death_guard_tallyband_fleshy_avalanche_added_phase_move_terrain_only_types",
            )
            for key in (
                "death_guard_tallyband_fleshy_avalanche_active",
                "death_guard_tallyband_fleshy_avalanche_expires_phase",
                "death_guard_tallyband_fleshy_avalanche_turn_owner",
                "death_guard_tallyband_fleshy_avalanche_turn",
                "death_guard_tallyband_fleshy_avalanche_source",
            ):
                sr.pop(key, None)
            root.special_rules = sr

    def _clear_signal_pox_if_expired(self, *, player=None, phase=None) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        owner_id = str(getattr(player, "id", "") or "")
        game_map = getattr(getattr(self, "game", None), "map", None)
        if phase_key != "COMMAND_PHASE" or not owner_id or game_map is None:
            return
        for objective in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(objective, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            if not bool(getattr(loc, "signal_pox_active", False)):
                continue
            if str(getattr(loc, "signal_pox_owner", "") or "") != owner_id:
                continue
            for key in (
                "signal_pox_active",
                "signal_pox_owner",
                "signal_pox_turn",
                "signal_pox_source",
            ):
                if hasattr(loc, key):
                    setattr(loc, key, None if key != "signal_pox_active" else False)

    def _clear_blighted_land_if_expired(self, *, player=None, phase=None) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        owner_id = str(getattr(player, "id", "") or "")
        game_map = getattr(getattr(self, "game", None), "map", None)
        if phase_key != "COMMAND_PHASE" or not owner_id or game_map is None:
            return
        for terrain_feature in list(getattr(game_map, "terrain_features", []) or []):
            if terrain_feature is None:
                continue
            if not bool(getattr(terrain_feature, "blighted_land_active", False)):
                continue
            if str(getattr(terrain_feature, "blighted_land_owner", "") or "") != owner_id:
                continue
            for attr in (
                "blighted_land_active",
                "blighted_land_owner",
                "blighted_land_turn",
                "blighted_land_source",
            ):
                if hasattr(terrain_feature, attr):
                    delattr(terrain_feature, attr)

    def _use_death_guard_stratagem(self, s, **kwargs):
        name_u = str(getattr(s, "name", "") or "").strip().upper()
        if name_u not in {
            "BLIGHTED LAND",
            "BLOOMING PESTILENCE",
            "BLESSINGS OF FILTH",
            "DEATH'S HEADS",
            "DRONING HORROR",
            "DRAWN TO DESPAIR",
            "ENERVATING ONSLAUGHT",
            "EYE OF THE SWARM",
            "EYESTINGER STORM",
            "FLESHY AVALANCHE",
            "FONT OF FILTH",
            "GNAWING HUNGER",
            "GRIP OF THE WALKING POX",
            "GRIM REAPERS",
            "GROTESQUE FORTITUDE",
            "HIDDEN AMONGST THE DEAD",
            "MIRESLICK",
            "MALIGNANCE MAGNIFIED",
            "MORTARION'S TEACHINGS",
            "MOBILE VECTOR",
            "MYPHITIC INVIGORATION",
            "NAUSEATING PAROXYSMS",
            "PERSISTENT PESTS",
            "RABID INFUSION",
            "RELENTLESS GRIND",
            "SHAMBLING WALL",
            "SHOCK AND HORROR",
            "SICKENING IMPACT",
            "SIGNAL POX",
            "SMEARED WITH FILTH",
            "STINKING MIRE",
            "UNDYING SPITE",
            "VERMIN CLOUD",
            "ALL IS ROT",
            "AVATARS OF DECAY",
            "CLUTCHING CORRUPTION",
        }:
            return None

        champions_name = name_u in {
            "BLESSINGS OF FILTH",
            "DEATH'S HEADS",
            "GROTESQUE FORTITUDE",
            "MALIGNANCE MAGNIFIED",
            "MOBILE VECTOR",
            "RABID INFUSION",
        }
        flyblown_name = name_u in {
            "DRONING HORROR",
            "ENERVATING ONSLAUGHT",
            "EYE OF THE SWARM",
            "MYPHITIC INVIGORATION",
            "NAUSEATING PAROXYSMS",
            "VERMIN CLOUD",
        }
        death_lords_name = name_u in {
            "BLOOMING PESTILENCE",
            "GRIM REAPERS",
            "MORTARION'S TEACHINGS",
            "SICKENING IMPACT",
            "SIGNAL POX",
            "UNDYING SPITE",
        }
        mortarions_hammer_name = name_u in {
            "BLIGHTED LAND",
            "DRAWN TO DESPAIR",
            "EYESTINGER STORM",
            "FONT OF FILTH",
            "RELENTLESS GRIND",
            "STINKING MIRE",
        }
        shamblerot_name = name_u in {
            "GNAWING HUNGER",
            "GRIP OF THE WALKING POX",
            "HIDDEN AMONGST THE DEAD",
            "SHAMBLING WALL",
            "SHOCK AND HORROR",
            "SMEARED WITH FILTH",
        }
        tallyband_name = name_u in {
            "ALL IS ROT",
            "AVATARS OF DECAY",
            "CLUTCHING CORRUPTION",
            "FLESHY AVALANCHE",
            "MIRESLICK",
            "PERSISTENT PESTS",
        }
        if champions_name and not self._is_champions_of_contagion_detachment():
            return False
        if flyblown_name and not self._is_flyblown_host_detachment():
            return False
        if death_lords_name and not self._is_death_lords_chosen_detachment():
            return False
        if mortarions_hammer_name and not self._is_mortarions_hammer_detachment():
            return False
        if shamblerot_name and not self._is_shamblerot_vectorium_detachment():
            return False
        if tallyband_name and not self._is_tallyband_summoners_detachment():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        phase_key = self._dg_phase_key(phase_name or self._dg_current_phase_key())
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None

        if name_u == "GNAWING HUNGER":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            candidates = self._dg_shamblerot_poxwalker_candidates()
            if root is None:
                logger.error("ERROR: GNAWING HUNGER: no target unit provided")
                return False
            if phase_key != "COMMAND_PHASE":
                logger.error("ERROR: GNAWING HUNGER: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: GNAWING HUNGER: not your turn")
                return False
            if root not in candidates:
                logger.error("ERROR: GNAWING HUNGER: target must be an eligible POXWALKERS unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="shamblerot_vectorium",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "move_bonus",
                        "value": 1,
                        "source": str(s.name or "Gnawing Hunger"),
                        "expires_mode": "turn",
                        "expires_phase": "",
                    },
                    {
                        "effect": "attacks_bonus",
                        "attack_type": "melee",
                        "value": 1,
                        "source": str(s.name or "Gnawing Hunger"),
                        "expires_mode": "turn",
                        "expires_phase": "",
                    },
                    {
                        "effect": "strength_bonus",
                        "attack_type": "melee",
                        "value": 1,
                        "source": str(s.name or "Gnawing Hunger"),
                        "expires_mode": "turn",
                        "expires_phase": "",
                    },
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: GNAWING HUNGER: target POXWALKERS unit gains +1 Move and +1 melee Attacks/Strength until end of turn.")
            return True

        if name_u == "HIDDEN AMONGST THE DEAD":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            candidates = self._dg_shamblerot_poxwalker_candidates(
                require_in_strategic_reserves=True,
                require_not_attached=True,
            )
            if root is None:
                logger.error("ERROR: HIDDEN AMONGST THE DEAD: no target unit provided")
                return False
            if phase_key != "MOVEMENT_PHASE":
                logger.error("ERROR: HIDDEN AMONGST THE DEAD: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: HIDDEN AMONGST THE DEAD: not your turn")
                return False
            if root not in candidates:
                logger.error("ERROR: HIDDEN AMONGST THE DEAD: target must be an eligible POXWALKERS unit in Strategic Reserves that is not Attached")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["death_guard_hidden_amongst_the_dead_temp_deep_strike"] = True
            sr["death_guard_hidden_amongst_the_dead_turn_owner"] = str(getattr(active_player, "id", "") or getattr(self.player, "id", "") or "")
            sr["death_guard_hidden_amongst_the_dead_turn"] = int(self._dg_current_turn())
            sr["death_guard_hidden_amongst_the_dead_expires_phase"] = "MOVEMENT_PHASE"
            sr["death_guard_hidden_amongst_the_dead_source"] = str(s.name or "HIDDEN AMONGST THE DEAD")
            root.special_rules = sr
            invalidate = getattr(root, "_invalidate_ability_cache", None)
            if callable(invalidate):
                invalidate()
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: HIDDEN AMONGST THE DEAD: target POXWALKERS unit gains Deep Strike until end of the phase.")
            return True

        if name_u == "BLESSINGS OF FILTH":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: BLESSINGS OF FILTH: no target unit provided")
                return False
            if not self._dg_is_death_guard_unit(root):
                logger.error("ERROR: BLESSINGS OF FILTH: target must be a DEATH GUARD unit")
                return False
            if not self._dg_is_attached_unit(root):
                logger.error("ERROR: BLESSINGS OF FILTH: target must be an Attached unit")
                return False
            if not self._dg_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: BLESSINGS OF FILTH: target unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: BLESSINGS OF FILTH: target cannot be selected")
                return False
            if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                logger.error("ERROR: BLESSINGS OF FILTH: wrong phase")
                return False
            if phase_key == "SHOOTING_PHASE" and active_player is not self.player:
                logger.error("ERROR: BLESSINGS OF FILTH: Shooting phase use requires your turn")
                return False
            if not self._dg_unit_not_selected_for_phase_action(root, phase_key=phase_key):
                logger.error("ERROR: BLESSINGS OF FILTH: unit has already been selected this phase")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            attack_type = "ranged" if phase_key == "SHOOTING_PHASE" else "melee"
            self._dg_apply_temp_effects(
                root,
                detachment="champions_of_contagion",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "crit_hit_threshold",
                        "attack_type": attack_type,
                        "value": 5,
                        "source": str(s.name or "Blessings of Filth"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: BLESSINGS OF FILTH: target unit scores critical hits on unmodified 5+ this phase.")
            return True

        if name_u == "MALIGNANCE MAGNIFIED":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: MALIGNANCE MAGNIFIED: no target unit provided")
                return False
            if not self._dg_is_death_guard_unit(root):
                logger.error("ERROR: MALIGNANCE MAGNIFIED: target must be a DEATH GUARD unit")
                return False
            if not self._dg_is_attached_unit(root):
                logger.error("ERROR: MALIGNANCE MAGNIFIED: target must be an Attached unit")
                return False
            if not self._dg_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: MALIGNANCE MAGNIFIED: target unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: MALIGNANCE MAGNIFIED: target cannot be selected")
                return False
            if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                logger.error("ERROR: MALIGNANCE MAGNIFIED: wrong phase")
                return False
            if phase_key == "SHOOTING_PHASE" and active_player is not self.player:
                logger.error("ERROR: MALIGNANCE MAGNIFIED: Shooting phase use requires your turn")
                return False
            if not self._dg_unit_not_selected_for_phase_action(root, phase_key=phase_key):
                logger.error("ERROR: MALIGNANCE MAGNIFIED: unit has already been selected this phase")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            attack_type = "ranged" if phase_key == "SHOOTING_PHASE" else "melee"
            effects = [
                {
                    "effect": "hit_reroll",
                    "attack_type": attack_type,
                    "reroll_mode": "full",
                    "target_condition": "below_starting_strength",
                    "source": str(s.name or "Malignance Magnified"),
                },
                {
                    "effect": "wound_reroll",
                    "attack_type": attack_type,
                    "reroll_mode": "full",
                    "target_condition": "below_starting_strength",
                    "source": str(s.name or "Malignance Magnified"),
                },
            ]
            self._dg_apply_temp_effects(
                root,
                detachment="champions_of_contagion",
                phase_key=phase_key,
                effects=effects,
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: MALIGNANCE MAGNIFIED: target unit re-rolls hit and wound rolls vs targets below Starting Strength this phase.")
            return True

        if name_u == "GROTESQUE FORTITUDE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "GROTESQUE FORTITUDE":
                        continue
                    root = self._dg_root(reaction.get("target_unit") or reaction.get("unit"))
                    if root is not None:
                        break
            if root is None:
                logger.error("ERROR: GROTESQUE FORTITUDE: no target unit provided")
                return False
            attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
            if attacking_unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "GROTESQUE FORTITUDE":
                        continue
                    attacking_unit = reaction.get("attacking_unit")
                    if attacking_unit is not None:
                        break
            attacker_root = self._dg_root(attacking_unit)
            if attacker_root is None:
                logger.error("ERROR: GROTESQUE FORTITUDE: missing attacking unit")
                return False
            if not self._dg_is_death_guard_unit(root):
                logger.error("ERROR: GROTESQUE FORTITUDE: target must be a DEATH GUARD unit")
                return False
            if not self._dg_is_attached_unit(root):
                logger.error("ERROR: GROTESQUE FORTITUDE: target must be an Attached unit")
                return False
            if not self._dg_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: GROTESQUE FORTITUDE: target unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: GROTESQUE FORTITUDE: target cannot be selected")
                return False
            if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                logger.error("ERROR: GROTESQUE FORTITUDE: wrong phase")
                return False
            if phase_key == "SHOOTING_PHASE" and active_player is self.player:
                logger.error("ERROR: GROTESQUE FORTITUDE: Shooting phase use requires your opponent's turn")
                return False
            if self._dg_owned_by_player(attacker_root, self.player):
                logger.error("ERROR: GROTESQUE FORTITUDE: attacking unit must be an enemy unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="champions_of_contagion",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "toughness_bonus",
                        "value": 2,
                        "source": str(s.name or "Grotesque Fortitude"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: GROTESQUE FORTITUDE: target unit gains +2 Toughness this phase.")
            return True

        if name_u == "RABID INFUSION":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: RABID INFUSION: no target unit provided")
                return False
            if not self._dg_is_death_guard_unit(root):
                logger.error("ERROR: RABID INFUSION: target must be a DEATH GUARD unit")
                return False
            if not self._dg_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: RABID INFUSION: target unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: RABID INFUSION: target cannot be selected")
                return False
            if phase_key != "FIGHT_PHASE":
                logger.error("ERROR: RABID INFUSION: wrong phase")
                return False
            if self._dg_character_model_count(root) < 2:
                logger.error("ERROR: RABID INFUSION: target unit must include two Character models")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="champions_of_contagion",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "fight_first",
                        "source": str(s.name or "Rabid Infusion"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: RABID INFUSION: target unit gains Fights First this phase.")
            return True

        if name_u == "MOBILE VECTOR":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            source_root = self._dg_root(unit)
            if source_root is None:
                logger.error("ERROR: MOBILE VECTOR: no source unit provided")
                return False
            if not self._dg_is_death_guard_character_unit(source_root):
                logger.error("ERROR: MOBILE VECTOR: source must be a DEATH GUARD CHARACTER unit")
                return False
            if not self._dg_on_battlefield(source_root, require_targetable=True):
                logger.error("ERROR: MOBILE VECTOR: source unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
                logger.error("ERROR: MOBILE VECTOR: source unit cannot be selected")
                return False
            if phase_key != "MOVEMENT_PHASE":
                logger.error("ERROR: MOBILE VECTOR: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: MOBILE VECTOR: not your turn")
                return False
            if getattr(source_root, "attached_to", None) is not None:
                logger.error("ERROR: MOBILE VECTOR: source unit is already leading a unit")
                return False
            bodyguard_unit = kwargs.get("bodyguard_unit") or kwargs.get("target_bodyguard_unit") or kwargs.get("other_unit")
            candidates = list(self._dg_mobile_vector_bodyguard_candidates(source_root) or [])
            if bodyguard_unit is None:
                if len(candidates) == 1:
                    bodyguard_unit = candidates[0]
                else:
                    logger.error("ERROR: MOBILE VECTOR: missing eligible bodyguard target")
                    return False
            bodyguard_root = self._dg_root(bodyguard_unit)
            if bodyguard_root is None or bodyguard_root not in candidates:
                logger.error("ERROR: MOBILE VECTOR: selected bodyguard unit is not eligible")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=source_root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            source_root.attach_to_unit(bodyguard_root)
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: MOBILE VECTOR: %s attached to %s.",
                getattr(source_root, "name", "Unit"),
                getattr(bodyguard_root, "name", "Unit"),
            )
            return True

        if name_u == "DEATH'S HEADS":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            source_root = self._dg_root(unit)
            if source_root is None:
                logger.error("ERROR: DEATH'S HEADS: no source unit provided")
                return False
            if not self._dg_is_death_guard_unit(source_root):
                logger.error("ERROR: DEATH'S HEADS: source must be a DEATH GUARD unit")
                return False
            if not self._dg_on_battlefield(source_root, require_targetable=True):
                logger.error("ERROR: DEATH'S HEADS: source unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
                logger.error("ERROR: DEATH'S HEADS: source unit cannot be selected")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: DEATH'S HEADS: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: DEATH'S HEADS: not your turn")
                return False
            if not self._dg_unit_contains_named_member(source_root, "Biologus Putrifier"):
                logger.error("ERROR: DEATH'S HEADS: source must be a Biologus Putrifier unit")
                return False
            if self._dg_is_unit_engaged(source_root):
                logger.error("ERROR: DEATH'S HEADS: source unit cannot be within Engagement Range")
                return False
            if not self._dg_unit_not_selected_for_phase_action(source_root, phase_key=phase_key):
                logger.error("ERROR: DEATH'S HEADS: source unit has already been selected to shoot")
                return False
            enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
            candidates = list(self._dg_deaths_heads_enemy_candidates(source_root) or [])
            if enemy_unit is None:
                if len(candidates) == 1:
                    enemy_unit = candidates[0]
                else:
                    logger.error("ERROR: DEATH'S HEADS: missing enemy target selection")
                    return False
            enemy_root = self._dg_root(enemy_unit)
            if enemy_root is None or enemy_root not in candidates:
                logger.error("ERROR: DEATH'S HEADS: selected enemy unit is not eligible")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=source_root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["deaths_heads_active"] = True
            sr["deaths_heads_owner"] = str(getattr(self.player, "id", "") or "")
            sr["deaths_heads_turn"] = int(self._dg_current_turn())
            sr["deaths_heads_source"] = str(s.name or "Death's Heads")
            enemy_root.special_rules = sr
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: DEATH'S HEADS: target enemy unit gains all Plague effects until your next turn.")
            return True

        if name_u == "ALL IS ROT":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: ALL IS ROT: no target unit provided")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: ALL IS ROT: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: ALL IS ROT: not your turn")
                return False
            candidates = self._dg_tallyband_plague_legions_candidates(require_engaged=True)
            if root not in candidates:
                logger.error("ERROR: ALL IS ROT: target must be an eligible engaged PLAGUE LEGIONS unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="tallyband_summoners",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "all_is_rot",
                        "source": str(s.name or "All is Rot"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: ALL IS ROT: target PLAGUE LEGIONS unit ignores its own Engagement Range when selecting ranged targets this phase and risks mortal wounds for each wound it inflicts in Engagement Range."
            )
            return True

        if name_u == "AVATARS OF DECAY":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: AVATARS OF DECAY: no target unit provided")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: AVATARS OF DECAY: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: AVATARS OF DECAY: not your turn")
                return False
            candidates = self._dg_tallyband_plague_legions_candidates()
            if root not in candidates:
                logger.error("ERROR: AVATARS OF DECAY: target must be an eligible PLAGUE LEGIONS unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="tallyband_summoners",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "afflict_aura",
                        "range": 6.0,
                        "source": str(s.name or "Avatars of Decay"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: AVATARS OF DECAY: enemy units within 6\" of the target PLAGUE LEGIONS unit are Afflicted this phase.")
            return True

        if name_u == "CLUTCHING CORRUPTION":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: CLUTCHING CORRUPTION: no target unit provided")
                return False
            if phase_key != "FIGHT_PHASE":
                logger.error("ERROR: CLUTCHING CORRUPTION: wrong phase")
                return False
            candidates = self._dg_death_guard_battlefield_unit_candidates(require_not_fought=True)
            if root not in candidates:
                logger.error("ERROR: CLUTCHING CORRUPTION: target must be an eligible DEATH GUARD unit that has not fought")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="tallyband_summoners",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "hit_reroll",
                        "attack_type": "melee",
                        "reroll_mode": "full",
                        "target_condition": "engaged_with_friendly_plague_legions",
                        "source": str(s.name or "Clutching Corruption"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: CLUTCHING CORRUPTION: target DEATH GUARD unit re-rolls melee Hit rolls against enemies engaged with friendly PLAGUE LEGIONS this phase.")
            return True

        if name_u == "FLESHY AVALANCHE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: FLESHY AVALANCHE: no target unit provided")
                return False
            if phase_key not in {"MOVEMENT_PHASE", "CHARGE_PHASE"}:
                logger.error("ERROR: FLESHY AVALANCHE: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: FLESHY AVALANCHE: not your turn")
                return False
            candidates = self._dg_tallyband_plague_legions_candidates(
                require_monster=True,
                require_not_selected_to_move=phase_key == "MOVEMENT_PHASE",
                require_not_selected_to_charge=phase_key == "CHARGE_PHASE",
            )
            if root not in candidates:
                logger.error("ERROR: FLESHY AVALANCHE: target must be an eligible PLAGUE LEGIONS MONSTER unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            move_types = {"move", "advance"} if phase_key == "MOVEMENT_PHASE" else {"charge"}
            self._dg_merge_phase_move_types(
                sr,
                "bearer_unit_phase_move_terrain_only_types",
                "death_guard_tallyband_fleshy_avalanche_added_phase_move_terrain_only_types",
                set(move_types),
            )
            sr["death_guard_tallyband_fleshy_avalanche_active"] = True
            sr["death_guard_tallyband_fleshy_avalanche_expires_phase"] = phase_key
            sr["death_guard_tallyband_fleshy_avalanche_source"] = str(s.name or "FLESHY AVALANCHE")
            owner_id = str(getattr(self.player, "id", "") or "")
            if owner_id:
                sr["death_guard_tallyband_fleshy_avalanche_turn_owner"] = owner_id
            turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
            if turn:
                sr["death_guard_tallyband_fleshy_avalanche_turn"] = turn
            root.special_rules = sr
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: FLESHY AVALANCHE: %s can move horizontally through terrain features this phase.",
                getattr(root, "name", "Unit"),
            )
            return True

        if name_u == "MIRESLICK":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = list(kwargs.get("candidates") or [])
            enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
            if unit is None or enemy_unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "MIRESLICK":
                        continue
                    unit = unit or reaction.get("unit") or reaction.get("target_unit")
                    enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("target_enemy_unit")
                    if not candidates:
                        candidates = list(reaction.get("candidates") or [])
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            enemy_root = self._dg_root(enemy_unit)
            if enemy_root is None:
                logger.error("ERROR: MIRESLICK: missing enemy unit selected to Fall Back")
                return False
            if phase_key != "MOVEMENT_PHASE":
                logger.error("ERROR: MIRESLICK: wrong phase")
                return False
            if active_player is self.player:
                logger.error("ERROR: MIRESLICK: Movement phase use requires your opponent's turn")
                return False
            if self._dg_owned_by_player(enemy_root, self.player):
                logger.error("ERROR: MIRESLICK: enemy unit must be controlled by your opponent")
                return False
            if self._dg_attached_unit_has_keyword(enemy_root, "MONSTER") or self._dg_attached_unit_has_keyword(enemy_root, "VEHICLE"):
                logger.error("ERROR: MIRESLICK: enemy unit cannot be a MONSTER or VEHICLE")
                return False
            if not candidates:
                candidates = self._dg_tallyband_mireslick_candidates(enemy_root)
            root = self._dg_root(unit)
            if root is None and len(candidates) == 1:
                root = candidates[0]
            if root is None or root not in candidates:
                logger.error("ERROR: MIRESLICK: target must be an eligible PLAGUE LEGIONS unit within Engagement Range of the enemy")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="tallyband_summoners",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "fall_back_leadership_lock",
                        "source": str(s.name or "Mireslick"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: MIRESLICK: enemy units within Engagement Range of the target PLAGUE LEGIONS unit must pass Leadership tests to Fall Back this phase.")
            return True

        if name_u == "PERSISTENT PESTS":
            unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("destroyed_unit")
            candidates = list(kwargs.get("candidates") or [])
            if unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "PERSISTENT PESTS":
                        continue
                    unit = reaction.get("destroyed_unit") or reaction.get("unit") or reaction.get("target_unit")
                    if not candidates:
                        candidates = list(reaction.get("candidates") or [])
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            if unit is None and len(candidates) == 1:
                unit = candidates[0]
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: PERSISTENT PESTS: no destroyed unit provided")
                return False
            if not self._dg_owned_by_player(root, self.player):
                logger.error("ERROR: PERSISTENT PESTS: target must be a friendly unit")
                return False
            if not self._dg_unit_is_nurglings(root):
                logger.error("ERROR: PERSISTENT PESTS: target must be a friendly NURGLINGS unit")
                return False
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive) and bool(is_alive()):
                logger.error("ERROR: PERSISTENT PESTS: target unit must have been just destroyed")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            replacement = self._dg_spawn_tallyband_persistent_pests_unit(root, game=self.game)
            if replacement is None:
                logger.error("ERROR: PERSISTENT PESTS: failed to create replacement unit")
                return False
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: PERSISTENT PESTS: added a new %s unit to Strategic Reserves at Starting Strength.",
                getattr(replacement, "name", "Nurglings"),
            )
            return True

        if name_u == "GRIP OF THE WALKING POX":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = list(kwargs.get("candidates") or [])
            attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
            if unit is None or attacking_unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "GRIP OF THE WALKING POX":
                        continue
                    unit = unit or reaction.get("unit") or reaction.get("target_unit")
                    attacking_unit = attacking_unit or reaction.get("attacking_unit") or reaction.get("attacker_unit")
                    if not candidates:
                        candidates = list(reaction.get("candidates") or [])
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            if unit is None and len(candidates) == 1:
                unit = candidates[0]
            root = self._dg_root(unit)
            attacker_root = self._dg_root(attacking_unit)
            if root is None:
                logger.error("ERROR: GRIP OF THE WALKING POX: no target unit provided")
                return False
            if attacker_root is None:
                logger.error("ERROR: GRIP OF THE WALKING POX: missing attacking unit")
                return False
            if phase_key != "FIGHT_PHASE":
                logger.error("ERROR: GRIP OF THE WALKING POX: wrong phase")
                return False
            if self._dg_owned_by_player(attacker_root, self.player):
                logger.error("ERROR: GRIP OF THE WALKING POX: attacking unit must be enemy")
                return False
            if candidates and root not in candidates:
                logger.error("ERROR: GRIP OF THE WALKING POX: target is not currently eligible")
                return False
            if not self._dg_is_death_guard_unit(root) or not self._dg_unit_is_poxwalkers(root):
                logger.error("ERROR: GRIP OF THE WALKING POX: target must be a friendly POXWALKERS unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            pending_entries = [
                dict(entry)
                for entry in list(sr.get("death_guard_shamblerot_grip_entries", []) or [])
                if isinstance(entry, dict)
            ]
            pending_entries.append(
                {
                    "attacker_unit_id": self._dg_sort_key(attacker_root),
                    "start_alive_models": len(list(self._dg_alive_models(root) or [])),
                    "phase": "FIGHT_PHASE",
                    "turn": int(self._dg_current_turn()),
                    "source": str(s.name or "GRIP OF THE WALKING POX"),
                }
            )
            pending_entries.sort(
                key=lambda entry: (
                    str(entry.get("attacker_unit_id", "") or ""),
                    int(entry.get("turn", 0) or 0),
                )
            )
            sr["death_guard_shamblerot_grip_entries"] = pending_entries
            root.special_rules = sr
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: GRIP OF THE WALKING POX: target unit will retaliate with mortal wounds after the attacker fights.")
            return True

        if name_u == "SHAMBLING WALL":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = list(kwargs.get("candidates") or [])
            attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
            support_unit = kwargs.get("support_unit") or kwargs.get("secondary_unit")
            support_by_unit = dict(kwargs.get("support_candidates_by_unit") or {})
            if unit is None or attacking_unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "SHAMBLING WALL":
                        continue
                    unit = unit or reaction.get("unit") or reaction.get("target_unit")
                    attacking_unit = attacking_unit or reaction.get("attacking_unit") or reaction.get("attacker_unit")
                    support_unit = support_unit or reaction.get("support_unit")
                    if not candidates:
                        candidates = list(reaction.get("candidates") or [])
                    if not support_by_unit:
                        support_by_unit = dict(reaction.get("support_candidates_by_unit") or {})
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            if unit is None and len(candidates) == 1:
                unit = candidates[0]
            root = self._dg_root(unit)
            attacker_root = self._dg_root(attacking_unit)
            if root is None:
                logger.error("ERROR: SHAMBLING WALL: no protected unit provided")
                return False
            if attacker_root is None:
                logger.error("ERROR: SHAMBLING WALL: missing attacking unit")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: SHAMBLING WALL: wrong phase")
                return False
            if active_player is self.player:
                logger.error("ERROR: SHAMBLING WALL: Shooting phase use requires your opponent's turn")
                return False
            if self._dg_owned_by_player(attacker_root, self.player):
                logger.error("ERROR: SHAMBLING WALL: attacking unit must be enemy")
                return False
            if candidates and root not in candidates:
                logger.error("ERROR: SHAMBLING WALL: protected unit is not currently eligible")
                return False
            if not self._dg_is_death_guard_unit(root) or not self._dg_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: SHAMBLING WALL: protected unit must be an eligible DEATH GUARD unit on the battlefield")
                return False
            support_candidates = list(support_by_unit.get(self._dg_sort_key(root), []) or [])
            if not support_candidates:
                support_candidates = self._dg_shamblerot_shambling_wall_support_candidates(root, attacker_root)
            if support_unit is None and len(support_candidates) == 1:
                support_unit = support_candidates[0]
            support_root = self._dg_root(support_unit)
            if support_root is None:
                logger.error("ERROR: SHAMBLING WALL: no support POXWALKERS unit provided")
                return False
            if support_candidates and support_root not in support_candidates:
                logger.error("ERROR: SHAMBLING WALL: support unit is not currently eligible")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["death_guard_shamblerot_shambling_wall_active"] = True
            sr["death_guard_shamblerot_shambling_wall_support_unit_id"] = self._dg_sort_key(support_root)
            sr["death_guard_shamblerot_shambling_wall_attacker_unit_id"] = self._dg_sort_key(attacker_root)
            sr["death_guard_shamblerot_shambling_wall_expires_phase"] = "SHOOTING_PHASE"
            sr["death_guard_shamblerot_shambling_wall_turn_owner"] = str(getattr(active_player, "id", "") or "")
            sr["death_guard_shamblerot_shambling_wall_turn"] = int(self._dg_current_turn())
            sr["death_guard_shamblerot_shambling_wall_source"] = str(s.name or "SHAMBLING WALL")
            root.special_rules = sr
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: SHAMBLING WALL: attacks allocated to the protected unit can be redirected into support POXWALKERS this phase.")
            return True

        if name_u == "SHOCK AND HORROR":
            unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("source_unit")
            candidates = list(kwargs.get("candidates") or [])
            action = str(kwargs.get("action") or "")
            if unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "SHOCK AND HORROR":
                        continue
                    unit = unit or reaction.get("source_unit") or reaction.get("unit") or reaction.get("target_unit")
                    if not candidates:
                        candidates = list(reaction.get("candidates") or [])
                    if not action:
                        action = str(reaction.get("action") or "")
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: SHOCK AND HORROR: missing source unit")
                return False
            if phase_key != "CHARGE_PHASE":
                logger.error("ERROR: SHOCK AND HORROR: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: SHOCK AND HORROR: not your turn")
                return False
            if candidates and root not in candidates:
                logger.error("ERROR: SHOCK AND HORROR: source unit is not currently eligible")
                return False
            if not self._dg_is_death_guard_unit(root):
                logger.error("ERROR: SHOCK AND HORROR: source must be a DEATH GUARD unit")
                return False
            action_key = str(action or "").strip().lower().replace("_", " ")
            if action_key not in {"charge", "charge move"}:
                logger.error("ERROR: SHOCK AND HORROR: source unit must have just ended a Charge move")
                return False
            enemy_candidates = [
                enemy
                for enemy in list(kwargs.get("enemy_candidates") or self._dg_sickening_impact_enemy_candidates(root) or [])
                if callable(getattr(enemy, "force_battle_shock_test", None))
            ]
            if not enemy_candidates:
                logger.error("ERROR: SHOCK AND HORROR: no eligible enemy units within Engagement Range")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            for enemy_root in list(enemy_candidates or []):
                force_test = getattr(enemy_root, "force_battle_shock_test", None)
                if not callable(force_test):
                    continue
                force_test(
                    int(self._dg_current_turn() or 1),
                    modifier=-1,
                    source=str(s.name or "SHOCK AND HORROR"),
                )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: SHOCK AND HORROR: enemy units within Engagement Range take Battle-shock tests at -1.")
            return True

        if name_u == "SMEARED WITH FILTH":
            unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("destroyed_unit")
            enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
            enemy_candidates = list(kwargs.get("enemy_candidates") or [])
            if unit is None or (enemy_unit is None and not enemy_candidates):
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "SMEARED WITH FILTH":
                        continue
                    unit = unit or reaction.get("destroyed_unit") or reaction.get("unit") or reaction.get("target_unit")
                    enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("target_enemy_unit")
                    if not enemy_candidates:
                        enemy_candidates = list(reaction.get("enemy_candidates") or [])
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: SMEARED WITH FILTH: no destroyed unit provided")
                return False
            if phase_key != "FIGHT_PHASE":
                logger.error("ERROR: SMEARED WITH FILTH: wrong phase")
                return False
            if not self._dg_is_death_guard_unit(root) or not self._dg_unit_is_poxwalkers(root):
                logger.error("ERROR: SMEARED WITH FILTH: target must be a friendly POXWALKERS unit")
                return False
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive) and bool(is_alive()):
                logger.error("ERROR: SMEARED WITH FILTH: target unit must have been just destroyed")
                return False
            if not enemy_candidates:
                enemy_candidates = self._dg_shamblerot_smeared_with_filth_enemy_candidates(root)
            enemy_root = self._dg_root(enemy_unit) if enemy_unit is not None else None
            if enemy_root is None and len(enemy_candidates) == 1:
                enemy_root = self._dg_root(enemy_candidates[0])
            if enemy_root is None:
                logger.error("ERROR: SMEARED WITH FILTH: missing enemy unit selection")
                return False
            if enemy_candidates and enemy_root not in enemy_candidates:
                logger.error("ERROR: SMEARED WITH FILTH: selected enemy unit is not eligible")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["death_guard_shamblerot_smeared_with_filth_active"] = True
            sr["death_guard_shamblerot_smeared_with_filth_owner"] = str(getattr(self.player, "id", "") or "")
            sr["death_guard_shamblerot_smeared_with_filth_source"] = str(s.name or "SMEARED WITH FILTH")
            enemy_root.special_rules = sr
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: SMEARED WITH FILTH: selected enemy unit becomes Afflicted until end of battle.")
            return True

        if name_u == "DRAWN TO DESPAIR":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: DRAWN TO DESPAIR: no target unit provided")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: DRAWN TO DESPAIR: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: DRAWN TO DESPAIR: not your turn")
                return False
            candidates = self._dg_death_guard_battlefield_unit_candidates(require_not_shot=True)
            if root not in candidates:
                logger.error("ERROR: DRAWN TO DESPAIR: target must be an eligible DEATH GUARD unit that has not shot")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="mortarions_hammer",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "hit_reroll",
                        "attack_type": "ranged",
                        "reroll_mode": "full",
                        "target_condition": "opponent_deployment_zone",
                        "condition": "target_visible",
                        "exclude_keywords_any": ["AIRCRAFT"],
                        "source": str(s.name or "Drawn to Despair"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: DRAWN TO DESPAIR: target unit re-rolls ranged Hit rolls against visible non-AIRCRAFT units in the opponent deployment zone this phase."
            )
            return True

        if name_u == "FONT OF FILTH":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: FONT OF FILTH: no target unit provided")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: FONT OF FILTH: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: FONT OF FILTH: not your turn")
                return False
            candidates = self._dg_mortarions_hammer_vehicle_candidates(require_not_shot=True)
            if root not in candidates:
                logger.error("ERROR: FONT OF FILTH: target must be an eligible DEATH GUARD VEHICLE unit that has not shot")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            source_name = str(s.name or "Font of Filth")
            root_id = self._dg_sort_key(root)
            for model in list(self._dg_alive_models(root) or []):
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if not callable(set_keywords):
                    continue
                model_id = self._dg_sort_key(model)
                weapon_names: list[str] = []
                for wargear in list(getattr(model, "wargear", []) or []):
                    if wargear is None:
                        continue
                    is_ranged = getattr(wargear, "is_ranged", None)
                    if callable(is_ranged) and not bool(is_ranged()):
                        continue
                    if not callable(is_ranged):
                        is_melee = getattr(wargear, "is_melee", None)
                        if callable(is_melee) and bool(is_melee()):
                            continue
                    weapon_name = str(getattr(wargear, "name", "") or "").strip()
                    if weapon_name and weapon_name not in weapon_names:
                        weapon_names.append(weapon_name)
                for weapon_name in sorted(list(weapon_names or []), key=str.lower):
                    set_keywords(
                        key=f"death_guard_mortarions_hammer_font_of_filth:{root_id}:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=["ASSAULT"],
                        source=source_name,
                        expires_phase="SHOOTING_PHASE",
                        attack_type="ranged",
                    )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: FONT OF FILTH: target unit gains [ASSAULT] on ranged weapons this phase.")
            return True

        if name_u == "RELENTLESS GRIND":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: RELENTLESS GRIND: no target unit provided")
                return False
            if phase_key not in {"MOVEMENT_PHASE", "CHARGE_PHASE"}:
                logger.error("ERROR: RELENTLESS GRIND: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: RELENTLESS GRIND: not your turn")
                return False
            candidates = self._dg_mortarions_hammer_vehicle_candidates(
                require_not_selected_to_move=phase_key == "MOVEMENT_PHASE",
                require_not_selected_to_charge=phase_key == "CHARGE_PHASE",
            )
            if root not in candidates:
                logger.error("ERROR: RELENTLESS GRIND: target must be an eligible DEATH GUARD VEHICLE unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            move_types = {"move", "advance"} if phase_key == "MOVEMENT_PHASE" else {"charge"}
            self._dg_merge_phase_move_types(
                sr,
                "bearer_unit_phase_move_terrain_only_types",
                "death_guard_mortarions_hammer_relentless_grind_added_phase_move_terrain_only_types",
                set(move_types),
            )
            sr["death_guard_mortarions_hammer_relentless_grind_active"] = True
            sr["death_guard_mortarions_hammer_relentless_grind_expires_phase"] = phase_key
            sr["death_guard_mortarions_hammer_relentless_grind_source"] = str(s.name or "RELENTLESS GRIND")
            owner_id = str(getattr(self.player, "id", "") or "")
            if owner_id:
                sr["death_guard_mortarions_hammer_relentless_grind_turn_owner"] = owner_id
            turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
            if turn:
                sr["death_guard_mortarions_hammer_relentless_grind_turn"] = turn
            root.special_rules = sr
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: RELENTLESS GRIND: %s can move horizontally through terrain features this phase.",
                getattr(root, "name", "Unit"),
            )
            return True

        if name_u == "BLIGHTED LAND":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: BLIGHTED LAND: no target unit provided")
                return False
            if phase_key != "MOVEMENT_PHASE":
                logger.error("ERROR: BLIGHTED LAND: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: BLIGHTED LAND: not your turn")
                return False
            candidates = self._dg_mortarions_hammer_vehicle_candidates()
            if root not in candidates:
                logger.error("ERROR: BLIGHTED LAND: target must be an eligible DEATH GUARD VEHICLE unit")
                return False
            terrain_feature = (
                kwargs.get("terrain_feature")
                or kwargs.get("target_terrain_feature")
                or kwargs.get("terrain")
            )
            terrain_candidates = list(kwargs.get("terrain_candidates") or [])
            if not terrain_candidates:
                terrain_candidates = self._dg_blighted_land_terrain_candidates(root)
            if terrain_feature is None and len(terrain_candidates) == 1:
                terrain_feature = terrain_candidates[0]
            selected_terrain = self._dg_resolve_terrain_candidate(terrain_feature, terrain_candidates)
            if selected_terrain is None:
                logger.error("ERROR: BLIGHTED LAND: selected terrain feature is not eligible")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            selected_terrain.blighted_land_active = True
            selected_terrain.blighted_land_owner = str(getattr(self.player, "id", "") or "")
            selected_terrain.blighted_land_turn = int(self._dg_current_turn())
            selected_terrain.blighted_land_source = str(s.name or "Blighted Land")
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: BLIGHTED LAND: selected terrain feature Afflicts enemy units within 3\" until your next turn.")
            return True

        if name_u == "EYESTINGER STORM":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = list(kwargs.get("candidates") or [])
            if unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "EYESTINGER STORM":
                        continue
                    unit = reaction.get("unit") or reaction.get("target_unit")
                    if not candidates:
                        candidates = list(reaction.get("candidates") or [])
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            if unit is None and len(candidates) == 1:
                unit = candidates[0]
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: EYESTINGER STORM: no target unit provided")
                return False
            if phase_key != "COMMAND_PHASE":
                logger.error("ERROR: EYESTINGER STORM: wrong phase")
                return False
            if active_player is self.player:
                logger.error("ERROR: EYESTINGER STORM: Command phase use requires your opponent's turn")
                return False
            if candidates and root not in candidates:
                logger.error("ERROR: EYESTINGER STORM: target is not currently eligible")
                return False
            if root not in self._dg_mortarions_hammer_vehicle_candidates():
                logger.error("ERROR: EYESTINGER STORM: target must be an eligible DEATH GUARD VEHICLE unit")
                return False
            objective = kwargs.get("objective") or kwargs.get("objective_marker")
            objective_candidates = list(kwargs.get("objective_candidates") or [])
            if not objective_candidates:
                objective_candidates = self._dg_eyestinger_storm_objective_candidates(root)
            if objective is None and len(objective_candidates) == 1:
                objective = objective_candidates[0]
            if objective is None:
                logger.error("ERROR: EYESTINGER STORM: no objective marker selected")
                return False
            selected_objective = self._dg_resolve_objective_candidate(objective, objective_candidates)
            if selected_objective is None:
                logger.error("ERROR: EYESTINGER STORM: selected objective marker is not eligible")
                return False
            affected_enemies = self._dg_afflicted_enemy_units_within_objective(selected_objective)
            if not affected_enemies:
                logger.error("ERROR: EYESTINGER STORM: no Afflicted enemy units are within range of the selected objective marker")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            current_turn = max(1, int(self._dg_current_turn() or 1))
            source_name = str(s.name or "EYESTINGER STORM")
            for enemy_root in list(affected_enemies or []):
                enemy_sr = getattr(enemy_root, "special_rules", None)
                if not isinstance(enemy_sr, dict):
                    enemy_sr = {}
                enemy_sr["battle_shock_suppress_other_tests_phase"] = "COMMAND_PHASE"
                enemy_sr["battle_shock_suppress_other_tests_source"] = source_name
                enemy_sr["battle_shock_allow_suppressed_test"] = True
                enemy_root.special_rules = enemy_sr
                take_test = getattr(enemy_root, "take_battle_shock_test", None)
                if callable(take_test):
                    take_test(current_turn)
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: EYESTINGER STORM: affected Afflicted enemy units within the selected objective marker's range take Battle-shock tests.")
            return True

        if name_u == "STINKING MIRE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = list(kwargs.get("candidates") or [])
            if unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "STINKING MIRE":
                        continue
                    unit = reaction.get("unit") or reaction.get("target_unit")
                    if not candidates:
                        candidates = list(reaction.get("candidates") or [])
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            if unit is None and len(candidates) == 1:
                unit = candidates[0]
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: STINKING MIRE: no target unit provided")
                return False
            if phase_key != "CHARGE_PHASE":
                logger.error("ERROR: STINKING MIRE: wrong phase")
                return False
            if active_player is self.player:
                logger.error("ERROR: STINKING MIRE: Charge phase use requires your opponent's turn")
                return False
            if candidates and root not in candidates:
                logger.error("ERROR: STINKING MIRE: target is not currently eligible")
                return False
            if root not in self._dg_mortarions_hammer_vehicle_candidates():
                logger.error("ERROR: STINKING MIRE: target must be an eligible DEATH GUARD VEHICLE unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["death_guard_mortarions_hammer_stinking_mire_active"] = True
            sr["death_guard_mortarions_hammer_stinking_mire_charge_modifier"] = 2
            sr["death_guard_mortarions_hammer_stinking_mire_expires_phase"] = "CHARGE_PHASE"
            sr["death_guard_mortarions_hammer_stinking_mire_source"] = str(s.name or "STINKING MIRE")
            sr["death_guard_mortarions_hammer_stinking_mire_turn_owner"] = str(
                getattr(getattr(self.game, "get_current_player", lambda: None)(), "id", "") or ""
            )
            sr["death_guard_mortarions_hammer_stinking_mire_turn"] = int(self._dg_current_turn())
            root.special_rules = sr
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: STINKING MIRE: enemy units suffer -2 to Charge rolls when charging the target unit this phase.")
            return True

        if name_u == "DRONING HORROR":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: DRONING HORROR: no target unit provided")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: DRONING HORROR: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: DRONING HORROR: not your turn")
                return False
            if root not in self._dg_flyblown_host_infantry_candidates(require_not_shot=True):
                logger.error("ERROR: DRONING HORROR: target must be an eligible DEATH GUARD INFANTRY unit that has not shot")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="flyblown_host",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "hit_reroll",
                        "attack_type": "ranged",
                        "reroll_mode": "ones",
                        "source": str(s.name or "Droning Horror"),
                    },
                    {
                        "effect": "hit_reroll",
                        "attack_type": "ranged",
                        "reroll_mode": "full",
                        "condition": "within_half_range",
                        "source": str(s.name or "Droning Horror"),
                    },
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: DRONING HORROR: target unit re-rolls ranged Hit rolls of 1, or all ranged Hit rolls against targets within half range, this phase."
            )
            return True

        if name_u == "EYE OF THE SWARM":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: EYE OF THE SWARM: no target unit provided")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: EYE OF THE SWARM: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: EYE OF THE SWARM: not your turn")
                return False
            if root not in self._dg_flyblown_host_infantry_candidates(require_not_shot=True):
                logger.error("ERROR: EYE OF THE SWARM: target must be an eligible DEATH GUARD INFANTRY unit that has not shot")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            source_name = str(s.name or "Eye of the Swarm")
            root_id = self._dg_sort_key(root)
            for model in list(self._dg_alive_models(root) or []):
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if not callable(set_keywords):
                    continue
                model_id = self._dg_sort_key(model)
                weapon_names: list[str] = []
                for wargear in list(getattr(model, "wargear", []) or []):
                    if wargear is None:
                        continue
                    is_ranged = getattr(wargear, "is_ranged", None)
                    if callable(is_ranged) and not bool(is_ranged()):
                        continue
                    if not callable(is_ranged):
                        is_melee = getattr(wargear, "is_melee", None)
                        if callable(is_melee) and bool(is_melee()):
                            continue
                    if self._dg_wargear_has_keyword(wargear, "BLAST"):
                        continue
                    weapon_name = str(getattr(wargear, "name", "") or "").strip()
                    if weapon_name and weapon_name not in weapon_names:
                        weapon_names.append(weapon_name)
                for weapon_name in sorted(list(weapon_names or []), key=str.lower):
                    set_keywords(
                        key=f"death_guard_flyblown_host_eye_of_the_swarm:{root_id}:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=["PISTOL"],
                        source=source_name,
                        expires_phase="SHOOTING_PHASE",
                        attack_type="ranged",
                    )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: EYE OF THE SWARM: target unit gains [PISTOL] on non-BLAST ranged weapons this phase.")
            return True

        if name_u == "NAUSEATING PAROXYSMS":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = list(kwargs.get("candidates") or [])
            if unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "NAUSEATING PAROXYSMS":
                        continue
                    unit = reaction.get("unit") or reaction.get("target_unit")
                    if not candidates:
                        candidates = list(reaction.get("candidates") or [])
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            if unit is None and len(candidates) == 1:
                unit = candidates[0]
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: NAUSEATING PAROXYSMS: no target unit provided")
                return False
            if phase_key != "FIGHT_PHASE":
                logger.error("ERROR: NAUSEATING PAROXYSMS: wrong phase")
                return False
            if candidates and root not in candidates:
                logger.error("ERROR: NAUSEATING PAROXYSMS: target is not currently eligible")
                return False
            if root not in self._dg_flyblown_host_infantry_candidates(require_engaged=True):
                logger.error("ERROR: NAUSEATING PAROXYSMS: target must be an eligible DEATH GUARD INFANTRY unit within Engagement Range")
                return False
            enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
            enemy_candidates = self._dg_nauseating_paroxysms_enemy_candidates(root)
            enemy_root = self._dg_root(enemy_unit) if enemy_unit is not None else None
            if enemy_root is None and len(enemy_candidates) == 1:
                enemy_root = self._dg_root(enemy_candidates[0])
            if enemy_root is None:
                logger.error("ERROR: NAUSEATING PAROXYSMS: missing enemy unit within Engagement Range")
                return False
            if enemy_root not in enemy_candidates:
                logger.error("ERROR: NAUSEATING PAROXYSMS: selected enemy unit is not eligible")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            force_test = getattr(enemy_root, "force_battle_shock_test", None)
            if not callable(force_test):
                logger.error("ERROR: NAUSEATING PAROXYSMS: target enemy unit cannot take a forced Battle-shock test")
                return False
            force_test(
                int(self._dg_current_turn() or 1),
                modifier=-1,
                source=str(s.name or "NAUSEATING PAROXYSMS"),
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: NAUSEATING PAROXYSMS: %s forces %s to take a Battle-shock test at -1.",
                getattr(root, "name", "Unit"),
                getattr(enemy_root, "name", "Enemy"),
            )
            return True

        if name_u == "VERMIN CLOUD":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: VERMIN CLOUD: no target unit provided")
                return False
            if phase_key != "FIGHT_PHASE":
                logger.error("ERROR: VERMIN CLOUD: wrong phase")
                return False
            if root not in self._dg_flyblown_host_infantry_candidates(require_not_fought=True):
                logger.error("ERROR: VERMIN CLOUD: target must be an eligible DEATH GUARD INFANTRY unit that has not fought")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr = dict(sr)
            sr["stratagem_pile_in_distance_override"] = max(6.0, float(sr.get("stratagem_pile_in_distance_override", 0.0) or 0.0))
            sr["stratagem_pile_in_expires_phase"] = "FIGHT_PHASE"
            sr["stratagem_pile_in_source"] = str(s.name or "VERMIN CLOUD")
            sr["stratagem_consolidate_distance_override"] = max(
                6.0,
                float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0),
            )
            sr["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
            sr["stratagem_consolidate_source"] = str(s.name or "VERMIN CLOUD")
            root.special_rules = sr
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: VERMIN CLOUD: target unit can Pile-in and Consolidate up to 6\" this phase.")
            return True

        if name_u == "ENERVATING ONSLAUGHT":
            unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("source_unit")
            enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
            enemy_candidates = list(kwargs.get("enemy_candidates") or [])
            action = str(kwargs.get("action") or "")
            if unit is None or (enemy_unit is None and not enemy_candidates):
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "ENERVATING ONSLAUGHT":
                        continue
                    unit = unit or reaction.get("source_unit") or reaction.get("unit") or reaction.get("target_unit")
                    enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("target_enemy_unit")
                    if not enemy_candidates:
                        enemy_candidates = list(reaction.get("enemy_candidates") or [])
                    if not action:
                        action = str(reaction.get("action") or "")
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: ENERVATING ONSLAUGHT: missing source unit")
                return False
            if phase_key != "CHARGE_PHASE":
                logger.error("ERROR: ENERVATING ONSLAUGHT: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: ENERVATING ONSLAUGHT: not your turn")
                return False
            if root not in self._dg_flyblown_host_infantry_candidates():
                logger.error("ERROR: ENERVATING ONSLAUGHT: source must be an eligible DEATH GUARD INFANTRY unit")
                return False
            action_key = str(action or "").strip().lower().replace("_", " ")
            if action_key not in {"charge", "charge move"}:
                logger.error("ERROR: ENERVATING ONSLAUGHT: source unit must have just ended a Charge move")
                return False
            if not enemy_candidates:
                enemy_candidates = self._dg_enervating_onslaught_enemy_candidates(root)
            enemy_root = self._dg_root(enemy_unit) if enemy_unit is not None else None
            if enemy_root is None and len(enemy_candidates) == 1:
                enemy_root = self._dg_root(enemy_candidates[0])
            if enemy_root is None:
                logger.error("ERROR: ENERVATING ONSLAUGHT: missing eligible enemy unit within Engagement Range")
                return False
            if enemy_candidates and enemy_root not in enemy_candidates:
                logger.error("ERROR: ENERVATING ONSLAUGHT: selected enemy unit is not eligible")
                return False
            engaged_models = self._dg_models_within_engagement_range_of_enemy(root, enemy_root)
            if not engaged_models:
                logger.error("ERROR: ENERVATING ONSLAUGHT: no models in your unit are within Engagement Range of that enemy")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            rolls: list[int] = []
            success_count = 0
            for model in list(engaged_models or []):
                roll = int(dice_module.get_roll("D6") or 0)
                rolls.append(int(roll))
                model_unit = getattr(model, "parent_unit", None)
                is_cultist = bool(model_unit is not None and self._dg_has_keyword(model_unit, "CULTIST"))
                is_poxwalker = bool(model_unit is not None and self._dg_has_keyword(model_unit, "POXWALKERS"))
                modifier = 0 if (is_cultist or is_poxwalker) else 1
                if int(roll) + int(modifier) >= 5:
                    success_count += 1
            mortal_wounds = min(6, int(success_count))
            if mortal_wounds > 0:
                apply_mortals = getattr(root, "_apply_mortal_wounds_to_unit", None)
                if callable(apply_mortals):
                    apply_mortals(enemy_root, int(mortal_wounds), game_map=getattr(self.game, "map", None))
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: ENERVATING ONSLAUGHT: %s rolled %s and dealt %d mortal wound(s) to %s.",
                getattr(root, "name", "Unit"),
                list(rolls),
                int(mortal_wounds),
                getattr(enemy_root, "name", "Enemy"),
            )
            return True

        if name_u == "MYPHITIC INVIGORATION":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = list(kwargs.get("candidates") or [])
            attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
            if unit is None or attacking_unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "MYPHITIC INVIGORATION":
                        continue
                    unit = unit or reaction.get("unit") or reaction.get("target_unit")
                    attacking_unit = attacking_unit or reaction.get("attacking_unit") or reaction.get("attacker_unit")
                    if not candidates:
                        candidates = list(reaction.get("candidates") or [])
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            if unit is None and len(candidates) == 1:
                unit = candidates[0]
            root = self._dg_root(unit)
            attacker_root = self._dg_root(attacking_unit)
            if root is None:
                logger.error("ERROR: MYPHITIC INVIGORATION: no target unit provided")
                return False
            if attacker_root is None:
                logger.error("ERROR: MYPHITIC INVIGORATION: missing attacking unit")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: MYPHITIC INVIGORATION: wrong phase")
                return False
            if active_player is self.player:
                logger.error("ERROR: MYPHITIC INVIGORATION: Shooting phase use requires your opponent's turn")
                return False
            if self._dg_owned_by_player(attacker_root, self.player):
                logger.error("ERROR: MYPHITIC INVIGORATION: attacking unit must be an enemy unit")
                return False
            if candidates and root not in candidates:
                logger.error("ERROR: MYPHITIC INVIGORATION: target is not currently eligible")
                return False
            if root not in self._dg_flyblown_host_infantry_candidates():
                logger.error("ERROR: MYPHITIC INVIGORATION: target must be an eligible DEATH GUARD INFANTRY unit")
                return False
            if not self._dg_unit_is_within_myphitic_blight_hauler_range(root):
                logger.error("ERROR: MYPHITIC INVIGORATION: target must be within 6\" of a friendly Myphitic Blight-hauler unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="flyblown_host",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "wound_roll_penalty",
                        "attack_type": "ranged",
                        "value": 1,
                        "condition": "strength_gt_toughness",
                        "source": str(s.name or "Myphitic Invigoration"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: MYPHITIC INVIGORATION: attacks that target this unit suffer -1 to wound if Strength exceeds its Toughness this phase.")
            return True

        if name_u == "BLOOMING PESTILENCE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: BLOOMING PESTILENCE: no target unit provided")
                return False
            candidates = self._dg_death_lords_chosen_terminator_candidates()
            if root not in candidates:
                logger.error("ERROR: BLOOMING PESTILENCE: target must be an eligible DEATH GUARD TERMINATOR unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="death_lords_chosen",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "contagion_range_bonus",
                        "value": 3,
                        "source": str(s.name or "Blooming Pestilence"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: BLOOMING PESTILENCE: target unit gains +3\" Contagion Range this phase.")
            return True

        if name_u == "GRIM REAPERS":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: GRIM REAPERS: no target unit provided")
                return False
            if phase_key != "FIGHT_PHASE":
                logger.error("ERROR: GRIM REAPERS: wrong phase")
                return False
            candidates = self._dg_death_lords_chosen_terminator_candidates(require_not_fought=True)
            if root not in candidates:
                logger.error("ERROR: GRIM REAPERS: target must be an eligible TERMINATOR unit that has not fought")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="death_lords_chosen",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "hit_reroll",
                        "attack_type": "melee",
                        "reroll_mode": "full",
                        "exclude_keywords_any": ["MONSTER", "VEHICLE"],
                        "source": str(s.name or "Grim Reapers"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: GRIM REAPERS: target unit re-rolls melee Hit rolls against non-MONSTER, non-VEHICLE targets this phase.")
            return True

        if name_u == "SIGNAL POX":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            source_root = self._dg_root(unit)
            if source_root is None:
                logger.error("ERROR: SIGNAL POX: no source unit provided")
                return False
            if not self._dg_is_death_guard_unit(source_root):
                logger.error("ERROR: SIGNAL POX: source must be a DEATH GUARD unit")
                return False
            if not self._dg_on_battlefield(source_root, require_targetable=True):
                logger.error("ERROR: SIGNAL POX: source unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
                logger.error("ERROR: SIGNAL POX: source unit cannot be selected")
                return False
            if phase_key != "COMMAND_PHASE":
                logger.error("ERROR: SIGNAL POX: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: SIGNAL POX: not your turn")
                return False
            if not self._dg_unit_contains_named_member(source_root, "Lord of Virulence"):
                logger.error("ERROR: SIGNAL POX: source must be a Lord of Virulence model")
                return False
            objective = kwargs.get("objective") or kwargs.get("objective_marker")
            objective_candidates = list(kwargs.get("objective_candidates") or [])
            if not objective_candidates:
                objective_candidates = self._dg_signal_pox_objective_candidates(source_root)
            if objective is None and len(objective_candidates) == 1:
                objective = objective_candidates[0]
            if objective is None:
                logger.error("ERROR: SIGNAL POX: no objective marker selected")
                return False
            selected_objective = self._dg_resolve_objective_candidate(objective, objective_candidates)
            if selected_objective is None:
                logger.error("ERROR: SIGNAL POX: selected objective marker is not eligible")
                return False
            objective_location = getattr(selected_objective, "location", None)
            if objective_location is None:
                logger.error("ERROR: SIGNAL POX: objective marker location unavailable")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=source_root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            objective_location.signal_pox_active = True
            objective_location.signal_pox_owner = str(getattr(self.player, "id", "") or "")
            objective_location.signal_pox_turn = int(self._dg_current_turn())
            objective_location.signal_pox_source = str(s.name or "Signal Pox")
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: SIGNAL POX: selected objective marker Afflicts enemy units within its range until your next turn.")
            return True

        if name_u == "UNDYING SPITE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = list(kwargs.get("candidates") or [])
            attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
            if unit is None or attacking_unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "UNDYING SPITE":
                        continue
                    unit = unit or reaction.get("unit") or reaction.get("target_unit")
                    attacking_unit = attacking_unit or reaction.get("attacking_unit") or reaction.get("attacker_unit")
                    if not candidates:
                        candidates = list(reaction.get("candidates") or [])
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            if unit is None and len(candidates) == 1:
                unit = candidates[0]
            root = self._dg_root(unit)
            attacker_root = self._dg_root(attacking_unit)
            if root is None:
                logger.error("ERROR: UNDYING SPITE: no target unit provided")
                return False
            if attacker_root is None:
                logger.error("ERROR: UNDYING SPITE: missing attacking unit")
                return False
            if phase_key != "FIGHT_PHASE":
                logger.error("ERROR: UNDYING SPITE: wrong phase")
                return False
            if self._dg_owned_by_player(attacker_root, self.player):
                logger.error("ERROR: UNDYING SPITE: attacking unit must be enemy")
                return False
            if candidates and root not in candidates:
                logger.error("ERROR: UNDYING SPITE: target is not currently eligible")
                return False
            if root not in self._dg_death_lords_chosen_terminator_candidates():
                logger.error("ERROR: UNDYING SPITE: target must be an eligible TERMINATOR unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr = dict(sr)
            sr["death_guard_undying_spite_active"] = True
            sr["death_guard_undying_spite_threshold"] = 4
            sr["death_guard_undying_spite_expires_phase"] = "FIGHT_PHASE"
            sr["death_guard_undying_spite_source"] = str(s.name or "UNDYING SPITE")
            sr["death_guard_undying_spite_turn"] = int(self._dg_current_turn())
            sr["death_guard_undying_spite_turn_owner"] = str(getattr(active_player, "id", "") or getattr(self.player, "id", "") or "")
            root.special_rules = sr
            invalidate = getattr(root, "_invalidate_ability_cache", None)
            if callable(invalidate):
                invalidate()
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: UNDYING SPITE: target unit gains melee fight-on-death on 4+ this phase.")
            return True

        if name_u == "MORTARION'S TEACHINGS":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: MORTARION'S TEACHINGS: no target unit provided")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: MORTARION'S TEACHINGS: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: MORTARION'S TEACHINGS: not your turn")
                return False
            candidates = self._dg_death_lords_chosen_terminator_candidates(require_not_shot=True)
            if root not in candidates:
                logger.error("ERROR: MORTARION'S TEACHINGS: target must be an eligible TERMINATOR unit that has not shot")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            source_name = str(s.name or "Mortarion's Teachings")
            root_id = self._dg_sort_key(root)
            for model in list(self._dg_alive_models(root) or []):
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if not callable(set_keywords):
                    continue
                model_id = self._dg_sort_key(model)
                weapon_names: list[str] = []
                for wargear in list(getattr(model, "wargear", []) or []):
                    if wargear is None:
                        continue
                    is_ranged = getattr(wargear, "is_ranged", None)
                    if callable(is_ranged) and not bool(is_ranged()):
                        continue
                    if not callable(is_ranged):
                        is_melee = getattr(wargear, "is_melee", None)
                        if callable(is_melee) and bool(is_melee()):
                            continue
                    weapon_name = str(getattr(wargear, "name", "") or "").strip()
                    if weapon_name and weapon_name not in weapon_names:
                        weapon_names.append(weapon_name)
                for weapon_name in sorted(list(weapon_names or []), key=str.lower):
                    set_keywords(
                        key=f"death_guard_death_lords_chosen_mortarions_teachings:{root_id}:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=["ASSAULT", "HEAVY"],
                        source=source_name,
                        expires_phase="SHOOTING_PHASE",
                        attack_type="ranged",
                    )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: MORTARION'S TEACHINGS: target unit gains [ASSAULT] and [HEAVY] on ranged weapons this phase.")
            return True

        if name_u == "SICKENING IMPACT":
            unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("source_unit")
            enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
            enemy_candidates = list(kwargs.get("enemy_candidates") or [])
            action = str(kwargs.get("action") or "")
            if unit is None or (enemy_unit is None and not enemy_candidates):
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "SICKENING IMPACT":
                        continue
                    unit = unit or reaction.get("source_unit") or reaction.get("unit") or reaction.get("target_unit")
                    enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("target_enemy_unit")
                    if not enemy_candidates:
                        enemy_candidates = list(reaction.get("enemy_candidates") or [])
                    if not action:
                        action = str(reaction.get("action") or "")
                    if not kwargs.get("phase_name"):
                        kwargs["phase_name"] = reaction.get("phase_name")
                    break
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: SICKENING IMPACT: missing source unit")
                return False
            if phase_key != "CHARGE_PHASE":
                logger.error("ERROR: SICKENING IMPACT: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: SICKENING IMPACT: not your turn")
                return False
            if root not in self._dg_death_lords_chosen_terminator_candidates():
                logger.error("ERROR: SICKENING IMPACT: source must be an eligible TERMINATOR unit")
                return False
            action_key = str(action or "").strip().lower().replace("_", " ")
            if action_key not in {"charge", "charge move"}:
                logger.error("ERROR: SICKENING IMPACT: source unit must have just ended a Charge move")
                return False
            if not enemy_candidates:
                enemy_candidates = self._dg_sickening_impact_enemy_candidates(root)
            enemy_root = self._dg_root(enemy_unit) if enemy_unit is not None else None
            if enemy_root is None and len(enemy_candidates) == 1:
                enemy_root = self._dg_root(enemy_candidates[0])
            if enemy_root is None:
                logger.error("ERROR: SICKENING IMPACT: missing enemy unit within Engagement Range")
                return False
            if enemy_candidates and enemy_root not in enemy_candidates:
                logger.error("ERROR: SICKENING IMPACT: selected enemy unit is not eligible")
                return False
            engaged_models = self._dg_models_within_engagement_range_of_enemy(root, enemy_root)
            if not engaged_models:
                logger.error("ERROR: SICKENING IMPACT: no models in your unit are within Engagement Range of that enemy")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            rolls = [int(dice_module.get_roll("D6") or 0) for _ in range(len(engaged_models))]
            mortal_wounds = min(6, sum(1 for roll in list(rolls or []) if int(roll or 0) >= 2))
            if mortal_wounds > 0:
                apply_mortals = getattr(root, "_apply_mortal_wounds_to_unit", None)
                if callable(apply_mortals):
                    apply_mortals(enemy_root, int(mortal_wounds), game_map=getattr(self.game, "map", None))
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: SICKENING IMPACT: %s rolled %s and dealt %d mortal wound(s) to %s.",
                getattr(root, "name", "Unit"),
                list(rolls),
                int(mortal_wounds),
                getattr(enemy_root, "name", "Enemy"),
            )
            return True

        return None
