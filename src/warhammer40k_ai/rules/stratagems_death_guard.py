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

    def _queue_death_guard_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
        event_name: str,
    ) -> None:
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
            "FONT OF FILTH",
            "GRIM REAPERS",
            "GROTESQUE FORTITUDE",
            "MALIGNANCE MAGNIFIED",
            "MORTARION'S TEACHINGS",
            "MOBILE VECTOR",
            "MYPHITIC INVIGORATION",
            "NAUSEATING PAROXYSMS",
            "RABID INFUSION",
            "RELENTLESS GRIND",
            "SICKENING IMPACT",
            "SIGNAL POX",
            "STINKING MIRE",
            "UNDYING SPITE",
            "VERMIN CLOUD",
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
        if champions_name and not self._is_champions_of_contagion_detachment():
            return False
        if flyblown_name and not self._is_flyblown_host_detachment():
            return False
        if death_lords_name and not self._is_death_lords_chosen_detachment():
            return False
        if mortarions_hammer_name and not self._is_mortarions_hammer_detachment():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        phase_key = self._dg_phase_key(phase_name or self._dg_current_phase_key())
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None

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
