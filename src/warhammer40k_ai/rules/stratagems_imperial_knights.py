from __future__ import annotations

from typing import Any, Optional
import logging

from ..utility import dice as dice_module
from ..utility.entity_ids import maybe_entity_id

logger = logging.getLogger(__name__)


class ImperialKnightsStratagemMixin:
    @staticmethod
    def _ik_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ik_sort_key(unit: Any) -> str:
        return str(maybe_entity_id(unit) or "")

    def _ik_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "imperial_knights_detachments", None)

    def _is_valourstrike_lance(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_valourstrike_lance", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_gate_warden_lance(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_gate_warden_lance", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_freeblade_company(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_freeblade_company", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_questor_forgepact(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_questor_forgepact", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_questoris_companions(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_questoris_companions", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_spearhead_at_arms(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_spearhead_at_arms", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _ik_normalize_name(value: str) -> str:
        return (
            str(value or "")
            .replace("\u2019", "'")
            .replace("\u2010", "-")
            .replace("\u2011", "-")
            .replace("\u2012", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
            .strip()
            .upper()
        )

    @staticmethod
    def _ik_phase_name_key(value: Any) -> str:
        return str(value or "").replace("_", " ").strip().lower()

    @staticmethod
    def _ik_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _ik_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _ik_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "is_in_reserves", False))

    def _ik_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._ik_is_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _is_imperial_knights_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "_unit_is_imperial_knights", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword("IMPERIAL KNIGHTS"))
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "QI"

    @staticmethod
    def _ik_has_any_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and has_any(keyword):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and has_kw(keyword):
            return True
        return False

    def _ik_is_armiger_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None or not self._is_imperial_knights_unit(root):
            return False
        if self._ik_has_any_keyword(root, "ARMIGER"):
            return True
        return "ARMIGER" in str(getattr(root, "name", "") or "").strip().upper()

    def _ik_is_destrier_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None or not self._is_imperial_knights_unit(root):
            return False
        if self._ik_has_any_keyword(root, "DESTRIER"):
            return True
        return "DESTRIER" in str(getattr(root, "name", "") or "").strip().upper()

    def _ik_is_titanic_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None or not self._is_imperial_knights_unit(root):
            return False
        if self._ik_has_any_keyword(root, "TITANIC"):
            return True
        return bool(getattr(root, "is_titanic", False))

    def _ik_is_character_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        return bool(root is not None and self._ik_has_any_keyword(root, "CHARACTER"))

    def _ik_is_adeptus_mechanicus_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "_unit_is_adeptus_mechanicus", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return bool(self._ik_has_any_keyword(root, "ADEPTUS MECHANICUS"))

    @staticmethod
    def _ik_is_knight_preceptor_unit(unit: Any) -> bool:
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        name = str(getattr(root, "name", "") or "").replace("\u2019", "'").strip().lower()
        return name == "knight preceptor"

    def _ik_unit_models(self, unit: Any) -> list[Any]:
        root = self._ik_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        alive_models = [model for model in models if self._ik_model_is_alive(model)]
        alive_models.sort(key=lambda model: str(maybe_entity_id(model) or ""))
        return alive_models

    def _ik_army_roots(self) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    @staticmethod
    def _ik_display_phase_name(value: Any, *, default: str = "") -> str:
        text = str(value or "").strip()
        if not text:
            return str(default or "").strip()
        phase_key = text.upper()
        mapping = {
            "COMMAND_PHASE": "Command phase",
            "MOVEMENT_PHASE": "Movement phase",
            "SHOOTING_PHASE": "Shooting phase",
            "CHARGE_PHASE": "Charge phase",
            "FIGHT_PHASE": "Fight phase",
        }
        if phase_key in mapping:
            return mapping[phase_key]
        if phase_key.replace(" ", "_") in mapping:
            return mapping[phase_key.replace(" ", "_")]
        return text

    @staticmethod
    def _ik_phase_end_key(value: Any, *, fallback: str = "ANY_PHASE") -> str:
        text = str(value or "").strip()
        if not text:
            return str(fallback or "ANY_PHASE").strip().upper()
        phase_key = text.upper().replace(" ", "_")
        mapping = {
            "COMMAND_PHASE": "COMMAND_PHASE",
            "MOVEMENT_PHASE": "MOVEMENT_PHASE",
            "SHOOTING_PHASE": "SHOOTING_PHASE",
            "CHARGE_PHASE": "CHARGE_PHASE",
            "FIGHT_PHASE": "FIGHT_PHASE",
        }
        return mapping.get(phase_key, phase_key)

    def _ik_visible_to_enemy_unit(self, enemy_unit: Any, target_unit: Any) -> bool:
        enemy_root = self._ik_root(enemy_unit)
        target_root = self._ik_root(target_unit)
        if enemy_root is None or target_root is None:
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        has_los = getattr(enemy_root, "_attacking_unit_has_any_los_to_target_unit", None)
        if not callable(has_los) or game_map is None:
            return False
        return bool(has_los(target_root, game_map))

    def _questor_forgepact_aggression_begets_aggression_candidates(self) -> list[Any]:
        if not self._is_questor_forgepact():
            return []
        out: list[Any] = []
        for root in self._ik_army_roots():
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _questor_forgepact_aggression_begets_aggression_supporting_candidates(self, unit: Any) -> list[Any]:
        if not self._is_questor_forgepact():
            return []
        root = self._ik_root(unit)
        if root is None or not self._ik_is_character_unit(root):
            return []
        if not self._is_imperial_knights_unit(root):
            return []
        if not self._ik_on_battlefield(root, require_targetable=True):
            return []
        out: list[Any] = []
        for friendly in self._ik_army_roots():
            if friendly is root:
                continue
            if not self._ik_is_adeptus_mechanicus_unit(friendly):
                continue
            if not self._ik_on_battlefield(friendly, require_targetable=True):
                continue
            distance = self._ik_distance_between_units(root, friendly)
            if distance is None or float(distance) > 6.0 + 1e-6:
                continue
            out.append(friendly)
        return sorted(out, key=self._ik_sort_key)

    def _questor_forgepact_machine_focus_candidates(self) -> list[Any]:
        if not self._is_questor_forgepact():
            return []
        out: list[Any] = []
        for root in self._ik_army_roots():
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _questor_forgepact_thronegheist_fury_candidates(
        self,
        *,
        enemy_unit: Any,
        action: str = "",
    ) -> list[Any]:
        if not self._is_questor_forgepact():
            return []
        if self.game is None:
            return []
        enemy_root = self._ik_root(enemy_unit)
        if enemy_root is None or self._ik_owned_by_player(enemy_root, self.player):
            return []
        if not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return []
        action_key = str(action or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back", "set_up"}:
            return []
        reactive_can_shoot = getattr(self.game, "_setup_reactive_can_shoot_target", None)
        if not callable(reactive_can_shoot):
            return []

        out: list[Any] = []
        for root in self._ik_army_roots():
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_is_titanic_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            distance = self._ik_distance_between_units(root, enemy_root)
            if distance is None or float(distance) > 24.0 + 1e-6:
                continue
            if not self._ik_visible_to_enemy_unit(enemy_root, root):
                continue
            if not bool(reactive_can_shoot(root, enemy_root)):
                continue
            allowed_model_ids, allowed_wargear_ids = self._questor_forgepact_thronegheist_fury_allowed_selection(
                root,
                enemy_root,
            )
            if not allowed_model_ids or not allowed_wargear_ids:
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _questor_forgepact_thronegheist_fury_allowed_selection(
        self,
        unit: Any,
        enemy_unit: Any,
    ) -> tuple[list[str], list[str]]:
        allowed_pairs = self._questor_forgepact_thronegheist_fury_allowed_pairs(unit, enemy_unit)
        allowed_model_ids = sorted(
            {
                str(pair.get("model_id", "") or "").strip()
                for pair in list(allowed_pairs or [])
                if str(pair.get("model_id", "") or "").strip()
            }
        )
        allowed_wargear_ids = sorted(
            {
                str(pair.get("wargear_id", "") or "").strip()
                for pair in list(allowed_pairs or [])
                if str(pair.get("wargear_id", "") or "").strip()
            }
        )
        return allowed_model_ids, allowed_wargear_ids

    def _questor_forgepact_thronegheist_fury_allowed_pairs(
        self,
        unit: Any,
        enemy_unit: Any,
    ) -> list[dict[str, str]]:
        root = self._ik_root(unit)
        enemy_root = self._ik_root(enemy_unit)
        if root is None or enemy_root is None or self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        can_target = getattr(root, "_can_model_shoot_weapon_at_target", None)
        if not callable(can_target):
            return []

        allowed_pairs: list[dict[str, str]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for model in self._ik_unit_models(root):
            model_id = str(maybe_entity_id(model) or "").strip()
            if not model_id:
                continue
            for weapon in sorted(
                list(getattr(model, "wargear", []) or []),
                key=lambda item: str(maybe_entity_id(item) or ""),
            ):
                is_ranged = getattr(weapon, "is_ranged", None)
                if callable(is_ranged):
                    if not bool(is_ranged()):
                        continue
                elif str(getattr(weapon, "type", "") or "").strip().lower() != "ranged":
                    continue
                weapon_id = str(maybe_entity_id(weapon) or "").strip()
                if not weapon_id:
                    continue
                profiles = getattr(weapon, "profiles", {}) or {}
                for profile_name in sorted(profiles):
                    profile = profiles.get(profile_name)
                    if profile is None:
                        continue
                    if not bool(can_target(model, profile, enemy_root, game_map)):
                        continue
                    pair_key = (model_id, weapon_id)
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        allowed_pairs.append({"model_id": model_id, "wargear_id": weapon_id})
                    break
        allowed_pairs.sort(key=lambda pair: (str(pair.get("model_id", "") or ""), str(pair.get("wargear_id", "") or "")))
        return allowed_pairs

    def _questoris_companions_driven_by_the_past_candidates(self) -> list[Any]:
        if not self._is_questoris_companions():
            return []
        out: list[Any] = []
        for root in self._ik_army_roots():
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_is_titanic_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not bool(getattr(getattr(root, "round_state", None), "advanced_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _questoris_companions_unstoppable_warrior_candidates(self) -> list[Any]:
        if not self._is_questoris_companions():
            return []
        out: list[Any] = []
        for root in self._ik_army_roots():
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_is_titanic_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _questoris_companions_objective_pool(self) -> list[Any]:
        if self.game is None:
            return []
        pool: list[Any] = []
        game_map = getattr(self.game, "map", None)
        if game_map is not None:
            pool.extend(list(getattr(game_map, "objectives", []) or []))
        pool.extend(list(getattr(self.game, "objectives", []) or []))
        seen: set[str] = set()
        out: list[Any] = []
        for objective in pool:
            objective_id = str(maybe_entity_id(objective) or getattr(objective, "id", "") or "").strip()
            if not objective_id:
                objective_id = f"obj:{id(objective)}"
            if objective_id in seen:
                continue
            location = getattr(objective, "location", None)
            if location is None or bool(getattr(location, "removed", False)):
                continue
            seen.add(objective_id)
            out.append(objective)
        out.sort(key=lambda objective: str(maybe_entity_id(objective) or getattr(objective, "id", "") or f"obj:{id(objective)}"))
        return out

    def _questoris_companions_heros_tread_objective_candidates(self, unit: Any) -> list[Any]:
        if not self._is_questoris_companions() or self.game is None:
            return []
        root = self._ik_root(unit)
        if root is None:
            return []
        if not self._is_imperial_knights_unit(root) or not self._ik_is_titanic_unit(root):
            return []
        if not self._ik_on_battlefield(root, require_targetable=True):
            return []
        candidates: list[Any] = []
        for objective in self._questoris_companions_objective_pool():
            location = getattr(objective, "location", None)
            if location is None:
                continue
            if getattr(location, "controlling_player", None) is not self.player:
                continue
            within_objective = getattr(root, "is_within_objective_range", None)
            if not callable(within_objective) or not bool(within_objective(location)):
                continue
            candidates.append(objective)
        return candidates

    def _questoris_companions_heros_tread_candidates(self) -> list[Any]:
        if not self._is_questoris_companions():
            return []
        out: list[Any] = []
        for root in self._ik_army_roots():
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_is_titanic_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._questoris_companions_heros_tread_objective_candidates(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_vow_of_retribution_candidates(self) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    @staticmethod
    def _ik_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    @staticmethod
    def _ik_selected_to_fight_this_phase(unit: Any) -> bool:
        return bool(getattr(getattr(unit, "round_state", None), "fought_this_phase", False))

    def _ik_unit_in_engagement_range(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._ik_root(enemy)
            if enemy_root is None:
                continue
            if not self._ik_on_battlefield(enemy_root, require_targetable=False):
                continue
            if bool(is_within_engagement(root, enemy_root)):
                return True
        return False

    def _ik_has_deadly_demise(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        has_deadly = getattr(root, "has_deadly_demise", None)
        if not callable(has_deadly):
            return False
        try:
            return bool(has_deadly()[0])
        except Exception:
            return False

    def _ik_unit_within_battlefield_edge_distance(self, unit: Any, distance: float) -> bool:
        root = self._ik_root(unit)
        if root is None or self.game is None:
            return False
        try:
            dist = float(distance)
        except Exception:
            return False
        if dist <= 0.0:
            return False
        width = getattr(getattr(self.game, "battlefield", None), "width", None)
        height = getattr(getattr(self.game, "battlefield", None), "height", None)
        if width is None or height is None:
            game_map = getattr(self.game, "map", None)
            width = getattr(game_map, "width", None)
            height = getattr(game_map, "height", None)
        if width is None or height is None:
            return False
        models = self._ik_unit_models(root)
        if not models:
            return False
        for model in models:
            base = getattr(model, "model_base", None)
            if base is None:
                continue
            try:
                x = float(getattr(base, "x", 0.0))
                y = float(getattr(base, "y", 0.0))
                radius = float(getattr(base, "get_radius", lambda: 0.0)())
            except Exception:
                continue
            if (
                (x - radius) <= dist + 1e-6
                or ((float(width) - x) - radius) <= dist + 1e-6
                or (y - radius) <= dist + 1e-6
                or ((float(height) - y) - radius) <= dist + 1e-6
            ):
                return True
        return False

    def _freeblade_strength_from_exile_candidates(self, *, phase_name: str = "") -> list[Any]:
        if not self._is_freeblade_company():
            return []
        phase_key = self._ik_phase_name_key(phase_name or self._current_phase_name)
        if phase_key not in {"shooting phase", "fight phase"}:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for root in self._ik_army_roots():
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if phase_key == "shooting phase" and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if phase_key == "fight phase" and self._ik_selected_to_fight_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _freeblade_survivor_of_strife_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_freeblade_company():
            return []
        attacker_root = self._ik_root(attacking_unit)
        if attacker_root is None or self._ik_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _freeblade_flanking_manoeuvres_candidates(self) -> list[Any]:
        if not self._is_freeblade_company():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for root in self._ik_army_roots():
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_is_armiger_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if self._ik_unit_in_engagement_range(root):
                continue
            if not self._ik_unit_within_battlefield_edge_distance(root, 9.0):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _freeblade_point_blank_barrage_candidates(self) -> list[Any]:
        if not self._is_freeblade_company():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for root in self._ik_army_roots():
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _freeblade_noble_sacrifice_candidates(self, *, destroyed_unit: Any = None, destroyed_model: Any = None) -> list[Any]:
        if not self._is_freeblade_company():
            return []
        root = self._ik_root(destroyed_unit)
        if root is None or not self._ik_owned_by_player(root, self.player):
            return []
        if not self._is_imperial_knights_unit(root):
            return []
        if not self._ik_has_deadly_demise(root):
            return []
        if destroyed_model is None or self._ik_model_is_alive(destroyed_model):
            return []
        for model in list(getattr(root, "models", []) or []):
            if model is destroyed_model:
                continue
            if self._ik_model_is_alive(model):
                return []
        return [root]

    def _imperial_knights_gate_warden_drive_them_out_candidates(self, *, phase_name: str = "") -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        phase_key = self._ik_phase_name_key(phase_name or self._current_phase_name)
        if phase_key not in {"shooting phase", "fight phase"}:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if phase_key == "shooting phase" and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if phase_key == "fight phase" and self._ik_selected_to_fight_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_gate_warden_fortress_candidates(self) -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        mgr = self._ik_detachment_mgr()
        on_line = getattr(mgr, "is_unit_on_dauntless_defensive_line", None) if mgr is not None else None
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None or not callable(on_line):
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._ik_is_titanic_unit(root):
                continue
            if not bool(on_line(root, game=self.game, game_map=getattr(self.game, "map", None) if self.game is not None else None)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_gate_warden_lancebreaker_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        attacker_root = self._ik_root(attacking_unit)
        if attacker_root is None or self._ik_owned_by_player(attacker_root, self.player):
            return []
        mgr = self._ik_detachment_mgr()
        on_line = getattr(mgr, "is_unit_on_dauntless_defensive_line", None) if mgr is not None else None
        if not callable(on_line):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not bool(on_line(root, game=self.game, game_map=getattr(self.game, "map", None) if self.game is not None else None)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_gate_warden_marshal_candidates(self) -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if self._ik_selected_to_move_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_gate_warden_steadfast_candidates(self) -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        mgr = self._ik_detachment_mgr()
        on_line = getattr(mgr, "is_unit_on_dauntless_defensive_line", None) if mgr is not None else None
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None or not callable(on_line):
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if self._ik_selected_to_fight_this_phase(root):
                continue
            if not bool(on_line(root, game=self.game, game_map=getattr(self.game, "map", None) if self.game is not None else None)):
                continue
            if not self._ik_unit_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_gate_warden_titanic_bombardment_candidates(self) -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        mgr = self._ik_detachment_mgr()
        on_line = getattr(mgr, "is_unit_on_dauntless_defensive_line", None) if mgr is not None else None
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None or not callable(on_line):
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_imperial_knights_unit(root) or not self._ik_is_titanic_unit(root):
                continue
            if not bool(on_line(root, game=self.game, game_map=getattr(self.game, "map", None) if self.game is not None else None)):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if not bool(getattr(getattr(root, "round_state", None), "remained_stationary_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_full_tilt_candidates(self) -> list[Any]:
        if not self._is_valourstrike_lance() and not self._is_freeblade_company():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if self._ik_selected_to_move_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_full_tilt_tool_action_context(self) -> dict[str, Any]:
        return {"candidates": self._imperial_knights_full_tilt_candidates()}

    def _imperial_knights_can_use_full_tilt_tool_action(self, kwargs: dict[str, Any]) -> bool:
        root = self._ik_root((kwargs or {}).get("unit") or (kwargs or {}).get("target_unit"))
        if root is None:
            return False
        candidate_ids = {self._ik_sort_key(candidate) for candidate in self._imperial_knights_full_tilt_candidates()}
        return self._ik_sort_key(root) in candidate_ids

    def _imperial_knights_run_them_through_candidates(self) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if self._ik_selected_to_fight_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    @staticmethod
    def _ik_normalize_weapon_name(value: str) -> str:
        name = str(value or "").replace("\u2019", "'").replace("\u0192?T", "'").strip().lower()
        return " ".join(name.split())

    @classmethod
    def _ik_is_feet_weapon_name(cls, value: str) -> bool:
        name = cls._ik_normalize_weapon_name(value)
        return ("armoured feet" in name) or ("titanic feet" in name)

    @staticmethod
    def _ik_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        checker = getattr(model, "is_alive", None)
        if callable(checker):
            return bool(checker())
        try:
            return int(getattr(model, "wounds", 1) or 0) > 0
        except (TypeError, ValueError):
            return True

    def _ik_model_weapon_profiles(self, model: Any, *, attack_type: str) -> list[Any]:
        attack_type_key = str(attack_type or "").strip().lower()
        if attack_type_key not in {"melee", "ranged"}:
            return []
        profiles: list[Any] = []
        for wargear in list(getattr(model, "wargear", []) or []):
            is_melee = bool(callable(getattr(wargear, "is_melee", None)) and wargear.is_melee())
            is_ranged = bool(callable(getattr(wargear, "is_ranged", None)) and wargear.is_ranged())
            if attack_type_key == "melee" and not is_melee:
                continue
            if attack_type_key == "ranged" and not is_ranged:
                continue
            wargear_profiles = getattr(wargear, "profiles", {}) or {}
            for profile_name in sorted(wargear_profiles):
                profile = wargear_profiles.get(profile_name)
                if profile is not None:
                    profiles.append(profile)
        return profiles

    @classmethod
    def _ik_model_has_feet_melee_weapon(cls, model: Any) -> bool:
        for weapon in list(getattr(model, "wargear", []) or []):
            is_melee = getattr(weapon, "is_melee", None)
            if callable(is_melee):
                if not bool(is_melee()):
                    continue
            elif str(getattr(weapon, "type", "") or "").strip().lower() != "melee":
                continue
            if cls._ik_is_feet_weapon_name(getattr(weapon, "name", "")):
                return True
        return False

    def _ik_select_thunderstomp_model(self, unit: Any, *, requested_model: Any = None) -> Any:
        root = self._ik_root(unit)
        if root is None:
            return None
        models = list(getattr(root, "models", []) or [])
        if not models:
            return None
        if requested_model is not None:
            wanted_id = str(maybe_entity_id(requested_model) or "")
            for model in models:
                model_id = str(maybe_entity_id(model) or "")
                if model is not requested_model and (not wanted_id or not model_id or model_id != wanted_id):
                    continue
                if not self._ik_model_is_alive(model):
                    return None
                if not self._ik_model_has_feet_melee_weapon(model):
                    return None
                return model
            return None
        ordered_models = sorted(models, key=lambda m: str(maybe_entity_id(m) or ""))
        for model in ordered_models:
            if not self._ik_model_is_alive(model):
                continue
            if not self._ik_model_has_feet_melee_weapon(model):
                continue
            return model
        return None

    def _imperial_knights_thunderstomp_candidates(self) -> list[Any]:
        units = self._imperial_knights_run_them_through_candidates()
        out: list[Any] = []
        for root in list(units or []):
            if self._ik_select_thunderstomp_model(root) is None:
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    @staticmethod
    def _ik_unit_in_candidates(root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = str(maybe_entity_id(root) or "")
        for cand in list(candidates or []):
            cand_root = cand
            get_root = getattr(cand, "get_attached_unit_root", None)
            if callable(get_root):
                cand_root = get_root()
            if cand_root is root:
                return True
            cid = str(maybe_entity_id(cand_root) or "")
            if rid and cid and rid == cid:
                return True
        return False

    def _ik_distance_between_units(self, source_unit: Any, target_unit: Any) -> Optional[float]:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        get_dist = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
        if not callable(get_dist):
            return None
        source_root = self._ik_root(source_unit)
        target_root = self._ik_root(target_unit)
        if source_root is None or target_root is None:
            return None
        try:
            return float(get_dist(source_root, target_root))
        except (TypeError, ValueError):
            return None

    def _imperial_knights_tactical_foil_candidates(
        self,
        *,
        enemy_unit: Any,
        action: str = "",
    ) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        if enemy_unit is None:
            return []
        action_key = str(action or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back"}:
            return []
        enemy_root = self._ik_root(enemy_unit)
        if enemy_root is None:
            return []
        if self._ik_owned_by_player(enemy_root, self.player):
            return []
        if not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return []

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            dist = self._ik_distance_between_units(root, enemy_root)
            if dist is None or float(dist) > 9.0 + 1e-6:
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _ik_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        enemy_unit: Any = None,
        target_unit: Any = None,
    ) -> bool:
        wanted_name = self._ik_normalize_name(stratagem_name)
        wanted_phase = str(phase_name or "").strip().lower()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if self._ik_normalize_name(str(reaction.get("stratagem", "") or "")) != wanted_name:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != wanted_phase:
                continue
            if enemy_unit is not None and self._ik_root(reaction.get("enemy_unit")) is not self._ik_root(enemy_unit):
                continue
            reaction_target = reaction.get("target_unit") or reaction.get("unit")
            if target_unit is not None and self._ik_root(reaction_target) is not self._ik_root(target_unit):
                continue
            return True
        return False

    def _ik_pending_context(self, stratagem_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        wanted = self._ik_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._ik_normalize_name(reaction.get("stratagem", "")) != wanted:
                continue
            merged.update(dict(reaction))
            break
        for key, value in dict(kwargs or {}).items():
            if value is not None:
                merged[key] = value
        return merged

    def _imperial_knights_let_duty_be_your_shield_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        attacker_root = self._ik_root(attacking_unit)
        if attacker_root is None:
            return []
        if self._ik_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._ik_is_armiger_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_exemplars_wisdom_friendly_candidates(self, *, source_unit: Any = None) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        source_root = self._ik_root(source_unit)
        if source_root is None:
            return []
        source_id = self._ik_sort_key(source_root)
        if not source_id:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if root is source_root:
                continue
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._ik_is_armiger_unit(root):
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("bondsman_active")):
                continue
            if str(sr.get("bondsman_source_unit_id", "") or "").strip() != source_id:
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_exemplars_wisdom_enemy_candidates(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        attacker_root = self._ik_root(attacker_unit)
        if attacker_root is None or not self._ik_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        if isinstance(hits_by_target, dict):
            for unit, hits in list(hits_by_target.items()):
                try:
                    if int(hits or 0) <= 0:
                        continue
                except (TypeError, ValueError):
                    continue
                root = self._ik_root(unit)
                if root is None:
                    continue
                uid = self._ik_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                if self._ik_owned_by_player(root, self.player):
                    continue
                if not self._ik_on_battlefield(root, require_targetable=True):
                    continue
                out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_spearhead_armiger_targets(
        self,
        source_unit: Any,
        *,
        phase_name: str = "",
        reserve_only: bool = False,
    ) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        source_root = self._ik_root(source_unit)
        if source_root is None:
            return []
        if not self._ik_owned_by_player(source_root, self.player):
            return []
        if not self._ik_on_battlefield(source_root, require_targetable=True):
            return []
        if not self._is_imperial_knights_unit(source_root):
            return []
        phase_key = self._ik_phase_name_key(phase_name)

        def _eligible_armiger(root: Any) -> bool:
            if root is None:
                return False
            if not self._ik_owned_by_player(root, self.player):
                return False
            if not self._ik_on_battlefield(root, require_targetable=True):
                return False
            if not self._ik_is_armiger_unit(root):
                return False
            if phase_key == "shooting phase" and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                return False
            if phase_key == "fight phase" and self._ik_selected_to_fight_this_phase(root):
                return False
            if reserve_only:
                if self._ik_unit_in_engagement_range(root):
                    return False
                if not bool(self._unit_wholly_within_battlefield_edge_distance(root, 9.0)):
                    return False
            return True

        if self._ik_is_armiger_unit(source_root):
            return [source_root] if _eligible_armiger(source_root) else []
        if not self._ik_is_titanic_unit(source_root):
            return []
        if phase_key == "shooting phase" and bool(getattr(getattr(source_root, "round_state", None), "shot_this_round", False)):
            return []
        if phase_key == "fight phase" and self._ik_selected_to_fight_this_phase(source_root):
            return []
        bonded = self._imperial_knights_exemplars_wisdom_friendly_candidates(source_unit=source_root)
        return [root for root in list(bonded or []) if _eligible_armiger(root)]

    def _imperial_knights_spearhead_shooting_source_candidates(self) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        out: list[Any] = []
        for root in self._ik_army_roots():
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._imperial_knights_spearhead_armiger_targets(root, phase_name="Shooting phase"):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_spearhead_fight_source_candidates(self) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        out: list[Any] = []
        for root in self._ik_army_roots():
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._imperial_knights_spearhead_armiger_targets(root, phase_name="Fight phase"):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_spearhead_squires_source_candidates(self) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        out: list[Any] = []
        for root in self._ik_army_roots():
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._imperial_knights_spearhead_armiger_targets(root, reserve_only=True):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_spearhead_enemy_candidates(self) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        pool = list(getattr(game_map, "units", []) or []) if game_map is not None else []
        if not pool:
            for current_player in list(getattr(self.game, "players", []) or []) if self.game is not None else []:
                army = getattr(current_player, "army", None)
                pool.extend(list(getattr(army, "units", []) or []))
        for unit in pool:
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _queue_imperial_knights_spearhead_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_spearhead_at_arms():
            return
        if self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._ik_root(attacking_unit)
        if attacker_root is None or self._ik_owned_by_player(attacker_root, self.player):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("LET DUTY BE YOUR SHIELD")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_root,
        ):
            return
        candidates = self._imperial_knights_let_duty_be_your_shield_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        payload = {
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
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_freeblade_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_freeblade_company() or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._ik_root(attacking_unit)
        if attacker_root is None or self._ik_owned_by_player(attacker_root, self.player):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("SURVIVOR OF STRIFE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_root,
        ):
            return
        candidates = self._freeblade_survivor_of_strife_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        payload = {
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
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_imperial_knights_spearhead_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> None:
        if not self._is_spearhead_at_arms():
            return
        if self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        attacker_root = self._ik_root(attacker_unit)
        if attacker_root is None:
            return
        if not self._ik_owned_by_player(attacker_root, self.player):
            return
        if not self._ik_on_battlefield(attacker_root, require_targetable=True):
            return
        if not self._ik_is_titanic_unit(attacker_root):
            return

        stratagem = self.get_by_name("EXEMPLAR'S WISDOM") or self.get_by_name("EXEMPLAR’S WISDOM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_root,
        ):
            return
        friendly_candidates = self._imperial_knights_exemplars_wisdom_friendly_candidates(source_unit=attacker_root)
        if not friendly_candidates:
            return
        enemy_candidates = self._imperial_knights_exemplars_wisdom_enemy_candidates(
            attacker_unit=attacker_root,
            hits_by_target=hits_by_target,
        )
        if not enemy_candidates:
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": attacker_root,
            "source_unit": attacker_root,
            "friendly_candidates": friendly_candidates,
            "enemy_candidates": enemy_candidates,
            "hits_by_target": hits_by_target,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
            payload["target_unit"] = enemy_candidates[0]
        self._queue_reaction(payload)

    def _queue_imperial_knights_spearhead_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_spearhead_at_arms() or self.game is None:
            return
        if player is self.player:
            return
        phase_key = self._ik_phase_name_key(getattr(phase, "name", phase))
        if phase_key != "fight phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("SQUIRES OFTHE HUNT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        source_candidates = self._imperial_knights_spearhead_squires_source_candidates()
        if not source_candidates:
            return
        payload = {
            "event": "phase_end",
            "phase": phase,
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": source_candidates,
            "source_candidates": source_candidates,
        }
        if len(source_candidates) == 1:
            friendly_candidates = self._imperial_knights_spearhead_armiger_targets(source_candidates[0], reserve_only=True)
            payload["source_unit"] = source_candidates[0]
            payload["unit"] = source_candidates[0]
            payload["target_unit"] = source_candidates[0]
            payload["friendly_candidates"] = friendly_candidates
            if len(friendly_candidates) == 1:
                payload["selected_units"] = [friendly_candidates[0]]
        self._queue_reaction(payload, use_timer=False)

    def _queue_freeblade_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_freeblade_company() or self.game is None:
            return
        if player is self.player:
            return
        phase_key = self._ik_phase_name_key(getattr(phase, "name", phase))
        if phase_key != "fight phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("FLANKING MANOEUVRES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        candidates = self._freeblade_flanking_manoeuvres_candidates()
        if not candidates:
            return
        payload = {
            "event": "phase_end",
            "phase": phase,
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_imperial_knights_gate_warden_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_gate_warden_lance() or player is self.player:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "CHARGE_PHASE":
            return
        stratagem = self.get_by_name("FORTRESS OF INTIMIDATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._imperial_knights_gate_warden_fortress_candidates()
        if not candidates:
            return
        if self._ik_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Charge phase",
        ):
            return
        payload = {
            "event": "phase_start",
            "phase_name": "Charge phase",
            "phase": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _process_imperial_knights_gate_warden_charge_declared(
        self,
        *,
        charging_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_gate_warden_lance():
            return
        if self._ik_phase_name_key(self._current_phase_name) != "charge phase":
            return
        charging_root = self._ik_root(charging_unit)
        if charging_root is None or self._ik_owned_by_player(charging_root, self.player):
            return
        if not self._ik_on_battlefield(charging_root, require_targetable=False):
            return
        mgr = self._ik_detachment_mgr()
        effect_state = getattr(mgr, "_gate_warden_temporary_effect_state", None) if mgr is not None else None
        if not callable(effect_state):
            return
        active_target = None
        for unit in list(target_units or []):
            target_root = self._ik_root(unit)
            if target_root is None or not self._ik_owned_by_player(target_root, self.player):
                continue
            if not self._ik_on_battlefield(target_root, require_targetable=True):
                continue
            effect_root, effect_rules = effect_state(
                target_root,
                prefix="gate_warden_fortress_of_intimidation",
                game=self.game,
            )
            if effect_root is None or effect_rules is None:
                continue
            active_target = effect_root
            break
        if active_target is None:
            return
        sr = getattr(charging_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["battle_shock_test_modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0) - 1
        reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
        reasons.append("FORTRESS OF INTIMIDATION")
        sr["battle_shock_test_modifier_reasons"] = reasons
        charging_root.special_rules = sr
        take_test = getattr(charging_root, "take_battle_shock_test", None)
        if callable(take_test):
            take_test(int(getattr(self.game, "turn", 0) or 0))

    def _queue_imperial_knights_gate_warden_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_gate_warden_lance():
            return
        if self._ik_phase_name_key(self._current_phase_name) != "fight phase":
            return
        attacker_root = self._ik_root(attacking_unit)
        if attacker_root is None or self._ik_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("LANCEBREAKER")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._imperial_knights_gate_warden_lancebreaker_candidates(
            attacking_unit=attacker_root,
            target_units=list(target_units or []),
        )
        if not candidates:
            return
        if self._ik_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacker_root,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_imperial_knights_spearhead_phase_end_effects(self, *, phase: Any = None) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if phase_name == "MOVEMENT_PHASE":
                exp = str(sr.get("gate_warden_marshal_the_defence_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_marshal_the_defence_active") is True and (not exp or exp == phase_name):
                    remove_modifiers = getattr(root, "remove_characteristic_modifiers_by_source", None)
                    if callable(remove_modifiers):
                        remove_modifiers("stratagem:imperial_knights_marshal_the_defence")
                    for key in (
                        "gate_warden_marshal_the_defence_active",
                        "gate_warden_marshal_the_defence_expires_phase",
                        "gate_warden_marshal_the_defence_turn_owner",
                        "gate_warden_marshal_the_defence_turn",
                        "gate_warden_marshal_the_defence_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("freeblade_full_tilt_expires_phase", "") or "").strip().upper()
                if sr.get("freeblade_full_tilt_active") is True and (not exp or exp == phase_name):
                    effects = list(sr.get("advance_no_roll_effects", []) or [])
                    kept = [
                        entry
                        for entry in effects
                        if not (
                            isinstance(entry, dict)
                            and str(entry.get("tag", "") or "") == "stratagem:imperial_knights_freeblade_full_tilt"
                        )
                    ]
                    if kept:
                        sr["advance_no_roll_effects"] = kept
                    else:
                        sr.pop("advance_no_roll_effects", None)
                    for key in (
                        "freeblade_full_tilt_active",
                        "freeblade_full_tilt_distance",
                        "freeblade_full_tilt_expires_phase",
                        "freeblade_full_tilt_turn_owner",
                        "freeblade_full_tilt_turn",
                        "freeblade_full_tilt_source",
                    ):
                        sr.pop(key, None)
            if phase_name == "SHOOTING_PHASE":
                exp = str(sr.get("imperial_knights_exemplars_wisdom_expires_phase", "") or "").strip().upper()
                if sr.get("imperial_knights_exemplars_wisdom_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "imperial_knights_exemplars_wisdom_active",
                        "imperial_knights_exemplars_wisdom_ap_bonus",
                        "imperial_knights_exemplars_wisdom_target_id",
                        "imperial_knights_exemplars_wisdom_source_unit_id",
                        "imperial_knights_exemplars_wisdom_expires_phase",
                        "imperial_knights_exemplars_wisdom_turn_owner",
                        "imperial_knights_exemplars_wisdom_turn",
                        "imperial_knights_exemplars_wisdom_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("spearhead_mantle_of_the_mentor_expires_phase", "") or "").strip().upper()
                if sr.get("spearhead_mantle_of_the_mentor_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "spearhead_mantle_of_the_mentor_active",
                        "spearhead_mantle_of_the_mentor_expires_phase",
                        "spearhead_mantle_of_the_mentor_turn_owner",
                        "spearhead_mantle_of_the_mentor_turn",
                        "spearhead_mantle_of_the_mentor_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("spearhead_thin_their_ranks_expires_phase", "") or "").strip().upper()
                if sr.get("spearhead_thin_their_ranks_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "spearhead_thin_their_ranks_active",
                        "spearhead_thin_their_ranks_expires_phase",
                        "spearhead_thin_their_ranks_turn_owner",
                        "spearhead_thin_their_ranks_turn",
                        "spearhead_thin_their_ranks_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("gate_warden_drive_them_out_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_drive_them_out_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "gate_warden_drive_them_out_active",
                        "gate_warden_drive_them_out_crit_hit_threshold",
                        "gate_warden_drive_them_out_expires_phase",
                        "gate_warden_drive_them_out_turn_owner",
                        "gate_warden_drive_them_out_turn",
                        "gate_warden_drive_them_out_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("gate_warden_titanic_bombardment_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_titanic_bombardment_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "gate_warden_titanic_bombardment_active",
                        "gate_warden_titanic_bombardment_sustained_hits",
                        "gate_warden_titanic_bombardment_expires_phase",
                        "gate_warden_titanic_bombardment_turn_owner",
                        "gate_warden_titanic_bombardment_turn",
                        "gate_warden_titanic_bombardment_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("questor_forgepact_aggression_begets_aggression_expires_phase", "") or "").strip().upper()
                if sr.get("questor_forgepact_aggression_begets_aggression_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "questor_forgepact_aggression_begets_aggression_active",
                        "questor_forgepact_aggression_begets_aggression_expires_phase",
                        "questor_forgepact_aggression_begets_aggression_turn_owner",
                        "questor_forgepact_aggression_begets_aggression_turn",
                        "questor_forgepact_aggression_begets_aggression_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("freeblade_strength_from_exile_expires_phase", "") or "").strip().upper()
                if sr.get("freeblade_strength_from_exile_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "freeblade_strength_from_exile_active",
                        "freeblade_strength_from_exile_expires_phase",
                        "freeblade_strength_from_exile_turn_owner",
                        "freeblade_strength_from_exile_turn",
                        "freeblade_strength_from_exile_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("freeblade_point_blank_barrage_expires_phase", "") or "").strip().upper()
                if sr.get("freeblade_point_blank_barrage_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "freeblade_point_blank_barrage_active",
                        "freeblade_point_blank_barrage_expires_phase",
                        "freeblade_point_blank_barrage_turn_owner",
                        "freeblade_point_blank_barrage_turn",
                        "freeblade_point_blank_barrage_source",
                        "freeblade_point_blank_barrage_pending_mortal_wounds",
                    ):
                        sr.pop(key, None)
            if phase_name == "FIGHT_PHASE":
                exp = str(sr.get("gate_warden_drive_them_out_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_drive_them_out_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "gate_warden_drive_them_out_active",
                        "gate_warden_drive_them_out_crit_hit_threshold",
                        "gate_warden_drive_them_out_expires_phase",
                        "gate_warden_drive_them_out_turn_owner",
                        "gate_warden_drive_them_out_turn",
                        "gate_warden_drive_them_out_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("gate_warden_steadfast_superiority_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_steadfast_superiority_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "gate_warden_steadfast_superiority_active",
                        "gate_warden_steadfast_superiority_expires_phase",
                        "gate_warden_steadfast_superiority_turn_owner",
                        "gate_warden_steadfast_superiority_turn",
                        "gate_warden_steadfast_superiority_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("spearhead_virtue_of_courage_expires_phase", "") or "").strip().upper()
                if sr.get("spearhead_virtue_of_courage_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "spearhead_virtue_of_courage_active",
                        "spearhead_virtue_of_courage_hit_bonus",
                        "spearhead_virtue_of_courage_target_id",
                        "spearhead_virtue_of_courage_source_unit_id",
                        "spearhead_virtue_of_courage_expires_phase",
                        "spearhead_virtue_of_courage_turn_owner",
                        "spearhead_virtue_of_courage_turn",
                        "spearhead_virtue_of_courage_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("freeblade_strength_from_exile_expires_phase", "") or "").strip().upper()
                if sr.get("freeblade_strength_from_exile_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "freeblade_strength_from_exile_active",
                        "freeblade_strength_from_exile_expires_phase",
                        "freeblade_strength_from_exile_turn_owner",
                        "freeblade_strength_from_exile_turn",
                        "freeblade_strength_from_exile_source",
                    ):
                        sr.pop(key, None)
            if phase_name == "CHARGE_PHASE":
                exp = str(sr.get("gate_warden_fortress_of_intimidation_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_fortress_of_intimidation_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "gate_warden_fortress_of_intimidation_active",
                        "gate_warden_fortress_of_intimidation_battle_shock_modifier",
                        "gate_warden_fortress_of_intimidation_expires_phase",
                        "gate_warden_fortress_of_intimidation_turn_owner",
                        "gate_warden_fortress_of_intimidation_turn",
                        "gate_warden_fortress_of_intimidation_source",
                    ):
                        sr.pop(key, None)
            root.special_rules = sr

    def _queue_imperial_knights_valourstrike_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_valourstrike_lance():
            return
        if unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "fall_back"}:
            return
        enemy_root = self._ik_root(unit)
        if enemy_root is None:
            return
        if self._ik_owned_by_player(enemy_root, self.player):
            return
        if not self._ik_is_alive(enemy_root) or not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        stratagem = self.get_by_name("TACTICAL FOIL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            enemy_unit=enemy_root,
        ):
            return

        candidates = self._imperial_knights_tactical_foil_candidates(enemy_unit=enemy_root, action=action_key)
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
        self._queue_reaction(payload)

    def _queue_questor_forgepact_mortal_wound_reactions(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any = None,
        target_model: Any = None,
        phase_name: str = "",
    ) -> None:
        if not self._is_questor_forgepact():
            return
        root = self._ik_root(target_unit)
        if root is None or not self._ik_owned_by_player(root, self.player):
            return
        if not self._ik_on_battlefield(root, require_targetable=True):
            return
        if not (self._is_imperial_knights_unit(root) or self._ik_is_adeptus_mechanicus_unit(root)):
            return
        if not phase_name:
            phase_name = str(getattr(self, "_current_phase_name", "") or "").strip()
        if not phase_name and self.game is not None:
            phase_name = self._ik_display_phase_name(
                getattr(getattr(self.game, "phase", None), "name", "") or "",
                default="Any phase",
            )
        if not phase_name:
            phase_name = "Any phase"
        stratagem = self.get_by_name("OMNISSIAH'S GRACE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="mortal_wound_allocated",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            target_unit=root,
        ):
            return
        self._queue_reaction(
            {
                "event": "mortal_wound_allocated",
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "attacking_unit": attacker_unit,
                "target_model": target_model,
                "candidates": [root],
                "mortal_wound_allocated": True,
            },
            use_timer=False,
        )

    def _queue_questor_forgepact_unit_destroyed_reactions(
        self,
        *,
        destroyed_unit: Any,
        destroyed_by_unit: Any = None,
    ) -> None:
        if not self._is_questor_forgepact() or self.game is None:
            return
        root = self._ik_root(destroyed_unit)
        enemy_root = self._ik_root(destroyed_by_unit)
        if root is None or enemy_root is None:
            return
        if not self._ik_owned_by_player(root, self.player):
            return
        if not self._is_imperial_knights_unit(root):
            return
        if self._ik_owned_by_player(enemy_root, self.player):
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip() or self._ik_display_phase_name(
            getattr(getattr(self.game, "phase", None), "name", "") or "",
            default="Any phase",
        )
        stratagem = self.get_by_name("VENGEANCE OF THE MACHINE CULT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            enemy_unit=enemy_root,
            target_unit=root,
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "enemy_unit": enemy_root,
            },
            use_timer=False,
        )

    def _queue_freeblade_model_destroyed_reactions(
        self,
        *,
        unit: Any,
        model: Any,
    ) -> None:
        if not self._is_freeblade_company() or self.game is None:
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip() or self._ik_display_phase_name(
            getattr(getattr(self.game, "phase", None), "name", "") or "",
            default="Any phase",
        )
        stratagem = self.get_by_name("NOBLE SACRIFICE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._freeblade_noble_sacrifice_candidates(destroyed_unit=unit, destroyed_model=model)
        if not candidates:
            return
        root = candidates[0]
        if self._ik_reaction_already_queued(
            event_name="model_destroyed_before_removal",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            target_unit=root,
        ):
            return
        self._queue_reaction(
            {
                "event": "model_destroyed_before_removal",
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "destroyed_unit": root,
                "destroyed_model": model,
                "unit": root,
                "target_unit": root,
                "candidates": [root],
            },
            use_timer=False,
        )

    def _queue_questor_forgepact_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_questor_forgepact() or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "fall_back"}:
            return
        enemy_root = self._ik_root(unit)
        if enemy_root is None or self._ik_owned_by_player(enemy_root, self.player):
            return
        if not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("THRONEGHEIST FURY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            enemy_unit=enemy_root,
        ):
            return
        candidates = self._questor_forgepact_thronegheist_fury_candidates(enemy_unit=enemy_root, action=action_key)
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
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_questor_forgepact_set_up_reactions(self, *, unit: Any) -> None:
        if not self._is_questor_forgepact() or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        enemy_root = self._ik_root(unit)
        if enemy_root is None or self._ik_owned_by_player(enemy_root, self.player):
            return
        if not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("THRONEGHEIST FURY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="unit_set_up",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            enemy_unit=enemy_root,
        ):
            return
        candidates = self._questor_forgepact_thronegheist_fury_candidates(enemy_unit=enemy_root, action="set_up")
        if not candidates:
            return
        payload = {
            "event": "unit_set_up",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "action": "set_up",
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_questoris_companions_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_questoris_companions() or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key == "fallback":
            action_key = "fall_back"
        if action_key != "fall_back":
            return
        root = self._ik_root(unit)
        if root is None or not self._ik_owned_by_player(root, self.player):
            return
        if not self._ik_on_battlefield(root, require_targetable=True):
            return
        if not self._is_imperial_knights_unit(root) or not self._ik_is_titanic_unit(root):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        if not self._ik_unit_in_candidates(root, self._questoris_companions_unstoppable_warrior_candidates()):
            return
        stratagem = self.get_by_name("UNSTOPPABLE WARRIOR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            target_unit=root,
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "candidates": [root],
                "action": "fall_back",
            },
            use_timer=False,
        )

    def _queue_questoris_companions_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_questoris_companions() or self.game is None:
            return
        if player is not self.player:
            return
        phase_key = self._ik_phase_name_key(getattr(phase, "name", phase))
        if phase_key != "command phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        stratagem = self.get_by_name("HERO'S TREAD")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Command phase",
        ):
            return
        candidates = self._questoris_companions_heros_tread_candidates()
        if not candidates:
            return
        payload = {
            "event": "phase_end",
            "phase": phase,
            "phase_name": "Command phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            objective_candidates = self._questoris_companions_heros_tread_objective_candidates(candidates[0])
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
            payload["objective_candidates"] = objective_candidates
            if len(objective_candidates) == 1:
                payload["objective"] = objective_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _ik_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return bool(
            self.player.spend_command_points(
                int(cp_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _ik_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u:
                used.add(name_u)
            normalized = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
            if normalized:
                used.add(normalized)

    def _use_imperial_knights_valourstrike_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        stratagem_id = str(
            getattr(stratagem, "id", "")
            or getattr(stratagem, "stratagem_id", "")
            or ""
        ).strip()
        if name_u == "DRIVE THEM OUT!":
            return self._use_gate_warden_drive_them_out(stratagem, **kwargs)
        if name_u == "FORTRESS OF INTIMIDATION":
            return self._use_gate_warden_fortress_of_intimidation(stratagem, **kwargs)
        if name_u == "LANCEBREAKER":
            return self._use_gate_warden_lancebreaker(stratagem, **kwargs)
        if name_u == "MARSHAL THE DEFENCE":
            return self._use_gate_warden_marshal_the_defence(stratagem, **kwargs)
        if name_u == "STEADFAST SUPERIORITY":
            return self._use_gate_warden_steadfast_superiority(stratagem, **kwargs)
        if name_u == "TITANIC BOMBARDMENT":
            return self._use_gate_warden_titanic_bombardment(stratagem, **kwargs)
        if name_u == "VOW OF RETRIBUTION":
            return self._use_valourstrike_vow_of_retribution(stratagem, **kwargs)
        if name_u == "FULL TILT":
            if stratagem_id == "000010756004" or self._is_freeblade_company():
                return self._use_freeblade_full_tilt(stratagem, **kwargs)
            return self._use_valourstrike_full_tilt(stratagem, **kwargs)
        if name_u == "STRENGTH FROM EXILE":
            return self._use_freeblade_strength_from_exile(stratagem, **kwargs)
        if name_u == "NOBLE SACRIFICE":
            return self._use_freeblade_noble_sacrifice(stratagem, **kwargs)
        if name_u == "SURVIVOR OF STRIFE":
            return self._use_freeblade_survivor_of_strife(stratagem, **kwargs)
        if name_u == "FLANKING MANOEUVRES":
            return self._use_freeblade_flanking_manoeuvres(stratagem, **kwargs)
        if name_u == "POINT-BLANK BARRAGE":
            return self._use_freeblade_point_blank_barrage(stratagem, **kwargs)
        if name_u == "RUN THEM THROUGH!":
            return self._use_valourstrike_run_them_through(stratagem, **kwargs)
        if name_u == "THUNDERSTOMP":
            return self._use_valourstrike_thunderstomp(stratagem, **kwargs)
        if name_u == "TACTICAL FOIL":
            return self._use_valourstrike_tactical_foil(stratagem, **kwargs)
        if name_u == "LET DUTY BE YOUR SHIELD":
            return self._use_spearhead_let_duty_be_your_shield(stratagem, **kwargs)
        if name_u == "EXEMPLAR'S WISDOM":
            return self._use_spearhead_exemplars_wisdom(stratagem, **kwargs)
        if name_u == "MANTLE OF THE MENTOR":
            return self._use_spearhead_mantle_of_the_mentor(stratagem, **kwargs)
        if name_u == "SQUIRES OFTHE HUNT":
            return self._use_spearhead_squires_ofthe_hunt(stratagem, **kwargs)
        if name_u == "THIN THEIR RANKS":
            return self._use_spearhead_thin_their_ranks(stratagem, **kwargs)
        if name_u == "VIRTUE OF COURAGE":
            return self._use_spearhead_virtue_of_courage(stratagem, **kwargs)
        if name_u == "DRIVEN BY THE PAST":
            return self._use_questoris_companions_driven_by_the_past(stratagem, **kwargs)
        if name_u == "HERO'S TREAD":
            return self._use_questoris_companions_heros_tread(stratagem, **kwargs)
        if name_u == "UNSTOPPABLE WARRIOR":
            return self._use_questoris_companions_unstoppable_warrior(stratagem, **kwargs)
        if name_u == "AGGRESSION BEGETS AGGRESSION":
            return self._use_questor_forgepact_aggression_begets_aggression(stratagem, **kwargs)
        if name_u == "BONDED IMPERATIVE":
            return self._use_questor_forgepact_bonded_imperative(stratagem, **kwargs)
        if name_u == "MACHINE FOCUS":
            return self._use_questor_forgepact_machine_focus(stratagem, **kwargs)
        if name_u == "OMNISSIAH'S GRACE":
            return self._use_questor_forgepact_omnissiahs_grace(stratagem, **kwargs)
        if name_u == "THRONEGHEIST FURY":
            return self._use_questor_forgepact_thronegheist_fury(stratagem, **kwargs)
        if name_u == "VENGEANCE OF THE MACHINE CULT":
            return self._use_questor_forgepact_vengeance_of_the_machine_cult(stratagem, **kwargs)
        return None

    def _use_gate_warden_drive_them_out(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: DRIVE THEM OUT!: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_key == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: DRIVE THEM OUT!: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DRIVE THEM OUT!: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: DRIVE THEM OUT!: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: DRIVE THEM OUT!: target must be an IMPERIAL KNIGHTS unit")
            return False
        eligible = candidates or self._imperial_knights_gate_warden_drive_them_out_candidates(phase_name=phase_key)
        if eligible and not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: DRIVE THEM OUT!: target is not currently eligible")
            return False
        if phase_key == "shooting phase" and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: DRIVE THEM OUT!: target has already shot this phase")
            return False
        if phase_key == "fight phase" and self._ik_selected_to_fight_this_phase(root):
            logger.error("ERROR: DRIVE THEM OUT!: target has already fought this phase")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["gate_warden_drive_them_out_active"] = True
        sr["gate_warden_drive_them_out_crit_hit_threshold"] = 5
        sr["gate_warden_drive_them_out_expires_phase"] = "SHOOTING_PHASE" if phase_key == "shooting phase" else "FIGHT_PHASE"
        sr["gate_warden_drive_them_out_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["gate_warden_drive_them_out_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["gate_warden_drive_them_out_source"] = str(getattr(stratagem, "name", "") or "DRIVE THEM OUT!")
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DRIVE THEM OUT!: %s scores critical hits on 5+ when attacking enemies on the defensive line this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_gate_warden_fortress_of_intimidation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._ik_normalize_name(str(reaction.get("stratagem", "") or "")) != "FORTRESS OF INTIMIDATION":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FORTRESS OF INTIMIDATION: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "charge phase":
            logger.error("ERROR: FORTRESS OF INTIMIDATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: FORTRESS OF INTIMIDATION: not opponent's Charge phase")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: FORTRESS OF INTIMIDATION: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._ik_is_titanic_unit(root):
            logger.error("ERROR: FORTRESS OF INTIMIDATION: target must be a Titanic unit")
            return False
        eligible = candidates or self._imperial_knights_gate_warden_fortress_candidates()
        if eligible and not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: FORTRESS OF INTIMIDATION: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["gate_warden_fortress_of_intimidation_active"] = True
        sr["gate_warden_fortress_of_intimidation_battle_shock_modifier"] = -1
        sr["gate_warden_fortress_of_intimidation_expires_phase"] = "CHARGE_PHASE"
        sr["gate_warden_fortress_of_intimidation_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["gate_warden_fortress_of_intimidation_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["gate_warden_fortress_of_intimidation_source"] = str(
            getattr(stratagem, "name", "") or "FORTRESS OF INTIMIDATION"
        )
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FORTRESS OF INTIMIDATION: enemies charging %s take Battle-shock tests at -1 this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_gate_warden_lancebreaker(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or attacking_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._ik_normalize_name(str(reaction.get("stratagem", "") or "")) != "LANCEBREAKER":
                    continue
                unit = unit or reaction.get("unit") or reaction.get("target_unit")
                attacking_unit = attacking_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: LANCEBREAKER: no target unit provided")
            return False
        root = self._ik_root(unit)
        attacker_root = self._ik_root(attacking_unit)
        if root is None or attacker_root is None:
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "fight phase":
            logger.error("ERROR: LANCEBREAKER: wrong phase")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: LANCEBREAKER: target unit is not yours")
            return False
        if self._ik_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: LANCEBREAKER: attacking unit must be enemy")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._ik_on_battlefield(attacker_root, require_targetable=False):
            return False
        eligible = candidates or self._imperial_knights_gate_warden_lancebreaker_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if eligible and not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: LANCEBREAKER: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        self._append_defensive_effect(
            root,
            "defensive_wound_mods",
            {
                "value": 1,
                "attack_type": "any",
                "expires_phase": "FIGHT_PHASE",
                "source": str(getattr(stratagem, "name", "") or "LANCEBREAKER"),
                "requires_strength_gt_toughness": True,
            },
        )
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LANCEBREAKER: %s imposes -1 to wound against stronger attacks this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_gate_warden_marshal_the_defence(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "movement phase":
            logger.error("ERROR: MARSHAL THE DEFENCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MARSHAL THE DEFENCE: not your Movement phase")
            return False
        selected_units = kwargs.get("selected_units") or kwargs.get("units") or kwargs.get("target_units")
        if selected_units is None:
            single_unit = kwargs.get("unit") or kwargs.get("target_unit")
            selected_units = [single_unit] if single_unit is not None else []
        selected_roots_raw = list(selected_units or [])
        candidates = list(kwargs.get("candidates") or self._imperial_knights_gate_warden_marshal_candidates())
        selected_roots: list[Any] = []
        seen: set[str] = set()
        for unit in selected_roots_raw:
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            selected_roots.append(root)
        if not selected_roots and len(candidates) == 1:
            selected_roots = [candidates[0]]
        if not selected_roots:
            logger.error("ERROR: MARSHAL THE DEFENCE: no target units provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: MARSHAL THE DEFENCE: may target up to two units")
            return False
        for root in selected_roots:
            if not self._ik_unit_in_candidates(root, candidates):
                logger.error("ERROR: MARSHAL THE DEFENCE: one or more selected units are not eligible")
                return False
        if not self._ik_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False
        from ..utility.modifiers import Modifier, ModifierOp

        for root in selected_roots:
            remove_modifiers = getattr(root, "remove_characteristic_modifiers_by_source", None)
            if callable(remove_modifiers):
                remove_modifiers("stratagem:imperial_knights_marshal_the_defence")
            add_modifier = getattr(root, "add_characteristic_modifier", None)
            if callable(add_modifier):
                add_modifier(
                    "movement",
                    Modifier(ModifierOp.ADD, 3, source="stratagem:imperial_knights_marshal_the_defence"),
                )
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["gate_warden_marshal_the_defence_active"] = True
            sr["gate_warden_marshal_the_defence_expires_phase"] = "MOVEMENT_PHASE"
            sr["gate_warden_marshal_the_defence_turn_owner"] = str(getattr(self.player, "id", "") or "")
            sr["gate_warden_marshal_the_defence_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
            sr["gate_warden_marshal_the_defence_source"] = str(
                getattr(stratagem, "name", "") or "MARSHAL THE DEFENCE"
            )
            root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MARSHAL THE DEFENCE: %d unit(s) gain +3\" Move this phase.",
            len(selected_roots),
        )
        return True

    def _use_gate_warden_steadfast_superiority(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "fight phase":
            logger.error("ERROR: STEADFAST SUPERIORITY: wrong phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._imperial_knights_gate_warden_steadfast_candidates())
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: STEADFAST SUPERIORITY: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: STEADFAST SUPERIORITY: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["gate_warden_steadfast_superiority_active"] = True
        sr["gate_warden_steadfast_superiority_expires_phase"] = "FIGHT_PHASE"
        sr["gate_warden_steadfast_superiority_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["gate_warden_steadfast_superiority_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["gate_warden_steadfast_superiority_source"] = str(
            getattr(stratagem, "name", "") or "STEADFAST SUPERIORITY"
        )
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: STEADFAST SUPERIORITY: %s re-rolls melee Hit rolls this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_gate_warden_titanic_bombardment(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "shooting phase":
            logger.error("ERROR: TITANIC BOMBARDMENT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: TITANIC BOMBARDMENT: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._imperial_knights_gate_warden_titanic_bombardment_candidates())
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TITANIC BOMBARDMENT: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: TITANIC BOMBARDMENT: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["gate_warden_titanic_bombardment_active"] = True
        sr["gate_warden_titanic_bombardment_sustained_hits"] = 2
        sr["gate_warden_titanic_bombardment_expires_phase"] = "SHOOTING_PHASE"
        sr["gate_warden_titanic_bombardment_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["gate_warden_titanic_bombardment_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["gate_warden_titanic_bombardment_source"] = str(
            getattr(stratagem, "name", "") or "TITANIC BOMBARDMENT"
        )
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TITANIC BOMBARDMENT: %s gains [SUSTAINED HITS 2] on ranged weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_spearhead_let_duty_be_your_shield(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_spearhead_at_arms():
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacker_unit = kwargs.get("attacker_unit") or kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._ik_normalize_name(str(reaction.get("stratagem", "") or "")) != "LET DUTY BE YOUR SHIELD":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                attacker_unit = attacker_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: no target unit provided")
            return False
        if attacker_unit is None:
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: missing attacking unit context")
            return False

        root = self._ik_root(unit)
        attacker_root = self._ik_root(attacker_unit)
        if root is None or attacker_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: not opponent's Shooting phase")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: target is not currently eligible")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._ik_is_armiger_unit(root):
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: target must be an Armiger unit")
            return False
        if self._ik_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: attacking unit must be enemy")
            return False
        if not self._ik_on_battlefield(attacker_root, require_targetable=False):
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        if not self._apply_armour_of_contempt(root, attacker_root, amount=1):
            return False

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LET DUTY BE YOUR SHIELD: %s worsens AP by 1 against attacks from %s.",
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "Enemy unit"),
        )
        return True

    def _use_spearhead_exemplars_wisdom(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_spearhead_at_arms():
            return False

        source_unit = kwargs.get("source_unit") or kwargs.get("unit")
        selected_units = kwargs.get("selected_units") or kwargs.get("units") or kwargs.get("friendly_units")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_unit")
        friendly_candidates = list(kwargs.get("friendly_candidates") or [])
        enemy_candidates = list(kwargs.get("enemy_candidates") or kwargs.get("candidates") or [])
        hits_by_target = kwargs.get("hits_by_target")
        if source_unit is None or not friendly_candidates or not enemy_candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._ik_normalize_name(str(reaction.get("stratagem", "") or "")) != "EXEMPLAR'S WISDOM":
                    continue
                source_unit = source_unit or reaction.get("source_unit") or reaction.get("unit")
                if selected_units is None:
                    selected_units = reaction.get("selected_units") or reaction.get("friendly_units")
                enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("target_unit")
                if not friendly_candidates:
                    friendly_candidates = list(reaction.get("friendly_candidates") or [])
                if not enemy_candidates:
                    enemy_candidates = list(reaction.get("enemy_candidates") or reaction.get("candidates") or [])
                if hits_by_target is None:
                    hits_by_target = reaction.get("hits_by_target")
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        source_root = self._ik_root(source_unit)
        if source_root is None:
            logger.error("ERROR: EXEMPLAR'S WISDOM: missing Titanic source unit")
            return False
        selected_roots_raw = list(selected_units) if isinstance(selected_units, (list, tuple, set)) else ([selected_units] if selected_units is not None else [])
        selected_roots: list[Any] = []
        seen_selected: set[str] = set()
        for unit in list(selected_roots_raw or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen_selected:
                continue
            if uid:
                seen_selected.add(uid)
            selected_roots.append(root)
        if not selected_roots and len(friendly_candidates) == 1:
            selected_roots = [friendly_candidates[0]]
        enemy_root = self._ik_root(enemy_unit)
        if enemy_root is None and len(enemy_candidates) == 1:
            enemy_root = self._ik_root(enemy_candidates[0])
        if not selected_roots:
            logger.error("ERROR: EXEMPLAR'S WISDOM: no bonded Armiger targets selected")
            return False
        if enemy_root is None:
            logger.error("ERROR: EXEMPLAR'S WISDOM: no enemy target selected")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: EXEMPLAR'S WISDOM: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: EXEMPLAR'S WISDOM: not your Shooting phase")
            return False
        if not self._ik_owned_by_player(source_root, self.player):
            logger.error("ERROR: EXEMPLAR'S WISDOM: source unit is not yours")
            return False
        if not self._ik_on_battlefield(source_root, require_targetable=True):
            return False
        if not self._ik_is_titanic_unit(source_root):
            logger.error("ERROR: EXEMPLAR'S WISDOM: source must be a Titanic Imperial Knights unit")
            return False
        if not bool(getattr(getattr(source_root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: EXEMPLAR'S WISDOM: source must have just shot")
            return False
        eligible_friendly = friendly_candidates or self._imperial_knights_exemplars_wisdom_friendly_candidates(source_unit=source_root)
        for root in list(selected_roots):
            if not self._ik_unit_in_candidates(root, eligible_friendly):
                logger.error("ERROR: EXEMPLAR'S WISDOM: one or more selected Armiger units are not eligible")
                return False
        if self._ik_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: EXEMPLAR'S WISDOM: enemy target is invalid")
            return False
        eligible_enemy = enemy_candidates or self._imperial_knights_exemplars_wisdom_enemy_candidates(
            attacker_unit=source_root,
            hits_by_target=hits_by_target,
        )
        if eligible_enemy and not self._ik_unit_in_candidates(enemy_root, eligible_enemy):
            logger.error("ERROR: EXEMPLAR'S WISDOM: enemy target was not hit by the Titanic model")
            return False
        if not self._ik_on_battlefield(enemy_root, require_targetable=True):
            return False
        if not self._ik_spend_cp(stratagem, target_unit=source_root):
            return False

        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        enemy_id = self._ik_sort_key(enemy_root)
        source_id = self._ik_sort_key(source_root)
        for root in list(selected_roots):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["imperial_knights_exemplars_wisdom_active"] = True
            sr["imperial_knights_exemplars_wisdom_ap_bonus"] = 1
            sr["imperial_knights_exemplars_wisdom_target_id"] = enemy_id
            sr["imperial_knights_exemplars_wisdom_source_unit_id"] = source_id
            sr["imperial_knights_exemplars_wisdom_expires_phase"] = "SHOOTING_PHASE"
            sr["imperial_knights_exemplars_wisdom_turn_owner"] = owner_id
            sr["imperial_knights_exemplars_wisdom_turn"] = turn
            sr["imperial_knights_exemplars_wisdom_source"] = str(getattr(stratagem, "name", "") or "EXEMPLAR'S WISDOM")
            root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: EXEMPLAR'S WISDOM: %d Armiger unit(s) improve AP by 1 against %s this phase.",
            len(selected_roots),
            getattr(enemy_root, "name", "Enemy unit"),
        )
        return True

    def _use_spearhead_mantle_of_the_mentor(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_spearhead_at_arms():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        source_unit = merged.get("source_unit") or merged.get("unit") or merged.get("target_unit")
        source_candidates = list(merged.get("source_candidates") or merged.get("candidates") or [])
        if source_unit is None and len(source_candidates) == 1:
            source_unit = source_candidates[0]
        if source_unit is None:
            logger.error("ERROR: MANTLE OF THE MENTOR: no source unit provided")
            return False
        source_root = self._ik_root(source_unit)
        if source_root is None:
            return False
        phase_key = self._ik_phase_name_key(merged.get("phase_name") or self._current_phase_name)
        if phase_key != "shooting phase":
            logger.error("ERROR: MANTLE OF THE MENTOR: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MANTLE OF THE MENTOR: not your Shooting phase")
            return False
        if source_candidates and not self._ik_unit_in_candidates(source_root, source_candidates):
            logger.error("ERROR: MANTLE OF THE MENTOR: source unit is not currently eligible")
            return False
        selected_units = merged.get("selected_units") or merged.get("units") or merged.get("friendly_units")
        eligible = list(merged.get("friendly_candidates") or self._imperial_knights_spearhead_armiger_targets(source_root, phase_name="Shooting phase"))
        selected_raw = (
            list(selected_units)
            if isinstance(selected_units, (list, tuple, set))
            else ([selected_units] if selected_units is not None else [])
        )
        selected_roots: list[Any] = []
        seen: set[str] = set()
        for unit in list(selected_raw or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            selected_roots.append(root)
        if not selected_roots and len(eligible) == 1:
            selected_roots = [eligible[0]]
        if not selected_roots:
            logger.error("ERROR: MANTLE OF THE MENTOR: no Armiger units selected")
            return False
        for root in list(selected_roots):
            if not self._ik_unit_in_candidates(root, eligible):
                logger.error("ERROR: MANTLE OF THE MENTOR: one or more selected Armiger units are not eligible")
                return False
        if not self._ik_spend_cp(stratagem, target_unit=source_root):
            return False
        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        for root in list(selected_roots):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["spearhead_mantle_of_the_mentor_active"] = True
            sr["spearhead_mantle_of_the_mentor_expires_phase"] = "SHOOTING_PHASE"
            sr["spearhead_mantle_of_the_mentor_turn_owner"] = owner_id
            sr["spearhead_mantle_of_the_mentor_turn"] = turn
            sr["spearhead_mantle_of_the_mentor_source"] = str(getattr(stratagem, "name", "") or "MANTLE OF THE MENTOR")
            root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MANTLE OF THE MENTOR: %d Armiger unit(s) can shoot this phase despite Falling Back.",
            len(selected_roots),
        )
        return True

    def _use_spearhead_thin_their_ranks(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_spearhead_at_arms():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        source_unit = merged.get("source_unit") or merged.get("unit") or merged.get("target_unit")
        source_candidates = list(merged.get("source_candidates") or merged.get("candidates") or [])
        if source_unit is None and len(source_candidates) == 1:
            source_unit = source_candidates[0]
        if source_unit is None:
            logger.error("ERROR: THIN THEIR RANKS: no source unit provided")
            return False
        source_root = self._ik_root(source_unit)
        if source_root is None:
            return False
        phase_key = self._ik_phase_name_key(merged.get("phase_name") or self._current_phase_name)
        if phase_key != "shooting phase":
            logger.error("ERROR: THIN THEIR RANKS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: THIN THEIR RANKS: not your Shooting phase")
            return False
        if source_candidates and not self._ik_unit_in_candidates(source_root, source_candidates):
            logger.error("ERROR: THIN THEIR RANKS: source unit is not currently eligible")
            return False
        selected_units = merged.get("selected_units") or merged.get("units") or merged.get("friendly_units")
        eligible = list(merged.get("friendly_candidates") or self._imperial_knights_spearhead_armiger_targets(source_root, phase_name="Shooting phase"))
        selected_raw = (
            list(selected_units)
            if isinstance(selected_units, (list, tuple, set))
            else ([selected_units] if selected_units is not None else [])
        )
        selected_roots: list[Any] = []
        seen: set[str] = set()
        for unit in list(selected_raw or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            selected_roots.append(root)
        if not selected_roots and len(eligible) == 1:
            selected_roots = [eligible[0]]
        if not selected_roots:
            logger.error("ERROR: THIN THEIR RANKS: no Armiger units selected")
            return False
        for root in list(selected_roots):
            if not self._ik_unit_in_candidates(root, eligible):
                logger.error("ERROR: THIN THEIR RANKS: one or more selected Armiger units are not eligible")
                return False
        if not self._ik_spend_cp(stratagem, target_unit=source_root):
            return False
        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        for root in list(selected_roots):
            for model in self._ik_unit_models(root):
                model_id = str(maybe_entity_id(model) or "")
                for profile in self._ik_model_weapon_profiles(model, attack_type="ranged"):
                    lookup_name = getattr(profile, "_temporary_weapon_lookup_name", None)
                    weapon_name = lookup_name() if callable(lookup_name) else str(getattr(profile, "name", "") or "")
                    if not weapon_name:
                        continue
                    setter = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                    if callable(setter):
                        setter(
                            key=f"spearhead_thin_their_ranks:{self._ik_sort_key(root)}:{model_id}:{weapon_name}",
                            weapon_name=weapon_name,
                            keywords=["RAPID FIRE 1"],
                            source=str(getattr(stratagem, "name", "") or "THIN THEIR RANKS"),
                            expires_phase="SHOOTING_PHASE",
                            attack_type="ranged",
                        )
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["spearhead_thin_their_ranks_active"] = True
            sr["spearhead_thin_their_ranks_expires_phase"] = "SHOOTING_PHASE"
            sr["spearhead_thin_their_ranks_turn_owner"] = owner_id
            sr["spearhead_thin_their_ranks_turn"] = turn
            sr["spearhead_thin_their_ranks_source"] = str(getattr(stratagem, "name", "") or "THIN THEIR RANKS")
            root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: THIN THEIR RANKS: %d Armiger unit(s) gain [RAPID FIRE 1] on ranged weapons this phase.",
            len(selected_roots),
        )
        return True

    def _use_spearhead_virtue_of_courage(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_spearhead_at_arms():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        source_unit = merged.get("source_unit") or merged.get("unit") or merged.get("target_unit")
        source_candidates = list(merged.get("source_candidates") or merged.get("candidates") or [])
        if source_unit is None and len(source_candidates) == 1:
            source_unit = source_candidates[0]
        if source_unit is None:
            logger.error("ERROR: VIRTUE OF COURAGE: no source unit provided")
            return False
        source_root = self._ik_root(source_unit)
        if source_root is None:
            return False
        phase_key = self._ik_phase_name_key(merged.get("phase_name") or self._current_phase_name)
        if phase_key != "fight phase":
            logger.error("ERROR: VIRTUE OF COURAGE: wrong phase")
            return False
        if source_candidates and not self._ik_unit_in_candidates(source_root, source_candidates):
            logger.error("ERROR: VIRTUE OF COURAGE: source unit is not currently eligible")
            return False
        selected_units = merged.get("selected_units") or merged.get("units") or merged.get("friendly_units")
        eligible = list(merged.get("friendly_candidates") or self._imperial_knights_spearhead_armiger_targets(source_root, phase_name="Fight phase"))
        selected_raw = (
            list(selected_units)
            if isinstance(selected_units, (list, tuple, set))
            else ([selected_units] if selected_units is not None else [])
        )
        selected_roots: list[Any] = []
        seen: set[str] = set()
        for unit in list(selected_raw or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            selected_roots.append(root)
        if not selected_roots and len(eligible) == 1:
            selected_roots = [eligible[0]]
        if not selected_roots:
            logger.error("ERROR: VIRTUE OF COURAGE: no Armiger units selected")
            return False
        for root in list(selected_roots):
            if not self._ik_unit_in_candidates(root, eligible):
                logger.error("ERROR: VIRTUE OF COURAGE: one or more selected Armiger units are not eligible")
                return False
        enemy_root = self._ik_root(merged.get("enemy_unit") or merged.get("target_enemy_unit") or merged.get("selected_enemy_unit"))
        enemy_candidates = list(merged.get("enemy_candidates") or self._imperial_knights_spearhead_enemy_candidates())
        if enemy_root is None and len(enemy_candidates) == 1:
            enemy_root = self._ik_root(enemy_candidates[0])
        if enemy_root is None:
            logger.error("ERROR: VIRTUE OF COURAGE: no enemy unit selected")
            return False
        if enemy_candidates and not self._ik_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error("ERROR: VIRTUE OF COURAGE: enemy unit is not currently eligible")
            return False
        if not self._ik_on_battlefield(enemy_root, require_targetable=True):
            return False
        if self._ik_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: VIRTUE OF COURAGE: enemy unit is invalid")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=source_root):
            return False
        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        enemy_id = self._ik_sort_key(enemy_root)
        source_id = self._ik_sort_key(source_root)
        for root in list(selected_roots):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["spearhead_virtue_of_courage_active"] = True
            sr["spearhead_virtue_of_courage_hit_bonus"] = 1
            sr["spearhead_virtue_of_courage_target_id"] = enemy_id
            sr["spearhead_virtue_of_courage_source_unit_id"] = source_id
            sr["spearhead_virtue_of_courage_expires_phase"] = "FIGHT_PHASE"
            sr["spearhead_virtue_of_courage_turn_owner"] = owner_id
            sr["spearhead_virtue_of_courage_turn"] = turn
            sr["spearhead_virtue_of_courage_source"] = str(getattr(stratagem, "name", "") or "VIRTUE OF COURAGE")
            root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: VIRTUE OF COURAGE: %d Armiger unit(s) gain +1 to hit against %s this phase.",
            len(selected_roots),
            getattr(enemy_root, "name", "Enemy unit"),
        )
        return True

    def _use_spearhead_squires_ofthe_hunt(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_spearhead_at_arms():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        source_unit = merged.get("source_unit") or merged.get("unit") or merged.get("target_unit")
        source_candidates = list(merged.get("source_candidates") or merged.get("candidates") or [])
        if source_unit is None and len(source_candidates) == 1:
            source_unit = source_candidates[0]
        if source_unit is None:
            logger.error("ERROR: SQUIRES OFTHE HUNT: no source unit provided")
            return False
        source_root = self._ik_root(source_unit)
        if source_root is None:
            return False
        phase_key = self._ik_phase_name_key(merged.get("phase_name") or self._current_phase_name)
        if phase_key != "fight phase":
            logger.error("ERROR: SQUIRES OFTHE HUNT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SQUIRES OFTHE HUNT: not your opponent's Fight phase")
            return False
        if str(merged.get("event", "") or "").strip().lower() != "phase_end":
            logger.error("ERROR: SQUIRES OFTHE HUNT: requires the end of your opponent's Fight phase")
            return False
        if source_candidates and not self._ik_unit_in_candidates(source_root, source_candidates):
            logger.error("ERROR: SQUIRES OFTHE HUNT: source unit is not currently eligible")
            return False
        selected_units = merged.get("selected_units") or merged.get("units") or merged.get("friendly_units")
        eligible = list(merged.get("friendly_candidates") or self._imperial_knights_spearhead_armiger_targets(source_root, reserve_only=True))
        selected_raw = (
            list(selected_units)
            if isinstance(selected_units, (list, tuple, set))
            else ([selected_units] if selected_units is not None else [])
        )
        selected_roots: list[Any] = []
        seen: set[str] = set()
        for unit in list(selected_raw or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            selected_roots.append(root)
        if not selected_roots and len(eligible) == 1:
            selected_roots = [eligible[0]]
        if not selected_roots:
            logger.error("ERROR: SQUIRES OFTHE HUNT: no Armiger units selected")
            return False
        for root in list(selected_roots):
            if not self._ik_unit_in_candidates(root, eligible):
                logger.error("ERROR: SQUIRES OFTHE HUNT: one or more selected Armiger units are not eligible")
                return False
        if not self._ik_spend_cp(stratagem, target_unit=source_root):
            return False
        moved_units = 0
        for root in list(selected_roots):
            enter_reserves = getattr(root, "enter_strategic_reserves_midgame", None)
            if callable(enter_reserves) and bool(
                enter_reserves(
                    game=self.game,
                    game_map=getattr(self.game, "map", None) if self.game is not None else None,
                    reason=str(getattr(stratagem, "name", "") or "SQUIRES OFTHE HUNT"),
                )
            ):
                moved_units += 1
        if moved_units <= 0:
            logger.error("ERROR: SQUIRES OFTHE HUNT: no selected Armiger units entered Strategic Reserves")
            return False
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SQUIRES OFTHE HUNT: %d Armiger unit(s) entered Strategic Reserves.",
            moved_units,
        )
        return True

    def _use_freeblade_full_tilt(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freeblade_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: FULL TILT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FULL TILT: not your Movement phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._imperial_knights_full_tilt_candidates())
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FULL TILT: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: FULL TILT: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: FULL TILT: target must be an IMPERIAL KNIGHTS unit")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: FULL TILT: target is not currently eligible")
            return False
        if self._ik_selected_to_move_this_phase(root):
            logger.error("ERROR: FULL TILT: target has already been selected to move this phase")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        fixed_distance = 9 if (self._ik_is_armiger_unit(root) or self._ik_is_destrier_unit(root)) else 6
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        effect_tag = "stratagem:imperial_knights_freeblade_full_tilt"
        effects = [
            entry
            for entry in list(sr.get("advance_no_roll_effects", []) or [])
            if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == effect_tag)
        ]
        effects.append(
            {
                "distance": int(fixed_distance),
                "source": str(getattr(stratagem, "name", "") or "FULL TILT"),
                "tag": effect_tag,
                "expires_phase": "MOVEMENT_PHASE",
            }
        )
        sr["advance_no_roll_effects"] = effects
        sr["freeblade_full_tilt_active"] = True
        sr["freeblade_full_tilt_distance"] = int(fixed_distance)
        sr["freeblade_full_tilt_expires_phase"] = "MOVEMENT_PHASE"
        sr["freeblade_full_tilt_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["freeblade_full_tilt_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["freeblade_full_tilt_source"] = str(getattr(stratagem, "name", "") or "FULL TILT")
        root.special_rules = sr
        refresh = getattr(root, "_refresh_advance_no_roll_flags", None)
        if callable(refresh):
            refresh()
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FULL TILT: %s advances a fixed %d\" this phase.",
            getattr(root, "name", "Unit"),
            int(fixed_distance),
        )
        return True

    def _use_freeblade_strength_from_exile(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freeblade_company():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: STRENGTH FROM EXILE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_key == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: STRENGTH FROM EXILE: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._freeblade_strength_from_exile_candidates(phase_name=phase_key))
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: STRENGTH FROM EXILE: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: STRENGTH FROM EXILE: target unit is not yours")
            return False
        if not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: STRENGTH FROM EXILE: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        expires_phase = "SHOOTING_PHASE" if phase_key == "shooting phase" else "FIGHT_PHASE"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["freeblade_strength_from_exile_active"] = True
        sr["freeblade_strength_from_exile_expires_phase"] = expires_phase
        sr["freeblade_strength_from_exile_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["freeblade_strength_from_exile_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["freeblade_strength_from_exile_source"] = str(getattr(stratagem, "name", "") or "STRENGTH FROM EXILE")
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: STRENGTH FROM EXILE: %s can re-roll Hit/Wound rolls of 1 while isolated this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_freeblade_survivor_of_strife(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freeblade_company():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or attacking_unit is None:
            merged = self._ik_pending_context(stratagem.name, kwargs)
            unit = unit or merged.get("unit") or merged.get("target_unit")
            attacking_unit = attacking_unit or merged.get("attacking_unit") or merged.get("enemy_unit")
            if not target_units:
                target_units = list(merged.get("target_units") or [])
            if not candidates:
                candidates = list(merged.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SURVIVOR OF STRIFE: no target unit provided")
            return False
        root = self._ik_root(unit)
        attacker_root = self._ik_root(attacking_unit)
        if root is None or attacker_root is None:
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "shooting phase":
            logger.error("ERROR: SURVIVOR OF STRIFE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SURVIVOR OF STRIFE: not your opponent's Shooting phase")
            return False
        eligible = candidates or self._freeblade_survivor_of_strife_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: SURVIVOR OF STRIFE: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        self._append_defensive_effect(
            root,
            "defensive_wound_mods",
            {
                "value": 1,
                "attack_type": "any",
                "expires_phase": "SHOOTING_PHASE",
                "source": str(getattr(stratagem, "name", "") or "SURVIVOR OF STRIFE"),
                "requires_strength_gt_toughness": True,
            },
        )
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SURVIVOR OF STRIFE: %s imposes -1 to wound against stronger attacks this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_freeblade_flanking_manoeuvres(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freeblade_company():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        unit = merged.get("unit") or merged.get("target_unit")
        candidates = list(merged.get("candidates") or self._freeblade_flanking_manoeuvres_candidates())
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FLANKING MANOEUVRES: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        phase_key = self._ik_phase_name_key(merged.get("phase_name") or self._current_phase_name)
        if phase_key != "fight phase":
            logger.error("ERROR: FLANKING MANOEUVRES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: FLANKING MANOEUVRES: not your opponent's Fight phase")
            return False
        if str(merged.get("event", "") or "").strip().lower() != "phase_end":
            logger.error("ERROR: FLANKING MANOEUVRES: requires the end of your opponent's Fight phase")
            return False
        if not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: FLANKING MANOEUVRES: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        enter_reserves = getattr(root, "enter_strategic_reserves_midgame", None)
        if not callable(enter_reserves) or not bool(
            enter_reserves(
                game=self.game,
                game_map=getattr(self.game, "map", None) if self.game is not None else None,
                reason=str(getattr(stratagem, "name", "") or "FLANKING MANOEUVRES"),
            )
        ):
            logger.error("ERROR: FLANKING MANOEUVRES: target unit did not enter Strategic Reserves")
            return False
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FLANKING MANOEUVRES: %s entered Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_freeblade_noble_sacrifice(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freeblade_company():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        root = self._ik_root(merged.get("destroyed_unit") or merged.get("unit") or merged.get("target_unit"))
        destroyed_model = merged.get("destroyed_model") or merged.get("model") or merged.get("target_model")
        if root is None or destroyed_model is None:
            logger.error("ERROR: NOBLE SACRIFICE: destroyed unit or model missing")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: NOBLE SACRIFICE: target unit is not yours")
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: NOBLE SACRIFICE: target must be an IMPERIAL KNIGHTS unit")
            return False
        if not self._ik_has_deadly_demise(root):
            logger.error("ERROR: NOBLE SACRIFICE: target unit does not have Deadly Demise")
            return False
        if self._ik_model_is_alive(destroyed_model):
            logger.error("ERROR: NOBLE SACRIFICE: destroyed model is still alive")
            return False
        eligible = list(merged.get("candidates") or self._freeblade_noble_sacrifice_candidates(destroyed_unit=root, destroyed_model=destroyed_model))
        if not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: NOBLE SACRIFICE: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        trigger_threshold = 3 if self._ik_is_armiger_unit(root) else 4
        setattr(destroyed_model, "_imperial_knights_noble_sacrifice_trigger_threshold_once", int(trigger_threshold))
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: NOBLE SACRIFICE: %s triggers Deadly Demise on %d+ for this destruction.",
            getattr(root, "name", "Unit"),
            int(trigger_threshold),
        )
        return True

    def _use_freeblade_point_blank_barrage(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freeblade_company():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "shooting phase":
            logger.error("ERROR: POINT-BLANK BARRAGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: POINT-BLANK BARRAGE: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._freeblade_point_blank_barrage_candidates())
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: POINT-BLANK BARRAGE: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: POINT-BLANK BARRAGE: target unit is not yours")
            return False
        if not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: POINT-BLANK BARRAGE: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["freeblade_point_blank_barrage_active"] = True
        sr["freeblade_point_blank_barrage_expires_phase"] = "SHOOTING_PHASE"
        sr["freeblade_point_blank_barrage_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["freeblade_point_blank_barrage_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["freeblade_point_blank_barrage_source"] = str(getattr(stratagem, "name", "") or "POINT-BLANK BARRAGE")
        sr["freeblade_point_blank_barrage_pending_mortal_wounds"] = int(
            sr.get("freeblade_point_blank_barrage_pending_mortal_wounds", 0) or 0
        )
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: POINT-BLANK BARRAGE: %s can fire Blast weapons into its own Engagement Range this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_valourstrike_vow_of_retribution(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VOW OF RETRIBUTION: wrong phase")
            return False

        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: VOW OF RETRIBUTION: not your Shooting phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VOW OF RETRIBUTION: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False

        candidates = self._imperial_knights_vow_of_retribution_candidates()
        if root not in candidates:
            logger.error(
                "ERROR: VOW OF RETRIBUTION: target must be an IMPERIAL KNIGHTS unit on the battlefield that has not shot"
            )
            return False

        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["vow_of_retribution_active"] = True
        sr["vow_of_retribution_expires_phase"] = "SHOOTING_PHASE"
        sr["vow_of_retribution_owner"] = str(getattr(self.player, "id", "") or "")
        sr["vow_of_retribution_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["vow_of_retribution_source"] = str(getattr(stratagem, "name", "") or "VOW OF RETRIBUTION")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: VOW OF RETRIBUTION: {getattr(root, 'name', 'Unit')} gains Lethal Hits with ranged weapons this phase."
        )
        return True

    def _use_valourstrike_full_tilt(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: FULL TILT: wrong phase")
            return False

        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FULL TILT: not your Movement phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FULL TILT: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: FULL TILT: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: FULL TILT: target must be an IMPERIAL KNIGHTS unit")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: FULL TILT: target is not currently eligible")
            return False
        if self._ik_selected_to_move_this_phase(root):
            logger.error("ERROR: FULL TILT: target has already been selected to move this phase")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        from ..utility.modifiers import Modifier, ModifierOp

        root.remove_characteristic_modifiers_by_source("stratagem:imperial_knights_full_tilt")
        root.add_characteristic_modifier(
            "movement",
            Modifier(ModifierOp.ADD, 2, source="stratagem:imperial_knights_full_tilt"),
        )

        effect_tag = "stratagem:imperial_knights_full_tilt"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        adv_mods = list(sr.get("advance_roll_modifiers", []) or [])
        adv_mods = [
            entry
            for entry in adv_mods
            if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == effect_tag)
        ]
        adv_mods.append(
            {
                "value": 2,
                "source": str(getattr(stratagem, "name", "") or "FULL TILT"),
                "tag": effect_tag,
            }
        )
        sr["advance_roll_modifiers"] = adv_mods
        sr["full_tilt_active"] = True
        sr["full_tilt_expires_phase"] = "MOVEMENT_PHASE"
        sr["full_tilt_owner"] = str(getattr(self.player, "id", "") or "")
        sr["full_tilt_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["full_tilt_source"] = str(getattr(stratagem, "name", "") or "FULL TILT")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FULL TILT: %s gains +2\" Move and +2 to Advance rolls this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_valourstrike_run_them_through(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: RUN THEM THROUGH!: wrong phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RUN THEM THROUGH!: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: RUN THEM THROUGH!: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: RUN THEM THROUGH!: target must be an IMPERIAL KNIGHTS unit")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: RUN THEM THROUGH!: target is not currently eligible")
            return False
        if self._ik_selected_to_fight_this_phase(root):
            logger.error("ERROR: RUN THEM THROUGH!: target has already been selected to fight this phase")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_knights_run_them_through_active"] = True
        sr["imperial_knights_run_them_through_expires_phase"] = "FIGHT_PHASE"
        sr["imperial_knights_run_them_through_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["imperial_knights_run_them_through_source"] = str(getattr(stratagem, "name", "") or "RUN THEM THROUGH!")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RUN THEM THROUGH!: %s gains [LANCE] on melee weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_valourstrike_thunderstomp(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: THUNDERSTOMP: wrong phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        model = kwargs.get("model") or kwargs.get("target_model")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and model is not None:
            unit = getattr(model, "parent_unit", None)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: THUNDERSTOMP: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: THUNDERSTOMP: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: THUNDERSTOMP: target must be an IMPERIAL KNIGHTS model")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: THUNDERSTOMP: target is not currently eligible")
            return False
        if self._ik_selected_to_fight_this_phase(root):
            logger.error("ERROR: THUNDERSTOMP: target has already been selected to fight this phase")
            return False

        chosen_model = self._ik_select_thunderstomp_model(root, requested_model=model)
        if chosen_model is None:
            logger.error("ERROR: THUNDERSTOMP: selected model must be an IMPERIAL KNIGHTS model with armoured/titanic feet")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_knights_thunderstomp_active"] = True
        sr["imperial_knights_thunderstomp_expires_phase"] = "FIGHT_PHASE"
        sr["imperial_knights_thunderstomp_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["imperial_knights_thunderstomp_source"] = str(getattr(stratagem, "name", "") or "THUNDERSTOMP")
        sr["imperial_knights_thunderstomp_model_id"] = str(maybe_entity_id(chosen_model) or "")
        sr["imperial_knights_thunderstomp_armoured_feet_attacks"] = 8
        sr["imperial_knights_thunderstomp_titanic_feet_attacks"] = 12
        sr["imperial_knights_thunderstomp_ap_bonus"] = 1
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: THUNDERSTOMP: %s gains enhanced Armoured/Titanic Feet profiles this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_valourstrike_tactical_foil(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("moving_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "TACTICAL FOIL":
                    continue
                from_pending = True
                unit = reaction.get("unit") or reaction.get("target_unit")
                enemy_unit = enemy_unit or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("action", reaction.get("action"))
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TACTICAL FOIL: no target unit provided")
            return False

        root = self._ik_root(unit)
        enemy_root = self._ik_root(enemy_unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: TACTICAL FOIL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: TACTICAL FOIL: not opponent's Movement phase")
            return False
        action_key = str(kwargs.get("action") or kwargs.get("trigger") or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back"}:
            logger.error("ERROR: TACTICAL FOIL: invalid trigger action")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: TACTICAL FOIL: target is not currently eligible")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: TACTICAL FOIL: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: TACTICAL FOIL: target must be an IMPERIAL KNIGHTS unit")
            return False
        if enemy_root is None:
            logger.error("ERROR: TACTICAL FOIL: missing enemy trigger unit")
            return False
        if self._ik_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: TACTICAL FOIL: trigger unit is not enemy")
            return False
        if not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return False
        dist = self._ik_distance_between_units(root, enemy_root)
        if dist is None or float(dist) > 9.0 + 1e-6:
            logger.error("ERROR: TACTICAL FOIL: target must be within 9\" of the enemy unit")
            return False
        if not from_pending and not action_key:
            logger.error("ERROR: TACTICAL FOIL: missing movement trigger context")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: TACTICAL FOIL: reactive move queue is unavailable")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        move_max = max(0, int(dice_module.get_roll("D6") or 0))
        req = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(move_max),
            kind="tactical_foil",
            movement_type="reactive",
            source=stratagem.name,
            moving_unit=enemy_root,
        )
        if req is None:
            logger.error("ERROR: TACTICAL FOIL: failed to queue reactive move")
            return False

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TACTICAL FOIL: %s can make a Normal move up to %d\".",
            getattr(root, "name", "Unit"),
            int(move_max),
        )
        return True

    def _use_questor_forgepact_aggression_begets_aggression(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_questor_forgepact():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: AGGRESSION BEGETS AGGRESSION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: AGGRESSION BEGETS AGGRESSION: not your Shooting phase")
            return False

        selected_units = kwargs.get("selected_units") or kwargs.get("units") or kwargs.get("target_units")
        if selected_units is None:
            selected_units = []
            primary = kwargs.get("unit") or kwargs.get("target_unit")
            support = kwargs.get("support_unit") or kwargs.get("secondary_unit")
            if primary is not None:
                selected_units.append(primary)
            if support is not None:
                selected_units.append(support)
        selected_roots: list[Any] = []
        seen_ids: set[str] = set()
        for unit in list(selected_units or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen_ids:
                continue
            if uid:
                seen_ids.add(uid)
            selected_roots.append(root)
        candidates = list(kwargs.get("candidates") or self._questor_forgepact_aggression_begets_aggression_candidates())
        if not selected_roots and len(candidates) == 1:
            selected_roots = [candidates[0]]
        if not selected_roots:
            logger.error("ERROR: AGGRESSION BEGETS AGGRESSION: no target unit provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: AGGRESSION BEGETS AGGRESSION: may target at most two units")
            return False

        target_roots: list[Any] = []
        if len(selected_roots) == 1:
            root = selected_roots[0]
            if not self._ik_unit_in_candidates(root, candidates):
                logger.error("ERROR: AGGRESSION BEGETS AGGRESSION: target is not currently eligible")
                return False
            target_roots = [root]
        else:
            ik_character_root = None
            admech_root = None
            for root in selected_roots:
                if self._is_imperial_knights_unit(root) and self._ik_is_character_unit(root):
                    ik_character_root = root
                elif self._ik_is_adeptus_mechanicus_unit(root):
                    admech_root = root
            if ik_character_root is None or admech_root is None:
                logger.error(
                    "ERROR: AGGRESSION BEGETS AGGRESSION: two-target use requires one IMPERIAL KNIGHTS CHARACTER and one ADEPTUS MECHANICUS unit"
                )
                return False
            if not self._ik_unit_in_candidates(ik_character_root, candidates):
                logger.error("ERROR: AGGRESSION BEGETS AGGRESSION: Imperial Knights CHARACTER is not currently eligible")
                return False
            support_candidates = self._questor_forgepact_aggression_begets_aggression_supporting_candidates(ik_character_root)
            if not self._ik_unit_in_candidates(admech_root, support_candidates):
                logger.error(
                    "ERROR: AGGRESSION BEGETS AGGRESSION: ADEPTUS MECHANICUS support unit must be within 6\" of the selected Imperial Knights CHARACTER"
                )
                return False
            target_roots = [ik_character_root, admech_root]

        primary_target = target_roots[0]
        if not self._ik_spend_cp(stratagem, target_unit=primary_target):
            return False

        owner_id = str(getattr(self.player, "id", "") or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "AGGRESSION BEGETS AGGRESSION")
        for root in list(target_roots):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["questor_forgepact_aggression_begets_aggression_active"] = True
            sr["questor_forgepact_aggression_begets_aggression_expires_phase"] = "SHOOTING_PHASE"
            sr["questor_forgepact_aggression_begets_aggression_turn_owner"] = owner_id
            sr["questor_forgepact_aggression_begets_aggression_turn"] = current_turn
            sr["questor_forgepact_aggression_begets_aggression_source"] = source_name
            root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: AGGRESSION BEGETS AGGRESSION: %d unit(s) gain [ASSAULT] on ranged weapons this phase.",
            len(target_roots),
        )
        return True

    def _use_questor_forgepact_bonded_imperative(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_questor_forgepact():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: BONDED IMPERATIVE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BONDED IMPERATIVE: not your Command phase")
            return False

        army = getattr(self.player, "army", None)
        bondsman_mgr = getattr(army, "bondsman", None)
        if bondsman_mgr is None:
            logger.error("ERROR: BONDED IMPERATIVE: Bondsman manager is unavailable")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(
            kwargs.get("candidates")
            or getattr(bondsman_mgr, "get_questor_forgepact_bonded_imperative_sources", lambda **_k: [])(
                game_map=getattr(self.game, "map", None) if self.game is not None else None
            )
        )
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BONDED IMPERATIVE: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: BONDED IMPERATIVE: target is not currently eligible")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: BONDED IMPERATIVE: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._ik_is_character_unit(root) or not self._is_imperial_knights_unit(root):
            logger.error("ERROR: BONDED IMPERATIVE: target must be an IMPERIAL KNIGHTS CHARACTER unit")
            return False
        if self._ik_is_knight_preceptor_unit(root):
            logger.error("ERROR: BONDED IMPERATIVE: Knight Preceptor cannot be targeted")
            return False
        can_activate = getattr(bondsman_mgr, "can_activate_questor_forgepact_bonded_imperative", None)
        if not callable(can_activate) or not bool(
            can_activate(root, game_map=getattr(self.game, "map", None) if self.game is not None else None)
        ):
            logger.error("ERROR: BONDED IMPERATIVE: target is not currently eligible to extend its Bondsman ability")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        activate = getattr(bondsman_mgr, "activate_questor_forgepact_bonded_imperative", None)
        if not callable(activate) or not bool(
            activate(
                root,
                game=self.game,
                player=self.player,
                source=str(getattr(stratagem, "name", "") or "BONDED IMPERATIVE"),
            )
        ):
            logger.error("ERROR: BONDED IMPERATIVE: failed to refresh the Bondsman selection")
            return False

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BONDED IMPERATIVE: %s can target ADEPTUS MECHANICUS with its next Bondsman use.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_questor_forgepact_machine_focus(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_questor_forgepact():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: MACHINE FOCUS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MACHINE FOCUS: not your Command phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._questor_forgepact_machine_focus_candidates())
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MACHINE FOCUS: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: MACHINE FOCUS: target is not currently eligible")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: MACHINE FOCUS: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: MACHINE FOCUS: target must be an IMPERIAL KNIGHTS unit")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._ik_detachment_mgr()
        clear_effect = getattr(mgr, "clear_questor_forgepact_machine_focus", None) if mgr is not None else None
        if callable(clear_effect):
            clear_effect(root)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["questor_forgepact_machine_focus_active"] = True
        sr["questor_forgepact_machine_focus_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["questor_forgepact_machine_focus_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["questor_forgepact_machine_focus_source"] = str(getattr(stratagem, "name", "") or "MACHINE FOCUS")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MACHINE FOCUS: %s can ignore WS/BS, Hit, and Wound modifiers until your next turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_questor_forgepact_omnissiahs_grace(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_questor_forgepact():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        root = self._ik_root(merged.get("unit") or merged.get("target_unit"))
        candidates = list(merged.get("candidates") or [])
        if root is None and len(candidates) == 1:
            root = self._ik_root(candidates[0])
        if root is None:
            logger.error("ERROR: OMNISSIAH'S GRACE: no target unit provided")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: OMNISSIAH'S GRACE: target is not currently eligible")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: OMNISSIAH'S GRACE: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: OMNISSIAH'S GRACE: target must be on the battlefield and targetable")
            return False
        if not (self._is_imperial_knights_unit(root) or self._ik_is_adeptus_mechanicus_unit(root)):
            logger.error("ERROR: OMNISSIAH'S GRACE: target must be an IMPERIAL KNIGHTS or ADEPTUS MECHANICUS unit")
            return False

        triggered = bool(merged.get("mortal_wound_allocated", False))
        trigger_name = str(merged.get("trigger", "") or "").strip().lower()
        if not triggered and trigger_name not in {"mortal_wound_allocated", "mortal_wound"}:
            logger.error("ERROR: OMNISSIAH'S GRACE: missing mortal-wound trigger context")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        phase_name = str(merged.get("phase_name") or self._current_phase_name or "Any phase")
        phase_key = self._ik_phase_end_key(phase_name, fallback="ANY_PHASE")
        key_seed = self._ik_normalize_name(getattr(stratagem, "name", "") or "").lower().replace(" ", "_")
        for index, model in enumerate(self._ik_unit_models(root)):
            key = f"{key_seed}:{maybe_entity_id(model) or index}"
            set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
            if callable(set_temporary_fnp):
                set_temporary_fnp(
                    key=key,
                    value=5,
                    source=str(getattr(stratagem, "name", "") or "OMNISSIAH'S GRACE"),
                    condition="against mortal wounds",
                    expires_phase=phase_key,
                )
                continue
            effects = getattr(model, "_temporary_effects", None)
            if not isinstance(effects, dict):
                effects = {}
                model._temporary_effects = effects
            effects[key] = {
                "expires_phase": str(phase_key or "").strip().upper(),
                "temporary_fnp_value": 5,
                "temporary_fnp_source": str(getattr(stratagem, "name", "") or "OMNISSIAH'S GRACE"),
                "temporary_fnp_condition": "against mortal wounds",
            }

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: OMNISSIAH'S GRACE: %s gains Feel No Pain 5+ against mortal wounds this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_questor_forgepact_thronegheist_fury(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_questor_forgepact():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        root = self._ik_root(merged.get("unit") or merged.get("target_unit"))
        enemy_root = self._ik_root(merged.get("enemy_unit") or merged.get("moving_unit"))
        candidates = list(merged.get("candidates") or [])
        if root is None and len(candidates) == 1:
            root = self._ik_root(candidates[0])
        if root is None:
            logger.error("ERROR: THRONEGHEIST FURY: no target unit provided")
            return False
        if enemy_root is None:
            logger.error("ERROR: THRONEGHEIST FURY: missing enemy trigger unit")
            return False

        phase_name = str(merged.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: THRONEGHEIST FURY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: THRONEGHEIST FURY: not opponent's Movement phase")
            return False
        action_key = str(merged.get("action") or merged.get("trigger") or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back", "set_up"}:
            logger.error("ERROR: THRONEGHEIST FURY: invalid trigger action")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: THRONEGHEIST FURY: target is not currently eligible")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: THRONEGHEIST FURY: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._ik_is_titanic_unit(root) or not self._is_imperial_knights_unit(root):
            logger.error("ERROR: THRONEGHEIST FURY: target must be a Titanic IMPERIAL KNIGHTS unit")
            return False
        if self._ik_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: THRONEGHEIST FURY: trigger unit must be enemy")
            return False
        if not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return False
        distance = self._ik_distance_between_units(root, enemy_root)
        if distance is None or float(distance) > 24.0 + 1e-6:
            logger.error("ERROR: THRONEGHEIST FURY: target must be within 24\" of the enemy unit")
            return False
        if not self._ik_visible_to_enemy_unit(enemy_root, root):
            logger.error("ERROR: THRONEGHEIST FURY: target must be visible to the enemy unit")
            return False

        allowed_pairs = self._questor_forgepact_thronegheist_fury_allowed_pairs(root, enemy_root)
        if not allowed_pairs:
            logger.error("ERROR: THRONEGHEIST FURY: no eligible model and ranged weapon can shoot that enemy unit")
            return False
        queue_shoot = getattr(self.game, "_queue_setup_reactive_shooting_decision", None) if self.game is not None else None
        if not callable(queue_shoot):
            logger.error("ERROR: THRONEGHEIST FURY: reactive shooting queue is unavailable")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        allowed_model_ids = sorted(
            {
                str(pair.get("model_id", "") or "").strip()
                for pair in list(allowed_pairs or [])
                if str(pair.get("model_id", "") or "").strip()
            }
        )
        allowed_wargear_ids = sorted(
            {
                str(pair.get("wargear_id", "") or "").strip()
                for pair in list(allowed_pairs or [])
                if str(pair.get("wargear_id", "") or "").strip()
            }
        )
        request = queue_shoot(
            player=self.player,
            unit=root,
            target_unit=enemy_root,
            source=str(getattr(stratagem, "name", "") or "THRONEGHEIST FURY"),
            allowed_model_ids=allowed_model_ids,
            allowed_wargear_ids=allowed_wargear_ids,
            max_declarations=1,
        )
        if request is None:
            logger.error("ERROR: THRONEGHEIST FURY: failed to queue reactive shooting")
            return False
        if hasattr(request, "context"):
            if not isinstance(getattr(request, "context", None), dict):
                request.context = {}
            request.context["thronegheist_fury_flow"] = True
            request.context["thronegheist_fury_trigger_action"] = action_key
            request.context["thronegheist_fury_enemy_unit_id"] = self._ik_sort_key(enemy_root)
            request.context["thronegheist_fury_allowed_pairs"] = [dict(pair) for pair in list(allowed_pairs or [])]

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: THRONEGHEIST FURY: %s can make a reactive shot with one ranged weapon against %s.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy unit"),
        )
        return True

    def _use_questor_forgepact_vengeance_of_the_machine_cult(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_questor_forgepact():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        root = self._ik_root(merged.get("unit") or merged.get("target_unit"))
        enemy_root = self._ik_root(merged.get("enemy_unit"))
        if root is None:
            logger.error("ERROR: VENGEANCE OF THE MACHINE CULT: no destroyed IMPERIAL KNIGHTS unit provided")
            return False
        if enemy_root is None:
            logger.error("ERROR: VENGEANCE OF THE MACHINE CULT: destroying enemy unit is missing")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: VENGEANCE OF THE MACHINE CULT: target unit is not yours")
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: VENGEANCE OF THE MACHINE CULT: target must be an IMPERIAL KNIGHTS unit")
            return False
        if self._ik_is_alive(root):
            logger.error("ERROR: VENGEANCE OF THE MACHINE CULT: target unit was not destroyed")
            return False
        if self._ik_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: VENGEANCE OF THE MACHINE CULT: destroying unit must be enemy")
            return False

        mgr = self._ik_detachment_mgr()
        mark_enemy = getattr(mgr, "set_questor_forgepact_vengeance_mark", None) if mgr is not None else None
        if not callable(mark_enemy):
            logger.error("ERROR: VENGEANCE OF THE MACHINE CULT: detachment manager is unavailable")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        if not bool(
            mark_enemy(
                enemy_root,
                player_id=str(getattr(self.player, "id", "") or ""),
                source=str(getattr(stratagem, "name", "") or "VENGEANCE OF THE MACHINE CULT"),
            )
        ):
            logger.error("ERROR: VENGEANCE OF THE MACHINE CULT: failed to mark the destroying enemy unit")
            return False

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: VENGEANCE OF THE MACHINE CULT: %s is Marked until the end of the battle.",
            getattr(enemy_root, "name", "Enemy unit"),
        )
        return True

    def _use_questoris_companions_driven_by_the_past(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_questoris_companions():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "charge phase":
            logger.error("ERROR: DRIVEN BY THE PAST: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: DRIVEN BY THE PAST: not your Charge phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DRIVEN BY THE PAST: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: DRIVEN BY THE PAST: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root) or not self._ik_is_titanic_unit(root):
            logger.error("ERROR: DRIVEN BY THE PAST: target must be a Titanic IMPERIAL KNIGHTS unit")
            return False
        eligible = candidates or self._questoris_companions_driven_by_the_past_candidates()
        if eligible and not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: DRIVEN BY THE PAST: target unit is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["questoris_companions_driven_by_the_past_active"] = True
        sr["questoris_companions_driven_by_the_past_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["questoris_companions_driven_by_the_past_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["questoris_companions_driven_by_the_past_source"] = str(
            getattr(stratagem, "name", "") or "DRIVEN BY THE PAST"
        )
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DRIVEN BY THE PAST: %s can declare a charge this turn despite Advancing.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_questoris_companions_heros_tread(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_questoris_companions():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        unit = merged.get("unit") or merged.get("target_unit")
        candidates = list(merged.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: HERO'S TREAD: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        phase_key = self._ik_phase_name_key(merged.get("phase_name") or self._current_phase_name)
        if phase_key != "command phase":
            logger.error("ERROR: HERO'S TREAD: wrong phase")
            return False
        end_of_phase_check = getattr(self, "_mob_rule_is_end_of_command_phase_context", None)
        if callable(end_of_phase_check) and not bool(end_of_phase_check(merged)):
            logger.error("ERROR: HERO'S TREAD: requires the end of your Command phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: HERO'S TREAD: not your Command phase")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: HERO'S TREAD: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root) or not self._ik_is_titanic_unit(root):
            logger.error("ERROR: HERO'S TREAD: target must be a Titanic IMPERIAL KNIGHTS unit")
            return False
        eligible = candidates or self._questoris_companions_heros_tread_candidates()
        if eligible and not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: HERO'S TREAD: target unit is not within range of a controlled objective")
            return False
        objective = merged.get("objective") or merged.get("objective_marker")
        objective_candidates = list(merged.get("objective_candidates") or [])
        if not objective_candidates:
            objective_candidates = self._questoris_companions_heros_tread_objective_candidates(root)
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: HERO'S TREAD: no objective marker available")
            return False
        if objective_candidates and objective not in list(objective_candidates or []):
            logger.error("ERROR: HERO'S TREAD: objective not in candidates")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        loc = getattr(objective, "location", None)
        if loc is None:
            logger.error("ERROR: HERO'S TREAD: selected objective has no location")
            return False
        if hasattr(loc, "set_sticky_control"):
            loc.set_sticky_control(
                self.player,
                source="heros_tread",
                minimum_control=5,
            )
        else:
            loc.sticky_controller = self.player
            loc.sticky_source = "heros_tread"
            loc.sticky_minimum_control = 5
            loc.controlling_player = self.player
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: HERO'S TREAD: selected objective remains under your control with Level of Control 5 until broken.",
        )
        return True

    def _use_questoris_companions_unstoppable_warrior(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_questoris_companions():
            return False
        merged = self._ik_pending_context(stratagem.name, kwargs)
        unit = merged.get("unit") or merged.get("target_unit")
        candidates = list(merged.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: UNSTOPPABLE WARRIOR: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        phase_key = self._ik_phase_name_key(merged.get("phase_name") or self._current_phase_name)
        if phase_key != "movement phase":
            logger.error("ERROR: UNSTOPPABLE WARRIOR: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: UNSTOPPABLE WARRIOR: not your Movement phase")
            return False
        action_key = str(merged.get("action", "") or "").strip().lower().replace(" ", "_")
        if action_key == "fallback":
            action_key = "fall_back"
        if action_key != "fall_back":
            logger.error("ERROR: UNSTOPPABLE WARRIOR: trigger action must be Fall Back")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: UNSTOPPABLE WARRIOR: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root) or not self._ik_is_titanic_unit(root):
            logger.error("ERROR: UNSTOPPABLE WARRIOR: target must be a Titanic IMPERIAL KNIGHTS unit")
            return False
        eligible = candidates or self._questoris_companions_unstoppable_warrior_candidates()
        if eligible and not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: UNSTOPPABLE WARRIOR: target unit is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["questoris_companions_unstoppable_warrior_active"] = True
        sr["questoris_companions_unstoppable_warrior_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["questoris_companions_unstoppable_warrior_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["questoris_companions_unstoppable_warrior_source"] = str(
            getattr(stratagem, "name", "") or "UNSTOPPABLE WARRIOR"
        )
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNSTOPPABLE WARRIOR: %s can shoot and declare a charge this turn despite Falling Back.",
            getattr(root, "name", "Unit"),
        )
        return True
