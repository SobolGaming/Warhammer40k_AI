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

    def _is_lords_of_dread_detachment(self) -> bool:
        mgr = self._chaos_knights_detachment_manager()
        checker = getattr(mgr, "is_lords_of_dread", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_traitoris_lance_detachment(self) -> bool:
        mgr = self._chaos_knights_detachment_manager()
        checker = getattr(mgr, "is_traitoris_lance", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_helhunt_lance_detachment(self) -> bool:
        mgr = self._chaos_knights_detachment_manager()
        checker = getattr(mgr, "is_helhunt_lance", None) if mgr is not None else None
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

    def _chaos_knights_preview_cp_cost(self, stratagem: Any, *, target_unit: Any = None, enemy_unit: Any = None) -> int:
        cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        preview = getattr(self.player, "preview_stratagem_cp_cost", None)
        if not callable(preview):
            return int(cost)
        try:
            payload = preview(
                stratagem,
                target_unit=target_unit,
                enemy_unit=enemy_unit,
                assume_optional_discounts=True,
            )
        except Exception:
            return int(cost)
        return int(payload.get("cost", cost) or cost)

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

    @staticmethod
    def _chaos_knights_has_keyword(unit: Any, keyword: str) -> bool:
        root = ChaosKnightsStratagemMixin._chaos_knights_root(unit)
        if root is None:
            return False
        key = ChaosKnightsStratagemMixin._chaos_knights_normalize_name(keyword)
        if not key:
            return False
        has_any_kw = getattr(root, "has_any_keyword", None)
        if callable(has_any_kw):
            try:
                if bool(has_any_kw(key)):
                    return True
            except Exception:
                pass
        keywords = list(getattr(root, "keywords", []) or [])
        faction_keywords = list(getattr(root, "faction_keywords", []) or [])
        for value in list(keywords) + list(faction_keywords):
            if ChaosKnightsStratagemMixin._chaos_knights_normalize_name(str(value or "")) == key:
                return True
        return False

    def _chaos_knights_is_monster_or_vehicle_unit(self, unit: Any) -> bool:
        return self._chaos_knights_has_keyword(unit, "MONSTER") or self._chaos_knights_has_keyword(unit, "VEHICLE")

    def _chaos_knights_has_deadly_demise(self, unit: Any) -> bool:
        root = self._chaos_knights_root(unit)
        if root is None:
            return False
        checker = getattr(root, "has_deadly_demise", None)
        if not callable(checker):
            return False
        try:
            has_deadly, _dice = checker()
        except Exception:
            return False
        return bool(has_deadly)

    def _is_chaos_knights_titanic_unit(self, unit: Any) -> bool:
        return self._chaos_knights_has_keyword(unit, "TITANIC")

    def _is_chaos_knights_abhorrent_unit(self, unit: Any) -> bool:
        if not self._is_chaos_knights_unit(unit):
            return False
        if self._is_chaos_knights_war_dog_unit(unit):
            return False
        if self._chaos_knights_has_keyword(unit, "ABHORRENT"):
            return True
        return self._is_chaos_knights_titanic_unit(unit)

    @staticmethod
    def _chaos_knights_merge_phase_move_types(
        special_rules: Dict[str, Any],
        rule_key: str,
        added_key: str,
        move_types: set[str],
    ) -> None:
        if not move_types:
            special_rules.pop(added_key, None)
            return
        current = set(special_rules.get(rule_key) or [])
        added = sorted([move_type for move_type in sorted(move_types) if move_type not in current])
        merged = sorted(current.union(move_types))
        if merged:
            special_rules[rule_key] = merged
        if added:
            special_rules[added_key] = added
        else:
            special_rules.pop(added_key, None)

    @staticmethod
    def _chaos_knights_remove_phase_move_types(
        special_rules: Dict[str, Any],
        rule_key: str,
        added_key: str,
    ) -> None:
        added = set(special_rules.get(added_key) or [])
        if added:
            current = list(special_rules.get(rule_key) or [])
            kept = [item for item in current if item not in added]
            if kept:
                special_rules[rule_key] = kept
            else:
                special_rules.pop(rule_key, None)
        special_rules.pop(added_key, None)

    def _chaos_knights_total_current_wounds(self, unit: Any) -> int:
        root = self._chaos_knights_root(unit)
        if root is None:
            return 0
        total = 0
        for model in list(self._chaos_knights_alive_models(root) or []):
            try:
                total += max(0, int(getattr(model, "wounds", 0) or 0))
            except Exception:
                continue
        return int(total)

    def _chaos_knights_candidate_ids(self, candidates: Any) -> set[str]:
        ids: set[str] = set()
        for candidate in list(candidates or []):
            root = self._chaos_knights_root(candidate)
            if root is None:
                continue
            root_id = self._chaos_knights_sort_key(root)
            if root_id:
                ids.add(root_id)
        return ids

    def _chaos_knights_is_visible_to_unit(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._chaos_knights_root(source_unit)
        target_root = self._chaos_knights_root(target_unit)
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if source_root is None or target_root is None or game_map is None:
            return False

        get_source_models = getattr(source_root, "get_attached_unit_models", None)
        source_models_raw = (
            list(get_source_models() or [])
            if callable(get_source_models)
            else list(getattr(source_root, "models", []) or [])
        )
        source_models = []
        for model in list(source_models_raw or []):
            alive_value = getattr(model, "is_alive", False)
            try:
                alive = bool(alive_value() if callable(alive_value) else alive_value)
            except Exception:
                alive = False
            if alive:
                source_models.append(model)
        if not source_models:
            return False

        can_see_unit = getattr(game, "_model_can_see_unit", None)
        if callable(can_see_unit):
            for model in list(source_models or []):
                try:
                    if bool(can_see_unit(model, target_root, game_map=game_map)):
                        return True
                except TypeError:
                    if bool(can_see_unit(model, target_root)):
                        return True
            return False

        has_los = getattr(source_root, "_has_line_of_sight_to_target", None)
        if callable(has_los):
            for model in list(source_models or []):
                try:
                    if bool(has_los(model, target_root, game_map)):
                        return True
                except Exception:
                    continue
            return False

        can_see_model = getattr(game_map, "can_model_see_model", None)
        if not callable(can_see_model):
            return True

        get_target_models = getattr(target_root, "get_attached_unit_models", None)
        target_models_raw = (
            list(get_target_models() or [])
            if callable(get_target_models)
            else list(getattr(target_root, "models", []) or [])
        )
        target_models = []
        for model in list(target_models_raw or []):
            alive_value = getattr(model, "is_alive", False)
            try:
                alive = bool(alive_value() if callable(alive_value) else alive_value)
            except Exception:
                alive = False
            if alive:
                target_models.append(model)
        for source_model in list(source_models or []):
            for target_model in list(target_models or []):
                try:
                    if bool(can_see_model(source_model, target_model)):
                        return True
                except Exception:
                    continue
        return False

    def _chaos_knights_unit_has_ranged_weapon_in_range(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._chaos_knights_root(source_unit)
        target_root = self._chaos_knights_root(target_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if source_root is None or target_root is None or game_map is None:
            return False
        can_shoot = getattr(source_root, "_can_model_shoot_weapon_at_target", None)
        get_models = getattr(source_root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(source_root, "models", []) or [])
        fallback_ranged_weapon_found = False
        for model in list(models or []):
            alive_value = getattr(model, "is_alive", False)
            try:
                alive = bool(alive_value() if callable(alive_value) else alive_value)
            except Exception:
                alive = False
            if not alive:
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                profiles = getattr(wargear, "profiles", None) or {}
                if not profiles:
                    fallback_ranged_weapon_found = True
                    continue
                for profile in list(profiles.values() or []):
                    if profile is None:
                        continue
                    if callable(can_shoot):
                        try:
                            if bool(can_shoot(model, profile, target_root, game_map)):
                                return True
                        except Exception:
                            continue
        return bool(fallback_ranged_weapon_found)

    def _chaos_knights_unit_can_fight_target(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._chaos_knights_root(source_unit)
        target_root = self._chaos_knights_root(target_unit)
        if source_root is None or target_root is None or self.game is None:
            return False
        fight_mgr = getattr(self.game, "fight_phase_manager", None)
        if fight_mgr is None:
            from ..engine.fight_phase_manager import FightPhaseManager

            fight_mgr = FightPhaseManager(self.game)
        get_targets = getattr(fight_mgr, "_get_eligible_targets", None)
        if callable(get_targets):
            try:
                return bool(target_root in list(get_targets(source_root) or []))
            except Exception:
                return False
        return bool(self._chaos_knights_in_engagement_range(source_root))

    def _chaos_knights_unit_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_empowered: bool = False,
        require_character: bool = False,
        require_war_dog: bool = False,
        require_fell_back: bool = False,
        require_not_in_engagement: bool = False,
        require_not_fought: bool = False,
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
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
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

    def _lords_of_dread_claimed_for_dark_gods_candidates(self) -> List[Any]:
        if not self._is_lords_of_dread_detachment():
            return []
        candidates: List[Any] = []
        for root in list(self._chaos_knights_unit_candidates(require_character=True) or []):
            if not self._corrupting_taint_objective_candidates(root):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _lords_of_dread_titanic_duel_candidates(self, *, phase_key: str) -> List[Any]:
        if not self._is_lords_of_dread_detachment():
            return []
        normalized_phase = str(phase_key or "").strip().upper()
        if normalized_phase == "SHOOTING_PHASE":
            return self._chaos_knights_unit_candidates(require_character=True, require_not_shot=True)
        if normalized_phase == "FIGHT_PHASE":
            return self._chaos_knights_unit_candidates(require_character=True, require_not_fought=True)
        return []

    def _lords_of_dread_titanic_duel_enemy_candidates(self, source_unit: Any) -> List[Any]:
        del source_unit
        if not self._is_lords_of_dread_detachment():
            return []
        candidates: List[Any] = []
        for enemy_root in list(self._chaos_knights_enemy_roots() or []):
            if not self._chaos_knights_on_battlefield(enemy_root, require_targetable=False):
                continue
            if not self._chaos_knights_is_monster_or_vehicle_unit(enemy_root):
                continue
            candidates.append(enemy_root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _lords_of_dread_crushed_like_vermin_enemy_candidates(self, source_unit: Any) -> List[Any]:
        if not self._is_lords_of_dread_detachment() or self.game is None:
            return []
        root = self._chaos_knights_root(source_unit)
        game_map = getattr(self.game, "map", None)
        if root is None or game_map is None:
            return []
        from ..utility.calcs import get_enemy_units_moved_over

        candidates_by_id: dict[str, Any] = {}
        for model in list(self._chaos_knights_alive_models(root) or []):
            path = getattr(model, "last_move_path", None)
            for enemy_root in list(
                get_enemy_units_moved_over(model, path, game_map, require_vertical_overlap=True) or []
            ):
                enemy_root = self._chaos_knights_root(enemy_root)
                if enemy_root is None:
                    continue
                if self._chaos_knights_owned_by_player(enemy_root, self.player):
                    continue
                if self._chaos_knights_is_monster_or_vehicle_unit(enemy_root):
                    continue
                if not self._chaos_knights_on_battlefield(enemy_root, require_targetable=False):
                    continue
                enemy_id = self._chaos_knights_sort_key(enemy_root)
                if enemy_id:
                    candidates_by_id[enemy_id] = enemy_root
        return [candidates_by_id[key] for key in sorted(candidates_by_id)]

    def _queue_lords_of_dread_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_lords_of_dread_detachment() or self.game is None:
            return
        if player is not self.player:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        phase_name = self._chaos_knights_phase_label(phase_key)

        if phase_key == "COMMAND_PHASE":
            claimed = self.get_by_name("CLAIMED FOR THE DARK GODS")
            if claimed is not None:
                if (claimed.name or "").strip().upper() not in self._used_stratagems_this_phase:
                    candidates = list(self._lords_of_dread_claimed_for_dark_gods_candidates() or [])
                    if candidates and not self._chaos_knights_reaction_exists("phase_start", claimed.name):
                        preview_cost = self._chaos_knights_preview_cp_cost(
                            claimed,
                            target_unit=candidates[0],
                        )
                        if int(getattr(self.player, "command_points", 0) or 0) >= preview_cost:
                            payload = {
                                "event": "phase_start",
                                "phase_name": phase_name,
                                "stratagem": claimed.name,
                                "cp_cost": claimed.cp_cost,
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["unit"] = candidates[0]
                                payload["target_unit"] = candidates[0]
                                payload["objective_candidates"] = self._corrupting_taint_objective_candidates(candidates[0])
                            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        titanic_duel = self.get_by_name("TITANIC DUEL")
        if titanic_duel is None:
            return
        if (titanic_duel.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = list(self._lords_of_dread_titanic_duel_candidates(phase_key=phase_key) or [])
        if not candidates or self._chaos_knights_reaction_exists("phase_start", titanic_duel.name):
            return
        preview_cost = self._chaos_knights_preview_cp_cost(
            titanic_duel,
            target_unit=candidates[0],
        )
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        payload = {
            "event": "phase_start",
            "phase_name": phase_name,
            "stratagem": titanic_duel.name,
            "cp_cost": titanic_duel.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
            payload["enemy_candidates"] = self._lords_of_dread_titanic_duel_enemy_candidates(candidates[0])
        self._queue_reaction(payload, use_timer=False)

    def _queue_lords_of_dread_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_lords_of_dread_detachment() or self.game is None:
            return
        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"move", "normal", "normal move"}:
            return
        stratagem = self.get_by_name("CRUSHED LIKE VERMIN")
        moving_root = self._chaos_knights_root(unit)
        if stratagem is None or moving_root is None:
            return
        if not self._chaos_knights_owned_by_player(moving_root, self.player):
            return
        if moving_root not in list(self._chaos_knights_unit_candidates(require_character=True) or []):
            return
        if self._chaos_knights_reaction_exists("unit_move_ended", stratagem.name, unit=moving_root):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        enemy_candidates = list(self._lords_of_dread_crushed_like_vermin_enemy_candidates(moving_root) or [])
        if not enemy_candidates:
            return
        preview_cost = self._chaos_knights_preview_cp_cost(
            stratagem,
            target_unit=moving_root,
        )
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": moving_root,
            "target_unit": moving_root,
            "enemy_candidates": enemy_candidates,
            "action": action,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_lords_of_dread_model_destroyed_reactions(self, *, unit: Any, model: Any) -> None:
        if not self._is_lords_of_dread_detachment() or self.game is None:
            return
        root = self._chaos_knights_root(unit)
        if root is None or model is None:
            return
        if not self._chaos_knights_owned_by_player(root, self.player):
            return
        if not self._is_chaos_knights_character_unit(root):
            return
        if not self._chaos_knights_has_deadly_demise(root):
            return
        if self._chaos_knights_alive_models(root):
            return
        stratagem = self.get_by_name("SPITEFUL DEMISE")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        model_id = str(get_entity_id(model) or "")
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "model_destroyed_before_removal":
                continue
            if self._chaos_knights_normalize_name(reaction.get("stratagem", "")) != "SPITEFUL DEMISE":
                continue
            if str(reaction.get("destroyed_model_id", "") or "") == model_id:
                return
        preview_cost = self._chaos_knights_preview_cp_cost(
            stratagem,
            target_unit=root,
        )
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        phase_name = str(self._current_phase_name or "").strip() or self._chaos_knights_phase_label(
            str(getattr(getattr(self.game, "phase", None), "name", "") or "")
        )
        self._queue_reaction(
            {
                "event": "model_destroyed_before_removal",
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "destroyed_unit": root,
                "destroyed_model": model,
                "destroyed_model_id": model_id,
                "unit": root,
                "target_unit": root,
            },
            use_timer=False,
        )

    def _use_lords_of_dread_claimed_for_dark_gods(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_lords_of_dread_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: CLAIMED FOR THE DARK GODS: no target unit provided")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: CLAIMED FOR THE DARK GODS: target unit is not yours")
            return False
        if not self._is_chaos_knights_character_unit(root):
            logger.error("ERROR: CLAIMED FOR THE DARK GODS: target must be a CHAOS KNIGHTS CHARACTER unit")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: CLAIMED FOR THE DARK GODS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: CLAIMED FOR THE DARK GODS: only usable in your Command phase")
            return False
        objective = merged.get("objective") or merged.get("objective_marker")
        objective_candidates = list(merged.get("objective_candidates", []) or [])
        if not objective_candidates:
            objective_candidates = list(self._corrupting_taint_objective_candidates(root) or [])
        if root not in list(self._lords_of_dread_claimed_for_dark_gods_candidates() or []):
            logger.error("ERROR: CLAIMED FOR THE DARK GODS: target unit is not within range of a controlled objective")
            return False
        if objective is None:
            objective = objective_candidates[0] if objective_candidates else None
        if objective is None:
            logger.error("ERROR: CLAIMED FOR THE DARK GODS: no objective marker available")
            return False
        if objective_candidates and objective not in list(objective_candidates or []):
            logger.error("ERROR: CLAIMED FOR THE DARK GODS: objective not in candidates")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        loc = getattr(objective, "location", None)
        if loc is None:
            logger.error("ERROR: CLAIMED FOR THE DARK GODS: selected objective has no location")
            return False
        if hasattr(loc, "set_sticky_control"):
            loc.set_sticky_control(
                self.player,
                source="claimed_for_the_dark_gods",
                minimum_control=5,
            )
        else:
            loc.sticky_controller = self.player
            loc.sticky_source = "claimed_for_the_dark_gods"
            loc.sticky_minimum_control = 5
            loc.controlling_player = self.player
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: CLAIMED FOR THE DARK GODS: selected objective remains under your control with Level of Control 5 until broken.",
        )
        return True

    def _use_lords_of_dread_crushed_like_vermin(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_lords_of_dread_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        enemy_root = self._chaos_knights_root(merged.get("enemy_unit") or merged.get("target_enemy_unit"))
        if root is None:
            logger.error("ERROR: CRUSHED LIKE VERMIN: no target unit provided")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: CRUSHED LIKE VERMIN: target unit is not yours")
            return False
        if not self._is_chaos_knights_character_unit(root):
            logger.error("ERROR: CRUSHED LIKE VERMIN: target must be a CHAOS KNIGHTS CHARACTER unit")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: CRUSHED LIKE VERMIN: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: CRUSHED LIKE VERMIN: only usable in your Movement phase")
            return False
        action_key = str(merged.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key not in {"move", "normal", "normal move"}:
            logger.error("ERROR: CRUSHED LIKE VERMIN: trigger requires a Normal move")
            return False
        enemy_candidates = list(merged.get("enemy_candidates", []) or [])
        if not enemy_candidates:
            enemy_candidates = list(self._lords_of_dread_crushed_like_vermin_enemy_candidates(root) or [])
        if enemy_root is None:
            enemy_root = self._chaos_knights_root(enemy_candidates[0]) if len(enemy_candidates) == 1 else None
        if enemy_root is None:
            logger.error("ERROR: CRUSHED LIKE VERMIN: no moved-over enemy unit selected")
            return False
        if enemy_candidates and enemy_root not in list(enemy_candidates or []):
            logger.error("ERROR: CRUSHED LIKE VERMIN: selected enemy unit was not moved over")
            return False
        if self._chaos_knights_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: CRUSHED LIKE VERMIN: target must be an enemy unit")
            return False
        if self._chaos_knights_is_monster_or_vehicle_unit(enemy_root):
            logger.error("ERROR: CRUSHED LIKE VERMIN: MONSTER and VEHICLE units are excluded")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        mortal_wounds = 0
        for _ in range(6):
            if int(get_roll("D6") or 0) >= 4:
                mortal_wounds += 1
        apply_mortal_wounds = getattr(root, "_apply_mortal_wounds_to_unit", None)
        if not callable(apply_mortal_wounds):
            logger.error("ERROR: CRUSHED LIKE VERMIN: mortal wound application helper unavailable")
            return False
        destroyed_models = int(
            apply_mortal_wounds(
                enemy_root,
                int(mortal_wounds),
                game_map=getattr(self.game, "map", None),
            )
            or 0
        )
        if destroyed_models > 0:
            take_battle_shock = getattr(enemy_root, "take_battle_shock_test", None)
            if callable(take_battle_shock):
                take_battle_shock(int(getattr(self.game, "turn", 1) or 1))
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: CRUSHED LIKE VERMIN: %s suffers %d mortal wound(s)%s.",
            getattr(enemy_root, "name", "Enemy Unit"),
            int(mortal_wounds),
            " and must take a Battle-shock test" if destroyed_models > 0 else "",
        )
        return True

    def _use_lords_of_dread_spiteful_demise(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_lords_of_dread_detachment():
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(
            merged.get("destroyed_unit") or merged.get("unit") or merged.get("target_unit")
        )
        destroyed_model = merged.get("destroyed_model")
        if root is None or destroyed_model is None:
            logger.error("ERROR: SPITEFUL DEMISE: destroyed unit or model missing")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: SPITEFUL DEMISE: target unit is not yours")
            return False
        if not self._is_chaos_knights_character_unit(root):
            logger.error("ERROR: SPITEFUL DEMISE: target must be a CHAOS KNIGHTS CHARACTER unit")
            return False
        if not self._chaos_knights_has_deadly_demise(root):
            logger.error("ERROR: SPITEFUL DEMISE: target unit does not have Deadly Demise")
            return False
        if self._chaos_knights_alive_models(root):
            logger.error("ERROR: SPITEFUL DEMISE: target unit was not destroyed")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        setattr(destroyed_model, "_chaos_knights_spiteful_demise_trigger_threshold_once", 4)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: SPITEFUL DEMISE: %s triggers Deadly Demise on 4+ for this destruction.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_lords_of_dread_titanic_duel(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_lords_of_dread_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        enemy_root = self._chaos_knights_root(merged.get("enemy_unit") or merged.get("target_enemy_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: TITANIC DUEL: no target unit provided")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: TITANIC DUEL: target unit is not yours")
            return False
        if not self._is_chaos_knights_character_unit(root):
            logger.error("ERROR: TITANIC DUEL: target must be a CHAOS KNIGHTS CHARACTER unit")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        phase_key = ""
        attack_type = ""
        if phase_name == "shooting phase":
            phase_key = "SHOOTING_PHASE"
            attack_type = "ranged"
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                logger.error("ERROR: TITANIC DUEL: target unit has already shot this phase")
                return False
        elif phase_name == "fight phase":
            phase_key = "FIGHT_PHASE"
            attack_type = "melee"
            if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                logger.error("ERROR: TITANIC DUEL: target unit has already fought this phase")
                return False
        else:
            logger.error("ERROR: TITANIC DUEL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: TITANIC DUEL: only usable in your phase")
            return False
        enemy_candidates = list(merged.get("enemy_candidates", []) or [])
        if not enemy_candidates:
            enemy_candidates = list(self._lords_of_dread_titanic_duel_enemy_candidates(root) or [])
        if enemy_root is None:
            enemy_root = self._chaos_knights_root(enemy_candidates[0]) if len(enemy_candidates) == 1 else None
        if enemy_root is None:
            logger.error("ERROR: TITANIC DUEL: no enemy MONSTER or VEHICLE selected")
            return False
        if enemy_candidates and enemy_root not in list(enemy_candidates or []):
            logger.error("ERROR: TITANIC DUEL: selected enemy is not an eligible candidate")
            return False
        if self._chaos_knights_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: TITANIC DUEL: target must be an enemy unit")
            return False
        if not self._chaos_knights_is_monster_or_vehicle_unit(enemy_root):
            logger.error("ERROR: TITANIC DUEL: target must be an enemy MONSTER or VEHICLE unit")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        enemy_id = self._chaos_knights_sort_key(enemy_root)
        reroll_mode = "full" if self._chaos_knights_has_keyword(enemy_root, "TITANIC") else "ones"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["lords_of_dread_titanic_duel_active"] = True
        sr["lords_of_dread_titanic_duel_target_id"] = enemy_id
        sr["lords_of_dread_titanic_duel_reroll_mode"] = reroll_mode
        sr["lords_of_dread_titanic_duel_attack_type"] = attack_type
        sr["lords_of_dread_titanic_duel_expires_phase"] = phase_key
        sr["lords_of_dread_titanic_duel_turn"] = int(getattr(self.game, "turn", 0) or 0)
        sr["lords_of_dread_titanic_duel_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["lords_of_dread_titanic_duel_source"] = str(getattr(stratagem, "name", "") or "TITANIC DUEL")
        root.special_rules = sr
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: TITANIC DUEL: %s re-rolls %s against %s this phase.",
            getattr(root, "name", "Unit"),
            "Hit and Wound rolls" if reroll_mode == "full" else "Hit and Wound rolls of 1",
            getattr(enemy_root, "name", "Enemy Unit"),
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

    def _chaos_knights_resolve_selected_units(self, values: Any) -> List[Any]:
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
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            selected.append(root)
        selected.sort(key=self._chaos_knights_sort_key)
        return selected

    def _traitoris_resolve_selected_units(self, values: Any) -> List[Any]:
        return self._chaos_knights_resolve_selected_units(values)

    def _traitoris_a_long_leash_source_candidates(self) -> List[Any]:
        if not self._is_traitoris_lance_detachment():
            return []
        candidates = [
            root
            for root in list(self._chaos_knights_unit_candidates() or [])
            if self._is_chaos_knights_abhorrent_unit(root)
        ]
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _traitoris_a_long_leash_war_dog_candidates(self, source_unit: Any = None) -> List[Any]:
        if not self._is_traitoris_lance_detachment():
            return []
        source_root = self._chaos_knights_root(source_unit)
        candidates = []
        for root in list(self._chaos_knights_unit_candidates(require_war_dog=True) or []):
            if source_root is not None and root is source_root:
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _traitoris_imperious_advance_war_dog_candidates(self, *, phase_name: str) -> List[Any]:
        if not self._is_traitoris_lance_detachment():
            return []
        phase_key = str(phase_name or "").strip().lower()
        candidates: List[Any] = []
        for root in list(self._traitoris_a_long_leash_war_dog_candidates() or []):
            round_state = getattr(root, "round_state", None)
            if phase_key == "movement phase":
                if bool(getattr(round_state, "moved_this_round", False)):
                    continue
                if bool(getattr(round_state, "advanced_this_round", False)):
                    continue
                if bool(getattr(round_state, "fell_back_this_round", False)):
                    continue
            elif phase_key == "charge phase":
                if bool(getattr(round_state, "attempted_charge_this_round", False)):
                    continue
            else:
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _traitoris_imperious_advance_titanic_candidates(self, *, phase_name: str) -> List[Any]:
        if not self._is_traitoris_lance_detachment():
            return []
        phase_key = str(phase_name or "").strip().lower()
        candidates: List[Any] = []
        for root in list(self._chaos_knights_unit_candidates() or []):
            if not self._is_chaos_knights_titanic_unit(root):
                continue
            round_state = getattr(root, "round_state", None)
            if phase_key == "movement phase":
                if bool(getattr(round_state, "moved_this_round", False)):
                    continue
                if bool(getattr(round_state, "advanced_this_round", False)):
                    continue
                if bool(getattr(round_state, "fell_back_this_round", False)):
                    continue
            elif phase_key == "charge phase":
                if bool(getattr(round_state, "attempted_charge_this_round", False)):
                    continue
            else:
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _traitoris_conquerors_without_mercy_candidates(self) -> List[Any]:
        if not self._is_traitoris_lance_detachment():
            return []
        candidates: List[Any] = []
        for root in list(self._chaos_knights_unit_candidates(require_not_fought=True) or []):
            if not self._is_chaos_knights_unit(root):
                continue
            round_state = getattr(root, "round_state", None)
            if not bool(getattr(round_state, "charged_this_round", False)):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _traitoris_targeted_chaos_knights_candidates(self, target_units: Any) -> List[Any]:
        candidates: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._chaos_knights_root(target)
            if root is None:
                continue
            root_id = self._chaos_knights_sort_key(root)
            if root_id and root_id in seen:
                continue
            if not self._chaos_knights_owned_by_player(root, self.player):
                continue
            if not self._chaos_knights_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_chaos_knights_unit(root):
                continue
            if root_id:
                seen.add(root_id)
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _traitoris_pterrorshades_candidates(self, enemy_unit: Any) -> List[Any]:
        if not self._is_traitoris_lance_detachment():
            return []
        enemy_root = self._chaos_knights_root(enemy_unit)
        if enemy_root is None or self._chaos_knights_owned_by_player(enemy_root, self.player):
            return []
        candidates: List[Any] = []
        for root in list(self._chaos_knights_unit_candidates() or []):
            distance = self._chaos_knights_distance_between_units(root, enemy_root)
            if distance is None or distance > 12.0 + 1e-6:
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _clear_traitoris_a_long_leash_effects(self) -> None:
        army = self._chaos_knights_army()
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_knights_root(unit)
            if root is None:
                continue
            root_id = self._chaos_knights_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            changed = False
            for key in (
                "traitoris_a_long_leash_active",
                "traitoris_a_long_leash_source_unit_id",
                "traitoris_a_long_leash_source",
            ):
                if key in special_rules:
                    special_rules.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = special_rules

    def _cleanup_traitoris_lance_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_traitoris_lance_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"MOVEMENT_PHASE", "CHARGE_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        army = self._chaos_knights_army()
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_knights_root(unit)
            if root is None:
                continue
            root_id = self._chaos_knights_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            changed = False

            if phase_key in {"MOVEMENT_PHASE", "CHARGE_PHASE"}:
                expires_phase = str(special_rules.get("traitoris_imperious_advance_expires_phase", "") or "").strip().upper()
                if special_rules.get("traitoris_imperious_advance_active") is True and (
                    not expires_phase or expires_phase == phase_key
                ):
                    for rule_key, added_key in (
                        ("bearer_unit_phase_move_types", "traitoris_imperious_advance_added_phase_move_types"),
                        (
                            "bearer_unit_phase_move_engagement_types",
                            "traitoris_imperious_advance_added_phase_move_engagement_types",
                        ),
                    ):
                        self._chaos_knights_remove_phase_move_types(special_rules, rule_key, added_key)
                    if bool(special_rules.get("traitoris_imperious_advance_added_auto_pass_desperate_escape", False)):
                        special_rules.pop("bearer_unit_auto_pass_desperate_escape", None)
                    if bool(special_rules.get("traitoris_imperious_advance_prev_titanic_block_present", False)):
                        previous = list(
                            special_rules.get("traitoris_imperious_advance_prev_titanic_block_value", []) or []
                        )
                        if previous:
                            special_rules["titanic_phase_move_block_titanic_types"] = previous
                        else:
                            special_rules.pop("titanic_phase_move_block_titanic_types", None)
                    for key in (
                        "traitoris_imperious_advance_active",
                        "traitoris_imperious_advance_expires_phase",
                        "traitoris_imperious_advance_turn_owner",
                        "traitoris_imperious_advance_turn",
                        "traitoris_imperious_advance_source",
                        "traitoris_imperious_advance_added_auto_pass_desperate_escape",
                        "traitoris_imperious_advance_prev_titanic_block_present",
                        "traitoris_imperious_advance_prev_titanic_block_value",
                    ):
                        special_rules.pop(key, None)
                    changed = True

            if phase_key == "SHOOTING_PHASE" and special_rules.get("traitoris_storm_of_darkness_active") is True:
                for key in (
                    "traitoris_storm_of_darkness_active",
                    "traitoris_storm_of_darkness_expires_phase",
                    "traitoris_storm_of_darkness_source",
                ):
                    special_rules.pop(key, None)
                changed = True

            if phase_key == "FIGHT_PHASE" and special_rules.get("traitoris_conquerors_without_mercy_active") is True:
                for key in (
                    "traitoris_conquerors_without_mercy_active",
                    "traitoris_conquerors_without_mercy_expires_phase",
                    "traitoris_conquerors_without_mercy_source",
                    "traitoris_conquerors_without_mercy_battle_shock_applied",
                ):
                    special_rules.pop(key, None)
                changed = True

            if changed:
                root.special_rules = special_rules

            if phase_key == "FIGHT_PHASE":
                for model in list(getattr(root, "models", []) or []) + list(getattr(root, "models_lost", []) or []):
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        continue
                    effects.pop("traitoris_conquerors_without_mercy_ap_boost", None)

    def _queue_traitoris_lance_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_traitoris_lance_detachment() or self.game is None:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        phase_name = self._chaos_knights_phase_label(phase_key)

        if phase_key == "COMMAND_PHASE" and player is self.player:
            self._clear_traitoris_a_long_leash_effects()
            stratagem = self.get_by_name("A LONG LEASH")
            if stratagem is not None and (stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase:
                for source_root in list(self._traitoris_a_long_leash_source_candidates() or []):
                    war_dog_candidates = list(self._traitoris_a_long_leash_war_dog_candidates(source_root) or [])
                    if not war_dog_candidates:
                        continue
                    if self._chaos_knights_reaction_exists("phase_start", stratagem.name, unit=source_root):
                        continue
                    preview_cost = self._chaos_knights_preview_cp_cost(stratagem, target_unit=source_root)
                    if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
                        continue
                    payload = {
                        "event": "phase_start",
                        "phase_name": phase_name,
                        "stratagem": stratagem.name,
                        "cp_cost": stratagem.cp_cost,
                        "unit": source_root,
                        "target_unit": source_root,
                        "war_dog_candidates": war_dog_candidates,
                        "war_dog_candidate_ids": [
                            self._chaos_knights_sort_key(candidate) for candidate in list(war_dog_candidates or [])
                        ],
                    }
                    self._queue_reaction(payload, use_timer=False)
            return

        if phase_key in {"MOVEMENT_PHASE", "CHARGE_PHASE"} and player is self.player:
            stratagem = self.get_by_name("IMPERIOUS ADVANCE")
            if stratagem is None:
                return
            if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            if self._chaos_knights_reaction_exists("phase_start", stratagem.name):
                return
            phase_label = "Movement phase" if phase_key == "MOVEMENT_PHASE" else "Charge phase"
            war_dog_candidates = list(self._traitoris_imperious_advance_war_dog_candidates(phase_name=phase_label) or [])
            titanic_candidates = list(
                self._traitoris_imperious_advance_titanic_candidates(phase_name=phase_label) or []
            )
            if not war_dog_candidates and not titanic_candidates:
                return
            preview_target = titanic_candidates[0] if titanic_candidates else war_dog_candidates[0]
            preview_cost = self._chaos_knights_preview_cp_cost(stratagem, target_unit=preview_target)
            if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
                return
            payload = {
                "event": "phase_start",
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "war_dog_candidates": war_dog_candidates,
                "war_dog_candidate_ids": [
                    self._chaos_knights_sort_key(candidate) for candidate in list(war_dog_candidates or [])
                ],
                "titanic_candidates": titanic_candidates,
                "titanic_candidate_ids": [
                    self._chaos_knights_sort_key(candidate) for candidate in list(titanic_candidates or [])
                ],
            }
            if len(titanic_candidates) == 1 and not war_dog_candidates:
                payload["unit"] = titanic_candidates[0]
                payload["target_unit"] = titanic_candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("CONQUERORS WITHOUT MERCY")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        for root in list(self._traitoris_conquerors_without_mercy_candidates() or []):
            if self._chaos_knights_reaction_exists("phase_start", stratagem.name, unit=root):
                continue
            preview_cost = self._chaos_knights_preview_cp_cost(stratagem, target_unit=root)
            if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
                continue
            self._queue_reaction(
                {
                    "event": "phase_start",
                    "phase_name": phase_name,
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "unit": root,
                    "target_unit": root,
                },
                use_timer=False,
            )

    def _queue_traitoris_shooting_target_reactions(self, *, attacking_unit: Any, target_units: List[Any]) -> None:
        if not self._is_traitoris_lance_detachment() or self.game is None:
            return
        stratagem = self.get_by_name("STORM OF DARKNESS")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacking_root = self._chaos_knights_root(attacking_unit)
        if attacking_root is None or self._chaos_knights_owned_by_player(attacking_root, self.player):
            return
        candidates = self._traitoris_targeted_chaos_knights_candidates(target_units)
        if not candidates:
            return
        preview_cost = self._chaos_knights_preview_cp_cost(stratagem, target_unit=candidates[0], enemy_unit=attacking_root)
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        if self._chaos_knights_reaction_exists(
            "shooting_targets_selected",
            stratagem.name,
            enemy_unit=attacking_root,
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_root,
            "enemy_unit": attacking_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_traitoris_fight_target_reactions(self, *, attacking_unit: Any, target_units: List[Any]) -> None:
        if not self._is_traitoris_lance_detachment() or self.game is None:
            return
        stratagem = self.get_by_name("DISDAIN FOR THE WEAK")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacking_root = self._chaos_knights_root(attacking_unit)
        if attacking_root is None or self._chaos_knights_owned_by_player(attacking_root, self.player):
            return
        candidates = self._traitoris_targeted_chaos_knights_candidates(target_units)
        if not candidates:
            return
        preview_cost = self._chaos_knights_preview_cp_cost(stratagem, target_unit=candidates[0], enemy_unit=attacking_root)
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        if self._chaos_knights_reaction_exists(
            "fight_targets_selected",
            stratagem.name,
            enemy_unit=attacking_root,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_root,
            "enemy_unit": attacking_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _helhunt_flush_the_quarry_source_candidates(self) -> List[Any]:
        if not self._is_helhunt_lance_detachment():
            return []
        candidates = [
            root
            for root in list(self._chaos_knights_unit_candidates() or [])
            if self._is_chaos_knights_titanic_unit(root)
        ]
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _helhunt_flush_the_quarry_war_dog_candidates(self, source_unit: Any) -> List[Any]:
        if not self._is_helhunt_lance_detachment():
            return []
        source_root = self._chaos_knights_root(source_unit)
        if source_root is None:
            return []
        candidates: List[Any] = []
        for root in list(self._chaos_knights_unit_candidates(require_war_dog=True) or []):
            if root is source_root:
                continue
            distance = self._chaos_knights_distance_between_units(source_root, root)
            if distance is None or distance > 6.0 + 1e-6:
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _helhunt_merciless_fusillade_source_candidates(self, *, phase_name: str) -> List[Any]:
        if not self._is_helhunt_lance_detachment():
            return []
        phase_key = str(phase_name or "").strip().lower()
        candidates = list(
            self._chaos_knights_unit_candidates(
                require_not_shot=phase_key == "shooting phase",
                require_not_fought=phase_key == "fight phase",
            )
            or []
        )
        candidates = [root for root in candidates if self._is_chaos_knights_titanic_unit(root)]
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _helhunt_merciless_fusillade_war_dog_candidates(self, source_unit: Any, *, phase_name: str) -> List[Any]:
        if not self._is_helhunt_lance_detachment():
            return []
        source_root = self._chaos_knights_root(source_unit)
        phase_key = str(phase_name or "").strip().lower()
        candidates = list(
            self._chaos_knights_unit_candidates(
                require_war_dog=True,
                require_not_shot=phase_key == "shooting phase",
                require_not_fought=phase_key == "fight phase",
            )
            or []
        )
        out: List[Any] = []
        for root in list(candidates or []):
            if source_root is not None and root is source_root:
                continue
            out.append(root)
        out.sort(key=self._chaos_knights_sort_key)
        return out

    def _helhunt_merciless_fusillade_enemy_candidates(
        self,
        source_unit: Any,
        selected_units: Any,
        *,
        phase_name: str,
    ) -> List[Any]:
        source_root = self._chaos_knights_root(source_unit)
        if source_root is None or not self._is_helhunt_lance_detachment():
            return []
        phase_key = str(phase_name or "").strip().lower()
        if phase_key not in {"shooting phase", "fight phase"}:
            return []
        selected_roots = [source_root] + list(self._chaos_knights_resolve_selected_units(selected_units) or [])
        unique_units: List[Any] = []
        seen_units: set[str] = set()
        for root in list(selected_roots or []):
            root_id = self._chaos_knights_sort_key(root)
            if root_id and root_id in seen_units:
                continue
            if root_id:
                seen_units.add(root_id)
            unique_units.append(root)
        candidates: List[Any] = []
        for enemy_root in list(self._chaos_knights_enemy_roots() or []):
            if phase_key == "shooting phase":
                if all(self._chaos_knights_unit_has_ranged_weapon_in_range(root, enemy_root) for root in unique_units):
                    candidates.append(enemy_root)
                continue
            if all(self._chaos_knights_unit_can_fight_target(root, enemy_root) for root in unique_units):
                candidates.append(enemy_root)
        candidates.sort(key=self._chaos_knights_sort_key)
        return candidates

    def _helhunt_targeted_chaos_knights_candidates(self, target_units: Any) -> List[Any]:
        if not self._is_helhunt_lance_detachment():
            return []
        return self._traitoris_targeted_chaos_knights_candidates(target_units)

    def _helhunt_contemptuous_volleys_candidates(self) -> List[Any]:
        if not self._is_helhunt_lance_detachment():
            return []
        return self._chaos_knights_unit_candidates(require_fell_back=True)

    def _helhunt_goaded_beast_wounds_before(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        data = getattr(self, "_helhunt_goaded_beast_wounds_before_by_attacker", None)
        if not isinstance(data, dict):
            data = {}
            self._helhunt_goaded_beast_wounds_before_by_attacker = data
        return data

    def _capture_helhunt_goaded_beast_shooting_targets(self, *, attacking_unit: Any, target_units: Any) -> None:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        stratagem = self.get_by_name("GOADED BEAST")
        if stratagem is None:
            return
        attacking_root = self._chaos_knights_root(attacking_unit)
        if attacking_root is None or self._chaos_knights_owned_by_player(attacking_root, self.player):
            return
        attacker_key = self._attacker_unit_key(attacking_root)
        if not attacker_key:
            return
        snapshot = dict(self._helhunt_goaded_beast_wounds_before().get(attacker_key, {}) or {})
        for root in list(self._helhunt_targeted_chaos_knights_candidates(target_units) or []):
            root_id = self._chaos_knights_sort_key(root)
            if not root_id:
                continue
            snapshot[root_id] = {
                "unit": root,
                "wounds_before": self._chaos_knights_total_current_wounds(root),
            }
        if snapshot:
            self._helhunt_goaded_beast_wounds_before()[attacker_key] = snapshot

    def _queue_helhunt_shooting_resolved_reactions(self, *, attacker_unit: Any) -> None:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        stratagem = self.get_by_name("GOADED BEAST")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacking_root = self._chaos_knights_root(attacker_unit)
        if attacking_root is None or self._chaos_knights_owned_by_player(attacking_root, self.player):
            return
        attacker_key = self._attacker_unit_key(attacking_root)
        if not attacker_key:
            return
        snapshot = dict(self._helhunt_goaded_beast_wounds_before().pop(attacker_key, {}) or {})
        if not snapshot:
            return
        candidates: List[Any] = []
        wounds_before_by_unit: Dict[str, int] = {}
        for unit_id, entry in list(snapshot.items()):
            if not isinstance(entry, dict):
                continue
            root = self._chaos_knights_root(entry.get("unit")) or self._chaos_knights_resolve_unit(unit_id)
            if root is None:
                continue
            if not self._chaos_knights_owned_by_player(root, self.player):
                continue
            if not self._chaos_knights_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_chaos_knights_unit(root):
                continue
            wounds_before = int(entry.get("wounds_before", 0) or 0)
            wounds_after = self._chaos_knights_total_current_wounds(root)
            if wounds_after >= wounds_before:
                continue
            candidates.append(root)
            wounds_before_by_unit[self._chaos_knights_sort_key(root)] = int(wounds_before)
        candidates.sort(key=self._chaos_knights_sort_key)
        if not candidates:
            return
        preview_cost = self._chaos_knights_preview_cp_cost(
            stratagem,
            target_unit=candidates[0],
            enemy_unit=attacking_root,
        )
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        if self._chaos_knights_reaction_exists(
            "unit_shooting_resolved",
            stratagem.name,
            enemy_unit=attacking_root,
        ):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacking_root,
            "attacking_unit": attacking_root,
            "candidates": candidates,
            "wounds_before_by_unit": wounds_before_by_unit,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _clear_helhunt_flush_the_quarry_effects(self, *, phase_key: str) -> None:
        if str(phase_key or "").strip().upper() != "MOVEMENT_PHASE":
            return
        army = self._chaos_knights_army()
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_knights_root(unit)
            if root is None:
                continue
            root_id = self._chaos_knights_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            expires_phase = str(special_rules.get("helhunt_flush_the_quarry_expires_phase", "") or "").strip().upper()
            if not bool(special_rules.get("helhunt_flush_the_quarry_active")):
                continue
            if expires_phase and expires_phase != str(phase_key or "").strip().upper():
                continue
            self._chaos_knights_remove_phase_move_types(
                special_rules,
                "bearer_unit_phase_move_types",
                "helhunt_flush_the_quarry_added_phase_move_types",
            )
            self._chaos_knights_remove_phase_move_types(
                special_rules,
                "bearer_unit_phase_move_engagement_types",
                "helhunt_flush_the_quarry_added_phase_move_engagement_types",
            )
            if bool(special_rules.get("helhunt_flush_the_quarry_added_auto_pass_desperate_escape", False)):
                special_rules.pop("bearer_unit_auto_pass_desperate_escape", None)
            for key in (
                "helhunt_flush_the_quarry_active",
                "helhunt_flush_the_quarry_expires_phase",
                "helhunt_flush_the_quarry_turn_owner",
                "helhunt_flush_the_quarry_turn",
                "helhunt_flush_the_quarry_source",
                "helhunt_flush_the_quarry_added_auto_pass_desperate_escape",
            ):
                special_rules.pop(key, None)
            root.special_rules = special_rules

    def _clear_helhunt_merciless_fusillade_effects(self, *, phase_key: str) -> None:
        if str(phase_key or "").strip().upper() not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        army = self._chaos_knights_army()
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_knights_root(unit)
            if root is None:
                continue
            root_id = self._chaos_knights_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            expires_phase = str(special_rules.get("helhunt_merciless_fusillade_expires_phase", "") or "").strip().upper()
            if bool(special_rules.get("helhunt_merciless_fusillade_active")) and (
                not expires_phase or expires_phase == str(phase_key or "").strip().upper()
            ):
                for key in (
                    "helhunt_merciless_fusillade_active",
                    "helhunt_merciless_fusillade_target_id",
                    "helhunt_merciless_fusillade_attack_type",
                    "helhunt_merciless_fusillade_target_lock",
                    "helhunt_merciless_fusillade_expires_phase",
                    "helhunt_merciless_fusillade_turn_owner",
                    "helhunt_merciless_fusillade_turn",
                    "helhunt_merciless_fusillade_source",
                ):
                    special_rules.pop(key, None)
                root.special_rules = special_rules
            for model in list(getattr(root, "models", []) or []) + list(getattr(root, "models_lost", []) or []):
                effects = getattr(model, "_temporary_effects", None)
                if not isinstance(effects, dict):
                    continue
                for key in list(effects.keys()):
                    if str(key or "").startswith("helhunt_merciless_fusillade:"):
                        effects.pop(key, None)

    def _clear_helhunt_contemptuous_volleys_effects(self) -> None:
        army = self._chaos_knights_army()
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_knights_root(unit)
            if root is None:
                continue
            root_id = self._chaos_knights_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            if not bool(special_rules.get("helhunt_contemptuous_volleys_active")):
                continue
            for key in (
                "helhunt_contemptuous_volleys_active",
                "helhunt_contemptuous_volleys_turn_owner",
                "helhunt_contemptuous_volleys_turn",
                "helhunt_contemptuous_volleys_source",
            ):
                special_rules.pop(key, None)
            root.special_rules = special_rules

    def _clear_helhunt_feral_arrogance_effects(self, *, phase_key: str) -> None:
        phase_key = str(phase_key or "").strip().upper()
        if not phase_key:
            return
        army = self._chaos_knights_army()
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_knights_root(unit)
            if root is None:
                continue
            root_id = self._chaos_knights_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            entries = list(special_rules.get("defensive_fnp_overrides", []) or [])
            if not entries:
                continue
            kept = []
            for entry in list(entries or []):
                source_name = self._chaos_knights_normalize_name(str(entry.get("source", "") or ""))
                entry_phase = str(entry.get("expires_phase", "") or "").strip().upper()
                if source_name == "FERAL ARROGANCE" and entry_phase == phase_key:
                    continue
                kept.append(entry)
            if kept:
                special_rules["defensive_fnp_overrides"] = kept
            else:
                special_rules.pop("defensive_fnp_overrides", None)
            root.special_rules = special_rules

    def _cleanup_helhunt_phase_end_effects(self, *, player: Any, phase: Any) -> None:
        del player
        if not self._is_helhunt_lance_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_key:
            return
        self._clear_helhunt_feral_arrogance_effects(phase_key=phase_key)
        if phase_key == "MOVEMENT_PHASE":
            self._clear_helhunt_flush_the_quarry_effects(phase_key=phase_key)
        if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            self._clear_helhunt_merciless_fusillade_effects(phase_key=phase_key)
        if phase_key == "SHOOTING_PHASE":
            self._helhunt_goaded_beast_wounds_before().clear()
        if phase_key == "FIGHT_PHASE":
            self._clear_helhunt_contemptuous_volleys_effects()

    def _queue_helhunt_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        phase_name = self._chaos_knights_phase_label(phase_key)

        if phase_key == "MOVEMENT_PHASE" and player is self.player:
            stratagem = self.get_by_name("FLUSH THE QUARRY")
            if stratagem is not None and (stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase:
                source_candidates = list(self._helhunt_flush_the_quarry_source_candidates() or [])
                if source_candidates:
                    preview_cost = self._chaos_knights_preview_cp_cost(stratagem, target_unit=source_candidates[0])
                    if (
                        int(getattr(self.player, "command_points", 0) or 0) >= preview_cost
                        and not self._chaos_knights_reaction_exists("phase_start", stratagem.name)
                    ):
                        payload = {
                            "event": "phase_start",
                            "phase_name": phase_name,
                            "stratagem": stratagem.name,
                            "cp_cost": stratagem.cp_cost,
                            "source_candidates": source_candidates,
                            "source_candidate_ids": [
                                self._chaos_knights_sort_key(candidate) for candidate in list(source_candidates or [])
                            ],
                        }
                        if len(source_candidates) == 1:
                            payload["unit"] = source_candidates[0]
                            payload["target_unit"] = source_candidates[0]
                        self._queue_reaction(payload, use_timer=False)

        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        if phase_key == "SHOOTING_PHASE" and player is not self.player:
            return
        stratagem = self.get_by_name("MERCILESS FUSILLADE")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        source_candidates = list(self._helhunt_merciless_fusillade_source_candidates(phase_name=phase_name) or [])
        if not source_candidates:
            return
        preview_cost = self._chaos_knights_preview_cp_cost(stratagem, target_unit=source_candidates[0])
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        if self._chaos_knights_reaction_exists("phase_start", stratagem.name):
            return
        payload = {
            "event": "phase_start",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "source_candidates": source_candidates,
            "source_candidate_ids": [
                self._chaos_knights_sort_key(candidate) for candidate in list(source_candidates or [])
            ],
        }
        if len(source_candidates) == 1:
            payload["unit"] = source_candidates[0]
            payload["target_unit"] = source_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_helhunt_shooting_target_reactions(self, *, attacking_unit: Any, target_units: List[Any]) -> None:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return
        stratagem = self.get_by_name("BEASTHIDE MANIFESTATION")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacking_root = self._chaos_knights_root(attacking_unit)
        if attacking_root is None or self._chaos_knights_owned_by_player(attacking_root, self.player):
            return
        candidates = self._helhunt_targeted_chaos_knights_candidates(target_units)
        if not candidates:
            return
        preview_cost = self._chaos_knights_preview_cp_cost(
            stratagem,
            target_unit=candidates[0],
            enemy_unit=attacking_root,
        )
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        if self._chaos_knights_reaction_exists(
            "shooting_targets_selected",
            stratagem.name,
            enemy_unit=attacking_root,
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_root,
            "enemy_unit": attacking_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_helhunt_fight_target_reactions(self, *, attacking_unit: Any, target_units: List[Any]) -> None:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return
        stratagem = self.get_by_name("BEASTHIDE MANIFESTATION")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacking_root = self._chaos_knights_root(attacking_unit)
        if attacking_root is None or self._chaos_knights_owned_by_player(attacking_root, self.player):
            return
        candidates = self._helhunt_targeted_chaos_knights_candidates(target_units)
        if not candidates:
            return
        preview_cost = self._chaos_knights_preview_cp_cost(
            stratagem,
            target_unit=candidates[0],
            enemy_unit=attacking_root,
        )
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        if self._chaos_knights_reaction_exists(
            "fight_targets_selected",
            stratagem.name,
            enemy_unit=attacking_root,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_root,
            "enemy_unit": attacking_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_helhunt_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        if str(action or "").strip().lower() != "fall_back":
            return
        stratagem = self.get_by_name("CONTEMPTUOUS VOLLEYS")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        root = self._chaos_knights_root(unit)
        if root is None or not self._chaos_knights_owned_by_player(root, self.player):
            return
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            return
        if not self._is_chaos_knights_unit(root):
            return
        preview_cost = self._chaos_knights_preview_cp_cost(stratagem, target_unit=root)
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        if self._chaos_knights_reaction_exists("unit_move_ended", stratagem.name, unit=root):
            return
        self._queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "action": action,
            },
            use_timer=False,
        )

    def _queue_helhunt_mortal_wound_reactions(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any,
        target_model: Any,
        phase_name: str,
    ) -> None:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return
        stratagem = self.get_by_name("FERAL ARROGANCE")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        root = self._chaos_knights_root(target_unit)
        if root is None or not self._chaos_knights_owned_by_player(root, self.player):
            return
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            return
        if not self._is_chaos_knights_unit(root):
            return
        preview_cost = self._chaos_knights_preview_cp_cost(stratagem, target_unit=root, enemy_unit=attacker_unit)
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        if self._chaos_knights_reaction_exists("mortal_wound_allocated", stratagem.name, unit=root):
            return
        self._queue_reaction(
            {
                "event": "mortal_wound_allocated",
                "phase_name": str(phase_name or self._current_phase_name or "").strip() or "Any phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "attacker_unit": attacker_unit,
                "target_model": target_model,
            },
            use_timer=False,
        )

    def _use_helhunt_beasthide_manifestation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        attacking_root = self._chaos_knights_root(merged.get("attacking_unit") or merged.get("enemy_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: BEASTHIDE MANIFESTATION: no target unit provided")
            return False
        if attacking_root is None:
            logger.error("ERROR: BEASTHIDE MANIFESTATION: missing attacking enemy unit")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: BEASTHIDE MANIFESTATION: target unit is not yours")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: BEASTHIDE MANIFESTATION: target must be on the battlefield and targetable")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: BEASTHIDE MANIFESTATION: target must be a CHAOS KNIGHTS unit")
            return False
        if self._chaos_knights_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: BEASTHIDE MANIFESTATION: attacking unit must be enemy")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: BEASTHIDE MANIFESTATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: BEASTHIDE MANIFESTATION: only usable in your opponent's Shooting phase")
            return False
        candidate_ids = self._chaos_knights_candidate_ids(merged.get("candidates") or [])
        root_id = self._chaos_knights_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: BEASTHIDE MANIFESTATION: target unit was not selected by the attacker")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        if not bool(self._apply_armour_of_contempt(root, attacking_root, amount=1)):
            logger.error("ERROR: BEASTHIDE MANIFESTATION: could not apply AP worsening effect")
            return False
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: BEASTHIDE MANIFESTATION: %s worsens AP by 1 against attacks from %s until it finishes its attacks.",
            getattr(root, "name", "Unit"),
            getattr(attacking_root, "name", "Enemy Unit"),
        )
        return True

    def _use_helhunt_flush_the_quarry(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: FLUSH THE QUARRY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: FLUSH THE QUARRY: only usable in your Movement phase")
            return False
        source_root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if source_root is None:
            source_candidates = list(merged.get("source_candidates", []) or [])
            source_root = self._chaos_knights_root(source_candidates[0]) if len(source_candidates) == 1 else None
        if source_root is None:
            logger.error("ERROR: FLUSH THE QUARRY: no TITANIC source unit provided")
            return False
        if not self._chaos_knights_owned_by_player(source_root, self.player):
            logger.error("ERROR: FLUSH THE QUARRY: source unit is not yours")
            return False
        if not self._chaos_knights_on_battlefield(source_root, require_targetable=True):
            logger.error("ERROR: FLUSH THE QUARRY: source unit must be on the battlefield and targetable")
            return False
        if not self._is_chaos_knights_titanic_unit(source_root):
            logger.error("ERROR: FLUSH THE QUARRY: source unit must be TITANIC")
            return False
        source_candidate_ids = self._chaos_knights_candidate_ids(merged.get("source_candidates") or [])
        source_id = self._chaos_knights_sort_key(source_root)
        if source_candidate_ids and source_id not in source_candidate_ids:
            logger.error("ERROR: FLUSH THE QUARRY: selected source unit is not currently eligible")
            return False
        selected_roots = self._chaos_knights_resolve_selected_units(
            merged.get("selected_units") or merged.get("selected_unit_ids")
        )
        if len(selected_roots) > 3:
            logger.error("ERROR: FLUSH THE QUARRY: select up to three WAR DOG units")
            return False
        candidate_ids = self._chaos_knights_candidate_ids(
            merged.get("war_dog_candidates") or self._helhunt_flush_the_quarry_war_dog_candidates(source_root)
        )
        for root in list(selected_roots or []):
            root_id = self._chaos_knights_sort_key(root)
            if candidate_ids and root_id not in candidate_ids:
                logger.error("ERROR: FLUSH THE QUARRY: selected WAR DOG unit is not currently eligible")
                return False
            if not self._chaos_knights_owned_by_player(root, self.player):
                logger.error("ERROR: FLUSH THE QUARRY: selected unit is not yours")
                return False
            if not self._chaos_knights_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: FLUSH THE QUARRY: selected unit must be on the battlefield and targetable")
                return False
            if not self._is_chaos_knights_war_dog_unit(root):
                logger.error("ERROR: FLUSH THE QUARRY: selected units must be WAR DOG units")
                return False
            distance = self._chaos_knights_distance_between_units(source_root, root)
            if distance is None or distance > 6.0 + 1e-6:
                logger.error("ERROR: FLUSH THE QUARRY: selected WAR DOG units must be within 6\" of the TITANIC source")
                return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=source_root):
            return False
        for root in list(selected_roots or []):
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                special_rules = {}
            self._chaos_knights_merge_phase_move_types(
                special_rules,
                "bearer_unit_phase_move_types",
                "helhunt_flush_the_quarry_added_phase_move_types",
                {"advance", "fall_back", "move"},
            )
            self._chaos_knights_merge_phase_move_types(
                special_rules,
                "bearer_unit_phase_move_engagement_types",
                "helhunt_flush_the_quarry_added_phase_move_engagement_types",
                {"advance", "fall_back", "move"},
            )
            if not bool(special_rules.get("bearer_unit_auto_pass_desperate_escape", False)):
                special_rules["helhunt_flush_the_quarry_added_auto_pass_desperate_escape"] = True
            special_rules["bearer_unit_auto_pass_desperate_escape"] = True
            special_rules["helhunt_flush_the_quarry_active"] = True
            special_rules["helhunt_flush_the_quarry_expires_phase"] = "MOVEMENT_PHASE"
            special_rules["helhunt_flush_the_quarry_turn_owner"] = str(getattr(self.player, "id", "") or "")
            special_rules["helhunt_flush_the_quarry_turn"] = int(getattr(self.game, "turn", 0) or 0)
            special_rules["helhunt_flush_the_quarry_source"] = str(
                getattr(stratagem, "name", "") or "FLUSH THE QUARRY"
            )
            root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: FLUSH THE QUARRY: %d WAR DOG unit(s) can move through models and terrain this phase.",
            len(list(selected_roots or [])),
        )
        return True

    def _use_helhunt_merciless_fusillade(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: MERCILESS FUSILLADE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: MERCILESS FUSILLADE: only usable in your Shooting phase")
            return False
        source_root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if source_root is None:
            source_candidates = list(merged.get("source_candidates", []) or [])
            source_root = self._chaos_knights_root(source_candidates[0]) if len(source_candidates) == 1 else None
        if source_root is None:
            logger.error("ERROR: MERCILESS FUSILLADE: no TITANIC source unit provided")
            return False
        if not self._chaos_knights_owned_by_player(source_root, self.player):
            logger.error("ERROR: MERCILESS FUSILLADE: source unit is not yours")
            return False
        if not self._chaos_knights_on_battlefield(source_root, require_targetable=True):
            logger.error("ERROR: MERCILESS FUSILLADE: source unit must be on the battlefield and targetable")
            return False
        if not self._is_chaos_knights_titanic_unit(source_root):
            logger.error("ERROR: MERCILESS FUSILLADE: source unit must be TITANIC")
            return False
        source_candidate_ids = self._chaos_knights_candidate_ids(
            merged.get("source_candidates") or self._helhunt_merciless_fusillade_source_candidates(phase_name=phase_name)
        )
        source_id = self._chaos_knights_sort_key(source_root)
        if source_candidate_ids and source_id not in source_candidate_ids:
            logger.error("ERROR: MERCILESS FUSILLADE: selected source unit is not currently eligible")
            return False
        selected_roots = self._chaos_knights_resolve_selected_units(
            merged.get("selected_units") or merged.get("selected_unit_ids")
        )
        if len(selected_roots) > 2:
            logger.error("ERROR: MERCILESS FUSILLADE: select up to two WAR DOG units")
            return False
        war_dog_candidate_ids = self._chaos_knights_candidate_ids(
            merged.get("war_dog_candidates") or self._helhunt_merciless_fusillade_war_dog_candidates(source_root, phase_name=phase_name)
        )
        for root in list(selected_roots or []):
            root_id = self._chaos_knights_sort_key(root)
            if war_dog_candidate_ids and root_id not in war_dog_candidate_ids:
                logger.error("ERROR: MERCILESS FUSILLADE: selected WAR DOG unit is not currently eligible")
                return False
            if not self._chaos_knights_owned_by_player(root, self.player):
                logger.error("ERROR: MERCILESS FUSILLADE: selected unit is not yours")
                return False
            if not self._chaos_knights_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: MERCILESS FUSILLADE: selected unit must be on the battlefield and targetable")
                return False
            if not self._is_chaos_knights_war_dog_unit(root):
                logger.error("ERROR: MERCILESS FUSILLADE: selected support units must be WAR DOG units")
                return False
        enemy_root = self._chaos_knights_root(merged.get("enemy_unit") or merged.get("target_enemy_unit"))
        enemy_candidates = list(
            merged.get("enemy_candidates")
            or self._helhunt_merciless_fusillade_enemy_candidates(
                source_root,
                selected_roots,
                phase_name=phase_name,
            )
            or []
        )
        if enemy_root is None and len(enemy_candidates) == 1:
            enemy_root = enemy_candidates[0]
        if enemy_root is None:
            logger.error("ERROR: MERCILESS FUSILLADE: no enemy unit selected")
            return False
        enemy_candidate_ids = self._chaos_knights_candidate_ids(enemy_candidates)
        enemy_id = self._chaos_knights_sort_key(enemy_root)
        if enemy_candidate_ids and enemy_id not in enemy_candidate_ids:
            logger.error("ERROR: MERCILESS FUSILLADE: selected enemy is not an eligible target for every chosen unit")
            return False
        if self._chaos_knights_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: MERCILESS FUSILLADE: selected enemy must be an enemy unit")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=source_root):
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        active_turn_owner_id = str(getattr(active_player, "id", "") or "").strip() or str(
            getattr(self.player, "id", "") or ""
        ).strip()
        attack_type = "ranged" if phase_name == "shooting phase" else "melee"
        expires_phase = "SHOOTING_PHASE" if attack_type == "ranged" else "FIGHT_PHASE"
        affected_units = self._chaos_knights_resolve_selected_units([source_root] + list(selected_roots or []))
        for root in list(affected_units or []):
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                special_rules = {}
            special_rules["helhunt_merciless_fusillade_active"] = True
            special_rules["helhunt_merciless_fusillade_target_id"] = str(enemy_id or "")
            special_rules["helhunt_merciless_fusillade_attack_type"] = attack_type
            special_rules["helhunt_merciless_fusillade_target_lock"] = True
            special_rules["helhunt_merciless_fusillade_expires_phase"] = expires_phase
            special_rules["helhunt_merciless_fusillade_turn_owner"] = active_turn_owner_id
            special_rules["helhunt_merciless_fusillade_turn"] = int(getattr(self.game, "turn", 0) or 0)
            special_rules["helhunt_merciless_fusillade_source"] = str(
                getattr(stratagem, "name", "") or "MERCILESS FUSILLADE"
            )
            root.special_rules = special_rules
            for model in list(self._chaos_knights_alive_models(root) or []):
                model_id = str(get_entity_id(model) or "")
                for wargear in list(getattr(model, "wargear", []) or []):
                    if attack_type == "ranged":
                        is_match = getattr(wargear, "is_ranged", None)
                    else:
                        is_match = getattr(wargear, "is_melee", None)
                    if not callable(is_match) or not bool(is_match()):
                        continue
                    for profile in list((getattr(wargear, "profiles", None) or {}).values() or []):
                        if profile is None:
                            continue
                        lookup_name = getattr(profile, "_temporary_weapon_lookup_name", None)
                        weapon_name = lookup_name() if callable(lookup_name) else str(getattr(profile, "name", "") or "")
                        if not weapon_name:
                            continue
                        model.set_temporary_weapon_keyword_bonuses(
                            key=(
                                "helhunt_merciless_fusillade:"
                                f"{self._chaos_knights_sort_key(root)}:{model_id}:{weapon_name}:{attack_type}"
                            ),
                            weapon_name=weapon_name,
                            keywords=["SUSTAINED HITS 1"],
                            source=str(getattr(stratagem, "name", "") or "MERCILESS FUSILLADE"),
                            expires_phase=expires_phase,
                            attack_type=attack_type,
                        )
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: MERCILESS FUSILLADE: %d unit(s) are locked to %s and gain [SUSTAINED HITS 1] this phase.",
            len(list(affected_units or [])),
            getattr(enemy_root, "name", "Enemy Unit"),
        )
        return True

    def _use_helhunt_goaded_beast(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: GOADED BEAST: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: GOADED BEAST: only usable in your opponent's Shooting phase")
            return False
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        attacking_root = self._chaos_knights_root(merged.get("attacking_unit") or merged.get("enemy_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: GOADED BEAST: no target unit provided")
            return False
        if attacking_root is None:
            logger.error("ERROR: GOADED BEAST: missing attacking enemy unit")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: GOADED BEAST: target unit is not yours")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: GOADED BEAST: target must be on the battlefield and targetable")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: GOADED BEAST: target must be a CHAOS KNIGHTS unit")
            return False
        if self._chaos_knights_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: GOADED BEAST: attacking unit must be enemy")
            return False
        candidate_ids = self._chaos_knights_candidate_ids(merged.get("candidates") or [])
        root_id = self._chaos_knights_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: GOADED BEAST: target unit did not lose wounds from those attacks")
            return False
        wounds_before_by_unit = dict(merged.get("wounds_before_by_unit") or {})
        if wounds_before_by_unit:
            before = int(wounds_before_by_unit.get(root_id, 0) or 0)
            after = self._chaos_knights_total_current_wounds(root)
            if before and after >= before:
                logger.error("ERROR: GOADED BEAST: target unit did not lose wounds from those attacks")
                return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        max_distance = kwargs.get("max_distance")
        if max_distance is None:
            max_distance = int(get_roll("D6") or 0)
        try:
            max_distance = int(max_distance or 0)
        except Exception:
            max_distance = 0
        if max_distance <= 0:
            logger.error("ERROR: GOADED BEAST: movement distance roll failed")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: GOADED BEAST: reactive movement queue unavailable")
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            attacker_unit=attacking_root,
            max_distance=int(max_distance),
            kind="helhunt_goaded_beast",
            movement_type="blood_surge",
            source=str(getattr(stratagem, "name", "") or "GOADED BEAST"),
            allow_engagement_range=True,
        )
        if request is None:
            logger.error("ERROR: GOADED BEAST: failed to queue reactive movement decision")
            return False
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: GOADED BEAST: %s can make a Surge move up to %d\".",
            getattr(root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_helhunt_contemptuous_volleys(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: CONTEMPTUOUS VOLLEYS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: CONTEMPTUOUS VOLLEYS: only usable in your Movement phase")
            return False
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            candidates = list(merged.get("candidates") or self._helhunt_contemptuous_volleys_candidates() or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: CONTEMPTUOUS VOLLEYS: no target unit provided")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: CONTEMPTUOUS VOLLEYS: target unit is not yours")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: CONTEMPTUOUS VOLLEYS: target must be on the battlefield and targetable")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: CONTEMPTUOUS VOLLEYS: target must be a CHAOS KNIGHTS unit")
            return False
        candidate_ids = self._chaos_knights_candidate_ids(
            merged.get("candidates") or self._helhunt_contemptuous_volleys_candidates()
        )
        root_id = self._chaos_knights_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: CONTEMPTUOUS VOLLEYS: target unit is not currently eligible")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: CONTEMPTUOUS VOLLEYS: target unit must have Fallen Back")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["helhunt_contemptuous_volleys_active"] = True
        special_rules["helhunt_contemptuous_volleys_turn_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["helhunt_contemptuous_volleys_turn"] = int(getattr(self.game, "turn", 0) or 0)
        special_rules["helhunt_contemptuous_volleys_source"] = str(
            getattr(stratagem, "name", "") or "CONTEMPTUOUS VOLLEYS"
        )
        root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: CONTEMPTUOUS VOLLEYS: %s can shoot and charge after Falling Back this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_helhunt_feral_arrogance(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_helhunt_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: FERAL ARROGANCE: no target unit provided")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: FERAL ARROGANCE: target unit is not yours")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: FERAL ARROGANCE: target must be on the battlefield and targetable")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: FERAL ARROGANCE: target must be a CHAOS KNIGHTS unit")
            return False
        candidate_ids = self._chaos_knights_candidate_ids(merged.get("candidates") or [])
        root_id = self._chaos_knights_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: FERAL ARROGANCE: target unit is not currently eligible")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip()
        phase_key = self._phase_key_from_name(phase_name)
        if not phase_key:
            logger.error("ERROR: FERAL ARROGANCE: could not resolve current phase")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        self._append_defensive_effect(
            root,
            "defensive_fnp_overrides",
            {
                "value": 5,
                "condition": "against mortal wounds",
                "attack_type": "any",
                "expires_phase": phase_key,
                "source": str(getattr(stratagem, "name", "") or "FERAL ARROGANCE"),
            },
        )
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: FERAL ARROGANCE: %s gains Feel No Pain 5+ against mortal wounds this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _queue_traitoris_failed_battleshock_reactions(self, *, enemy_unit: Any, passed: bool) -> None:
        if passed or not self._is_traitoris_lance_detachment() or self.game is None:
            return
        enemy_root = self._chaos_knights_root(enemy_unit)
        if enemy_root is None or self._chaos_knights_owned_by_player(enemy_root, self.player):
            return
        stratagem = self.get_by_name("PTERRORSHADES")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._traitoris_pterrorshades_candidates(enemy_root)
        if not candidates:
            return
        preview_cost = self._chaos_knights_preview_cp_cost(stratagem, target_unit=candidates[0], enemy_unit=enemy_root)
        if int(getattr(self.player, "command_points", 0) or 0) < preview_cost:
            return
        if self._chaos_knights_reaction_exists(
            "battle_shock_test_resolved",
            stratagem.name,
            enemy_unit=enemy_root,
        ):
            return
        payload = {
            "event": "battle_shock_test_resolved",
            "phase_name": str(getattr(self, "_current_phase_name", "") or "").strip() or "Any phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "enemy_unit_id": self._chaos_knights_sort_key(enemy_root),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _traitoris_destroyed_enemy_units(self, killing_models_by_target: Any) -> List[Any]:
        if not isinstance(killing_models_by_target, dict):
            return []
        destroyed: List[Any] = []
        seen: set[str] = set()
        for target, killed_models in list(killing_models_by_target.items()):
            if not list(killed_models or []):
                continue
            target_root = self._chaos_knights_root(target)
            if target_root is None or self._chaos_knights_owned_by_player(target_root, self.player):
                continue
            if self._chaos_knights_alive_models(target_root):
                continue
            target_id = self._chaos_knights_sort_key(target_root)
            if target_id and target_id in seen:
                continue
            if target_id:
                seen.add(target_id)
            destroyed.append(target_root)
        destroyed.sort(key=self._chaos_knights_sort_key)
        return destroyed

    def _queue_traitoris_fight_attacks_resolved_reactions(
        self,
        *,
        unit: Any,
        target_unit: Any,
        killing_models_by_target: Any,
    ) -> None:
        del target_unit
        if not self._is_traitoris_lance_detachment() or self.game is None:
            return
        root = self._chaos_knights_root(unit)
        if root is None or not self._chaos_knights_owned_by_player(root, self.player):
            return
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            return
        if special_rules.get("traitoris_conquerors_without_mercy_active") is not True:
            return
        if special_rules.get("traitoris_conquerors_without_mercy_battle_shock_applied") is True:
            return
        destroyed_units = self._traitoris_destroyed_enemy_units(killing_models_by_target)
        if not destroyed_units:
            return
        destroyed_ids = {self._chaos_knights_sort_key(enemy_root) for enemy_root in list(destroyed_units or [])}
        affected: List[Any] = []
        for enemy_root in list(self._chaos_knights_enemy_roots() or []):
            enemy_id = self._chaos_knights_sort_key(enemy_root)
            if enemy_id and enemy_id in destroyed_ids:
                continue
            distance = self._chaos_knights_distance_between_units(root, enemy_root)
            if distance is None or distance > 6.0 + 1e-6:
                continue
            affected.append(enemy_root)
        turn = int(getattr(self.game, "turn", 1) or 1)
        tested_names: List[str] = []
        for enemy_root in list(affected or []):
            take_battle_shock = getattr(enemy_root, "take_battle_shock_test", None)
            if not callable(take_battle_shock):
                continue
            take_battle_shock(int(turn))
            tested_names.append(str(getattr(enemy_root, "name", "Enemy Unit") or "Enemy Unit"))
        special_rules["traitoris_conquerors_without_mercy_battle_shock_applied"] = True
        root.special_rules = special_rules
        logger.info(
            "INFO: CONQUERORS WITHOUT MERCY: %s destroyed %d enemy unit(s); %d nearby enemy unit(s) test for Battle-shock%s.",
            getattr(root, "name", "Unit"),
            len(list(destroyed_units or [])),
            len(list(tested_names or [])),
            f" ({', '.join(tested_names)})" if tested_names else "",
        )

    def _use_traitoris_a_long_leash(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_traitoris_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        source_root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if source_root is None:
            logger.error("ERROR: A LONG LEASH: no ABHORRENT source unit provided")
            return False
        if not self._chaos_knights_owned_by_player(source_root, self.player):
            logger.error("ERROR: A LONG LEASH: source unit is not yours")
            return False
        if not self._is_chaos_knights_abhorrent_unit(source_root):
            logger.error("ERROR: A LONG LEASH: source unit must be an ABHORRENT unit")
            return False
        if not self._chaos_knights_on_battlefield(source_root, require_targetable=True):
            logger.error("ERROR: A LONG LEASH: source unit must be an eligible battlefield unit")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: A LONG LEASH: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: A LONG LEASH: only usable in your Command phase")
            return False
        candidate_roots = list(merged.get("war_dog_candidates", []) or [])
        if not candidate_roots:
            candidate_roots = list(self._traitoris_a_long_leash_war_dog_candidates(source_root) or [])
        selected_roots = self._traitoris_resolve_selected_units(
            merged.get("selected_units")
            or merged.get("selected_unit_ids")
            or merged.get("war_dog_units")
            or merged.get("war_dog_unit_ids")
        )
        if not selected_roots and len(candidate_roots) <= 2:
            selected_roots = list(candidate_roots)
        if len(selected_roots) > 2:
            logger.error("ERROR: A LONG LEASH: select up to two friendly WAR DOG units")
            return False
        candidate_ids = {self._chaos_knights_sort_key(root) for root in list(candidate_roots or [])}
        for target_root in list(selected_roots or []):
            if candidate_ids and self._chaos_knights_sort_key(target_root) not in candidate_ids:
                logger.error("ERROR: A LONG LEASH: selected WAR DOG unit is not currently eligible")
                return False
            if not self._chaos_knights_owned_by_player(target_root, self.player):
                logger.error("ERROR: A LONG LEASH: selected WAR DOG unit is not yours")
                return False
            if not self._is_chaos_knights_war_dog_unit(target_root):
                logger.error("ERROR: A LONG LEASH: selected target must be a WAR DOG unit")
                return False
            if not self._chaos_knights_on_battlefield(target_root, require_targetable=True):
                logger.error("ERROR: A LONG LEASH: selected WAR DOG unit is not an eligible battlefield unit")
                return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=source_root):
            return False

        self._clear_traitoris_a_long_leash_effects()
        source_id = self._chaos_knights_sort_key(source_root)
        source_name = str(getattr(stratagem, "name", "") or "A LONG LEASH")
        for target_root in list(selected_roots or []):
            special_rules = getattr(target_root, "special_rules", None)
            if not isinstance(special_rules, dict):
                special_rules = {}
            special_rules["traitoris_a_long_leash_active"] = True
            special_rules["traitoris_a_long_leash_source_unit_id"] = source_id
            special_rules["traitoris_a_long_leash_source"] = source_name
            target_root.special_rules = special_rules

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: A LONG LEASH: %d WAR DOG unit(s) count as within %s's Aura abilities until your next Command phase.",
            len(list(selected_roots or [])),
            getattr(source_root, "name", "ABHORRENT unit"),
        )
        return True

    def _use_traitoris_pterrorshades(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_traitoris_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        enemy_root = self._chaos_knights_root(merged.get("enemy_unit") or merged.get("target_enemy_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: PTERRORSHADES: no source unit provided")
            return False
        if enemy_root is None:
            logger.error("ERROR: PTERRORSHADES: missing failed Battle-shock enemy unit")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: PTERRORSHADES: source unit is not yours")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: PTERRORSHADES: source unit must be on the battlefield and targetable")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: PTERRORSHADES: source unit must be a CHAOS KNIGHTS unit")
            return False
        if self._chaos_knights_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: PTERRORSHADES: selected enemy must be an enemy unit")
            return False
        if not self._chaos_knights_on_battlefield(enemy_root, require_targetable=False):
            logger.error("ERROR: PTERRORSHADES: enemy unit must still be on the battlefield")
            return False
        distance = self._chaos_knights_distance_between_units(root, enemy_root)
        if distance is None or distance > 12.0 + 1e-6:
            logger.error("ERROR: PTERRORSHADES: enemy unit must be within 12\"")
            return False
        candidates = list(merged.get("candidates", []) or [])
        eligible = candidates or self._traitoris_pterrorshades_candidates(enemy_root)
        if eligible and root not in list(eligible or []):
            logger.error("ERROR: PTERRORSHADES: selected source unit is not currently eligible")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False

        rolls = [int(get_roll("D6") or 0) for _ in range(6)]
        mortal_wounds = sum(1 for roll in list(rolls or []) if int(roll or 0) >= 4)
        if mortal_wounds > 0:
            apply_mortals = getattr(root, "_apply_mortal_wounds_to_unit", None)
            if not callable(apply_mortals):
                logger.error("ERROR: PTERRORSHADES: mortal wound application helper unavailable")
                return False
            apply_mortals(
                enemy_root,
                int(mortal_wounds),
                game_map=getattr(self.game, "map", None),
            )
        healed = self._chaos_knights_heal_lost_wounds(root, int(mortal_wounds))
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: PTERRORSHADES: %s rolls %s into %d mortal wound(s) on %s and restores %d wound(s).",
            getattr(root, "name", "Unit"),
            rolls,
            int(mortal_wounds),
            getattr(enemy_root, "name", "Enemy Unit"),
            int(healed),
        )
        return True

    def _use_traitoris_conquerors_without_mercy(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_traitoris_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        if root is None:
            logger.error("ERROR: CONQUERORS WITHOUT MERCY: no target unit provided")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: CONQUERORS WITHOUT MERCY: target unit is not yours")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: CONQUERORS WITHOUT MERCY: target must be a CHAOS KNIGHTS unit")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: CONQUERORS WITHOUT MERCY: target must be on the battlefield and targetable")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: CONQUERORS WITHOUT MERCY: wrong phase")
            return False
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "charged_this_round", False)):
            logger.error("ERROR: CONQUERORS WITHOUT MERCY: target must have made a Charge move this turn")
            return False
        if bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: CONQUERORS WITHOUT MERCY: target has already fought this phase")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        for model in list(self._chaos_knights_alive_models(root) or []):
            effects = getattr(model, "_temporary_effects", None)
            if not isinstance(effects, dict):
                effects = {}
                model._temporary_effects = effects
            effects["traitoris_conquerors_without_mercy_ap_boost"] = {
                "expires_phase": "FIGHT_PHASE",
                "melee_ap_bonus": 1,
            }
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["traitoris_conquerors_without_mercy_active"] = True
        special_rules["traitoris_conquerors_without_mercy_expires_phase"] = "FIGHT_PHASE"
        special_rules["traitoris_conquerors_without_mercy_source"] = str(
            getattr(stratagem, "name", "") or "CONQUERORS WITHOUT MERCY"
        )
        special_rules.pop("traitoris_conquerors_without_mercy_battle_shock_applied", None)
        root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: CONQUERORS WITHOUT MERCY: %s improves melee AP by 1 this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_traitoris_disdain_for_the_weak(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_traitoris_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        attacking_root = self._chaos_knights_root(merged.get("attacking_unit") or merged.get("enemy_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: DISDAIN FOR THE WEAK: no target unit provided")
            return False
        if attacking_root is None:
            logger.error("ERROR: DISDAIN FOR THE WEAK: missing attacking enemy unit")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: DISDAIN FOR THE WEAK: target unit is not yours")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: DISDAIN FOR THE WEAK: target must be a CHAOS KNIGHTS unit")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: DISDAIN FOR THE WEAK: target must be on the battlefield and targetable")
            return False
        if self._chaos_knights_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: DISDAIN FOR THE WEAK: attacking unit must be enemy")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: DISDAIN FOR THE WEAK: wrong phase")
            return False
        candidates = list(merged.get("candidates", []) or [])
        if candidates and root not in list(candidates or []):
            logger.error("ERROR: DISDAIN FOR THE WEAK: target unit was not selected as an enemy target")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        self._append_defensive_effect(
            root,
            "defensive_fnp_overrides",
            {
                "value": 6,
                "attack_type": "melee",
                "expires_phase": "FIGHT_PHASE",
                "source": str(getattr(stratagem, "name", "") or "DISDAIN FOR THE WEAK"),
            },
        )
        self._append_defensive_effect(
            root,
            "defensive_fnp_overrides",
            {
                "value": 5,
                "attack_type": "melee",
                "condition": "against attacks made by Battle-shocked models",
                "expires_phase": "FIGHT_PHASE",
                "source": str(getattr(stratagem, "name", "") or "DISDAIN FOR THE WEAK"),
            },
        )
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: DISDAIN FOR THE WEAK: %s gains Feel No Pain 6+, improving to 5+ against Battle-shocked attackers, this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_traitoris_imperious_advance(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_traitoris_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"movement phase", "charge phase"}:
            logger.error("ERROR: IMPERIOUS ADVANCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: IMPERIOUS ADVANCE: only usable in your turn")
            return False
        selected_roots = self._traitoris_resolve_selected_units(
            merged.get("selected_units") or merged.get("selected_unit_ids")
        )
        if not selected_roots:
            root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
            if root is not None:
                selected_roots = [root]
        war_dog_candidates = list(merged.get("war_dog_candidates", []) or [])
        titanic_candidates = list(merged.get("titanic_candidates", []) or [])
        if not war_dog_candidates:
            war_dog_candidates = list(self._traitoris_imperious_advance_war_dog_candidates(phase_name=phase_name) or [])
        if not titanic_candidates:
            titanic_candidates = list(
                self._traitoris_imperious_advance_titanic_candidates(phase_name=phase_name) or []
            )
        if not selected_roots:
            if len(titanic_candidates) == 1 and not war_dog_candidates:
                selected_roots = [titanic_candidates[0]]
            elif 0 < len(war_dog_candidates) <= 2 and not titanic_candidates:
                selected_roots = list(war_dog_candidates)
        if not selected_roots:
            logger.error("ERROR: IMPERIOUS ADVANCE: no units selected")
            return False
        titanic_ids = {self._chaos_knights_sort_key(root) for root in list(titanic_candidates or [])}
        war_dog_ids = {self._chaos_knights_sort_key(root) for root in list(war_dog_candidates or [])}
        selected_ids = {self._chaos_knights_sort_key(root) for root in list(selected_roots or [])}
        selecting_titanic = any(root_id in titanic_ids for root_id in list(selected_ids or []))
        if selecting_titanic:
            if len(selected_roots) != 1:
                logger.error("ERROR: IMPERIOUS ADVANCE: select either up to two WAR DOG units or one TITANIC unit")
                return False
        elif len(selected_roots) > 2:
            logger.error("ERROR: IMPERIOUS ADVANCE: select up to two WAR DOG units")
            return False
        for root in list(selected_roots or []):
            root_id = self._chaos_knights_sort_key(root)
            if selecting_titanic:
                if root_id not in titanic_ids:
                    logger.error("ERROR: IMPERIOUS ADVANCE: selected TITANIC unit is not currently eligible")
                    return False
                if not self._is_chaos_knights_titanic_unit(root):
                    logger.error("ERROR: IMPERIOUS ADVANCE: TITANIC target is invalid")
                    return False
            else:
                if root_id not in war_dog_ids:
                    logger.error("ERROR: IMPERIOUS ADVANCE: selected WAR DOG unit is not currently eligible")
                    return False
                if not self._is_chaos_knights_war_dog_unit(root):
                    logger.error("ERROR: IMPERIOUS ADVANCE: target must be a WAR DOG unit")
                    return False
            if not self._chaos_knights_owned_by_player(root, self.player):
                logger.error("ERROR: IMPERIOUS ADVANCE: selected unit is not yours")
                return False
            if not self._chaos_knights_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: IMPERIOUS ADVANCE: selected unit must be on the battlefield and targetable")
                return False
            round_state = getattr(root, "round_state", None)
            if phase_name == "movement phase":
                if bool(getattr(round_state, "moved_this_round", False)):
                    logger.error("ERROR: IMPERIOUS ADVANCE: selected unit has already moved this phase")
                    return False
                if bool(getattr(round_state, "advanced_this_round", False)):
                    logger.error("ERROR: IMPERIOUS ADVANCE: selected unit has already moved this phase")
                    return False
                if bool(getattr(round_state, "fell_back_this_round", False)):
                    logger.error("ERROR: IMPERIOUS ADVANCE: selected unit has already moved this phase")
                    return False
            if phase_name == "charge phase" and bool(getattr(round_state, "attempted_charge_this_round", False)):
                logger.error("ERROR: IMPERIOUS ADVANCE: selected unit has already declared a charge this phase")
                return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False
        expires_phase = "MOVEMENT_PHASE" if phase_name == "movement phase" else "CHARGE_PHASE"
        move_types = {"move", "advance", "fall_back"} if phase_name == "movement phase" else {"charge"}
        engagement_types = {"move", "advance", "fall_back"} if phase_name == "movement phase" else set()
        for root in list(selected_roots or []):
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                special_rules = {}
            self._chaos_knights_merge_phase_move_types(
                special_rules,
                "bearer_unit_phase_move_types",
                "traitoris_imperious_advance_added_phase_move_types",
                set(move_types),
            )
            self._chaos_knights_merge_phase_move_types(
                special_rules,
                "bearer_unit_phase_move_engagement_types",
                "traitoris_imperious_advance_added_phase_move_engagement_types",
                set(engagement_types),
            )
            if not bool(special_rules.get("bearer_unit_auto_pass_desperate_escape", False)):
                special_rules["traitoris_imperious_advance_added_auto_pass_desperate_escape"] = True
            special_rules["bearer_unit_auto_pass_desperate_escape"] = True
            if "titanic_phase_move_block_titanic_types" in special_rules:
                special_rules["traitoris_imperious_advance_prev_titanic_block_present"] = True
                special_rules["traitoris_imperious_advance_prev_titanic_block_value"] = list(
                    special_rules.get("titanic_phase_move_block_titanic_types", []) or []
                )
                special_rules.pop("titanic_phase_move_block_titanic_types", None)
            special_rules["traitoris_imperious_advance_active"] = True
            special_rules["traitoris_imperious_advance_expires_phase"] = expires_phase
            special_rules["traitoris_imperious_advance_turn_owner"] = str(getattr(self.player, "id", "") or "")
            special_rules["traitoris_imperious_advance_turn"] = int(getattr(self.game, "turn", 0) or 0)
            special_rules["traitoris_imperious_advance_source"] = str(
                getattr(stratagem, "name", "") or "IMPERIOUS ADVANCE"
            )
            root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: IMPERIOUS ADVANCE: %d unit(s) can move through models and terrain this %s.",
            len(list(selected_roots or [])),
            phase_name,
        )
        return True

    def _use_traitoris_storm_of_darkness(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_traitoris_lance_detachment() or self.game is None:
            return False
        merged = self._chaos_knights_pending_context(stratagem.name, kwargs)
        root = self._chaos_knights_root(merged.get("unit") or merged.get("target_unit"))
        attacking_root = self._chaos_knights_root(merged.get("attacking_unit") or merged.get("enemy_unit"))
        if root is None:
            candidates = list(merged.get("candidates", []) or [])
            root = self._chaos_knights_root(candidates[0]) if len(candidates) == 1 else None
        if root is None:
            logger.error("ERROR: STORM OF DARKNESS: no target unit provided")
            return False
        if attacking_root is None:
            logger.error("ERROR: STORM OF DARKNESS: missing attacking enemy unit")
            return False
        if not self._chaos_knights_owned_by_player(root, self.player):
            logger.error("ERROR: STORM OF DARKNESS: target unit is not yours")
            return False
        if not self._is_chaos_knights_unit(root):
            logger.error("ERROR: STORM OF DARKNESS: target must be a CHAOS KNIGHTS unit")
            return False
        if not self._chaos_knights_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: STORM OF DARKNESS: target must be on the battlefield and targetable")
            return False
        if self._chaos_knights_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: STORM OF DARKNESS: attacking unit must be enemy")
            return False
        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: STORM OF DARKNESS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: STORM OF DARKNESS: only usable in your opponent's Shooting phase")
            return False
        candidates = list(merged.get("candidates", []) or [])
        if candidates and root not in list(candidates or []):
            logger.error("ERROR: STORM OF DARKNESS: target unit was not selected by the attacker")
            return False
        if not self._chaos_knights_spend_cp(stratagem, target_unit=root):
            return False
        self._append_defensive_effect(
            root,
            "defensive_cover_bonuses",
            {
                "attack_type": "ranged",
                "expires_phase": "SHOOTING_PHASE",
                "source": str(getattr(stratagem, "name", "") or "STORM OF DARKNESS"),
            },
        )
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["traitoris_storm_of_darkness_active"] = True
        special_rules["traitoris_storm_of_darkness_expires_phase"] = "SHOOTING_PHASE"
        special_rules["traitoris_storm_of_darkness_source"] = str(
            getattr(stratagem, "name", "") or "STORM OF DARKNESS"
        )
        root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        logger.info(
            "INFO: STORM OF DARKNESS: %s gains Stealth and Benefit of Cover this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_chaos_knights_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_key = self._chaos_knights_normalize_name(getattr(stratagem, "name", "") or "")
        if name_key == "CLAIMED FOR THE DARK GODS":
            return self._use_lords_of_dread_claimed_for_dark_gods(stratagem, **kwargs)
        if name_key == "CRUSHED LIKE VERMIN":
            return self._use_lords_of_dread_crushed_like_vermin(stratagem, **kwargs)
        if name_key == "SPITEFUL DEMISE":
            if self._is_lords_of_dread_detachment():
                return self._use_lords_of_dread_spiteful_demise(stratagem, **kwargs)
            return None
        if name_key == "TITANIC DUEL":
            return self._use_lords_of_dread_titanic_duel(stratagem, **kwargs)
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
        if name_key == "A LONG LEASH":
            return self._use_traitoris_a_long_leash(stratagem, **kwargs)
        if name_key == "PTERRORSHADES":
            return self._use_traitoris_pterrorshades(stratagem, **kwargs)
        if name_key == "CONQUERORS WITHOUT MERCY":
            return self._use_traitoris_conquerors_without_mercy(stratagem, **kwargs)
        if name_key == "DISDAIN FOR THE WEAK":
            return self._use_traitoris_disdain_for_the_weak(stratagem, **kwargs)
        if name_key == "IMPERIOUS ADVANCE":
            return self._use_traitoris_imperious_advance(stratagem, **kwargs)
        if name_key == "STORM OF DARKNESS":
            return self._use_traitoris_storm_of_darkness(stratagem, **kwargs)
        if name_key == "BEASTHIDE MANIFESTATION":
            return self._use_helhunt_beasthide_manifestation(stratagem, **kwargs)
        if name_key == "FLUSH THE QUARRY":
            return self._use_helhunt_flush_the_quarry(stratagem, **kwargs)
        if name_key == "MERCILESS FUSILLADE":
            return self._use_helhunt_merciless_fusillade(stratagem, **kwargs)
        if name_key == "GOADED BEAST":
            return self._use_helhunt_goaded_beast(stratagem, **kwargs)
        if name_key == "CONTEMPTUOUS VOLLEYS":
            return self._use_helhunt_contemptuous_volleys(stratagem, **kwargs)
        if name_key == "FERAL ARROGANCE":
            return self._use_helhunt_feral_arrogance(stratagem, **kwargs)
        return None
