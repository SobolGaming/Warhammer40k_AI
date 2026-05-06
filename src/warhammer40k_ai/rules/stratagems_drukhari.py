from __future__ import annotations

import logging
from typing import Any, Optional

from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
from ..engine.decisions import DecisionOption, DecisionRequest
from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class DrukhariStratagemMixin:
    @staticmethod
    def _drukhari_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _drukhari_clear_unit_ability_cache(unit: Any) -> None:
        if unit is None:
            return
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            maybe_root = get_root()
            if maybe_root is not None:
                root = maybe_root
        invalidate = getattr(root, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()
            return
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.clear()

    @staticmethod
    def _drukhari_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    def _drukhari_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "drukhari_detachments", None)

    def _is_drukhari_skysplinter_assault(self) -> bool:
        mgr = self._drukhari_detachment_mgr()
        checker = getattr(mgr, "is_skysplinter_assault", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_drukhari_reapers_wager(self) -> bool:
        mgr = self._drukhari_detachment_mgr()
        checker = getattr(mgr, "is_reapers_wager", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_drukhari_covenite_coterie(self) -> bool:
        mgr = self._drukhari_detachment_mgr()
        checker = getattr(mgr, "is_covenite_coterie", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_drukhari_kabalite_cartel(self) -> bool:
        mgr = self._drukhari_detachment_mgr()
        checker = getattr(mgr, "is_kabalite_cartel", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_drukhari_realspace_raiders(self) -> bool:
        mgr = self._drukhari_detachment_mgr()
        checker = getattr(mgr, "is_realspace_raiders", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _drukhari_has_keyword(unit: Any, keyword: str) -> bool:
        if unit is None:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(keyword)):
            return True
        has_kw = getattr(unit, "has_keyword", None)
        if callable(has_kw) and bool(has_kw(keyword)):
            return True
        return False

    def _is_drukhari_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if faction_id == "DRU":
            return True
        return self._drukhari_has_keyword(root, "DRUKHARI")

    def _is_harlequins_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        if self._drukhari_has_keyword(root, "HARLEQUINS"):
            return True
        try:
            faction_data = getattr(getattr(root, "_datasheet", None), "faction_data", None)
            faction_name = str(getattr(faction_data, "get", lambda *_args, **_kwargs: "")("name", "") or "").strip().upper()
        except Exception:
            faction_name = ""
        return "HARLEQUIN" in faction_name

    def _is_drukhari_or_harlequins_unit(self, unit: Any) -> bool:
        return self._is_drukhari_unit(unit) or self._is_harlequins_unit(unit)

    def _is_drukhari_infantry(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None or not self._is_drukhari_unit(root):
            return False
        return self._drukhari_has_keyword(root, "INFANTRY")

    def _is_harlequins_infantry(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None or not self._is_harlequins_unit(root):
            return False
        return self._drukhari_has_keyword(root, "INFANTRY")

    def _is_drukhari_or_harlequins_infantry(self, unit: Any) -> bool:
        return self._is_drukhari_infantry(unit) or self._is_harlequins_infantry(unit)

    def _is_drukhari_transport(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None or not self._is_drukhari_unit(root):
            return False
        if not bool(getattr(root, "is_transport", False)):
            if not self._drukhari_has_keyword(root, "TRANSPORT"):
                return False
        return True

    def _is_drukhari_wyches_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        if self._drukhari_has_keyword(root, "WYCHES"):
            return True
        if self._drukhari_has_keyword(root, "WYCH CULT"):
            return True
        name_u = str(getattr(root, "name", "") or "").strip().upper()
        return "WYCH" in name_u

    def _is_drukhari_kabalite_warriors_or_hand_of_the_archon_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        if self._drukhari_has_keyword(root, "KABALITE WARRIORS"):
            return True
        if self._drukhari_has_keyword(root, "HAND OF THE ARCHON"):
            return True
        name_u = str(getattr(root, "name", "") or "").strip().upper()
        if "KABALITE WARRIORS" in name_u:
            return True
        return "HAND OF THE ARCHON" in name_u

    def _is_drukhari_kabalite_warriors_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        if self._drukhari_has_keyword(root, "KABALITE WARRIORS"):
            return True
        name_u = str(getattr(root, "name", "") or "").strip().upper()
        return "KABALITE WARRIORS" in name_u

    def _is_drukhari_wracks_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        if self._drukhari_has_keyword(root, "WRACKS"):
            return True
        name_u = str(getattr(root, "name", "") or "").strip().upper()
        return "WRACKS" in name_u

    def _is_drukhari_battleline_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None or not self._is_drukhari_unit(root):
            return False
        return self._drukhari_has_keyword(root, "BATTLELINE")

    def _is_drukhari_scourges_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        if self._drukhari_has_keyword(root, "SCOURGES"):
            return True
        name_u = str(getattr(root, "name", "") or "").strip().upper()
        return "SCOURGES" in name_u

    def _drukhari_owned_by_player(self, unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(army, "player", None) is player

    @staticmethod
    def _drukhari_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    def _drukhari_on_battlefield(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        if not self._drukhari_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        return True

    def _drukhari_unit_in_candidates(self, root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = self._drukhari_sort_key(root)
        for candidate in list(candidates or []):
            cand_root = self._drukhari_root(candidate)
            if cand_root is None:
                continue
            if cand_root is root:
                return True
            if rid and self._drukhari_sort_key(cand_root) == rid:
                return True
        return False

    @staticmethod
    def _drukhari_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    def _drukhari_reapers_wager_callous_competition_side(self, unit: Any) -> str:
        root = self._drukhari_root(unit)
        if root is None or not self._is_drukhari_reapers_wager():
            return ""
        mgr = self._drukhari_detachment_mgr()
        resolver = getattr(mgr, "_unit_side_for_callous_competition", None) if mgr is not None else None
        if callable(resolver):
            side = str(resolver(root) or "").strip().upper()
            if side:
                return side
        if self._is_harlequins_unit(root):
            return "HARLEQUINS"
        if self._is_drukhari_unit(root):
            return "DRUKHARI"
        return ""

    def _drukhari_reapers_wager_unit_is_losing(self, unit: Any) -> bool:
        side = self._drukhari_reapers_wager_callous_competition_side(unit)
        if not side:
            return False
        mgr = self._drukhari_detachment_mgr()
        checker = getattr(mgr, "callous_competition_side_is_losing", None) if mgr is not None else None
        return bool(checker(side)) if callable(checker) else False

    def _drukhari_normalized_phase_name(self, phase_name: str) -> str:
        return str(phase_name or "").strip().replace("_", " ").lower()

    @staticmethod
    def _drukhari_reapers_wager_malicious_frenzy_choice_key(choice_payload: Any) -> str:
        text = str(choice_payload or "").strip().upper().replace(" ", "_")
        if text == "LETHAL_HITS":
            return "LETHAL_HITS"
        if text in {"SUSTAINED_HITS", "SUSTAINED_HITS_1"}:
            return "SUSTAINED_HITS_1"
        return ""

    @classmethod
    def _drukhari_reapers_wager_malicious_frenzy_choice_label(cls, choice_key: str) -> str:
        choice = cls._drukhari_reapers_wager_malicious_frenzy_choice_key(choice_key)
        if choice == "LETHAL_HITS":
            return "Lethal Hits"
        if choice == "SUSTAINED_HITS_1":
            return "Sustained Hits 1"
        return ""

    def _drukhari_unit_has_weapon_of_attack_type(self, unit: Any, *, attack_type: str) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        if not models:
            models = list(getattr(root, "models", []) or [])
        predicate_name = "is_ranged" if str(attack_type or "").strip().lower() == "ranged" else "is_melee"
        for model in list(models or []):
            if model is None:
                continue
            is_alive_attr = getattr(model, "is_alive", True)
            if not bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                predicate = getattr(wargear, predicate_name, None)
                if callable(predicate) and bool(predicate()):
                    return True
        return False

    def apply_drukhari_reapers_wager_malicious_frenzy(
        self,
        unit: Any,
        *,
        choice_key: str,
        phase_name: str,
        source: str = "MALICIOUS FRENZY",
    ) -> dict:
        root = self._drukhari_root(unit)
        choice = self._drukhari_reapers_wager_malicious_frenzy_choice_key(choice_key)
        phase_key = self._drukhari_normalized_phase_name(phase_name)
        if root is None:
            return {"ok": False, "reason": "Unit not found."}
        if choice not in {"LETHAL_HITS", "SUSTAINED_HITS_1"}:
            return {"ok": False, "reason": "Choice is invalid."}
        if phase_key not in {"shooting phase", "fight phase"}:
            return {"ok": False, "reason": "Phase is invalid."}

        keyword = "LETHAL HITS" if choice == "LETHAL_HITS" else "SUSTAINED HITS 1"
        attack_type = "ranged" if phase_key == "shooting phase" else "melee"
        expires_phase = "SHOOTING_PHASE" if attack_type == "ranged" else "FIGHT_PHASE"
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        if not models:
            models = list(getattr(root, "models", []) or [])

        applied = False
        for model in list(models or []):
            if model is None:
                continue
            is_alive_attr = getattr(model, "is_alive", True)
            if not bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr):
                continue
            model_id = str(get_entity_id(model) or "")
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                attack_check = getattr(wargear, "is_ranged" if attack_type == "ranged" else "is_melee", None)
                if not callable(attack_check) or not bool(attack_check()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=f"drukhari_reapers_wager_malicious_frenzy:{choice}:{attack_type}:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=[keyword],
                        source=str(source or "MALICIOUS FRENZY").strip() or "MALICIOUS FRENZY",
                        expires_phase=expires_phase,
                        attack_type=attack_type,
                    )
                    applied = True
        if not applied:
            return {"ok": False, "reason": "Unit has no eligible weapons for the selected phase."}

        self._drukhari_clear_unit_ability_cache(root)
        return {
            "ok": True,
            "choice_key": choice,
            "choice_name": self._drukhari_reapers_wager_malicious_frenzy_choice_label(choice) or choice,
            "keyword": keyword,
            "attack_type": attack_type,
        }

    def _drukhari_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        effective_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        preview_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(preview_fn):
            preview = preview_fn(stratagem, target_unit=target_unit) or {}
            effective_cost = int(preview.get("cost", effective_cost))
        return bool(
            self.player.spend_command_points(
                effective_cost,
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _drukhari_transport_made_normal_move_this_round(self, transport: Any) -> bool:
        root = self._drukhari_root(transport)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        moved = bool(getattr(round_state, "moved_this_round", False))
        stationary = bool(getattr(round_state, "remained_stationary_this_round", False))
        advanced = bool(getattr(round_state, "advanced_this_round", False))
        fell_back = bool(getattr(round_state, "fell_back_this_round", False))
        return bool(moved and (not stationary) and (not advanced) and (not fell_back))

    def _drukhari_resolve_friendly_transport_for_disembarked_unit(self, unit: Any) -> Any:
        root = self._drukhari_root(unit)
        if root is None:
            return None
        round_state = getattr(root, "round_state", None)
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "")
        if not transport_id:
            return None
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        for unit_entry in list(getattr(army, "units", []) or []):
            candidate = self._drukhari_root(unit_entry)
            if candidate is None:
                continue
            if self._drukhari_sort_key(candidate) != transport_id:
                continue
            if not self._drukhari_owned_by_player(candidate, self.player):
                continue
            return candidate
        return None

    def _drukhari_friendly_transport_candidates(self) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._drukhari_root(unit)
            if root is None:
                continue
            uid = self._drukhari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if not self._is_drukhari_transport(root):
                continue
            out.append(root)
        return sorted(out, key=self._drukhari_sort_key)

    def _drukhari_has_enemy_within_engagement_range(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._drukhari_root(enemy)
            if enemy_root is None:
                continue
            if not self._drukhari_on_battlefield(enemy_root):
                continue
            if bool(is_within(root, enemy_root)):
                return True
        return False

    def _drukhari_distance_between_units(self, source_unit: Any, target_unit: Any) -> Optional[float]:
        game_map = getattr(getattr(self, "game", None), "map", None)
        get_dist = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
        if not callable(get_dist):
            return None
        source_root = self._drukhari_root(source_unit)
        target_root = self._drukhari_root(target_unit)
        if source_root is None or target_root is None:
            return None
        try:
            return float(get_dist(source_root, target_root))
        except (TypeError, ValueError):
            return None

    def _drukhari_skysplinter_swooping_mockery_candidates(self, *, enemy_unit: Any, action: str = "") -> list[Any]:
        if not self._is_drukhari_skysplinter_assault():
            return []
        action_key = str(action or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back"}:
            return []
        enemy_root = self._drukhari_root(enemy_unit)
        if enemy_root is None:
            return []
        if self._drukhari_owned_by_player(enemy_root, self.player):
            return []
        if not self._drukhari_on_battlefield(enemy_root):
            return []
        out: list[Any] = []
        for root in self._drukhari_friendly_transport_candidates():
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            dist = self._drukhari_distance_between_units(root, enemy_root)
            if dist is None or float(dist) > 9.0 + 1e-6:
                continue
            out.append(root)
        return sorted(out, key=self._drukhari_sort_key)

    def _drukhari_resolve_unit_by_entity_id(self, entity_id: str) -> Any:
        uid = str(entity_id or "").strip()
        if not uid:
            return None
        game = getattr(self, "game", None)
        registry = getattr(game, "entity_registry", None) if game is not None else None
        if registry is not None:
            resolved = registry.get(uid, kind="unit")
            if resolved is not None:
                return self._drukhari_root(resolved)
            rebuild = getattr(game, "rebuild_entity_registry", None) if game is not None else None
            if callable(rebuild):
                rebuild()
                resolved = registry.get(uid, kind="unit")
                if resolved is not None:
                    return self._drukhari_root(resolved)
        for player in list(getattr(game, "players", []) or []):
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                root = self._drukhari_root(unit)
                if root is None:
                    continue
                if self._drukhari_sort_key(root) == uid:
                    return root
        return None

    def _drukhari_resolve_model_by_entity_id(self, entity_id: str) -> Any:
        uid = str(entity_id or "").strip()
        if not uid:
            return None
        game = getattr(self, "game", None)
        registry = getattr(game, "entity_registry", None) if game is not None else None
        if registry is not None:
            resolved = registry.get(uid, kind="model")
            if resolved is not None:
                return resolved
            rebuild = getattr(game, "rebuild_entity_registry", None) if game is not None else None
            if callable(rebuild):
                rebuild()
                resolved = registry.get(uid, kind="model")
                if resolved is not None:
                    return resolved
        for player in list(getattr(game, "players", []) or []):
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                for model in list(getattr(unit, "models", []) or []):
                    if self._drukhari_sort_key(model) == uid:
                        return model
                for model in list(getattr(unit, "models_lost", []) or []):
                    if self._drukhari_sort_key(model) == uid:
                        return model
        return None

    @staticmethod
    def _drukhari_phase_key_from_name(phase_name: str) -> str:
        return str(phase_name or "").strip().upper().replace(" ", "_")

    def _drukhari_resolve_selected_units(self, **kwargs) -> list[Any]:
        selected: list[Any] = []
        seen: set[str] = set()
        raw_values = []
        for key in ("units", "target_units", "selected_units", "candidates"):
            values = kwargs.get(key)
            if isinstance(values, list):
                raw_values.extend(list(values))
                break
        if not raw_values:
            for key in ("unit", "target_unit"):
                value = kwargs.get(key)
                if value is not None:
                    raw_values.append(value)
                    break
        if not raw_values:
            for key in ("unit_ids", "target_unit_ids", "selected_unit_ids"):
                values = kwargs.get(key)
                if not isinstance(values, list):
                    continue
                for unit_id in list(values or []):
                    resolved = self._drukhari_resolve_unit_by_entity_id(str(unit_id or ""))
                    if resolved is not None:
                        raw_values.append(resolved)
                if raw_values:
                    break
        for value in list(raw_values or []):
            root = self._drukhari_root(value)
            if root is None:
                continue
            unit_id = self._drukhari_sort_key(root)
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            selected.append(root)
        return list(selected)

    def _drukhari_validate_multi_unit_selection(
        self,
        selected_units: list[Any],
        *,
        candidates: list[Any],
        max_units: int,
        dual_unit_filter,
    ) -> tuple[list[Any], str]:
        roots = [self._drukhari_root(unit) for unit in list(selected_units or []) if self._drukhari_root(unit) is not None]
        roots = list(dict.fromkeys(roots))
        if not roots:
            return [], "no units selected"
        if len(roots) > int(max_units):
            return [], "too many units selected"
        if candidates and any(not self._drukhari_unit_in_candidates(root, candidates) for root in list(roots or [])):
            return [], "selected unit is not currently eligible"
        if len(roots) > 1 and callable(dual_unit_filter):
            if not all(bool(dual_unit_filter(root)) for root in list(roots or [])):
                return [], "multi-unit selection is not currently eligible"
        return roots, ""

    def _drukhari_power_from_pain_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "power_from_pain", None) if army is not None else None

    def _drukhari_can_spend_pain_tokens(self, amount: int = 1) -> bool:
        mgr = self._drukhari_power_from_pain_mgr()
        if mgr is None:
            return False
        try:
            needed = int(amount or 0)
        except (TypeError, ValueError):
            needed = 0
        if needed <= 0:
            return True
        return int(getattr(mgr, "tokens", 0) or 0) >= needed

    def _drukhari_spend_pain_tokens(self, amount: int, *, reason: str = "") -> bool:
        mgr = self._drukhari_power_from_pain_mgr()
        if mgr is None:
            return False
        spend = getattr(mgr, "spend_tokens", None)
        if not callable(spend):
            return False
        try:
            needed = int(amount or 0)
        except (TypeError, ValueError):
            needed = 0
        if needed <= 0:
            return True
        return bool(spend(int(needed), reason=reason))

    def _drukhari_gain_pain_tokens(self, amount: int, *, reason: str = "") -> int:
        mgr = self._drukhari_power_from_pain_mgr()
        gain = getattr(mgr, "gain_tokens", None) if mgr is not None else None
        if not callable(gain):
            return 0
        try:
            count = int(amount or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            return 0
        try:
            return int(gain(int(count), reason=reason) or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _drukhari_model_has_keyword(model: Any, keyword: str) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(keyword)):
            return True
        has_kw = getattr(model, "has_keyword", None)
        if callable(has_kw) and bool(has_kw(keyword)):
            return True
        return False

    def _drukhari_is_battle_shocked(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        check = getattr(root, "is_battle_shocked", None)
        if callable(check):
            try:
                return bool(check())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(getattr(root, "battle_shocked", False))

    def _drukhari_is_haemonculus_covens_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None:
            return False
        detachment_mgr = self._drukhari_detachment_mgr()
        checker = getattr(detachment_mgr, "_unit_is_haemonculus_covens", None) if detachment_mgr is not None else None
        if callable(checker):
            try:
                if bool(checker(root)):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        if self._drukhari_has_keyword(root, "HAEMONCULUS COVENS"):
            return True
        name_u = str(getattr(root, "name", "") or "").strip().upper()
        return "HAEMONCULUS" in name_u or "WRACK" in name_u or "TALOS" in name_u or "CRONOS" in name_u

    def _drukhari_is_haemonculus_model(self, model: Any) -> bool:
        if model is None:
            return False
        if self._drukhari_model_has_keyword(model, "HAEMONCULUS"):
            return True
        unit = getattr(model, "parent_unit", None)
        root = self._drukhari_root(unit)
        if self._drukhari_has_keyword(root, "HAEMONCULUS"):
            return True
        model_name = str(getattr(model, "name", "") or "").strip().upper()
        if "HAEMONCULUS" in model_name:
            return True
        root_name = str(getattr(root, "name", "") or "").strip().upper()
        return "HAEMONCULUS" in root_name

    def _drukhari_visible_enemy_units_within_range(
        self,
        source_unit: Any,
        range_inches: float,
        *,
        exclude_keywords_any: list[str] | tuple[str, ...] | None = None,
    ) -> list[Any]:
        source_root = self._drukhari_root(source_unit)
        if source_root is None or not self._drukhari_on_battlefield(source_root):
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        get_enemy = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy):
            return []
        can_see = getattr(game, "_model_can_see_unit", None)
        try:
            distance_limit = float(range_inches)
        except (TypeError, ValueError):
            distance_limit = 0.0
        excluded = {
            str(value or "").strip().upper()
            for value in list(exclude_keywords_any or [])
            if str(value or "").strip()
        }
        source_models = list(getattr(source_root, "get_attached_unit_models", lambda: [])() or [])
        out: list[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy(source_root) or []):
            enemy_root = self._drukhari_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._drukhari_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if not self._drukhari_on_battlefield(enemy_root):
                continue
            if excluded and any(self._drukhari_has_keyword(enemy_root, keyword) for keyword in excluded):
                continue
            dist = self._drukhari_distance_between_units(source_root, enemy_root)
            if dist is None or float(dist) > distance_limit + 1e-6:
                continue
            if callable(can_see):
                visible = False
                for model in list(source_models or []):
                    alive = getattr(model, "is_alive", False)
                    model_alive = bool(alive() if callable(alive) else alive)
                    if not model_alive:
                        continue
                    try:
                        if bool(can_see(model, enemy_root, game_map=game_map)):
                            visible = True
                            break
                    except (AttributeError, TypeError, ValueError):
                        continue
                if not visible:
                    continue
            out.append(enemy_root)
        return sorted(out, key=self._drukhari_sort_key)

    def _drukhari_covenite_selected_shooting_targets_by_attacker(self) -> dict[str, list[str]]:
        snapshots = getattr(self, "_drukhari_covenite_selected_shooting_targets", None)
        if not isinstance(snapshots, dict):
            snapshots = {}
            self._drukhari_covenite_selected_shooting_targets = snapshots
        return snapshots

    def _drukhari_connoisseurs_of_pain_pending_refunds(self) -> list[dict[str, Any]]:
        pending = getattr(self, "_drukhari_connoisseurs_of_pain_pending_refunds_store", None)
        if not isinstance(pending, list):
            pending = []
            self._drukhari_connoisseurs_of_pain_pending_refunds_store = pending
        return pending

    def _drukhari_postmortality_pending_returns(self) -> list[dict[str, Any]]:
        pending = getattr(self, "_drukhari_postmortality_pending_returns_store", None)
        if not isinstance(pending, list):
            pending = []
            self._drukhari_postmortality_pending_returns_store = pending
        return pending

    def _drukhari_postmortality_used_model_ids(self) -> set[str]:
        used = getattr(self, "_drukhari_postmortality_used_model_id_set", None)
        if not isinstance(used, set):
            used = set()
            self._drukhari_postmortality_used_model_id_set = used
        return used

    def _drukhari_postmortality_model_eligible(self, *, unit: Any, model: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None or model is None:
            return False
        if not self._drukhari_is_haemonculus_model(model):
            return False
        alive_attr = getattr(model, "is_alive", None)
        model_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if model_alive:
            return False
        return True

    def _drukhari_covenite_distillers_candidates(self) -> list[Any]:
        if not self._is_drukhari_covenite_coterie():
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        friendly_units = getattr(self, "_tool_action_friendly_units", lambda: [])()
        for unit in list(friendly_units or []):
            root = self._drukhari_root(unit)
            if root is None:
                continue
            unit_id = self._drukhari_sort_key(root)
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._drukhari_is_haemonculus_covens_unit(root):
                continue
            if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._drukhari_sort_key)

    def _drukhari_tool_action_context(
        self,
        name_u: str,
        *,
        phase_name: str,
        is_active_turn: bool,
    ) -> dict[str, Any] | None:
        name_key = str(name_u or "").strip().upper()
        phase_key = str(phase_name or "").strip().lower()
        if name_key == "DISTILLERS OF FEAR":
            if phase_key != "fight phase" or not bool(is_active_turn):
                return {"candidates": []}
            return {"candidates": self._drukhari_covenite_distillers_candidates()}
        if name_key in {
            "CONNOISSEURS OF PAIN",
            "ENFOLDING NIGHTMARE",
            "POISONER'S ART",
            "POSTMORTALITY",
            "SYMPHONY OF SUFFERING",
        }:
            return {"candidates": []}
        return None

    def _drukhari_can_use_tool_action(self, name_u: str, kwargs: dict[str, Any]) -> bool | None:
        name_key = str(name_u or "").strip().upper()
        if name_key not in {
            "CONNOISSEURS OF PAIN",
            "DISTILLERS OF FEAR",
            "ENFOLDING NIGHTMARE",
            "POISONER'S ART",
            "POSTMORTALITY",
            "SYMPHONY OF SUFFERING",
        }:
            return None
        if not self._is_drukhari_covenite_coterie():
            return False

        context = dict(kwargs or {})
        unit = context.get("unit") or context.get("target_unit") or context.get("destroyed_unit")
        root = self._drukhari_root(unit)
        phase_key = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        candidates = list(context.get("candidates") or [])
        if name_key == "DISTILLERS OF FEAR":
            if phase_key != "fight phase":
                return False
            if root is None:
                return bool(candidates)
            if candidates and not self._drukhari_unit_in_candidates(root, candidates):
                return False
            if not self._drukhari_owned_by_player(root, self.player):
                return False
            if not self._drukhari_on_battlefield(root):
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                return False
            if not self._drukhari_is_haemonculus_covens_unit(root):
                return False
            return not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False))

        if name_key == "POSTMORTALITY":
            model = context.get("model") or context.get("target_model") or context.get("destroyed_model")
            if root is None or model is None:
                return False
            if not self._drukhari_owned_by_player(root, self.player):
                return False
            if not self._drukhari_postmortality_model_eligible(unit=root, model=model):
                return False
            model_id = self._drukhari_sort_key(model)
            if model_id and model_id in self._drukhari_postmortality_used_model_ids():
                return False
            return self._drukhari_can_spend_pain_tokens(1)

        if root is None:
            return False
        if name_key in {"POISONER'S ART", "SYMPHONY OF SUFFERING", "DISTILLERS OF FEAR"} and phase_key != "fight phase":
            return False
        if name_key in {"CONNOISSEURS OF PAIN", "ENFOLDING NIGHTMARE"}:
            if name_key == "ENFOLDING NIGHTMARE" and phase_key != "shooting phase":
                return False
            if name_key == "CONNOISSEURS OF PAIN" and phase_key not in {"shooting phase", "fight phase"}:
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if phase_key == "shooting phase" and active_player is self.player:
                return False
        if not self._drukhari_owned_by_player(root, self.player):
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False

        if name_key == "CONNOISSEURS OF PAIN":
            attacker = context.get("attacking_unit") or context.get("attacker_unit") or context.get("enemy_unit")
            attacker_root = self._drukhari_root(attacker)
            if attacker_root is None or self._drukhari_owned_by_player(attacker_root, self.player):
                return False
            if not self._is_drukhari_unit(root):
                return False
            return self._drukhari_can_spend_pain_tokens(1)

        if name_key == "ENFOLDING NIGHTMARE":
            attacker = context.get("attacking_unit") or context.get("attacker_unit") or context.get("enemy_unit")
            attacker_root = self._drukhari_root(attacker)
            if attacker_root is None or self._drukhari_owned_by_player(attacker_root, self.player):
                return False
            return self._drukhari_is_haemonculus_covens_unit(root)

        if name_key == "POISONER'S ART":
            if not self._drukhari_is_haemonculus_covens_unit(root):
                return False
            if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                return False
            enemy = context.get("enemy_unit") or context.get("target_enemy_unit") or context.get("selected_unit") or context.get("poisoned_unit")
            if enemy is None:
                return bool(candidates)
            enemy_root = self._drukhari_root(enemy)
            if enemy_root is None or self._drukhari_owned_by_player(enemy_root, self.player):
                return False
            if candidates and not self._drukhari_unit_in_candidates(enemy_root, candidates):
                return False
            if not self._drukhari_on_battlefield(enemy_root):
                return False
            return not self._drukhari_has_keyword(enemy_root, "VEHICLE")

        if name_key == "SYMPHONY OF SUFFERING":
            return self._is_drukhari_unit(root)
        return None

    def _build_drukhari_tool_action_specs_for_item(
        self,
        *,
        item: dict[str, Any],
        stratagem: Any,
        base_ctx: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        name_key = str(getattr(stratagem, "name", "") or item.get("name", "") or "").strip().upper()
        if name_key not in {
            "CONNOISSEURS OF PAIN",
            "DISTILLERS OF FEAR",
            "ENFOLDING NIGHTMARE",
            "POISONER'S ART",
            "POSTMORTALITY",
            "SYMPHONY OF SUFFERING",
        }:
            return None

        context = dict(item.get("context", {}) or {})
        specs: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_probe(kwargs: dict[str, Any], label_suffix: str = "") -> None:
            self._tool_action_add_probe(
                specs=specs,
                seen=seen,
                stratagem=stratagem,
                item=item,
                kwargs=kwargs,
                label_suffix=label_suffix,
            )

        phase_name = str(base_ctx.get("phase_name") or context.get("phase_name") or getattr(self, "_current_phase_name", "") or "")
        common_ctx = {**base_ctx, "phase_name": phase_name}
        unit = context.get("unit") or context.get("target_unit") or context.get("destroyed_unit")
        root = self._drukhari_root(unit)

        if name_key == "DISTILLERS OF FEAR":
            candidates = list(context.get("candidates") or [])
            if root is not None:
                candidates = [root]
            elif not candidates:
                candidates = self._drukhari_covenite_distillers_candidates()
            for candidate in sorted((self._drukhari_root(unit) for unit in candidates), key=self._drukhari_sort_key):
                if candidate is None:
                    continue
                add_probe(
                    {
                        **common_ctx,
                        "unit": candidate,
                        "target_unit": candidate,
                    },
                    self._tool_action_label_value(candidate),
                )
            return specs

        if name_key == "POSTMORTALITY":
            model = context.get("model") or context.get("target_model") or context.get("destroyed_model")
            if root is None or model is None:
                return []
            add_probe(
                {
                    **common_ctx,
                    "unit": root,
                    "target_unit": root,
                    "destroyed_unit": root,
                    "model": model,
                    "target_model": model,
                    "destroyed_model": model,
                    "destroyed_position": context.get("destroyed_position"),
                },
                f"{self._tool_action_label_value(root)} -> {self._tool_action_label_value(model)}",
            )
            return specs

        if root is None:
            return []

        if name_key in {"CONNOISSEURS OF PAIN", "ENFOLDING NIGHTMARE"}:
            attacker = (
                context.get("attacking_unit")
                or context.get("attacker_unit")
                or context.get("enemy_unit")
                or context.get("target_enemy_unit")
            )
            attacker_root = self._drukhari_root(attacker)
            if attacker_root is None:
                return []
            add_probe(
                {
                    **common_ctx,
                    "unit": root,
                    "target_unit": root,
                    "attacking_unit": attacker_root,
                    "attacker_unit": attacker_root,
                    "enemy_unit": attacker_root,
                    "target_enemy_unit": attacker_root,
                },
                f"{self._tool_action_label_value(root)} vs {self._tool_action_label_value(attacker_root)}",
            )
            return specs

        if name_key == "POISONER'S ART":
            candidates = list(context.get("candidates") or context.get("enemy_candidates") or [])
            enemies = sorted((self._drukhari_root(enemy) for enemy in candidates), key=self._drukhari_sort_key)
            for enemy_root in enemies:
                if enemy_root is None:
                    continue
                add_probe(
                    {
                        **common_ctx,
                        "unit": root,
                        "target_unit": root,
                        "enemy_unit": enemy_root,
                        "target_enemy_unit": enemy_root,
                    },
                    f"{self._tool_action_label_value(root)} vs {self._tool_action_label_value(enemy_root)}",
                )
            return specs

        if name_key == "SYMPHONY OF SUFFERING":
            add_probe(
                {
                    **common_ctx,
                    "unit": root,
                    "target_unit": root,
                },
                self._tool_action_label_value(root),
            )
            return specs
        return None

    def _drukhari_vicious_blades_roll_modifiers(self, transport_unit: Any) -> list[int]:
        transport_root = self._drukhari_root(transport_unit)
        if transport_root is None:
            return []
        passengers = list(getattr(transport_root, "transport_passengers", []) or [])
        ordered_passengers = sorted(
            [self._drukhari_root(passenger) for passenger in passengers if passenger is not None],
            key=self._drukhari_sort_key,
        )
        roll_modifiers: list[int] = []
        for passenger_root in ordered_passengers:
            if passenger_root is None or not self._drukhari_is_alive(passenger_root):
                continue
            is_wracks = self._drukhari_has_keyword(passenger_root, "WRACKS")
            if not is_wracks:
                name_u = str(getattr(passenger_root, "name", "") or "").strip().upper()
                is_wracks = "WRACKS" in name_u
            get_models = getattr(passenger_root, "get_attached_unit_models", None)
            models = list(get_models() or []) if callable(get_models) else list(getattr(passenger_root, "models", []) or [])
            models = sorted([model for model in models if model is not None], key=self._drukhari_sort_key)
            for model in models:
                is_alive_attr = getattr(model, "is_alive", None)
                model_alive = bool(is_alive_attr()) if callable(is_alive_attr) else bool(is_alive_attr)
                if not model_alive:
                    continue
                roll_modifiers.append(1 if is_wracks else 0)
        return roll_modifiers

    def _drukhari_skysplinter_skyborne_annihilation_candidates(self) -> list[Any]:
        if not self._is_drukhari_skysplinter_assault():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._drukhari_root(unit)
            if root is None:
                continue
            uid = self._drukhari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_drukhari_unit(root):
                continue
            round_state = getattr(root, "round_state", None)
            if not bool(getattr(round_state, "disembarked_this_round", False)):
                continue
            if bool(getattr(round_state, "shot_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._drukhari_sort_key)

    def _drukhari_friendly_battlefield_units(self) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._drukhari_root(unit)
            if root is None:
                continue
            uid = self._drukhari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            out.append(root)
        return sorted(out, key=self._drukhari_sort_key)

    def _is_drukhari_kabal_or_blades_for_hire_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None or not self._is_drukhari_unit(root):
            return False
        return bool(
            self._drukhari_has_keyword(root, "KABAL")
            or self._drukhari_has_keyword(root, "BLADES FOR HIRE")
        )

    def _is_drukhari_non_vehicle_unit(self, unit: Any) -> bool:
        root = self._drukhari_root(unit)
        if root is None or not self._is_drukhari_unit(root):
            return False
        return not bool(self._drukhari_has_keyword(root, "VEHICLE"))

    def _drukhari_kabalite_phase_candidates(
        self,
        *,
        unit_filter,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> list[Any]:
        if not self._is_drukhari_kabalite_cartel():
            return []
        out: list[Any] = []
        for root in self._drukhari_friendly_battlefield_units():
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if callable(unit_filter) and not bool(unit_filter(root)):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and (
                bool(getattr(round_state, "fought_this_phase", False))
                or bool(getattr(round_state, "fought_this_round", False))
            ):
                continue
            out.append(root)
        return sorted(out, key=self._drukhari_sort_key)

    def _drukhari_kabalite_archon_warlord(self) -> Any:
        mgr = self._drukhari_detachment_mgr()
        getter = getattr(mgr, "kabalite_archon_warlord", None) if mgr is not None else None
        if not callable(getter):
            return None
        try:
            return self._drukhari_root(getter(game=getattr(self, "game", None)))
        except (AttributeError, TypeError, ValueError):
            return None

    def _drukhari_kabalite_contract_target_root(self) -> Any:
        mgr = self._drukhari_detachment_mgr()
        if mgr is None:
            return None
        if not bool(getattr(mgr, "_murderous_agenda_has_selection", lambda: False)()):
            return None
        if bool(getattr(mgr, "murderous_agenda_contract_completed", False)):
            return None
        target_id = str(getattr(mgr, "murderous_agenda_contract_target_unit_id", "") or "").strip()
        if not target_id:
            return None
        resolver = getattr(mgr, "_resolve_unit_by_id", None)
        if not callable(resolver):
            return None
        try:
            resolved = resolver(target_id, game=getattr(self, "game", None))
        except (AttributeError, TypeError, ValueError):
            return None
        root = self._drukhari_root(resolved)
        if root is None or not self._drukhari_on_battlefield(root):
            return None
        return root

    def _drukhari_kabalite_making_a_point_candidates(self) -> list[Any]:
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name != "shooting phase" or active_player is not self.player:
            return []
        return self._drukhari_kabalite_phase_candidates(
            unit_filter=self._is_drukhari_kabalite_warriors_or_hand_of_the_archon_unit,
            require_not_shot=True,
        )

    def _drukhari_kabalite_tailored_toxins_candidates(self) -> list[Any]:
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if self._drukhari_kabalite_contract_target_root() is None:
            return []
        if phase_name == "shooting phase":
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                return []
            return self._drukhari_kabalite_phase_candidates(
                unit_filter=self._is_drukhari_kabal_or_blades_for_hire_unit,
                require_not_shot=True,
            )
        if phase_name == "fight phase":
            return self._drukhari_kabalite_phase_candidates(
                unit_filter=self._is_drukhari_kabal_or_blades_for_hire_unit,
                require_not_fought=True,
            )
        return []

    def _drukhari_kabalite_taken_alive_candidates(self) -> list[Any]:
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            return []
        return self._drukhari_kabalite_phase_candidates(
            unit_filter=self._is_drukhari_unit,
            require_not_fought=True,
        )

    def _drukhari_kabalite_enemies_without_number_candidates(self) -> list[Any]:
        if not self._is_drukhari_kabalite_cartel():
            return []
        mgr = self._drukhari_detachment_mgr()
        checker = getattr(mgr, "murderous_agenda_reselect_window_active", None) if mgr is not None else None
        if not callable(checker):
            return []
        if not bool(checker(game=getattr(self, "game", None), player=self.player)):
            return []
        warlord = self._drukhari_kabalite_archon_warlord()
        if warlord is None or bool(self._unit_cannot_be_target_of_stratagem(warlord)):
            return []
        return [warlord]

    def _drukhari_kabalite_deadly_deceivers_candidates(self, *, target_units: list[Any]) -> list[Any]:
        out: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._drukhari_root(target)
            if root is None:
                continue
            uid = self._drukhari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_drukhari_kabal_or_blades_for_hire_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._drukhari_sort_key)

    def _drukhari_kabalite_double_cross_candidate_map(
        self,
        *,
        protected_units: list[Any],
    ) -> dict[str, list[Any]]:
        support_pool = self._drukhari_kabalite_phase_candidates(
            unit_filter=self._is_drukhari_non_vehicle_unit,
        )
        out: dict[str, list[Any]] = {}
        for protected in list(protected_units or []):
            protected_root = self._drukhari_root(protected)
            if protected_root is None:
                continue
            uid = self._drukhari_sort_key(protected_root)
            if not uid:
                continue
            out[uid] = list(support_pool)
        return out

    def _drukhari_realspace_phase_candidates(
        self,
        *,
        unit_filter,
        require_not_selected_to_move: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_not_engaged: bool = False,
    ) -> list[Any]:
        if not self._is_drukhari_realspace_raiders():
            return []
        out: list[Any] = []
        for root in self._drukhari_friendly_battlefield_units():
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if callable(unit_filter) and not bool(unit_filter(root)):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_selected_to_move and self._drukhari_selected_to_move_this_phase(root):
                continue
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_not_engaged and self._drukhari_has_enemy_within_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._drukhari_sort_key)

    def _drukhari_realspace_instinctive_spite_candidates(self) -> list[Any]:
        phase_name = self._drukhari_normalized_phase_name(getattr(self, "_current_phase_name", "") or "")
        if phase_name == "shooting phase":
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                return []
            return self._drukhari_realspace_phase_candidates(
                unit_filter=self._is_drukhari_unit,
                require_not_shot=True,
            )
        if phase_name == "fight phase":
            return self._drukhari_realspace_phase_candidates(
                unit_filter=self._is_drukhari_unit,
                require_not_fought=True,
            )
        return []

    def _drukhari_realspace_dark_harvest_candidates(self) -> list[Any]:
        phase_name = self._drukhari_normalized_phase_name(getattr(self, "_current_phase_name", "") or "")
        if phase_name != "fight phase":
            return []
        return self._drukhari_realspace_phase_candidates(
            unit_filter=self._is_drukhari_unit,
            require_not_fought=True,
        )

    def _drukhari_realspace_eager_for_the_kill_candidates(self) -> list[Any]:
        phase_name = self._drukhari_normalized_phase_name(getattr(self, "_current_phase_name", "") or "")
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name != "movement phase" or active_player is not self.player:
            return []
        return self._drukhari_realspace_phase_candidates(
            unit_filter=self._is_drukhari_unit,
            require_not_selected_to_move=True,
        )

    def _drukhari_realspace_raid_and_fade_candidates(self) -> list[Any]:
        phase_name = self._drukhari_normalized_phase_name(getattr(self, "_current_phase_name", "") or "")
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name != "shooting phase" or active_player is not self.player:
            return []
        return self._drukhari_realspace_phase_candidates(
            unit_filter=lambda unit: (
                self._is_drukhari_unit(unit)
                and not self._is_drukhari_scourges_unit(unit)
                and not self._drukhari_has_keyword(unit, "AIRCRAFT")
            ),
            require_not_engaged=True,
        )

    def _drukhari_realspace_fighting_shadows_candidates(self, *, target_units: list[Any]) -> list[Any]:
        out: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._drukhari_root(target)
            if root is None:
                continue
            unit_id = self._drukhari_sort_key(root)
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_drukhari_unit(root):
                continue
            if self._drukhari_is_haemonculus_covens_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._drukhari_sort_key)

    def _queue_drukhari_kabalite_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_drukhari_kabalite_cartel():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "COMMAND_PHASE":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player or player is not self.player:
            return
        candidates = self._drukhari_kabalite_enemies_without_number_candidates()
        if not candidates:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("ENEMIES WITHOUT NUMBER")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_start":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != "command phase":
                continue
            return
        payload = {
            "event": "phase_start",
            "phase": "Command phase",
            "phase_name": "Command phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
            "unit": candidates[0],
            "target_unit": candidates[0],
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_kabalite_deadly_deceivers_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_drukhari_kabalite_cartel():
            return
        attacker_root = self._drukhari_root(attacking_unit)
        if attacker_root is None:
            return
        candidates = self._drukhari_kabalite_deadly_deceivers_candidates(target_units=list(target_units or []))
        if not candidates:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("DEADLY DECEIVERS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        attacker_id = self._drukhari_sort_key(attacker_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "shooting_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            reaction_attacker = self._drukhari_root(reaction.get("attacking_unit") or reaction.get("enemy_unit"))
            if attacker_id and self._drukhari_sort_key(reaction_attacker) == attacker_id:
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "phase": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_kabalite_double_cross_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_drukhari_kabalite_cartel():
            return
        attacker_root = self._drukhari_root(attacking_unit)
        if attacker_root is None:
            return
        candidates = self._drukhari_kabalite_deadly_deceivers_candidates(target_units=list(target_units or []))
        if not candidates:
            return
        support_by_unit = self._drukhari_kabalite_double_cross_candidate_map(protected_units=candidates)
        if not any(list(value or []) for value in support_by_unit.values()):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("DOUBLE-CROSS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        attacker_id = self._drukhari_sort_key(attacker_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            reaction_attacker = self._drukhari_root(reaction.get("attacking_unit") or reaction.get("enemy_unit"))
            if attacker_id and self._drukhari_sort_key(reaction_attacker) == attacker_id:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "phase": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "candidates": candidates,
            "support_candidates_by_unit": support_by_unit,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_realspace_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_drukhari_realspace_raiders():
            return
        phase_key = self._drukhari_phase_key_from_name(getattr(phase, "name", "") or "")
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        queue_specs: list[tuple[str, list[Any], str]] = []
        if phase_key == "MOVEMENT_PHASE" and active_player is self.player and player is self.player:
            queue_specs.append(("EAGER FOR THE KILL", self._drukhari_realspace_eager_for_the_kill_candidates(), "Movement phase"))
        elif phase_key == "SHOOTING_PHASE" and active_player is self.player and player is self.player:
            queue_specs.append(("INSTINCTIVE SPITE", self._drukhari_realspace_instinctive_spite_candidates(), "Shooting phase"))
        elif phase_key == "FIGHT_PHASE":
            queue_specs.extend(
                [
                    ("INSTINCTIVE SPITE", self._drukhari_realspace_instinctive_spite_candidates(), "Fight phase"),
                    ("DARK HARVEST", self._drukhari_realspace_dark_harvest_candidates(), "Fight phase"),
                ]
            )
        else:
            return

        queue_reaction = getattr(self, "_queue_reaction", None)
        if not callable(queue_reaction):
            return
        for stratagem_name, candidates, phase_name in list(queue_specs or []):
            if not candidates:
                continue
            stratagem = getattr(self, "get_by_name", lambda _name: None)(stratagem_name)
            if stratagem is None:
                continue
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                continue
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                continue
            already_pending = False
            for reaction in list(getattr(self, "_pending_reactions", []) or []):
                if str(reaction.get("event", "") or "") != "phase_start":
                    continue
                if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                    continue
                if str(reaction.get("phase_name", "") or "").strip().lower() != str(phase_name or "").strip().lower():
                    continue
                already_pending = True
                break
            if already_pending:
                continue
            payload = {
                "event": "phase_start",
                "phase": phase_name,
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_realspace_fighting_shadows_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
    ) -> None:
        if not self._is_drukhari_realspace_raiders():
            return
        attacker_root = self._drukhari_root(attacking_unit)
        if attacker_root is None or self._drukhari_owned_by_player(attacker_root, self.player):
            return
        candidates = self._drukhari_realspace_fighting_shadows_candidates(target_units=list(target_units or []))
        if not candidates:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("FIGHTING SHADOWS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        event_name = "shooting_targets_selected" if self._drukhari_normalized_phase_name(phase_name) == "shooting phase" else "fight_targets_selected"
        attacker_id = self._drukhari_sort_key(attacker_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != event_name:
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            reaction_attacker = self._drukhari_root(reaction.get("attacking_unit") or reaction.get("enemy_unit"))
            if attacker_id and self._drukhari_sort_key(reaction_attacker) == attacker_id:
                return
        payload = {
            "event": event_name,
            "phase_name": phase_name,
            "phase": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_realspace_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_drukhari_realspace_raiders():
            return
        phase_key = self._drukhari_phase_key_from_name(getattr(phase, "name", "") or "")
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_key != "SHOOTING_PHASE" or active_player is not self.player or player is not self.player:
            return
        candidates = self._drukhari_realspace_raid_and_fade_candidates()
        if not candidates:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("RAID AND FADE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_end":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != "shooting phase":
                continue
            return
        payload = {
            "event": "phase_end",
            "phase": "Shooting phase",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _resolve_drukhari_kabalite_taken_alive_fight_attacks_resolved(
        self,
        *,
        unit: Any,
        target_unit: Any,
    ) -> None:
        if not self._is_drukhari_kabalite_cartel():
            return
        mgr = self._drukhari_detachment_mgr()
        if mgr is None:
            return
        root = self._drukhari_root(unit)
        if root is None or not self._drukhari_owned_by_player(root, self.player):
            return
        effect_state = getattr(mgr, "_kabalite_effect_state", None)
        if not callable(effect_state):
            return
        prefix = getattr(mgr, "_KABALITE_TAKEN_ALIVE_PREFIX", "")
        effect_root, special_rules, source_name = effect_state(root, prefix=prefix, game=getattr(self, "game", None))
        if effect_root is None or not isinstance(special_rules, dict):
            return
        if bool(special_rules.get(f"{prefix}_battle_shock_triggered", False)):
            return
        contract_target_id = str(
            special_rules.get(f"{prefix}_contract_target_unit_id", "")
            or getattr(mgr, "murderous_agenda_contract_target_unit_id", "")
            or ""
        ).strip()
        if not contract_target_id:
            return
        resolved_target = self._drukhari_root(target_unit)
        if resolved_target is not None and self._drukhari_sort_key(resolved_target) != contract_target_id:
            return
        resolve_target = getattr(mgr, "_resolve_unit_by_id", None)
        if callable(resolve_target):
            try:
                resolved_target = resolve_target(contract_target_id, game=getattr(self, "game", None))
            except (AttributeError, TypeError, ValueError):
                resolved_target = target_unit
        target_destroyed = getattr(mgr, "_murderous_agenda_target_destroyed", None)
        if callable(target_destroyed):
            if not bool(target_destroyed(resolved_target)):
                return
        elif resolved_target is not None and self._drukhari_is_alive(self._drukhari_root(resolved_target)):
            return
        special_rules[f"{prefix}_battle_shock_triggered"] = True
        effect_root.special_rules = special_rules
        self._drukhari_clear_unit_ability_cache(effect_root)

        game = getattr(self, "game", None)
        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        source_label = str(source_name or "Taken Alive").strip() or "Taken Alive"
        get_enemy_units = getattr(game, "get_enemy_units", None) if game is not None else None
        enemy_pool = list(get_enemy_units(self.player) or []) if callable(get_enemy_units) else []
        tested = 0
        seen: set[str] = set()
        for enemy in list(enemy_pool or []):
            enemy_root = self._drukhari_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._drukhari_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if not self._drukhari_on_battlefield(enemy_root):
                continue
            mark_fn = getattr(mgr, "mark_taken_alive_battle_shock", None)
            if callable(mark_fn):
                mark_fn(enemy_root, game=game, source=source_label)
            force_test = getattr(enemy_root, "force_battle_shock_test", None)
            if callable(force_test):
                try:
                    force_test(
                        current_turn=max(1, int(current_turn)),
                        modifier=0,
                        source=source_label,
                    )
                    tested += 1
                    continue
                except (AttributeError, TypeError, ValueError):
                    pass
            take_test = getattr(enemy_root, "take_battle_shock_test", None)
            if callable(take_test):
                try:
                    take_test(max(1, int(current_turn)))
                    tested += 1
                except (AttributeError, TypeError, ValueError):
                    continue
        logger.info(
            "INFO: TAKEN ALIVE: %s forced %d Battle-shock test(s).",
            getattr(root, "name", "Unit"),
            int(tested),
        )

    def _queue_drukhari_skysplinter_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_drukhari_skysplinter_assault():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "SHOOTING_PHASE":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("SKYBORNE ANNIHILATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._drukhari_skysplinter_skyborne_annihilation_candidates()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_start":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != "shooting phase":
                continue
            return
        payload = {
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
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_skysplinter_unit_disembarked_reactions(self, *, unit: Any, transport_unit: Any = None) -> None:
        if unit is None or not self._is_drukhari_skysplinter_assault():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        root = self._drukhari_root(unit)
        if root is None:
            return
        if not self._drukhari_owned_by_player(root, self.player):
            return
        if not self._drukhari_on_battlefield(root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        if not self._is_drukhari_infantry(root):
            return
        round_state = getattr(root, "round_state", None)
        disembarked_this_round = bool(getattr(round_state, "disembarked_this_round", False))
        if not disembarked_this_round and getattr(root, "embarked_in", None) is not None:
            return
        transport_root = self._drukhari_root(transport_unit)
        if transport_root is None:
            transport_root = self._drukhari_resolve_friendly_transport_for_disembarked_unit(root)
        if transport_root is None:
            return
        if not self._is_drukhari_transport(transport_root):
            return
        if not self._drukhari_transport_made_normal_move_this_round(transport_root):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("POUNCE ON THE PREY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_disembarked":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("unit") is root:
                return
        payload = {
            "event": "unit_disembarked",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "transport_unit": transport_root,
            "candidates": [root],
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_skysplinter_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or not self._is_drukhari_skysplinter_assault():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            return
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "fall_back"}:
            return
        enemy_root = self._drukhari_root(unit)
        if enemy_root is None:
            return
        if self._drukhari_owned_by_player(enemy_root, self.player):
            return
        if not self._drukhari_on_battlefield(enemy_root):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("SWOOPING MOCKERY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if self._drukhari_root(reaction.get("enemy_unit")) is enemy_root:
                return

        candidates = self._drukhari_skysplinter_swooping_mockery_candidates(enemy_unit=enemy_root, action=action_key)
        if not candidates:
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "action": action_key,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_skysplinter_vicious_blades_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if attacking_unit is None or not self._is_drukhari_skysplinter_assault():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            return
        transport_root = self._drukhari_root(attacking_unit)
        if transport_root is None:
            return
        if not self._drukhari_owned_by_player(transport_root, self.player):
            return
        if not self._drukhari_on_battlefield(transport_root):
            return
        if not self._is_drukhari_transport(transport_root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(transport_root)):
            return
        enemy_targets: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            target_root = self._drukhari_root(target)
            if target_root is None:
                continue
            uid = self._drukhari_sort_key(target_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if self._drukhari_owned_by_player(target_root, self.player):
                continue
            if not self._drukhari_on_battlefield(target_root):
                continue
            enemy_targets.append(target_root)
        if not enemy_targets:
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("VICIOUS BLADES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if self._drukhari_root(reaction.get("unit")) is transport_root:
                return

        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": transport_root,
            "target_unit": transport_root,
            "enemy_candidates": sorted(enemy_targets, key=self._drukhari_sort_key),
            "candidates": [transport_root],
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _resolve_drukhari_skysplinter_vicious_blades_after_fight(self, *, unit: Any) -> None:
        if unit is None or not self._is_drukhari_skysplinter_assault():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            return
        transport_root = self._drukhari_root(unit)
        if transport_root is None:
            return
        sr = getattr(transport_root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        if not bool(sr.get("drukhari_vicious_blades_pending", False)):
            return
        owner_id = str(sr.get("drukhari_vicious_blades_owner", "") or "")
        if owner_id and owner_id != str(getattr(self.player, "id", "") or ""):
            return
        pending_turn = int(sr.get("drukhari_vicious_blades_turn", 0) or 0)
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if pending_turn and current_turn and pending_turn != current_turn:
            sr.pop("drukhari_vicious_blades_pending", None)
            sr.pop("drukhari_vicious_blades_owner", None)
            sr.pop("drukhari_vicious_blades_turn", None)
            sr.pop("drukhari_vicious_blades_source", None)
            sr.pop("drukhari_vicious_blades_target_ids", None)
            sr.pop("drukhari_vicious_blades_selected_target_id", None)
            transport_root.special_rules = sr
            return

        selected_id = str(sr.get("drukhari_vicious_blades_selected_target_id", "") or "")
        target_ids = [
            str(value or "").strip()
            for value in list(sr.get("drukhari_vicious_blades_target_ids", []) or [])
            if str(value or "").strip()
        ]
        candidate_ids: list[str] = []
        if selected_id:
            candidate_ids.append(selected_id)
        for tid in target_ids:
            if tid not in candidate_ids:
                candidate_ids.append(tid)

        target_root = None
        for tid in candidate_ids:
            resolved = self._drukhari_resolve_unit_by_entity_id(tid)
            if resolved is None:
                continue
            if self._drukhari_owned_by_player(resolved, self.player):
                continue
            if not self._drukhari_on_battlefield(resolved):
                continue
            target_root = resolved
            break

        if target_root is not None:
            roll_modifiers = self._drukhari_vicious_blades_roll_modifiers(transport_root)
            successes = 0
            rolls: list[int] = []
            if roll_modifiers:
                for modifier in roll_modifiers:
                    roll = dice_module.get_roll("D6")
                    final_value = int(roll + int(modifier))
                    rolls.append(final_value)
                    if final_value >= 5:
                        successes += 1
                mortal_wounds = min(6, int(successes))
                if mortal_wounds > 0:
                    transport_root._apply_mortal_wounds_to_unit(
                        target_root,
                        int(mortal_wounds),
                        game_map=getattr(self.game, "map", None),
                        attacker_unit=transport_root,
                    )
                logger.info(
                    "INFO: VICIOUS BLADES: %s resolves %d embarked-model roll(s) into %d mortal wound(s) on %s.",
                    getattr(transport_root, "name", "Transport"),
                    int(len(roll_modifiers)),
                    int(mortal_wounds),
                    getattr(target_root, "name", "Unit"),
                )
            else:
                logger.info(
                    "INFO: VICIOUS BLADES: %s has no embarked models; no mortal wounds dealt.",
                    getattr(transport_root, "name", "Transport"),
                )

        sr.pop("drukhari_vicious_blades_pending", None)
        sr.pop("drukhari_vicious_blades_owner", None)
        sr.pop("drukhari_vicious_blades_turn", None)
        sr.pop("drukhari_vicious_blades_source", None)
        sr.pop("drukhari_vicious_blades_target_ids", None)
        sr.pop("drukhari_vicious_blades_selected_target_id", None)
        transport_root.special_rules = sr

    def _queue_drukhari_skysplinter_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_drukhari_skysplinter_assault():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("WRAITHLIKE RETREAT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._drukhari_root(unit)
            if root is None:
                continue
            uid = self._drukhari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_drukhari_infantry(root):
                continue
            if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._drukhari_sort_key)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_end":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != "fight phase":
                continue
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
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_reapers_wager_scintillating_tempo_reactions(
        self,
        *,
        unit: Any,
        trigger: str,
        action: str = "",
    ) -> None:
        if unit is None or not self._is_drukhari_reapers_wager():
            return
        phase_raw = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_raw not in {"movement phase", "charge phase"}:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return

        root = self._drukhari_root(unit)
        if root is None:
            return
        if not self._drukhari_owned_by_player(root, self.player):
            return
        if not self._drukhari_on_battlefield(root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        if not self._is_drukhari_or_harlequins_unit(root):
            return

        action_norm = str(action or "").strip().lower()
        if str(trigger or "").strip().lower() == "move_started":
            if action_norm not in {"move", "normal", "normal_move", "advance", "fall_back", "fallback"}:
                return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("SCINTILLATING TEMPO")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("scintillating_tempo_no_overwatch", False)):
            owner = str(sr.get("scintillating_tempo_turn_owner", "") or "")
            turn_mark = int(sr.get("scintillating_tempo_turn", 0) or 0)
            current_owner = str(getattr(self.player, "id", "") or "")
            current_turn = int(getattr(game, "turn", 0) or 0)
            owner_match = not owner or owner == current_owner
            turn_match = not turn_mark or turn_mark == current_turn
            if owner_match and turn_match:
                return

        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "drukhari_reapers_wager_scintillating_tempo":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if self._drukhari_root(reaction.get("unit")) is root:
                return

        payload = {
            "event": "drukhari_reapers_wager_scintillating_tempo",
            "phase_name": "Movement phase" if phase_raw == "movement phase" else "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "trigger": str(trigger or "").strip().lower(),
            "unit": root,
            "target_unit": root,
            "candidates": [root],
        }
        if action_norm:
            payload["action"] = action_norm
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_reapers_wager_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or not self._is_drukhari_reapers_wager():
            return
        phase_name = self._drukhari_normalized_phase_name(getattr(self, "_current_phase_name", "") or "")
        if phase_name != "movement phase":
            return
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "fall_back"}:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        trigger_root = self._drukhari_root(unit)
        if trigger_root is None or not self._drukhari_on_battlefield(trigger_root):
            return

        if self._drukhari_owned_by_player(trigger_root, self.player):
            if active_player is not self.player or action_key != "advance":
                return
            if bool(self._unit_cannot_be_target_of_stratagem(trigger_root)):
                return
            if not self._is_drukhari_or_harlequins_unit(trigger_root):
                return
            stratagem = getattr(self, "get_by_name", lambda _name: None)("SHORTEN THE ODDS")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            sr = getattr(trigger_root, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("drukhari_reapers_wager_shorten_the_odds_active", False)):
                owner = str(sr.get("drukhari_reapers_wager_shorten_the_odds_turn_owner", "") or "")
                turn_mark = int(sr.get("drukhari_reapers_wager_shorten_the_odds_turn", 0) or 0)
                current_owner = str(getattr(self.player, "id", "") or "")
                current_turn = int(getattr(game, "turn", 0) or 0)
                if (not owner or owner == current_owner) and (not turn_mark or turn_mark == current_turn):
                    return
            for reaction in list(getattr(self, "_pending_reactions", []) or []):
                if str(reaction.get("event", "") or "") != "unit_move_ended":
                    continue
                if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                    continue
                if self._drukhari_root(reaction.get("unit")) is trigger_root:
                    return
            payload = {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "phase": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": trigger_root,
                "target_unit": trigger_root,
                "action": action_key,
                "candidates": [trigger_root],
            }
            queue_reaction = getattr(self, "_queue_reaction", None)
            if callable(queue_reaction):
                queue_reaction(payload, use_timer=False)
            return

        if active_player is self.player:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("DANCE MACABRE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if self._drukhari_root(reaction.get("enemy_unit")) is trigger_root:
                return

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for candidate in list(getattr(army, "units", []) or []):
            root = self._drukhari_root(candidate)
            if root is None:
                continue
            unit_id = self._drukhari_sort_key(root)
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_drukhari_or_harlequins_infantry(root):
                continue
            distance = self._drukhari_distance_between_units(root, trigger_root)
            if distance is None or float(distance) > 9.0 + 1e-6:
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._drukhari_sort_key)
        if not candidates:
            return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "phase": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": trigger_root,
            "moving_unit": trigger_root,
            "action": action_key,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_drukhari_reapers_wager_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if attacking_unit is None or not self._is_drukhari_reapers_wager():
            return
        attacker_root = self._drukhari_root(attacking_unit)
        if attacker_root is None or self._drukhari_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("FATEFUL ROLE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._drukhari_root(target)
            if root is None:
                continue
            target_id = self._drukhari_sort_key(root)
            if target_id and target_id in seen:
                continue
            if target_id:
                seen.add(target_id)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_drukhari_or_harlequins_unit(root):
                continue
            candidates.append(root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if self._drukhari_root(reaction.get("enemy_unit")) is attacker_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "phase": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "candidates": sorted(candidates, key=self._drukhari_sort_key),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_drukhari_skysplinter_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "SHOOTING_PHASE":
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._drukhari_root(unit)
            if root is None:
                continue
            uid = self._drukhari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("drukhari_skyborne_annihilation_active")):
                continue
            if bool(sr.get("drukhari_skyborne_annihilation_added_sustained_ranged")):
                prev = int(sr.get("drukhari_skyborne_annihilation_prev_sustained_ranged", 0) or 0)
                if prev > 0:
                    sr["bearer_unit_sustained_hits_value_ranged"] = int(prev)
                else:
                    sr.pop("bearer_unit_sustained_hits_value_ranged", None)
            for key in (
                "drukhari_skyborne_annihilation_active",
                "drukhari_skyborne_annihilation_expires_phase",
                "drukhari_skyborne_annihilation_turn_owner",
                "drukhari_skyborne_annihilation_turn",
                "drukhari_skyborne_annihilation_source",
                "drukhari_skyborne_annihilation_sustained_hits_value",
                "drukhari_skyborne_annihilation_prev_sustained_ranged",
                "drukhari_skyborne_annihilation_added_sustained_ranged",
            ):
                sr.pop(key, None)
            root.special_rules = sr

    def _queue_drukhari_covenite_connoisseurs_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_drukhari_covenite_coterie():
            return
        attacker_root = self._drukhari_root(attacking_unit)
        if attacker_root is None or self._drukhari_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("CONNOISSEURS OF PAIN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if not self._drukhari_can_spend_pain_tokens(1):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates: list[Any] = []
        selected_target_ids: list[str] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._drukhari_root(target)
            if root is None:
                continue
            target_id = self._drukhari_sort_key(root)
            if target_id and target_id in seen:
                continue
            if target_id:
                seen.add(target_id)
                selected_target_ids.append(target_id)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_drukhari_unit(root):
                continue
            candidates.append(root)
        attacker_id = self._drukhari_sort_key(attacker_root)
        if attacker_id:
            self._drukhari_covenite_selected_shooting_targets_by_attacker()[attacker_id] = list(selected_target_ids)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "shooting_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "CONNOISSEURS OF PAIN":
                continue
            if self._drukhari_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "candidates": sorted(candidates, key=self._drukhari_sort_key),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_drukhari_covenite_unit_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Any = None,
    ) -> None:
        if not self._is_drukhari_covenite_coterie():
            return
        attacker_root = self._drukhari_root(attacker_unit)
        if attacker_root is None or self._drukhari_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("ENFOLDING NIGHTMARE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        attacker_id = self._drukhari_sort_key(attacker_root)
        snapshot_ids = []
        if attacker_id:
            snapshot_ids = list(self._drukhari_covenite_selected_shooting_targets_by_attacker().pop(attacker_id, []) or [])
        candidate_ids = [str(value or "").strip() for value in list(snapshot_ids or []) if str(value or "").strip()]
        if isinstance(hits_by_target, dict):
            for raw_target in list(hits_by_target.keys()):
                target_root = self._drukhari_root(raw_target)
                target_id = self._drukhari_sort_key(target_root)
                if target_id and target_id not in candidate_ids:
                    candidate_ids.append(target_id)
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit_id in list(candidate_ids or []):
            root = self._drukhari_resolve_unit_by_entity_id(unit_id)
            if root is None:
                continue
            resolved_id = self._drukhari_sort_key(root)
            if resolved_id and resolved_id in seen:
                continue
            if resolved_id:
                seen.add(resolved_id)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._drukhari_is_haemonculus_covens_unit(root):
                continue
            candidates.append(root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_shooting_resolved":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "ENFOLDING NIGHTMARE":
                continue
            if self._drukhari_root(reaction.get("enemy_unit")) is attacker_root:
                return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacker_unit": attacker_root,
            "candidates": sorted(candidates, key=self._drukhari_sort_key),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_drukhari_covenite_connoisseurs_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_drukhari_covenite_coterie():
            return
        attacker_root = self._drukhari_root(attacking_unit)
        if attacker_root is None or self._drukhari_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("CONNOISSEURS OF PAIN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if not self._drukhari_can_spend_pain_tokens(1):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._drukhari_root(target)
            if root is None:
                continue
            target_id = self._drukhari_sort_key(root)
            if target_id and target_id in seen:
                continue
            if target_id:
                seen.add(target_id)
            if not self._drukhari_owned_by_player(root, self.player):
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_drukhari_unit(root):
                continue
            candidates.append(root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "CONNOISSEURS OF PAIN":
                continue
            if self._drukhari_root(reaction.get("enemy_unit")) is attacker_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "candidates": sorted(candidates, key=self._drukhari_sort_key),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_drukhari_covenite_model_destroyed_reactions(self, *, unit: Any, model: Any) -> None:
        if not self._is_drukhari_covenite_coterie():
            return
        root = self._drukhari_root(unit)
        if root is None or model is None:
            return
        if not self._drukhari_owned_by_player(root, self.player):
            return
        if not self._drukhari_postmortality_model_eligible(unit=root, model=model):
            return
        model_id = self._drukhari_sort_key(model)
        if model_id and model_id in self._drukhari_postmortality_used_model_ids():
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("POSTMORTALITY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if not self._drukhari_can_spend_pain_tokens(1):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "model_destroyed_before_removal":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "POSTMORTALITY":
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
                    destroyed_position = (float(pos[0]), float(pos[1]), float(pos[2]), float(pos[3]))
                except (TypeError, ValueError):
                    destroyed_position = None
        payload = {
            "event": "model_destroyed_before_removal",
            "phase_name": str(getattr(self, "_current_phase_name", "") or ""),
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

    def _queue_drukhari_covenite_fight_attacks_resolved_reactions(
        self,
        *,
        unit: Any,
        target_unit: Any,
        hits_by_target: Any = None,
        killing_models_by_target: Any = None,
    ) -> None:
        if not self._is_drukhari_covenite_coterie():
            return
        root = self._drukhari_root(unit)
        if root is None or not self._drukhari_owned_by_player(root, self.player):
            return

        poison_stratagem = getattr(self, "get_by_name", lambda _name: None)("POISONER'S ART")
        if poison_stratagem is not None:
            candidates: list[Any] = []
            seen: set[str] = set()
            target_items = (hits_by_target or {}).items() if isinstance(hits_by_target, dict) else []
            if not target_items and target_unit is not None:
                target_items = [(target_unit, 1)]
            for raw_target, hits in list(target_items):
                try:
                    hit_count = int(hits or 0)
                except (TypeError, ValueError):
                    hit_count = 0
                if hit_count <= 0:
                    continue
                enemy_root = self._drukhari_root(raw_target)
                if enemy_root is None:
                    continue
                enemy_id = self._drukhari_sort_key(enemy_root)
                if enemy_id and enemy_id in seen:
                    continue
                if enemy_id:
                    seen.add(enemy_id)
                if self._drukhari_owned_by_player(enemy_root, self.player):
                    continue
                if not self._drukhari_on_battlefield(enemy_root):
                    continue
                if self._drukhari_has_keyword(enemy_root, "VEHICLE"):
                    continue
                candidates.append(enemy_root)
            if (
                candidates
                and self._drukhari_is_haemonculus_covens_unit(root)
                and int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(poison_stratagem, "cp_cost", 0) or 0)
                and str(getattr(poison_stratagem, "name", "") or "").strip().upper() not in set(getattr(self, "_used_stratagems_this_phase", set()) or set())
            ):
                duplicate = False
                for reaction in list(getattr(self, "_pending_reactions", []) or []):
                    if str(reaction.get("event", "") or "") != "fight_attacks_resolved":
                        continue
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "POISONER'S ART":
                        continue
                    if self._drukhari_root(reaction.get("unit")) is root:
                        duplicate = True
                        break
                if not duplicate:
                    payload = {
                        "event": "fight_attacks_resolved",
                        "phase_name": "Fight phase",
                        "stratagem": poison_stratagem.name,
                        "cp_cost": poison_stratagem.cp_cost,
                        "unit": root,
                        "target_unit": root,
                        "candidates": sorted(candidates, key=self._drukhari_sort_key),
                        "hits_by_target": hits_by_target,
                    }
                    self._queue_reaction(payload, use_timer=False)

        symphony_stratagem = getattr(self, "get_by_name", lambda _name: None)("SYMPHONY OF SUFFERING")
        if symphony_stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(symphony_stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(symphony_stratagem, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        destroyed_enemy = False
        target_items = (killing_models_by_target or {}).items() if isinstance(killing_models_by_target, dict) else []
        for raw_target, _destroyed_models in list(target_items):
            enemy_root = self._drukhari_root(raw_target)
            if enemy_root is None or self._drukhari_owned_by_player(enemy_root, self.player):
                continue
            if self._drukhari_is_alive(enemy_root):
                continue
            destroyed_enemy = True
            break
        if not destroyed_enemy and target_unit is not None:
            enemy_root = self._drukhari_root(target_unit)
            if enemy_root is not None and not self._drukhari_owned_by_player(enemy_root, self.player):
                destroyed_enemy = not self._drukhari_is_alive(enemy_root)
        if not destroyed_enemy:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_attacks_resolved":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "SYMPHONY OF SUFFERING":
                continue
            if self._drukhari_root(reaction.get("unit")) is root:
                return
        self._queue_reaction(
            {
                "event": "fight_attacks_resolved",
                "phase_name": "Fight phase",
                "stratagem": symphony_stratagem.name,
                "cp_cost": symphony_stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "killing_models_by_target": killing_models_by_target,
            },
            use_timer=False,
        )

    def _drukhari_queue_postmortality_choice_request(
        self,
        *,
        unit: Any,
        model: Any,
        destroyed_position: Any = None,
        phase_name: str = "",
        source_name: str = "Postmortality",
    ) -> Any:
        game = getattr(self, "game", None)
        request_decision = getattr(game, "request_decision", None) if game is not None else None
        if not callable(request_decision):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        root = self._drukhari_root(unit)
        if root is None or model is None:
            return None
        unit_id = self._drukhari_sort_key(root)
        model_id = self._drukhari_sort_key(model)
        if not unit_id or not model_id:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for pending in list(queue.list() or []):
                if str(getattr(pending, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(pending, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "drukhari_postmortality":
                    continue
                if str(ctx.get("source_model_id", "") or "") == model_id:
                    return pending
        max_tokens = min(3, int(getattr(self._drukhari_power_from_pain_mgr(), "tokens", 0) or 0))
        if max_tokens <= 0:
            return None
        options = []
        allowed_choice_keys: list[str] = []
        for spend in range(1, max_tokens + 1):
            choice_key = f"SPEND_{int(spend)}"
            allowed_choice_keys.append(choice_key)
            suffix = "" if spend == 1 else "s"
            options.append(
                DecisionOption.create(
                    f"Spend {int(spend)} Pain token{suffix}",
                    payload={
                        "choice_key": choice_key,
                        "pain_token_cost": int(spend),
                        "source_unit_id": unit_id,
                        "source_model_id": model_id,
                    },
                )
            )
        phase_key = self._drukhari_phase_key_from_name(phase_name)
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{source_name}: choose Pain tokens to spend.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "drukhari_postmortality",
                "ability_name": source_name,
                "source_unit_id": unit_id,
                "target_unit_id": unit_id,
                "source_model_id": model_id,
                "model_id": model_id,
                "phase_name": str(phase_name or ""),
                "phase_key": phase_key,
                "allowed_choice_keys": list(allowed_choice_keys),
                "destroyed_position": destroyed_position,
            },
        )
        request_decision(request)
        return request

    def _drukhari_commit_postmortality_choice(
        self,
        *,
        unit: Any,
        model: Any,
        pain_tokens: int,
        destroyed_position: Any = None,
        phase_name: str = "",
        phase_key: str = "",
        source_name: str = "Postmortality",
    ) -> bool:
        root = self._drukhari_root(unit)
        if root is None or model is None:
            return False
        if not self._drukhari_postmortality_model_eligible(unit=root, model=model):
            return False
        model_id = self._drukhari_sort_key(model)
        if model_id and model_id in self._drukhari_postmortality_used_model_ids():
            return False
        try:
            token_count = int(pain_tokens or 0)
        except (TypeError, ValueError):
            token_count = 0
        token_count = max(1, min(3, int(token_count)))
        if not self._drukhari_spend_pain_tokens(token_count, reason=f"{source_name}: {getattr(model, 'name', 'Model')}"):
            return False
        trigger_phase_name = str(phase_name or getattr(self, "_current_phase_name", "") or "")
        trigger_phase_key = self._drukhari_phase_key_from_name(phase_key or trigger_phase_name)
        self._drukhari_postmortality_pending_returns().append(
            {
                "unit": root,
                "model": model,
                "model_id": model_id,
                "destroyed_position": destroyed_position,
                "trigger_phase_name": trigger_phase_name,
                "trigger_phase_key": trigger_phase_key,
                "pain_tokens": int(token_count),
                "source": str(source_name or "Postmortality"),
            }
        )
        if model_id:
            self._drukhari_postmortality_used_model_ids().add(model_id)
        return True

    def _drukhari_postmortality_find_placement(self, *, unit: Any, model: Any, anchor: Any) -> Any:
        root = self._drukhari_root(unit)
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if root is None or model is None or game_map is None:
            return None
        try:
            anchor_x = float(anchor[0])
            anchor_y = float(anchor[1])
            anchor_z = float(anchor[2]) if len(anchor) > 2 else 0.0
            anchor_f = float(anchor[3]) if len(anchor) > 3 else 0.0
        except (TypeError, ValueError, IndexError):
            return None
        find_pos = getattr(game, "_find_closest_valid_reposition_position", None)
        try:
            alive_models = [
                existing
                for existing in list(getattr(root, "models", []) or [])
                if existing is not None and existing is not model and bool(getattr(existing, "is_alive", False))
            ]
        except (AttributeError, TypeError, ValueError):
            alive_models = []
        if callable(find_pos) and len(alive_models) == 0:
            try:
                return find_pos(root, (anchor_x, anchor_y, anchor_z, anchor_f), game_map=game_map)
            except (AttributeError, TypeError, ValueError):
                return None

        create_base = getattr(root, "_create_potential_base", None)
        validate_reanimation = getattr(root, "_reanimation_position_valid", None)
        if not callable(create_base) or not callable(validate_reanimation):
            return None
        try:
            required_neighbors = int(getattr(root, "required_neighbors", 0) or 0)
        except (TypeError, ValueError):
            required_neighbors = 0

        import math

        from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
        from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL

        get_enemy = getattr(game_map, "get_enemy_units", None)
        enemy_units = list(get_enemy(root) or []) if callable(get_enemy) else []
        max_radius = float(max(getattr(game_map, "width", 0) or 0, getattr(game_map, "height", 0) or 0))
        if max_radius <= 0:
            max_radius = 30.0
        radius = 0.0
        while radius <= max_radius + 1e-6:
            angles = (0,) if radius <= 1e-6 else range(0, 360, 15)
            for deg in angles:
                angle = math.radians(float(deg))
                x = anchor_x + math.cos(angle) * radius
                y = anchor_y + math.sin(angle) * radius
                height_fn = getattr(game_map, "get_height_at_point", None)
                if callable(height_fn):
                    try:
                        height = height_fn(x, y)
                    except (AttributeError, TypeError, ValueError):
                        height = None
                    z = float(height) if height is not None else anchor_z
                else:
                    z = anchor_z
                if not bool(validate_reanimation(x, y, z, anchor_f, model, alive_models, game_map, required_neighbors)):
                    continue
                try:
                    candidate_base = create_base(x, y, z, anchor_f, model=model)
                except (AttributeError, TypeError, ValueError):
                    continue
                engaged = False
                for enemy in list(enemy_units or []):
                    enemy_root = self._drukhari_root(enemy)
                    if enemy_root is None or not self._drukhari_on_battlefield(enemy_root):
                        continue
                    enemy_models = list(getattr(enemy_root, "get_models_for_collision", lambda: [])() or [])
                    if not enemy_models:
                        enemy_models = list(getattr(enemy_root, "models", []) or [])
                    for enemy_model in list(enemy_models or []):
                        if enemy_model is None or not bool(getattr(enemy_model, "is_alive", False)):
                            continue
                        try:
                            horizontal = float(horizontal_distance_between_bases_2d(candidate_base, enemy_model.model_base))
                            vertical = float(vertical_distance_between_bases(candidate_base, enemy_model.model_base))
                        except (AttributeError, TypeError, ValueError):
                            continue
                        if horizontal <= float(ENGAGEMENT_RANGE_HORIZONTAL) + 1e-6 and vertical <= float(ENGAGEMENT_RANGE_VERTICAL) + 1e-6:
                            engaged = True
                            break
                    if engaged:
                        break
                if engaged:
                    continue
                return (float(x), float(y), float(z), float(anchor_f))
            radius += 0.5
        return None

    def _resolve_drukhari_covenite_phase_end_effects(self, *, player: Any, phase: Any) -> None:
        if not self._is_drukhari_covenite_coterie():
            return
        phase_key = self._drukhari_phase_key_from_name(getattr(phase, "name", "") or getattr(self, "_current_phase_name", ""))
        if not phase_key:
            return
        remaining_refunds: list[dict[str, Any]] = []
        for entry in list(self._drukhari_connoisseurs_of_pain_pending_refunds() or []):
            if not isinstance(entry, dict):
                continue
            trigger_key = self._drukhari_phase_key_from_name(entry.get("trigger_phase_key") or entry.get("trigger_phase_name") or "")
            if trigger_key and trigger_key != phase_key:
                remaining_refunds.append(entry)
                continue
            root = self._drukhari_root(entry.get("unit"))
            if root is None:
                root = self._drukhari_resolve_unit_by_entity_id(entry.get("unit_id") or "")
            if root is None:
                continue
            if not self._drukhari_on_battlefield(root):
                continue
            if not self._drukhari_is_haemonculus_covens_unit(root):
                continue
            self._drukhari_gain_pain_tokens(1, reason=f"Connoisseurs of Pain: {getattr(root, 'name', 'Unit')}")
        self._drukhari_connoisseurs_of_pain_pending_refunds()[:] = remaining_refunds

        remaining_returns: list[dict[str, Any]] = []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        for entry in list(self._drukhari_postmortality_pending_returns() or []):
            if not isinstance(entry, dict):
                continue
            trigger_key = self._drukhari_phase_key_from_name(entry.get("trigger_phase_key") or entry.get("trigger_phase_name") or "")
            if trigger_key and trigger_key != phase_key:
                remaining_returns.append(entry)
                continue
            root = self._drukhari_root(entry.get("unit"))
            if root is None:
                root = self._drukhari_resolve_unit_by_entity_id(entry.get("unit_id") or "")
            model = entry.get("model")
            if model is None:
                model = self._drukhari_resolve_model_by_entity_id(entry.get("model_id") or "")
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
                base_wounds = int(
                    getattr(
                        model,
                        "_base_wounds",
                        getattr(model, "base_wounds", getattr(model, "wounds", getattr(model, "_wounds", 1))),
                    )
                    or 1
                )
            except (AttributeError, TypeError, ValueError):
                base_wounds = 1
            try:
                wound_value = min(int(base_wounds), max(1, int(entry.get("pain_tokens", 1) or 1)))
            except (TypeError, ValueError):
                wound_value = 1
            try:
                model.wounds = int(wound_value)
            except (AttributeError, TypeError, ValueError):
                try:
                    model._wounds = int(wound_value)
                except (AttributeError, TypeError, ValueError):
                    pass
            for key, value in (
                ("_on_death_reactions_resolved", False),
                ("_fight_on_death_used", False),
                ("_shoot_on_death_used", False),
                ("_pending_placement", False),
                ("_pending_placement_source", None),
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
            placement = self._drukhari_postmortality_find_placement(unit=root, model=model, anchor=anchor)
            if placement is not None:
                try:
                    model.set_location(float(placement[0]), float(placement[1]), float(placement[2]), float(placement[3]))
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
                "INFO: POSTMORTALITY: returned %s with %d wound(s).",
                getattr(model, "name", "Model"),
                int(wound_value),
            )
        self._drukhari_postmortality_pending_returns()[:] = remaining_returns

    def _cleanup_drukhari_kabalite_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_drukhari_kabalite_cartel():
            return
        phase_key = self._drukhari_phase_key_from_name(getattr(phase, "name", "") or "")
        prefixes: tuple[str, ...] = ()
        if phase_key == "SHOOTING_PHASE":
            prefixes = (
                "drukhari_kabalite_making_a_point",
                "drukhari_kabalite_tailored_toxins",
                "drukhari_kabalite_deadly_deceivers",
            )
        elif phase_key == "FIGHT_PHASE":
            prefixes = (
                "drukhari_kabalite_tailored_toxins",
                "drukhari_kabalite_taken_alive",
                "drukhari_kabalite_double_cross",
            )
        else:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._drukhari_root(unit)
            if root is None:
                continue
            root_id = self._drukhari_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in list(sr.keys()):
                if any(str(key).startswith(f"{prefix}_") for prefix in prefixes):
                    sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr
                self._drukhari_clear_unit_ability_cache(root)
        if phase_key == "FIGHT_PHASE":
            mgr = self._drukhari_detachment_mgr()
            if mgr is not None:
                try:
                    mgr.kabalite_taken_alive_failed_test_count = 0
                except (AttributeError, TypeError, ValueError):
                    pass

    def _cleanup_drukhari_realspace_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_drukhari_realspace_raiders():
            return
        phase_key = self._drukhari_phase_key_from_name(getattr(phase, "name", "") or "")
        prefixes: tuple[str, ...] = ()
        if phase_key == "MOVEMENT_PHASE":
            prefixes = ()
        elif phase_key == "SHOOTING_PHASE":
            prefixes = ("drukhari_realspace_instinctive_spite",)
        elif phase_key == "FIGHT_PHASE":
            prefixes = (
                "drukhari_realspace_instinctive_spite",
                "drukhari_realspace_dark_harvest",
            )
        else:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._drukhari_root(unit)
            if root is None:
                continue
            root_id = self._drukhari_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            if phase_key == "MOVEMENT_PHASE":
                effect_tag = "stratagem:drukhari_realspace_eager_for_the_kill"
                existing_effects = list(sr.get("advance_no_roll_effects", []) or [])
                effects = [
                    entry
                    for entry in existing_effects
                    if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == effect_tag)
                ]
                if len(effects) != len(existing_effects):
                    if effects:
                        sr["advance_no_roll_effects"] = effects
                    else:
                        sr.pop("advance_no_roll_effects", None)
                    changed = True
            for key in list(sr.keys()):
                if any(str(key).startswith(f"{prefix}_") for prefix in prefixes):
                    sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr
                self._drukhari_clear_unit_ability_cache(root)

    def _cleanup_drukhari_covenite_phase_end_effects(self, *, phase: Any) -> None:
        phase_key = self._drukhari_phase_key_from_name(getattr(phase, "name", "") or "")
        if phase_key != "FIGHT_PHASE":
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._drukhari_root(unit)
            if root is None:
                continue
            root_id = self._drukhari_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            for key in (
                "drukhari_distillers_of_fear_active",
                "drukhari_distillers_of_fear_source",
                "drukhari_distillers_of_fear_phase",
            ):
                sr.pop(key, None)
            root.special_rules = sr

    def _use_drukhari_skysplinter_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "DARK HARVEST":
            return self._use_drukhari_realspace_dark_harvest(stratagem, **kwargs)
        if name_u == "EAGER FOR THE KILL":
            return self._use_drukhari_realspace_eager_for_the_kill(stratagem, **kwargs)
        if name_u == "FIGHTING SHADOWS":
            return self._use_drukhari_realspace_fighting_shadows(stratagem, **kwargs)
        if name_u == "INSTINCTIVE SPITE":
            return self._use_drukhari_realspace_instinctive_spite(stratagem, **kwargs)
        if name_u == "RAID AND FADE":
            return self._use_drukhari_realspace_raid_and_fade(stratagem, **kwargs)
        if name_u == "DEADLY DECEIVERS":
            return self._use_drukhari_kabalite_deadly_deceivers(stratagem, **kwargs)
        if name_u == "DOUBLE-CROSS":
            return self._use_drukhari_kabalite_double_cross(stratagem, **kwargs)
        if name_u == "ENEMIES WITHOUT NUMBER":
            return self._use_drukhari_kabalite_enemies_without_number(stratagem, **kwargs)
        if name_u == "MAKING A POINT":
            return self._use_drukhari_kabalite_making_a_point(stratagem, **kwargs)
        if name_u == "TAILORED TOXINS":
            return self._use_drukhari_kabalite_tailored_toxins(stratagem, **kwargs)
        if name_u == "TAKEN ALIVE":
            return self._use_drukhari_kabalite_taken_alive(stratagem, **kwargs)
        if name_u == "CONNOISSEURS OF PAIN":
            return self._use_drukhari_covenite_connoisseurs_of_pain(stratagem, **kwargs)
        if name_u == "DISTILLERS OF FEAR":
            return self._use_drukhari_covenite_distillers_of_fear(stratagem, **kwargs)
        if name_u == "ENFOLDING NIGHTMARE":
            return self._use_drukhari_covenite_enfolding_nightmare(stratagem, **kwargs)
        if name_u == "POISONER'S ART":
            return self._use_drukhari_covenite_poisoners_art(stratagem, **kwargs)
        if name_u == "POSTMORTALITY":
            return self._use_drukhari_covenite_postmortality(stratagem, **kwargs)
        if name_u == "SYMPHONY OF SUFFERING":
            return self._use_drukhari_covenite_symphony_of_suffering(stratagem, **kwargs)
        if name_u == "MALICIOUS FRENZY":
            return self._use_drukhari_reapers_wager_malicious_frenzy(stratagem, **kwargs)
        if name_u == "FATEFUL ROLE":
            return self._use_drukhari_reapers_wager_fateful_role(stratagem, **kwargs)
        if name_u == "SCINTILLATING TEMPO":
            return self._use_drukhari_reapers_wager_scintillating_tempo(stratagem, **kwargs)
        if name_u == "SHORTEN THE ODDS":
            return self._use_drukhari_reapers_wager_shorten_the_odds(stratagem, **kwargs)
        if name_u == "DANCE MACABRE":
            return self._use_drukhari_reapers_wager_dance_macabre(stratagem, **kwargs)
        if name_u == "SWOOPING MOCKERY":
            return self._use_drukhari_skysplinter_swooping_mockery(stratagem, **kwargs)
        if name_u == "VICIOUS BLADES":
            return self._use_drukhari_skysplinter_vicious_blades(stratagem, **kwargs)
        if name_u == "POUNCE ON THE PREY":
            return self._use_drukhari_skysplinter_pounce_on_the_prey(stratagem, **kwargs)
        if name_u == "SKYBORNE ANNIHILATION":
            return self._use_drukhari_skysplinter_skyborne_annihilation(stratagem, **kwargs)
        if name_u == "WRAITHLIKE RETREAT":
            return self._use_drukhari_skysplinter_wraithlike_retreat(stratagem, **kwargs)
        return None

    def _use_drukhari_realspace_instinctive_spite(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_realspace_raiders():
            return False
        phase_name = self._drukhari_normalized_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: INSTINCTIVE SPITE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: INSTINCTIVE SPITE: not your Shooting phase")
            return False
        selected_units = self._drukhari_resolve_selected_units(**kwargs)
        candidates = list(kwargs.get("candidates") or self._drukhari_realspace_instinctive_spite_candidates() or [])
        if not selected_units and len(candidates) == 1:
            selected_units = [candidates[0]]
        selected_roots, error = self._drukhari_validate_multi_unit_selection(
            selected_units,
            candidates=candidates,
            max_units=2,
            dual_unit_filter=self._is_drukhari_battleline_unit,
        )
        if error:
            logger.error("ERROR: INSTINCTIVE SPITE: %s", error)
            return False
        for root in list(selected_roots or []):
            if not self._drukhari_owned_by_player(root, self.player):
                logger.error("ERROR: INSTINCTIVE SPITE: target unit is not yours")
                return False
            if not self._drukhari_on_battlefield(root):
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: INSTINCTIVE SPITE: target cannot be selected")
                return False
            if not self._is_drukhari_unit(root):
                logger.error("ERROR: INSTINCTIVE SPITE: target must be a Drukhari unit")
                return False
            round_state = getattr(root, "round_state", None)
            if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
                logger.error("ERROR: INSTINCTIVE SPITE: selected unit has already shot this phase")
                return False
            if phase_name == "fight phase" and (
                bool(getattr(round_state, "fought_this_phase", False))
            ):
                logger.error("ERROR: INSTINCTIVE SPITE: selected unit has already fought this phase")
                return False
        source_name = str(getattr(stratagem, "name", "INSTINCTIVE SPITE") or "INSTINCTIVE SPITE")
        spend_pain_explicit = "spend_pain_token" in kwargs
        spend_pain = bool(kwargs.get("spend_pain_token", False))
        if not spend_pain_explicit and self._drukhari_can_spend_pain_tokens(1):
            queue_confirmation = getattr(getattr(self, "game", None), "_queue_optional_ability_confirmation", None)
            if callable(queue_confirmation):
                selected_unit_ids = sorted(
                    {
                        str(get_entity_id(root) or "").strip()
                        for root in list(selected_roots or [])
                        if str(get_entity_id(root) or "").strip()
                    }
                )
                candidate_unit_ids = sorted(
                    {
                        str(get_entity_id(self._drukhari_root(unit)) or "").strip()
                        for unit in list(candidates or [])
                        if self._drukhari_root(unit) is not None and str(get_entity_id(self._drukhari_root(unit)) or "").strip()
                    }
                )
                queue_confirmation(
                    player=self.player,
                    ability_key="drukhari_realspace_instinctive_spite_pain_token",
                    ability_name="Instinctive Spite",
                    message=(
                        "Spend 1 Pain token to also gain +1 to wound against Below Half-strength targets?"
                    ),
                    context={
                        "phase_name": "Shooting phase" if phase_name == "shooting phase" else "Fight phase",
                        "stratagem_name": source_name,
                        "selected_unit_ids": list(selected_unit_ids),
                        "candidate_unit_ids": list(candidate_unit_ids),
                    },
                    payload={
                        "phase_name": "Shooting phase" if phase_name == "shooting phase" else "Fight phase",
                        "stratagem_name": source_name,
                    },
                    instance_key=f"{phase_name}:{':'.join(selected_unit_ids)}:instinctive_spite",
                )
                return True
        if spend_pain and not self._drukhari_can_spend_pain_tokens(1):
            logger.error("ERROR: INSTINCTIVE SPITE: insufficient Pain tokens")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False
        if spend_pain and not self._drukhari_spend_pain_tokens(1, reason=source_name):
            logger.error("ERROR: INSTINCTIVE SPITE: failed to spend Pain token")
            return False
        mgr = self._drukhari_detachment_mgr()
        resolve_owner = getattr(mgr, "_resolve_owner_and_turn", None) if mgr is not None else None
        if callable(resolve_owner):
            owner_id, turn = resolve_owner(game=getattr(self, "game", None))
        else:
            owner_id = str(getattr(self.player, "id", "") or "")
            turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        for root in list(selected_roots or []):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["drukhari_realspace_instinctive_spite_active"] = True
            sr["drukhari_realspace_instinctive_spite_source"] = source_name
            sr["drukhari_realspace_instinctive_spite_expires_phase"] = phase_key
            sr["drukhari_realspace_instinctive_spite_turn_owner"] = owner_id
            sr["drukhari_realspace_instinctive_spite_turn"] = int(turn)
            sr["drukhari_realspace_instinctive_spite_hit_bonus"] = 1
            sr["drukhari_realspace_instinctive_spite_wound_bonus"] = 1 if spend_pain else 0
            root.special_rules = sr
            self._drukhari_clear_unit_ability_cache(root)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: INSTINCTIVE SPITE: %d unit(s) gain +1 to hit%s against Below Half-strength targets this phase.",
            len(list(selected_roots or [])),
            " and +1 to wound" if spend_pain else "",
        )
        return True

    def _use_drukhari_realspace_dark_harvest(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_realspace_raiders():
            return False
        phase_name = self._drukhari_normalized_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "")
        if phase_name != "fight phase":
            logger.error("ERROR: DARK HARVEST: wrong phase")
            return False
        selected_units = self._drukhari_resolve_selected_units(**kwargs)
        candidates = list(kwargs.get("candidates") or self._drukhari_realspace_dark_harvest_candidates() or [])
        if not selected_units and len(candidates) == 1:
            selected_units = [candidates[0]]
        selected_roots, error = self._drukhari_validate_multi_unit_selection(
            selected_units,
            candidates=candidates,
            max_units=2,
            dual_unit_filter=self._is_drukhari_wracks_unit,
        )
        if error:
            logger.error("ERROR: DARK HARVEST: %s", error)
            return False
        for root in list(selected_roots or []):
            if not self._drukhari_owned_by_player(root, self.player):
                logger.error("ERROR: DARK HARVEST: target unit is not yours")
                return False
            if not self._drukhari_on_battlefield(root):
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: DARK HARVEST: target cannot be selected")
                return False
            if not self._is_drukhari_unit(root):
                logger.error("ERROR: DARK HARVEST: target must be a Drukhari unit")
                return False
            round_state = getattr(root, "round_state", None)
            if bool(getattr(round_state, "fought_this_phase", False)):
                logger.error("ERROR: DARK HARVEST: selected unit has already fought this phase")
                return False
        if not self._drukhari_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False
        mgr = self._drukhari_detachment_mgr()
        resolve_owner = getattr(mgr, "_resolve_owner_and_turn", None) if mgr is not None else None
        if callable(resolve_owner):
            owner_id, turn = resolve_owner(game=getattr(self, "game", None))
        else:
            owner_id = str(getattr(self.player, "id", "") or "")
            turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        source_name = str(getattr(stratagem, "name", "DARK HARVEST") or "DARK HARVEST")
        for root in list(selected_roots or []):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["drukhari_realspace_dark_harvest_active"] = True
            sr["drukhari_realspace_dark_harvest_source"] = source_name
            sr["drukhari_realspace_dark_harvest_expires_phase"] = "FIGHT_PHASE"
            sr["drukhari_realspace_dark_harvest_turn_owner"] = owner_id
            sr["drukhari_realspace_dark_harvest_turn"] = int(turn)
            root.special_rules = sr
            self._drukhari_clear_unit_ability_cache(root)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: DARK HARVEST: %d unit(s) gain [LETHAL HITS] on melee weapons this phase.",
            len(list(selected_roots or [])),
        )
        return True

    def _use_drukhari_realspace_eager_for_the_kill(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_realspace_raiders():
            return False
        phase_name = self._drukhari_normalized_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "")
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name != "movement phase":
            logger.error("ERROR: EAGER FOR THE KILL: wrong phase")
            return False
        if active_player is not self.player:
            logger.error("ERROR: EAGER FOR THE KILL: not your Movement phase")
            return False
        selected_units = self._drukhari_resolve_selected_units(**kwargs)
        candidates = list(kwargs.get("candidates") or self._drukhari_realspace_eager_for_the_kill_candidates() or [])
        if not selected_units and len(candidates) == 1:
            selected_units = [candidates[0]]
        selected_roots, error = self._drukhari_validate_multi_unit_selection(
            selected_units,
            candidates=candidates,
            max_units=2,
            dual_unit_filter=self._is_drukhari_wyches_unit,
        )
        if error:
            logger.error("ERROR: EAGER FOR THE KILL: %s", error)
            return False
        for root in list(selected_roots or []):
            if not self._drukhari_owned_by_player(root, self.player):
                logger.error("ERROR: EAGER FOR THE KILL: target unit is not yours")
                return False
            if not self._drukhari_on_battlefield(root):
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: EAGER FOR THE KILL: target cannot be selected")
                return False
            if not self._is_drukhari_unit(root):
                logger.error("ERROR: EAGER FOR THE KILL: target must be a Drukhari unit")
                return False
            if self._drukhari_selected_to_move_this_phase(root):
                logger.error("ERROR: EAGER FOR THE KILL: target has already been selected to move this phase")
                return False
        if not self._drukhari_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False
        source_name = str(getattr(stratagem, "name", "EAGER FOR THE KILL") or "EAGER FOR THE KILL")
        for root in list(selected_roots or []):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            effect_tag = "stratagem:drukhari_realspace_eager_for_the_kill"
            effects = [
                entry
                for entry in list(sr.get("advance_no_roll_effects", []) or [])
                if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == effect_tag)
            ]
            effects.append(
                {
                    "distance": 6,
                    "source": source_name,
                    "tag": effect_tag,
                    "expires_phase": "MOVEMENT_PHASE",
                }
            )
            sr["advance_no_roll_effects"] = effects
            root.special_rules = sr
            self._drukhari_clear_unit_ability_cache(root)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: EAGER FOR THE KILL: %d unit(s) add 6\" to Move when they Advance this phase.",
            len(list(selected_roots or [])),
        )
        return True

    def _use_drukhari_realspace_fighting_shadows(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_realspace_raiders():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacker_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "FIGHTING SHADOWS":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                attacker_unit = attacker_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FIGHTING SHADOWS: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        attacker_root = self._drukhari_root(attacker_unit)
        if root is None or attacker_root is None:
            return False
        phase_name = self._drukhari_normalized_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: FIGHTING SHADOWS: wrong phase")
            return False
        if phase_name == "shooting phase":
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is self.player:
                logger.error("ERROR: FIGHTING SHADOWS: only in your opponent's Shooting phase")
                return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: FIGHTING SHADOWS: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: FIGHTING SHADOWS: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: FIGHTING SHADOWS: target cannot be selected")
            return False
        if not self._is_drukhari_unit(root) or self._drukhari_is_haemonculus_covens_unit(root):
            logger.error("ERROR: FIGHTING SHADOWS: target must be a non-Haemonculus Covens Drukhari unit")
            return False
        if self._drukhari_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: FIGHTING SHADOWS: attacking unit must be enemy")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        apply_effect = getattr(self, "_apply_generic_defensive_effect", None)
        if not callable(apply_effect):
            logger.error("ERROR: FIGHTING SHADOWS: defensive effect helper unavailable")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        ok = apply_effect(
            root,
            {"duration": "phase", "effect_type": "hit_penalty", "value": 1, "attack_type": "any"},
            attacker_unit=attacker_root,
            phase_name=phase_label,
            source_name=str(getattr(stratagem, "name", "FIGHTING SHADOWS") or "FIGHTING SHADOWS"),
        )
        if not ok:
            logger.error("ERROR: FIGHTING SHADOWS: failed to apply defensive effect")
            return False
        self._drukhari_clear_unit_ability_cache(root)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: FIGHTING SHADOWS: %s is -1 to hit until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_realspace_raid_and_fade(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_realspace_raiders():
            return False
        phase_name = self._drukhari_normalized_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "")
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name != "shooting phase":
            logger.error("ERROR: RAID AND FADE: wrong phase")
            return False
        if active_player is not self.player:
            logger.error("ERROR: RAID AND FADE: not your Shooting phase")
            return False
        selected_units = self._drukhari_resolve_selected_units(**kwargs)
        candidates = list(kwargs.get("candidates") or self._drukhari_realspace_raid_and_fade_candidates() or [])
        if not selected_units and len(candidates) == 1:
            selected_units = [candidates[0]]
        selected_roots, error = self._drukhari_validate_multi_unit_selection(
            selected_units,
            candidates=candidates,
            max_units=2,
            dual_unit_filter=self._is_drukhari_kabalite_warriors_unit,
        )
        if error:
            logger.error("ERROR: RAID AND FADE: %s", error)
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: RAID AND FADE: reactive move decision queue unavailable")
            return False
        for root in list(selected_roots or []):
            if not self._drukhari_owned_by_player(root, self.player):
                logger.error("ERROR: RAID AND FADE: target unit is not yours")
                return False
            if not self._drukhari_on_battlefield(root):
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: RAID AND FADE: target cannot be selected")
                return False
            if not self._is_drukhari_unit(root):
                logger.error("ERROR: RAID AND FADE: target must be a Drukhari unit")
                return False
            if self._is_drukhari_scourges_unit(root) or self._drukhari_has_keyword(root, "AIRCRAFT"):
                logger.error("ERROR: RAID AND FADE: Scourges and AIRCRAFT cannot be selected")
                return False
            if self._drukhari_has_enemy_within_engagement_range(root):
                logger.error("ERROR: RAID AND FADE: engaged units cannot be selected")
                return False
        if not self._drukhari_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False
        source_name = str(getattr(stratagem, "name", "RAID AND FADE") or "RAID AND FADE")
        queued = 0
        for root in list(selected_roots or []):
            request = queue_move(
                player=self.player,
                unit=root,
                attacker_unit=root,
                max_distance=6,
                kind="post_shoot_no_charge",
                movement_type="reactive",
                source=source_name,
                allow_skip=True,
            )
            if request is None:
                logger.error("ERROR: RAID AND FADE: failed to queue reactive move decision")
                return False
            queued += 1
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: RAID AND FADE: queued %d reactive move decision(s) up to 6\" with no charge this turn.",
            int(queued),
        )
        return True

    def _use_drukhari_kabalite_making_a_point(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_kabalite_cartel():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._drukhari_kabalite_making_a_point_candidates() or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MAKING A POINT: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: MAKING A POINT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MAKING A POINT: not your Shooting phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: MAKING A POINT: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: MAKING A POINT: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: MAKING A POINT: target cannot be selected")
            return False
        if not self._is_drukhari_kabalite_warriors_or_hand_of_the_archon_unit(root):
            logger.error("ERROR: MAKING A POINT: target must be Kabalite Warriors or Hand of the Archon")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: MAKING A POINT: target has already shot this phase")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._drukhari_detachment_mgr()
        resolve_owner = getattr(mgr, "_resolve_owner_and_turn", None) if mgr is not None else None
        if callable(resolve_owner):
            owner_id, turn = resolve_owner(game=getattr(self, "game", None))
        else:
            owner_id = str(getattr(self.player, "id", "") or "")
            turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["drukhari_kabalite_making_a_point_active"] = True
        sr["drukhari_kabalite_making_a_point_source"] = str(getattr(stratagem, "name", "MAKING A POINT") or "MAKING A POINT")
        sr["drukhari_kabalite_making_a_point_expires_phase"] = "SHOOTING_PHASE"
        sr["drukhari_kabalite_making_a_point_turn_owner"] = owner_id
        sr["drukhari_kabalite_making_a_point_turn"] = int(turn)
        sr["drukhari_kabalite_making_a_point_skill_bonus"] = 1
        sr["drukhari_kabalite_making_a_point_ap_bonus"] = 1
        root.special_rules = sr
        self._drukhari_clear_unit_ability_cache(root)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: MAKING A POINT: %s improves ranged BS and AP by 1 until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_kabalite_tailored_toxins(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_kabalite_cartel():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._drukhari_kabalite_tailored_toxins_candidates() or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TAILORED TOXINS: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: TAILORED TOXINS: wrong phase")
            return False
        if phase_name == "shooting phase":
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: TAILORED TOXINS: Shooting use requires your turn")
                return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: TAILORED TOXINS: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: TAILORED TOXINS: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: TAILORED TOXINS: target cannot be selected")
            return False
        if not self._is_drukhari_kabal_or_blades_for_hire_unit(root):
            logger.error("ERROR: TAILORED TOXINS: target must be a Kabal or Blades for Hire unit")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: TAILORED TOXINS: target has already shot this phase")
            return False
        if phase_name == "fight phase" and (
            bool(getattr(round_state, "fought_this_phase", False))
            or bool(getattr(round_state, "fought_this_round", False))
        ):
            logger.error("ERROR: TAILORED TOXINS: target has already fought this phase")
            return False
        contract_target = self._drukhari_kabalite_contract_target_root()
        if contract_target is None:
            logger.error("ERROR: TAILORED TOXINS: no active Contract target")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._drukhari_detachment_mgr()
        resolve_owner = getattr(mgr, "_resolve_owner_and_turn", None) if mgr is not None else None
        if callable(resolve_owner):
            owner_id, turn = resolve_owner(game=getattr(self, "game", None))
        else:
            owner_id = str(getattr(self.player, "id", "") or "")
            turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        phase_key = self._drukhari_phase_key_from_name(phase_name)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["drukhari_kabalite_tailored_toxins_active"] = True
        sr["drukhari_kabalite_tailored_toxins_source"] = str(getattr(stratagem, "name", "TAILORED TOXINS") or "TAILORED TOXINS")
        sr["drukhari_kabalite_tailored_toxins_expires_phase"] = phase_key
        sr["drukhari_kabalite_tailored_toxins_turn_owner"] = owner_id
        sr["drukhari_kabalite_tailored_toxins_turn"] = int(turn)
        sr["drukhari_kabalite_tailored_toxins_contract_target_unit_id"] = self._drukhari_sort_key(contract_target)
        sr["drukhari_kabalite_tailored_toxins_crit_hit_threshold"] = 5
        root.special_rules = sr
        self._drukhari_clear_unit_ability_cache(root)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: TAILORED TOXINS: %s scores critical hits on 5+ against the Contract unit this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_kabalite_taken_alive(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_kabalite_cartel():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._drukhari_kabalite_taken_alive_candidates() or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TAKEN ALIVE: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: TAKEN ALIVE: wrong phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: TAKEN ALIVE: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: TAKEN ALIVE: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: TAKEN ALIVE: target cannot be selected")
            return False
        if not self._is_drukhari_unit(root):
            logger.error("ERROR: TAKEN ALIVE: target must be a Drukhari unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)) or bool(
            getattr(getattr(root, "round_state", None), "fought_this_round", False)
        ):
            logger.error("ERROR: TAKEN ALIVE: target has already fought this phase")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._drukhari_detachment_mgr()
        resolve_owner = getattr(mgr, "_resolve_owner_and_turn", None) if mgr is not None else None
        if callable(resolve_owner):
            owner_id, turn = resolve_owner(game=getattr(self, "game", None))
        else:
            owner_id = str(getattr(self.player, "id", "") or "")
            turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        contract_target = self._drukhari_kabalite_contract_target_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["drukhari_kabalite_taken_alive_active"] = True
        sr["drukhari_kabalite_taken_alive_source"] = str(getattr(stratagem, "name", "TAKEN ALIVE") or "TAKEN ALIVE")
        sr["drukhari_kabalite_taken_alive_expires_phase"] = "FIGHT_PHASE"
        sr["drukhari_kabalite_taken_alive_turn_owner"] = owner_id
        sr["drukhari_kabalite_taken_alive_turn"] = int(turn)
        sr["drukhari_kabalite_taken_alive_hit_bonus"] = 1
        sr["drukhari_kabalite_taken_alive_battle_shock_triggered"] = False
        sr["drukhari_kabalite_taken_alive_contract_target_unit_id"] = (
            self._drukhari_sort_key(contract_target) if contract_target is not None else ""
        )
        root.special_rules = sr
        self._drukhari_clear_unit_ability_cache(root)
        if mgr is not None:
            try:
                mgr.kabalite_taken_alive_failed_test_count = 0
            except (AttributeError, TypeError, ValueError):
                pass
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: TAKEN ALIVE: %s gains +1 to Hit this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_kabalite_deadly_deceivers(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_kabalite_cartel():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacker_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "DEADLY DECEIVERS":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                attacker_unit = attacker_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DEADLY DECEIVERS: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        attacker_root = self._drukhari_root(attacker_unit)
        if root is None or attacker_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: DEADLY DECEIVERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: DEADLY DECEIVERS: only in your opponent's Shooting phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: DEADLY DECEIVERS: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: DEADLY DECEIVERS: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: DEADLY DECEIVERS: target cannot be selected")
            return False
        if not self._is_drukhari_kabal_or_blades_for_hire_unit(root):
            logger.error("ERROR: DEADLY DECEIVERS: target must be a Kabal or Blades for Hire unit")
            return False
        if self._drukhari_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: DEADLY DECEIVERS: attacking unit must be enemy")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._drukhari_detachment_mgr()
        resolve_owner = getattr(mgr, "_resolve_owner_and_turn", None) if mgr is not None else None
        if callable(resolve_owner):
            owner_id, turn = resolve_owner(game=getattr(self, "game", None))
        else:
            owner_id = ""
            turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["drukhari_kabalite_deadly_deceivers_active"] = True
        sr["drukhari_kabalite_deadly_deceivers_source"] = str(
            getattr(stratagem, "name", "DEADLY DECEIVERS") or "DEADLY DECEIVERS"
        )
        sr["drukhari_kabalite_deadly_deceivers_expires_phase"] = "SHOOTING_PHASE"
        sr["drukhari_kabalite_deadly_deceivers_turn_owner"] = owner_id
        sr["drukhari_kabalite_deadly_deceivers_turn"] = int(turn)
        sr["drukhari_kabalite_deadly_deceivers_targeting_range"] = 18.0
        root.special_rules = sr
        self._drukhari_clear_unit_ability_cache(root)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: DEADLY DECEIVERS: %s can only be targeted by ranged attacks from within 18\" this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_kabalite_double_cross(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_kabalite_cartel():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        support_unit = kwargs.get("support_unit") or kwargs.get("secondary_unit")
        attacker_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        support_by_unit = dict(kwargs.get("support_candidates_by_unit") or {})
        if unit is None or support_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "DOUBLE-CROSS":
                    continue
                unit = unit or reaction.get("unit") or reaction.get("target_unit")
                attacker_unit = attacker_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not support_by_unit:
                    support_by_unit = dict(reaction.get("support_candidates_by_unit") or {})
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._drukhari_root(unit)
        attacker_root = self._drukhari_root(attacker_unit)
        if root is None or attacker_root is None:
            logger.error("ERROR: DOUBLE-CROSS: missing protected unit or attacker context")
            return False
        if support_unit is None:
            support_candidates = list(support_by_unit.get(self._drukhari_sort_key(root), []) or [])
            if len(support_candidates) == 1:
                support_unit = support_candidates[0]
        support_root = self._drukhari_root(support_unit)
        if support_root is None:
            logger.error("ERROR: DOUBLE-CROSS: no support unit selected")
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: DOUBLE-CROSS: wrong phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: DOUBLE-CROSS: protected unit is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: DOUBLE-CROSS: protected unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: DOUBLE-CROSS: protected unit cannot be selected")
            return False
        if not self._is_drukhari_kabal_or_blades_for_hire_unit(root):
            logger.error("ERROR: DOUBLE-CROSS: protected unit must be a Kabal or Blades for Hire unit")
            return False
        if self._drukhari_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: DOUBLE-CROSS: attacking unit must be enemy")
            return False
        if not self._drukhari_owned_by_player(support_root, self.player):
            logger.error("ERROR: DOUBLE-CROSS: support unit is not yours")
            return False
        if not self._drukhari_on_battlefield(support_root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(support_root)):
            logger.error("ERROR: DOUBLE-CROSS: support unit cannot be selected")
            return False
        if not self._is_drukhari_non_vehicle_unit(support_root):
            logger.error("ERROR: DOUBLE-CROSS: support unit must be a non-Vehicle Drukhari unit")
            return False
        support_candidates = list(support_by_unit.get(self._drukhari_sort_key(root), []) or [])
        if support_candidates and not self._drukhari_unit_in_candidates(support_root, support_candidates):
            logger.error("ERROR: DOUBLE-CROSS: support unit is not currently eligible")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._drukhari_detachment_mgr()
        resolve_owner = getattr(mgr, "_resolve_owner_and_turn", None) if mgr is not None else None
        if callable(resolve_owner):
            owner_id, turn = resolve_owner(game=getattr(self, "game", None))
        else:
            owner_id = ""
            turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["drukhari_kabalite_double_cross_active"] = True
        sr["drukhari_kabalite_double_cross_source"] = str(getattr(stratagem, "name", "DOUBLE-CROSS") or "DOUBLE-CROSS")
        sr["drukhari_kabalite_double_cross_expires_phase"] = "FIGHT_PHASE"
        sr["drukhari_kabalite_double_cross_turn_owner"] = owner_id
        sr["drukhari_kabalite_double_cross_turn"] = int(turn)
        sr["drukhari_kabalite_double_cross_support_unit_id"] = self._drukhari_sort_key(support_root)
        sr["drukhari_kabalite_double_cross_attacker_unit_id"] = self._drukhari_sort_key(attacker_root)
        root.special_rules = sr
        self._drukhari_clear_unit_ability_cache(root)
        self._drukhari_clear_unit_ability_cache(support_root)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: DOUBLE-CROSS: %s redirects qualifying attacks into %s this phase.",
            getattr(root, "name", "Unit"),
            getattr(support_root, "name", "Support Unit"),
        )
        return True

    def _use_drukhari_kabalite_enemies_without_number(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_kabalite_cartel():
            return False
        mgr = self._drukhari_detachment_mgr()
        if mgr is None:
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._drukhari_kabalite_enemies_without_number_candidates() or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "ENEMIES WITHOUT NUMBER":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ENEMIES WITHOUT NUMBER: no Archon WARLORD provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: ENEMIES WITHOUT NUMBER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: ENEMIES WITHOUT NUMBER: not your Command phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: ENEMIES WITHOUT NUMBER: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: ENEMIES WITHOUT NUMBER: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: ENEMIES WITHOUT NUMBER: target cannot be selected")
            return False
        if self._drukhari_root(root) is not self._drukhari_root(self._drukhari_kabalite_archon_warlord()):
            logger.error("ERROR: ENEMIES WITHOUT NUMBER: target must be your Archon WARLORD")
            return False
        checker = getattr(mgr, "murderous_agenda_reselect_window_active", None)
        if not callable(checker) or not bool(checker(game=getattr(self, "game", None), player=self.player)):
            logger.error("ERROR: ENEMIES WITHOUT NUMBER: no Contract was just completed this Command phase")
            return False
        build_request = getattr(mgr, "build_murderous_agenda_request", None)
        if not callable(build_request):
            return False
        request = build_request(
            game=getattr(self, "game", None),
            player=self.player,
            allow_reselect=True,
            ability="murderous_agenda",
            ability_name=str(getattr(stratagem, "name", "ENEMIES WITHOUT NUMBER") or "ENEMIES WITHOUT NUMBER"),
            source_unit_id=self._drukhari_sort_key(root),
        )
        if request is None:
            logger.error("ERROR: ENEMIES WITHOUT NUMBER: no valid Contract re-selection request could be created")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        request_decision = getattr(getattr(self, "game", None), "request_decision", None)
        if callable(request_decision):
            request_decision(request)
        else:
            queue = getattr(getattr(self, "game", None), "decision_queue", None)
            if queue is None or not hasattr(queue, "add"):
                logger.error("ERROR: ENEMIES WITHOUT NUMBER: decision queue unavailable")
                return False
            queue.add(request)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: ENEMIES WITHOUT NUMBER: %s may select a new Murderous Agenda Contract.",
            getattr(root, "name", "Archon"),
        )
        return True

    def _use_drukhari_covenite_connoisseurs_of_pain(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_covenite_coterie():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacker_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "CONNOISSEURS OF PAIN":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                attacker_unit = attacker_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CONNOISSEURS OF PAIN: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        attacker_root = self._drukhari_root(attacker_unit)
        if root is None or attacker_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: CONNOISSEURS OF PAIN: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: CONNOISSEURS OF PAIN: only in your opponent's Shooting phase")
            return False
        if self._drukhari_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: CONNOISSEURS OF PAIN: attacking unit must be enemy")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: CONNOISSEURS OF PAIN: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: CONNOISSEURS OF PAIN: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if not self._is_drukhari_unit(root):
            logger.error("ERROR: CONNOISSEURS OF PAIN: target must be a Drukhari unit")
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: CONNOISSEURS OF PAIN: target cannot be selected")
            return False
        if not self._drukhari_can_spend_pain_tokens(1):
            logger.error("ERROR: CONNOISSEURS OF PAIN: insufficient Pain tokens")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        if not self._drukhari_spend_pain_tokens(1, reason=f"Connoisseurs of Pain: {getattr(root, 'name', 'Unit')}"):
            return False
        if not bool(self._apply_armour_of_contempt(root, attacker_root, amount=1)):
            logger.error("ERROR: CONNOISSEURS OF PAIN: failed to apply AP worsen effect")
            return False
        if self._drukhari_is_haemonculus_covens_unit(root):
            self._drukhari_connoisseurs_of_pain_pending_refunds().append(
                {
                    "unit": root,
                    "unit_id": self._drukhari_sort_key(root),
                    "trigger_phase_name": str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or ""),
                    "trigger_phase_key": self._drukhari_phase_key_from_name(
                        kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or ""
                    ),
                }
            )
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: CONNOISSEURS OF PAIN: %s worsens %s AP by 1 until attacks resolve.",
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "Enemy Unit"),
        )
        return True

    def _use_drukhari_covenite_distillers_of_fear(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_covenite_coterie():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "DISTILLERS OF FEAR":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DISTILLERS OF FEAR: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: DISTILLERS OF FEAR: wrong phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: DISTILLERS OF FEAR: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: DISTILLERS OF FEAR: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: DISTILLERS OF FEAR: target cannot be selected")
            return False
        if not self._drukhari_is_haemonculus_covens_unit(root):
            logger.error("ERROR: DISTILLERS OF FEAR: target must be a Haemonculus Covens unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: DISTILLERS OF FEAR: target has already fought this phase")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["drukhari_distillers_of_fear_active"] = True
        sr["drukhari_distillers_of_fear_source"] = str(getattr(stratagem, "name", "DISTILLERS OF FEAR") or "DISTILLERS OF FEAR")
        sr["drukhari_distillers_of_fear_phase"] = "FIGHT_PHASE"
        root.special_rules = sr
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: DISTILLERS OF FEAR: %s gains Devastating Wounds against Battle-shocked targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_covenite_enfolding_nightmare(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_covenite_coterie():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacker_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "ENFOLDING NIGHTMARE":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                attacker_unit = attacker_unit or reaction.get("attacker_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ENFOLDING NIGHTMARE: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        attacker_root = self._drukhari_root(attacker_unit)
        if root is None or attacker_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: ENFOLDING NIGHTMARE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: ENFOLDING NIGHTMARE: only in your opponent's Shooting phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: ENFOLDING NIGHTMARE: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: ENFOLDING NIGHTMARE: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: ENFOLDING NIGHTMARE: target cannot be selected")
            return False
        if not self._drukhari_is_haemonculus_covens_unit(root):
            logger.error("ERROR: ENFOLDING NIGHTMARE: target must be a Haemonculus Covens unit")
            return False
        if self._drukhari_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: ENFOLDING NIGHTMARE: attacking unit must be enemy")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: ENFOLDING NIGHTMARE: reactive move decision queue unavailable")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        max_distance = dice_module.get_roll("D6")
        if max_distance <= 0:
            logger.error("ERROR: ENFOLDING NIGHTMARE: invalid move distance roll")
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(max_distance),
            kind="enfolding_nightmare",
            movement_type="reactive",
            reactive_movement_type="enfolding_nightmare",
            source=str(getattr(stratagem, "name", "ENFOLDING NIGHTMARE") or "ENFOLDING NIGHTMARE"),
            moving_unit=attacker_root,
            attacker_unit=attacker_root,
            range_value=int(max_distance),
            allow_engagement_range=True,
            allow_skip=True,
            extra_context={
                "enfolding_nightmare_closest_enemy_exclude_keywords_any": ["AIRCRAFT"],
            },
        )
        if request is None:
            logger.error("ERROR: ENFOLDING NIGHTMARE: failed to queue move decision")
            return False
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: ENFOLDING NIGHTMARE: %s can make a reactive move of up to %d\".",
            getattr(root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_drukhari_covenite_poisoners_art(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_covenite_coterie():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        target_enemy = kwargs.get("enemy_unit") or kwargs.get("selected_unit") or kwargs.get("poisoned_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "POISONER'S ART":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                target_enemy = target_enemy or reaction.get("enemy_unit") or reaction.get("selected_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None:
            logger.error("ERROR: POISONER'S ART: no source unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: POISONER'S ART: wrong phase")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: POISONER'S ART: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if not self._drukhari_is_haemonculus_covens_unit(root):
            logger.error("ERROR: POISONER'S ART: target must be a Haemonculus Covens unit")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: POISONER'S ART: source unit must have fought this phase")
            return False
        if target_enemy is None and len(candidates) == 1:
            target_enemy = candidates[0]
        if target_enemy is not None and candidates and not self._drukhari_unit_in_candidates(self._drukhari_root(target_enemy), candidates):
            logger.error("ERROR: POISONER'S ART: selected enemy unit is not eligible")
            return False
        if target_enemy is not None:
            enemy_root = self._drukhari_root(target_enemy)
            if enemy_root is None:
                logger.error("ERROR: POISONER'S ART: enemy unit could not be resolved")
                return False
            if self._drukhari_owned_by_player(enemy_root, self.player):
                logger.error("ERROR: POISONER'S ART: selected unit must be an enemy")
                return False
            if not self._drukhari_on_battlefield(enemy_root):
                logger.error("ERROR: POISONER'S ART: selected enemy unit is not on the battlefield")
                return False
            if self._drukhari_has_keyword(enemy_root, "VEHICLE"):
                logger.error("ERROR: POISONER'S ART: VEHICLE units cannot be poisoned")
                return False
        if len(candidates) > 1:
            game = getattr(self, "game", None)
            request_decision = getattr(game, "request_decision", None) if game is not None else None
            if target_enemy is None and not callable(request_decision):
                logger.error("ERROR: POISONER'S ART: target decision queue unavailable")
                return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        ability_name = str(getattr(stratagem, "name", "Poisoner's Art") or "Poisoner's Art")
        if target_enemy is None:
            from ..engine.decision_kinds import DECISION_CHOOSE_DAEMONIC_POISONS_TARGET
            from ..engine.decisions import DecisionOption, DecisionRequest

            options = [
                DecisionOption.create(
                    str(getattr(candidate, "name", "Unit") or "Unit"),
                    payload={"unit_id": self._drukhari_sort_key(candidate)},
                )
                for candidate in list(sorted(candidates, key=self._drukhari_sort_key) or [])
            ]
            request = DecisionRequest.create(
                DECISION_CHOOSE_DAEMONIC_POISONS_TARGET,
                f"{ability_name}: select a unit to poison.",
                player_id=getattr(self.player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": self._drukhari_sort_key(root),
                    "ability_name": ability_name,
                    "phase": "Fight phase",
                },
            )
            self.game.request_decision(request)
        else:
            from ..rules.daemonic_poisons import apply_daemonic_poisons

            enemy_root = self._drukhari_root(target_enemy)
            if enemy_root is None:
                logger.error("ERROR: POISONER'S ART: enemy unit could not be resolved")
                return False
            apply_daemonic_poisons(
                enemy_root,
                source_unit=root,
                ability_name=ability_name,
                game=self.game,
                player=self.player,
            )
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: POISONER'S ART: %s applies poison for the rest of the battle.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_covenite_postmortality(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_covenite_coterie():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("destroyed_unit")
        model = kwargs.get("model") or kwargs.get("destroyed_model")
        destroyed_position = kwargs.get("destroyed_position")
        if unit is None or model is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "POSTMORTALITY":
                    continue
                unit = unit or reaction.get("unit") or reaction.get("target_unit") or reaction.get("destroyed_unit")
                model = model or reaction.get("destroyed_model")
                destroyed_position = destroyed_position or reaction.get("destroyed_position")
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None or model is None:
            logger.error("ERROR: POSTMORTALITY: no destroyed model provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            logger.error("ERROR: POSTMORTALITY: source unit could not be resolved")
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip()
        if not phase_name:
            logger.error("ERROR: POSTMORTALITY: phase context is required")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: POSTMORTALITY: target model is not from your army")
            return False
        if not self._drukhari_postmortality_model_eligible(unit=root, model=model):
            logger.error("ERROR: POSTMORTALITY: model is not an eligible destroyed Haemonculus")
            return False
        model_id = self._drukhari_sort_key(model)
        if model_id and model_id in self._drukhari_postmortality_used_model_ids():
            logger.error("ERROR: POSTMORTALITY: this model has already returned once this battle")
            return False
        if not self._drukhari_can_spend_pain_tokens(1):
            logger.error("ERROR: POSTMORTALITY: insufficient Pain tokens")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        request = self._drukhari_queue_postmortality_choice_request(
            unit=root,
            model=model,
            destroyed_position=destroyed_position,
            phase_name=phase_name,
            source_name=str(getattr(stratagem, "name", "Postmortality") or "Postmortality"),
        )
        if request is None:
            logger.error("ERROR: POSTMORTALITY: failed to queue Pain token choice")
            return False
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: POSTMORTALITY: queued return choice for %s.",
            getattr(model, "name", "Model"),
        )
        return True

    def _use_drukhari_covenite_symphony_of_suffering(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_covenite_coterie():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SYMPHONY OF SUFFERING":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None:
            logger.error("ERROR: SYMPHONY OF SUFFERING: no source unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SYMPHONY OF SUFFERING: wrong phase")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: SYMPHONY OF SUFFERING: source unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if not self._is_drukhari_unit(root):
            logger.error("ERROR: SYMPHONY OF SUFFERING: source must be a Drukhari unit")
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SYMPHONY OF SUFFERING: source unit cannot be selected")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        modifier = -1 if self._drukhari_is_haemonculus_covens_unit(root) else 0
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        targets = self._drukhari_visible_enemy_units_within_range(root, 9.0)
        for enemy_unit in list(targets or []):
            force_test = getattr(enemy_unit, "force_battle_shock_test", None)
            if not callable(force_test):
                continue
            try:
                force_test(
                    current_turn=max(1, int(current_turn)),
                    modifier=int(modifier),
                    source=str(getattr(stratagem, "name", "Symphony of Suffering") or "Symphony of Suffering"),
                )
            except (AttributeError, TypeError, ValueError):
                continue
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: SYMPHONY OF SUFFERING: %s forced %d Battle-shock test(s).",
            getattr(root, "name", "Unit"),
            len(list(targets or [])),
        )
        return True

    def _use_drukhari_reapers_wager_scintillating_tempo(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_reapers_wager():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SCINTILLATING TEMPO":
                    continue
                unit = unit or reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None:
            logger.error("ERROR: SCINTILLATING TEMPO: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"movement phase", "charge phase"}:
            logger.error("ERROR: SCINTILLATING TEMPO: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SCINTILLATING TEMPO: not your phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: SCINTILLATING TEMPO: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: SCINTILLATING TEMPO: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SCINTILLATING TEMPO: target cannot be selected")
            return False
        if not self._is_drukhari_or_harlequins_unit(root):
            logger.error("ERROR: SCINTILLATING TEMPO: target must be a Drukhari or Harlequins unit")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False

        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["scintillating_tempo_no_overwatch"] = True
            if owner:
                sr["scintillating_tempo_turn_owner"] = owner
            if turn:
                sr["scintillating_tempo_turn"] = int(turn)
            sr["scintillating_tempo_source"] = str(getattr(stratagem, "name", "SCINTILLATING TEMPO") or "SCINTILLATING TEMPO")
            member.special_rules = sr

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: SCINTILLATING TEMPO: %s cannot be targeted by Fire Overwatch until end of turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_reapers_wager_malicious_frenzy(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_reapers_wager():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MALICIOUS FRENZY: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = self._drukhari_normalized_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: MALICIOUS FRENZY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: MALICIOUS FRENZY: not your Shooting phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: MALICIOUS FRENZY: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: MALICIOUS FRENZY: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: MALICIOUS FRENZY: target cannot be selected")
            return False
        if not self._is_drukhari_or_harlequins_unit(root):
            logger.error("ERROR: MALICIOUS FRENZY: target must be a Drukhari or Harlequins unit")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: MALICIOUS FRENZY: target has already been selected to shoot this phase")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: MALICIOUS FRENZY: target has already been selected to fight this phase")
            return False

        choice_key = self._drukhari_reapers_wager_malicious_frenzy_choice_key(
            kwargs.get("choice_key") or kwargs.get("key") or kwargs.get("choice") or kwargs.get("selection")
        )
        if choice_key:
            attack_type = "ranged" if phase_name == "shooting phase" else "melee"
            if not self._drukhari_unit_has_weapon_of_attack_type(root, attack_type=attack_type):
                logger.error("ERROR: MALICIOUS FRENZY: target has no eligible %s weapons", attack_type)
                return False
            if not self._drukhari_spend_cp(stratagem, target_unit=root):
                return False
            outcome = self.apply_drukhari_reapers_wager_malicious_frenzy(
                root,
                choice_key=choice_key,
                phase_name=phase_name,
                source=stratagem.name or "MALICIOUS FRENZY",
            )
            if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
                logger.error("ERROR: MALICIOUS FRENZY: invalid choice")
                return False
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(stratagem.name)
            self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
            logger.info(
                "INFO: MALICIOUS FRENZY: %s gains [%s] on %s weapons this phase.",
                getattr(root, "name", "Unit"),
                str(outcome.get("keyword", choice_key) or choice_key),
                str(outcome.get("attack_type", "") or "selected"),
            )
            return True

        queue = getattr(self.game, "decision_queue", None)
        unit_id = str(get_entity_id(root) or "")
        if queue is not None and hasattr(queue, "list"):
            for request in list(queue.list() or []):
                if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(request, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "drukhari_reapers_wager_malicious_frenzy_choice":
                    continue
                if str(ctx.get("unit_id", "") or "") == unit_id:
                    return True

        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())

        choice_keys = ["LETHAL_HITS", "SUSTAINED_HITS_1"]
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Malicious Frenzy: select a weapon keyword.",
            player_id=getattr(self.player, "id", None),
            options=[
                DecisionOption.create(
                    self._drukhari_reapers_wager_malicious_frenzy_choice_label(choice) or choice,
                    payload={
                        "choice_key": choice,
                        "unit_id": unit_id,
                    },
                )
                for choice in choice_keys
            ],
            context={
                "ability": "drukhari_reapers_wager_malicious_frenzy_choice",
                "ability_name": str(stratagem.name or "MALICIOUS FRENZY"),
                "unit_id": unit_id,
                "army_id": get_entity_id(getattr(self.player, "army", None)),
                "phase_name": "Shooting phase" if phase_name == "shooting phase" else "Fight phase",
                "turn": int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0,
                "turn_owner_id": str(getattr(active_player, "id", "") or getattr(self.player, "id", "") or ""),
                "allowed_choice_keys": list(choice_keys),
                "optional": False,
            },
        )
        self.game.request_decision(request)
        logger.info(
            "INFO: MALICIOUS FRENZY: %s must select Lethal Hits or Sustained Hits 1.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_reapers_wager_fateful_role(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_reapers_wager():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacker_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "FATEFUL ROLE":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                attacker_unit = attacker_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FATEFUL ROLE: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        attacker_root = self._drukhari_root(attacker_unit)
        if root is None or attacker_root is None:
            return False
        phase_name = self._drukhari_normalized_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "")
        if phase_name != "fight phase":
            logger.error("ERROR: FATEFUL ROLE: wrong phase")
            return False
        if self._drukhari_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: FATEFUL ROLE: attacking unit must be enemy")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: FATEFUL ROLE: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: FATEFUL ROLE: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: FATEFUL ROLE: target cannot be selected")
            return False
        if not self._is_drukhari_or_harlequins_unit(root):
            logger.error("ERROR: FATEFUL ROLE: target must be a Drukhari or Harlequins unit")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["drukhari_reapers_wager_fateful_role_active"] = True
        sr["drukhari_reapers_wager_fateful_role_threshold"] = 4
        sr["drukhari_reapers_wager_fateful_role_roll_modifier"] = 1 if self._drukhari_reapers_wager_unit_is_losing(root) else 0
        sr["drukhari_reapers_wager_fateful_role_expires_phase"] = "FIGHT_PHASE"
        sr["drukhari_reapers_wager_fateful_role_source"] = str(getattr(stratagem, "name", "FATEFUL ROLE") or "FATEFUL ROLE")
        if self.game is not None:
            sr["drukhari_reapers_wager_fateful_role_turn"] = int(getattr(self.game, "turn", 0) or 0)
        current_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        sr["drukhari_reapers_wager_fateful_role_turn_owner"] = str(
            getattr(current_player, "id", "") or getattr(self.player, "id", "") or ""
        )
        root.special_rules = sr
        self._drukhari_clear_unit_ability_cache(root)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: FATEFUL ROLE: %s fights on death on 4+%s until end of phase.",
            getattr(root, "name", "Unit"),
            " (+1 while losing the wager)" if int(sr.get("drukhari_reapers_wager_fateful_role_roll_modifier", 0) or 0) else "",
        )
        return True

    def _use_drukhari_reapers_wager_shorten_the_odds(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_reapers_wager():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        action_key = str(kwargs.get("action") or "").strip().lower()
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SHORTEN THE ODDS":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not action_key:
                    action_key = str(reaction.get("action", "") or "").strip().lower()
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SHORTEN THE ODDS: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = self._drukhari_normalized_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "")
        if phase_name != "movement phase":
            logger.error("ERROR: SHORTEN THE ODDS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SHORTEN THE ODDS: not your Movement phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: SHORTEN THE ODDS: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: SHORTEN THE ODDS: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SHORTEN THE ODDS: target cannot be selected")
            return False
        if not self._is_drukhari_or_harlequins_unit(root):
            logger.error("ERROR: SHORTEN THE ODDS: target must be a Drukhari or Harlequins unit")
            return False
        if action_key and action_key != "advance":
            logger.error("ERROR: SHORTEN THE ODDS: trigger unit must have Advanced")
            return False
        if not action_key and not bool(getattr(getattr(root, "round_state", None), "advanced_this_round", False)):
            logger.error("ERROR: SHORTEN THE ODDS: target must have Advanced this phase")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["drukhari_reapers_wager_shorten_the_odds_active"] = True
        sr["drukhari_reapers_wager_shorten_the_odds_source"] = str(getattr(stratagem, "name", "SHORTEN THE ODDS") or "SHORTEN THE ODDS")
        if self.game is not None:
            sr["drukhari_reapers_wager_shorten_the_odds_turn"] = int(getattr(self.game, "turn", 0) or 0)
        sr["drukhari_reapers_wager_shorten_the_odds_turn_owner"] = str(getattr(self.player, "id", "") or "")
        root.special_rules = sr
        self._drukhari_clear_unit_ability_cache(root)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: SHORTEN THE ODDS: %s can shoot and charge after Advancing this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_reapers_wager_dance_macabre(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_reapers_wager():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("moving_unit") or kwargs.get("attacking_unit")
        candidates = list(kwargs.get("candidates") or [])
        action_key = str(kwargs.get("action") or "").strip().lower()
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "DANCE MACABRE":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("moving_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not action_key:
                    action_key = str(reaction.get("action", "") or "").strip().lower()
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DANCE MACABRE: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        enemy_root = self._drukhari_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        phase_name = self._drukhari_normalized_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "")
        if phase_name != "movement phase":
            logger.error("ERROR: DANCE MACABRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: DANCE MACABRE: only in your opponent's Movement phase")
            return False
        if action_key and action_key not in {"move", "advance", "fall_back"}:
            logger.error("ERROR: DANCE MACABRE: trigger must be a Normal, Advance, or Fall Back move")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: DANCE MACABRE: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: DANCE MACABRE: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: DANCE MACABRE: target cannot be selected")
            return False
        if not self._is_drukhari_or_harlequins_infantry(root):
            logger.error("ERROR: DANCE MACABRE: target must be Drukhari Infantry or Harlequins Infantry")
            return False
        if self._drukhari_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: DANCE MACABRE: trigger unit must be enemy")
            return False
        if not self._drukhari_on_battlefield(enemy_root):
            return False
        distance = self._drukhari_distance_between_units(root, enemy_root)
        if distance is None or float(distance) > 9.0 + 1e-6:
            logger.error("ERROR: DANCE MACABRE: target must be within 9\" of the enemy unit")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: DANCE MACABRE: reactive move decision queue unavailable")
            return False
        max_distance = 6 if self._drukhari_reapers_wager_unit_is_losing(root) else dice_module.get_roll("D6")
        if max_distance <= 0:
            logger.error("ERROR: DANCE MACABRE: invalid move distance")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(max_distance),
            kind="drukhari_reapers_wager_dance_macabre",
            movement_type="move",
            reactive_movement_type="dance_macabre",
            source=str(getattr(stratagem, "name", "DANCE MACABRE") or "DANCE MACABRE"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            range_value=int(max_distance),
        )
        if request is None:
            logger.error("ERROR: DANCE MACABRE: failed to queue reactive move")
            return False
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: DANCE MACABRE: %s can make a Normal move of up to %d\".",
            getattr(root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_drukhari_skysplinter_swooping_mockery(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_skysplinter_assault():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("moving_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SWOOPING MOCKERY":
                    continue
                from_pending = True
                unit = reaction.get("unit") or reaction.get("target_unit")
                enemy_unit = enemy_unit or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                kwargs.setdefault("action", reaction.get("action"))
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SWOOPING MOCKERY: no target transport provided")
            return False

        root = self._drukhari_root(unit)
        enemy_root = self._drukhari_root(enemy_unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: SWOOPING MOCKERY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SWOOPING MOCKERY: not opponent's Movement phase")
            return False
        action_key = str(kwargs.get("action") or kwargs.get("trigger") or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back"}:
            logger.error("ERROR: SWOOPING MOCKERY: invalid trigger action")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: SWOOPING MOCKERY: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: SWOOPING MOCKERY: target transport is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SWOOPING MOCKERY: target cannot be selected")
            return False
        if not self._is_drukhari_transport(root):
            logger.error("ERROR: SWOOPING MOCKERY: target must be a Drukhari Transport")
            return False
        if enemy_root is None:
            logger.error("ERROR: SWOOPING MOCKERY: missing enemy trigger unit")
            return False
        if self._drukhari_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: SWOOPING MOCKERY: trigger unit is not enemy")
            return False
        if not self._drukhari_on_battlefield(enemy_root):
            return False
        dist = self._drukhari_distance_between_units(root, enemy_root)
        if dist is None or float(dist) > 9.0 + 1e-6:
            logger.error("ERROR: SWOOPING MOCKERY: target must be within 9\" of the enemy unit")
            return False
        if not from_pending and not action_key:
            logger.error("ERROR: SWOOPING MOCKERY: missing movement trigger context")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: SWOOPING MOCKERY: reactive move decision queue unavailable")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False

        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind="swooping_mockery",
            movement_type="move",
            source=stratagem.name,
            moving_unit=enemy_root,
        )
        if request is None:
            logger.error("ERROR: SWOOPING MOCKERY: failed to queue reactive move")
            return False

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: SWOOPING MOCKERY: %s can make a Normal move up to 6\".",
            getattr(root, "name", "Transport"),
        )
        return True

    def _use_drukhari_skysplinter_vicious_blades(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_skysplinter_assault():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("enemy_target") or kwargs.get("selected_enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_candidates = list(kwargs.get("enemy_candidates") or [])
        if unit is None or not enemy_candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "VICIOUS BLADES":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                enemy_unit = enemy_unit or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not enemy_candidates:
                    enemy_candidates = list(reaction.get("enemy_candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VICIOUS BLADES: no target transport provided")
            return False

        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: VICIOUS BLADES: wrong phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: VICIOUS BLADES: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: VICIOUS BLADES: target transport is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: VICIOUS BLADES: target cannot be selected")
            return False
        if not self._is_drukhari_transport(root):
            logger.error("ERROR: VICIOUS BLADES: target must be a Drukhari Transport")
            return False

        if not enemy_candidates:
            recent_targets = list(getattr(getattr(root, "round_state", None), "last_fight_targets", []) or [])
            enemy_candidates = list(recent_targets)
        enemy_roots: list[Any] = []
        seen_enemy_ids: set[str] = set()
        for candidate in list(enemy_candidates or []):
            enemy_root = self._drukhari_root(candidate)
            if enemy_root is None:
                continue
            uid = self._drukhari_sort_key(enemy_root)
            if uid and uid in seen_enemy_ids:
                continue
            if uid:
                seen_enemy_ids.add(uid)
            if self._drukhari_owned_by_player(enemy_root, self.player):
                continue
            if not self._drukhari_on_battlefield(enemy_root):
                continue
            enemy_roots.append(enemy_root)
        enemy_roots = sorted(enemy_roots, key=self._drukhari_sort_key)
        if not enemy_roots:
            logger.error("ERROR: VICIOUS BLADES: no eligible enemy target from selected fight targets")
            return False

        chosen_enemy_root = self._drukhari_root(enemy_unit)
        if chosen_enemy_root is None:
            chosen_enemy_root = enemy_roots[0]
        chosen_id = self._drukhari_sort_key(chosen_enemy_root)
        enemy_ids = [self._drukhari_sort_key(value) for value in enemy_roots]
        if chosen_id not in enemy_ids:
            logger.error("ERROR: VICIOUS BLADES: chosen enemy was not selected as a fight target")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["drukhari_vicious_blades_pending"] = True
        sr["drukhari_vicious_blades_owner"] = str(getattr(self.player, "id", "") or "")
        sr["drukhari_vicious_blades_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["drukhari_vicious_blades_source"] = str(getattr(stratagem, "name", "VICIOUS BLADES") or "VICIOUS BLADES")
        sr["drukhari_vicious_blades_target_ids"] = list(enemy_ids)
        sr["drukhari_vicious_blades_selected_target_id"] = str(chosen_id or "")
        root.special_rules = sr

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: VICIOUS BLADES: %s is primed to resolve post-fight mortal wounds into %s.",
            getattr(root, "name", "Transport"),
            getattr(chosen_enemy_root, "name", "Unit"),
        )
        return True

    def _use_drukhari_skysplinter_pounce_on_the_prey(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_skysplinter_assault():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        transport_unit = kwargs.get("transport_unit") or kwargs.get("transport")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "POUNCE ON THE PREY":
                    continue
                unit = unit or reaction.get("unit") or reaction.get("target_unit")
                transport_unit = transport_unit or reaction.get("transport_unit") or reaction.get("transport")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None:
            logger.error("ERROR: POUNCE ON THE PREY: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: POUNCE ON THE PREY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: POUNCE ON THE PREY: not your Movement phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: POUNCE ON THE PREY: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: POUNCE ON THE PREY: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: POUNCE ON THE PREY: target cannot be selected")
            return False
        if not self._is_drukhari_infantry(root):
            logger.error("ERROR: POUNCE ON THE PREY: target must be a Drukhari Infantry unit")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "disembarked_this_round", False)):
            logger.error("ERROR: POUNCE ON THE PREY: target did not disembark this round")
            return False
        transport_root = self._drukhari_root(transport_unit)
        if transport_root is None:
            transport_root = self._drukhari_resolve_friendly_transport_for_disembarked_unit(root)
        if transport_root is None:
            logger.error("ERROR: POUNCE ON THE PREY: transport context missing")
            return False
        if not self._is_drukhari_transport(transport_root):
            logger.error("ERROR: POUNCE ON THE PREY: disembark source must be a Drukhari Transport")
            return False
        if not self._drukhari_transport_made_normal_move_this_round(transport_root):
            logger.error("ERROR: POUNCE ON THE PREY: transport did not make a Normal move this phase")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False

        root.round_state.disembarked_cannot_charge = False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pounce_on_the_prey_active"] = True
        sr["pounce_on_the_prey_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["pounce_on_the_prey_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["pounce_on_the_prey_source"] = str(getattr(stratagem, "name", "POUNCE ON THE PREY") or "POUNCE ON THE PREY")
        root.special_rules = sr

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: POUNCE ON THE PREY: %s is eligible to declare a charge this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_drukhari_skysplinter_skyborne_annihilation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_skysplinter_assault():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SKYBORNE ANNIHILATION":
                    continue
                unit = unit or reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None:
            logger.error("ERROR: SKYBORNE ANNIHILATION: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SKYBORNE ANNIHILATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SKYBORNE ANNIHILATION: not your Shooting phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: SKYBORNE ANNIHILATION: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: SKYBORNE ANNIHILATION: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SKYBORNE ANNIHILATION: target cannot be selected")
            return False
        if not self._is_drukhari_unit(root):
            logger.error("ERROR: SKYBORNE ANNIHILATION: target must be a Drukhari unit")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: SKYBORNE ANNIHILATION: target has already been selected to shoot")
            return False
        if not bool(getattr(round_state, "disembarked_this_round", False)):
            logger.error("ERROR: SKYBORNE ANNIHILATION: target did not disembark this turn")
            return False
        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False

        sustained_hits_value = 2 if self._is_drukhari_kabalite_warriors_or_hand_of_the_archon_unit(root) else 1
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        prev_ranged_sustained = int(sr.get("bearer_unit_sustained_hits_value_ranged", 0) or 0)
        new_ranged_sustained = max(int(prev_ranged_sustained), int(sustained_hits_value))
        sr["drukhari_skyborne_annihilation_active"] = True
        sr["drukhari_skyborne_annihilation_expires_phase"] = "SHOOTING_PHASE"
        sr["drukhari_skyborne_annihilation_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["drukhari_skyborne_annihilation_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["drukhari_skyborne_annihilation_source"] = str(
            getattr(stratagem, "name", "SKYBORNE ANNIHILATION") or "SKYBORNE ANNIHILATION"
        )
        sr["drukhari_skyborne_annihilation_sustained_hits_value"] = int(sustained_hits_value)
        sr["drukhari_skyborne_annihilation_prev_sustained_ranged"] = int(prev_ranged_sustained)
        sr["drukhari_skyborne_annihilation_added_sustained_ranged"] = bool(
            int(new_ranged_sustained) != int(prev_ranged_sustained)
        )
        sr["bearer_unit_sustained_hits_value_ranged"] = int(new_ranged_sustained)
        root.special_rules = sr

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: SKYBORNE ANNIHILATION: %s gains [SUSTAINED HITS %d] on ranged weapons until end of phase.",
            getattr(root, "name", "Unit"),
            int(sustained_hits_value),
        )
        return True

    def _use_drukhari_skysplinter_wraithlike_retreat(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_drukhari_skysplinter_assault():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "WRAITHLIKE RETREAT":
                    continue
                unit = unit or reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None:
            logger.error("ERROR: WRAITHLIKE RETREAT: no target unit provided")
            return False
        root = self._drukhari_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: WRAITHLIKE RETREAT: wrong phase")
            return False
        if candidates and not self._drukhari_unit_in_candidates(root, candidates):
            logger.error("ERROR: WRAITHLIKE RETREAT: target is not currently eligible")
            return False
        if not self._drukhari_owned_by_player(root, self.player):
            logger.error("ERROR: WRAITHLIKE RETREAT: target unit is not yours")
            return False
        if not self._drukhari_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: WRAITHLIKE RETREAT: target cannot be selected")
            return False
        if not self._is_drukhari_infantry(root):
            logger.error("ERROR: WRAITHLIKE RETREAT: target must be a Drukhari Infantry unit")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: WRAITHLIKE RETREAT: target must have fought this phase")
            return False

        engaged = self._drukhari_has_enemy_within_engagement_range(root)
        movement_type = "fall_back" if engaged else "move"
        if movement_type == "move":
            max_distance = 6
        else:
            max_distance = int(getattr(root, "movement", 0) or 0)
            if max_distance <= 0:
                max_distance = 1

        require_embark = not self._is_drukhari_wyches_unit(root)
        transport_ids: list[str] = []
        if require_embark:
            for transport in self._drukhari_friendly_transport_candidates():
                tid = self._drukhari_sort_key(transport)
                if not tid:
                    continue
                transport_ids.append(tid)
            if not transport_ids:
                logger.error("ERROR: WRAITHLIKE RETREAT: no friendly Drukhari Transport available for embark requirement")
                return False

        if not self._drukhari_spend_cp(stratagem, target_unit=root):
            return False

        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: WRAITHLIKE RETREAT: reactive move decision queue unavailable")
            return False

        extra_context = {
            "wraithlike_retreat_source": str(getattr(stratagem, "name", "WRAITHLIKE RETREAT") or "WRAITHLIKE RETREAT"),
            "wraithlike_retreat_require_embark": bool(require_embark),
            "wraithlike_retreat_transport_ids": list(transport_ids),
        }
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(max_distance),
            kind="wraithlike_retreat",
            movement_type=str(movement_type),
            source=str(getattr(stratagem, "name", "WRAITHLIKE RETREAT") or "WRAITHLIKE RETREAT"),
            allow_skip=True,
            extra_context=extra_context,
        )
        if request is None:
            logger.error("ERROR: WRAITHLIKE RETREAT: failed to queue move decision")
            return False

        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(stratagem.name or "").strip().upper())
        logger.info(
            "INFO: WRAITHLIKE RETREAT: %s can make a %s move.",
            getattr(root, "name", "Unit"),
            "Fall Back" if movement_type == "fall_back" else "Normal",
        )
        return True
